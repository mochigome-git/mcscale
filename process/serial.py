"""
Serial Data Processing for PLC Integration.

This module processes serial data from a weighing scale and writes valid weight data
to a PLC device. It includes error handling, retry logic, and a timeout reset mechanism.

### Main Functionalities:
- **process_weight_data**: Processes weight data with retry and validation mechanisms.
- **process_weight_data_2**: An alternative, simpler process for weight data.
- **reset_plc_if_timeout**: Resets the PLC state after a timeout.
- **smode_process_serial_data**: Non-blocking handler for incoming serial data.

### Environment Variables:
- `WEIGHT_PROCESS_MODE`: Determines which processing function to use (`1` or `2`).

### Usage Example:
```python
import os

process_mode = os.getenv("WEIGHT_PROCESS_MODE", "1")

if process_mode == "1":
    process_func = process_weight_data
else:
    process_func = process_weight_data_2

"""

import time
import os
import socket
import re
import utility
import threading


def process_weight_data(
    message, state, ser, pymc3e, headdevice, bitunit, logger, max_retries=3
):
    """
    Processes weight data from the serial input and writes to the PLC with retries.
    ----------
    Parameters
    ----------
    message : str
        The incoming serial data string.
    state : dict
        Maintains state like `last_weight` and `last_update_time`.
    ser : Serial
        Serial port object for reading data.
    pymc3e : pymc3e.Connection
        Connection object for PLC communication.
    headdevice : str
        PLC head device address.
    bitunit : str
        PLC bit unit for activation.
    logger : logging.Logger
        Logger instance for logging information and errors.
    max_retries : int, optional
        Maximum number of retries for write operations (default is 3).

    Returns
    -------
    bool
        True if processing and writing were successful, False otherwise.
    """
    cleaned_data = message.strip()
    if not cleaned_data:
        return False

    match = re.match(r"^ST,\+(\d+\.\d+)\s+g$", cleaned_data)
    if not match:
        return False

    try:
        weight_value = float(match.group(1))
        target_value = int(weight_value * 100)
        initial_delay = 0.5
        delay_increment = 0.5
        delay = 0.3

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
            threading.Timer(
                delay, pymc3e.batchwrite_wordunits, args=(headdevice, converted_values)
            ).start()
            threading.Timer(
                delay * 2,
                pymc3e.batchwrite_wordunits,
                args=(headdevice, converted_values),
            ).start()

            read_back = pymc3e.batchread_wordunits(headdevice=headdevice, readsize=1)
            if read_back and int(read_back[0]) == target_value:
                read_back = []
                break
            logger.warning(
                "Retry %d: Failed to write weight data to PLC: %d (Sent: %s, Received: %s)",
                attempt + 1,
                target_value,
                converted_values,
                read_back,
            )

            delay = initial_delay + attempt * delay_increment
            time.sleep(delay)
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


def process_weight_data_2(message, state, ser, pymc3e, headdevice, bitunit, logger):
    """
    Simplified version of weight data processing without retries.
    ----------
    Parameters
    ----------
    message : str
        The incoming serial data string.
    state : dict
        Maintains state like `last_weight` and `last_update_time`.
    ser : Serial
        Serial port object for reading data.
    pymc3e : pymc3e.Connection
        Connection object for PLC communication.
    headdevice : str
        PLC head device address.
    bitunit : str
        PLC bit unit for activation.
    logger : logging.Logger
        Logger instance for logging information and errors.
    max_retries : int, optional
        Maximum number of retries for write operations (default is 3).

    Returns
    -------
    bool
        True if processing and writing were successful, False otherwise.
    """
    cleaned_data = message.strip()
    if not cleaned_data:
        return False

    match = re.match(r"^ST,\+(\d+\.\d+)\s+g$", cleaned_data)
    if not match:
        return False

    try:
        weight_value = float(match.group(1))
        target_value = int(weight_value * 100)

        if target_value < 100:
            return False

        if target_value > state["last_weight"]:
            state["last_weight"] = target_value
            logger.info("Received weight data from %s: %s", ser.port, cleaned_data)
            converted_values = utility.split_32bit_to_16bit(state["last_weight"])
            pymc3e.batchwrite_wordunits(headdevice=headdevice, values=converted_values)

            pymc3e.batchwrite_bitunits(headdevice=bitunit, values=[1])
            state["last_update_time"] = time.time()
            logger.info(
                "Updated PLC with weight: %d and activated bit unit.",
                state["last_weight"],
            )
        else:
            return False

    except ValueError:
        logger.error("Failed to convert weight data to float: %s", cleaned_data)
        return False


def reset_plc_if_timeout(
    state, pymc3e, headdevice, bitunit, logger, stop_event, data_in_progress
):
    """
    Resets the PLC state if no valid data has been processed within a timeout period.
    ----------
    Parameters
    ----------
    state : dict
        The processing state.
    pymc3e : pymc3e.Connection
        Connection object for PLC communication.
    headdevice : str
        PLC head device address.
    bitunit : str
        PLC bit unit for activation.
    logger : logging.Logger
        Logger instance for logging information and errors.
    stop_event : threading.Event
        Event to signal stopping the process.
    data_in_progress : bool
        Flag to indicate if data processing is in progress.

    Returns
    -------
    None
    """
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
        except (socket.timeout, TimeoutError, OSError) as e:
            logger.error("Failed to reset PLC data: %s", e)
            stop_event.set()

def smode_process_serial_data(context):
    """
    Process incoming streaming data from the weighing scale.
    This function is non-blocking and processes only the currently available data.
    ----------
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
    process_mode = os.getenv("PLC_CPU_MODEL", "RCPU04")

    if process_mode == "RCPU04":
        process_func = process_weight_data
    else:
        process_func = process_weight_data_2

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
                    if process_func(
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
