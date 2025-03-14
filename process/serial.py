"""
Proccess the serial data and write to PLC
"""

import time
import socket
import sys
import re
import utility


def process_serial_data(ser, headdevice, bitunit, pymc3e, stop_event, logger):
    """Process incoming serial data."""
    buffer = b""  # Buffer for binary data
    bit_active = False  # Track if the bit is currently active
    last_activation_time = 0  # Time of the last activation

    while not stop_event.is_set():
        if ser.in_waiting > 0:
            data = ser.read(ser.in_waiting)
            buffer += data

            try:
                decoded_data = buffer.decode("ascii")
            except UnicodeDecodeError:
                logger.error("Could not decode data: %s", buffer.hex())
                buffer = b""  # Clear buffer on decode error
                continue

            messages = decoded_data.split("\r\n")  # Split messages by line endings
            for message in messages:
                cleaned_data = message.strip()

                ##if cleaned_data and re.match(r'^ST,\+(\d{6}\.\d)\s*g$', cleaned_data):
                ##    weight_str = re.match(r'^ST,\+(\d{6}\.\d)\s*g$', cleaned_data).group(1)
                ##    print("weight_str1", weight_str)
                if cleaned_data and re.match(r"^ST,\+(\d+\.\d+)\s+g$", cleaned_data):
                    weight_str = re.match(r"^ST,\+(\d+\.\d+)\s+g$", cleaned_data).group(
                        1
                    )

                    try:
                        weight_value = float(weight_str)
                        target_value = int(weight_value * 100)
                        logger.info(
                            "Received weight data from %s: %s", ser.port, cleaned_data
                        )

                        # Write the split 16-bit values to the PLC
                        converted_values = utility.split_32bit_to_16bit(target_value)
                        ## print(target_value)
                        ## print(converted_values)
                        pymc3e.batchwrite_wordunits(
                            headdevice=headdevice, values=converted_values
                        )

                        # Activate bit unit if not already active
                        if not bit_active:
                            pymc3e.batchwrite_bitunits(headdevice=bitunit, values=[1])
                            bit_active = True  # Mark the bit as active
                            logger.info("Bit unit activated")

                        # Reset the last activation time for each signal received
                        last_activation_time = time.time()
                        logger.info("Last activation time reset")

                    except ValueError:
                        logger.error(
                            "Failed to convert weight data to float: %s", weight_str
                        )

            buffer = b""  # Reset buf

        # Check if the bit should be set to false (0) after 10 seconds from the last activation
        current_time = time.time()
        if bit_active and (current_time - last_activation_time) >= 7:
            try:
                pymc3e.batchwrite_bitunits(headdevice=bitunit, values=[0])
                bit_active = False  # Reset the bit status
                logger.info("Bit unit set to 0 after 10 seconds from last signal")
            except pymc3e.mcprotocolerror.MCProtocolError as e:
                logger.error("Failed to set bit to 0: %s", e)

        time.sleep(0.1)  # Reduce CPU usage when no data is available


def _smode_process_serial_data(ser, headdevice, bitunit, pymc3e, stop_event, logger):
    """Process incoming streaming data from the weighing scale."""
    buffer = b""  # Buffer for binary data
    last_weight = 0  # Track the last largest weight
    last_update_time = 0  # Time when the last weight update occurred

    while not stop_event.is_set():
        if ser.in_waiting > 0:
            data = ser.read(ser.in_waiting)
            buffer += data

            try:
                decoded_data = buffer.decode("ascii")
            except UnicodeDecodeError:
                logger.error("Could not decode data: %s", buffer.hex())
                buffer = b""  # Clear buffer on decode error
                continue

            messages = decoded_data.split("\r\n")  # Split messages by line endings
            buffer = b""  # Reset buffer after splitting messages

            for message in messages:
                cleaned_data = message.strip()
                if cleaned_data and re.match(r"^ST,\+(\d+\.\d+)\s+g$", cleaned_data):
                    weight_str = re.match(r"^ST,\+(\d+\.\d+)\s+g$", cleaned_data).group(
                        1
                    )

                    try:
                        weight_value = float(weight_str)
                        target_value = int(weight_value * 100)

                        # Filter out weights lower than 100
                        if target_value < 100:
                            # logger.info("Filtered out weight data: %d (less than threshold).", target_value)
                            continue

                        if target_value > last_weight:
                            # Update last_weight and write to PLC
                            last_weight = target_value
                            logger.info(
                                "Received weight data from %s: %s",
                                ser.port,
                                cleaned_data,
                            )
                            converted_values = utility.split_32bit_to_16bit(last_weight)
                            pymc3e.batchwrite_wordunits(
                                headdevice=headdevice, values=converted_values
                            )

                            # Activate the bit unit
                            pymc3e.batchwrite_bitunits(headdevice=bitunit, values=[1])
                            last_update_time = time.time()  # Reset the update time
                            logger.info(
                                "Updated PLC with weight: %d and activated bit unit.",
                                last_weight,
                            )

                    except ValueError:
                        logger.error(
                            "Failed to convert weight data to float: %s", weight_str
                        )

        # Check if the 20-second timeout has elapsed without a larger weight
        current_time = time.time()
        if last_update_time and (current_time - last_update_time) >= 10:
            try:
                # Reset the PLC data and bit unit
                pymc3e.batchwrite_wordunits(headdevice=headdevice, values=[0, 0])
                pymc3e.batchwrite_bitunits(headdevice=bitunit, values=[0])
                last_update_time = 0  # Reset the update time
                logger.info("Reset PLC data and bit unit due to timeout.")
                last_weight = 0  # Reset last weight
            except pymc3e.mcprotocolerror.MCProtocolError as e:
                logger.error("Failed to reset PLC data: %s", e)

        time.sleep(0.01)  # Reduce CPU usage when no data is available


def process_weight_data(
    message, state, ser, pymc3e, headdevice, bitunit, logger, max_retries=3
):
    """Process a single weight data message."""
    cleaned_data = message.strip()
    if not cleaned_data:
        return False

    match = re.match(r"^ST,\+(\d+\.\d+)\s+g$", cleaned_data)
    if not match:
        return False

    try:
        weight_value = float(match.group(1))
        target_value = int(weight_value * 100)

        # Ignore invalid weights early
        if target_value < 100:
            return False

        # Always update last_update_time for valid data
        state["last_update_time"] = time.time()

        # Skip processing if it's a duplicate weight, unless last_weight is 0
        if state["last_weight"] != 0 and target_value <= state["last_weight"]:
            return False

        logger.info("Received weight data from %s: %s", ser.port, cleaned_data)

        # Perform write with retries
        for attempt in range(max_retries):
            converted_values = utility.split_32bit_to_16bit(target_value)
            pymc3e.batchwrite_wordunits(headdevice=headdevice, values=converted_values)
            time.sleep(0.35)

            read_back = pymc3e.batchread_wordunits(headdevice=headdevice, readsize=1)
            if read_back and int(read_back[0]) == target_value:
                break
            logger.warning(
                "Retry %d: Failed to write weight data to PLC: %d (Sent: %s, Received: %s)",
                attempt + 1,
                target_value,
                converted_values,
                read_back,
            )
        else:
            return False

        # Activate bit unit with retries
        for attempt in range(max_retries):
            pymc3e.batchwrite_bitunits(headdevice=bitunit, values=[1])
            bit_status = pymc3e.batchread_bitunits(headdevice=bitunit, readsize=1)
            if bit_status and int(bit_status[0]) == 1:
                break
            logger.warning(
                "Retry %d: Failed to activate bit unit for weight: %d",
                attempt + 1,
                target_value,
            )
        else:
            return False

        # Update state only after successful operations
        state["last_weight"] = target_value

        logger.info("PLC updated with weight: %d and bit unit activated.", target_value)
        return True

    except ValueError:
        logger.error("Failed to convert weight data to float: %s", cleaned_data)
        return False


def reset_plc_if_timeout(
    state, pymc3e, headdevice, bitunit, logger, stop_event, data_in_progress
):
    """Reset PLC if timeout is reached and no valid data has been processed."""
    current_time = time.time()
    timeout = 15  # Timeout in seconds

    if (
        not data_in_progress
        and state["last_update_time"]
        and (current_time - state["last_update_time"]) >= timeout
    ):
        try:
            pymc3e.batchwrite_wordunits(headdevice=headdevice, values=[0, 0])
            pymc3e.batchwrite_bitunits(headdevice=bitunit, values=[0])
            state["last_update_time"] = 0
            state["last_weight"] = 0
            logger.info("Reset PLC data and bit unit due to timeout.")
        except pymc3e.mcprotocolerror.MCProtocolError as e:
            logger.error("Failed to reset PLC data: %s", e)
            stop_event.set()


def smode_process_serial_data(context):
    """
    Process incoming streaming data from the weighing scale.
    This function is non-blocking and processes only the currently available data.

    Parameters
    ----------
    context : dict
        A dictionary containing:
        - ser: The serial port object.
        - headdevice: The PLC head device to write weight data to.
        - bitunit: The PLC bit unit to activate/deactivate.
        - pymc3e: The pymc3e connection object.
        - logger: Logger for logging messages.
        - state: Dictionary to maintain function state across calls.
        - stop_event: A threading Event to stop the worker.
    """
    ser = context["ser"]
    headdevice = context["headdevice"]
    bitunit = context["bitunit"]
    pymc3e = context["pymc3e"]
    logger = context["logger"]
    state = context["state"]
    stop_event = context["stop_event"]

    try:
        if stop_event.is_set():
            return

        data_in_progress = False

        if ser.in_waiting > 0:
            data = ser.read(ser.in_waiting)
            state["buffer"] += data

            try:
                decoded_data = state["buffer"].decode("ascii")
                messages = decoded_data.split("\r\n")
                state["buffer"] = b""

                for message in messages:
                    if process_weight_data(
                        message, state, ser, pymc3e, headdevice, bitunit, logger
                    ):
                        data_in_progress = True

            except UnicodeDecodeError:
                logger.error("Could not decode data: %s", state["buffer"].hex())
                state["buffer"] = b""

        reset_plc_if_timeout(
            state, pymc3e, headdevice, bitunit, logger, stop_event, data_in_progress
        )
        time.sleep(0.1)

    except (ValueError, socket.error) as e:
        logger.error("Error in processing serial data: %s", e)
        stop_event.set()


def direct_process_serial_data(context):
    """
    Process incoming streaming data from the weighing scale.
    This function is non-blocking and processes only the currently available data.

    Parameters
    ----------
    context : dict
        A dictionary containing:
        - ser: The serial port object.
        - headdevice: The PLC head device to write weight data to.
        - bitunit: The PLC bit unit to activate/deactivate.
        - pymc3e: The pymc3e connection object.
        - logger: Logger for logging messages.
        - state: Dictionary to maintain function state across calls.
        - stop_event: A threading Event to stop the worker.
    """
    ser = context["ser"]
    headdevice = context["headdevice"]
    pymc3e = context["pymc3e"]
    logger = context["logger"]
    state = context["state"]
    stop_event = context["stop_event"]
    delay_between_write = 0.1

    try:
        if stop_event.is_set():
            return  # Exit if the stop event is set

        if ser.in_waiting > 0:
            data = ser.read(ser.in_waiting)
            state["buffer"] += data

            try:
                decoded_data = state["buffer"].decode("ascii")
            except UnicodeDecodeError:
                logger.error("Could not decode data: %s", state["buffer"].hex())
                state["buffer"] = b""  # Clear buffer on decode error
                return

            messages = decoded_data.split("\r\n")  # Split messages by line endings
            state["buffer"] = b""  # Reset buffer after splitting messages

            for message in messages:
                cleaned_data = message.strip()
                if cleaned_data and re.match(r"^ST,\+(\d+\.\d+)\s+g$", cleaned_data):
                    weight_str = re.match(r"^ST,\+(\d+\.\d+)\s+g$", cleaned_data).group(
                        1
                    )

                    try:
                        weight_value = float(weight_str)
                        target_value = int(weight_value * 100)

                        if target_value < 100:
                            continue  # Filter out weights lower than 100

                        state["last_weight"] = target_value
                        logger.info(
                            "Received weight data from %s: %s", ser.port, target_value
                        )

                        # Convert and write word units
                        converted_values = utility.split_32bit_to_16bit(target_value)
                        if pymc3e.batchwrite_wordunits(
                            headdevice=headdevice, values=converted_values
                        ):
                            logger.info("Successfully wrote weight data to PLC.")

                        time.sleep(delay_between_write)

                        # Optional read to confirm the write
                        read_values = pymc3e.batchread_wordunits(
                            headdevice=headdevice, readsize=2
                        )
                        logger.info(
                            "Updated PLC with weight: %d and activated bit unit.",
                            read_values,
                        )

                    except ValueError:
                        logger.error(
                            "Failed to convert weight data to float: %s", weight_str
                        )

    except (ValueError, socket.error) as e:
        logger.error("Error in processing serial data: %s", e)
        stop_event.set()
