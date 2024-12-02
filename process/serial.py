import time
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
                decoded_data = buffer.decode('ascii')
            except UnicodeDecodeError:
                logger.error("Could not decode data: %s", buffer.hex())
                buffer = b""  # Clear buffer on decode error
                continue  

            messages = decoded_data.split('\r\n')  # Split messages by line endings
            for message in messages:
                cleaned_data = message.strip()

                ##if cleaned_data and re.match(r'^ST,\+(\d{6}\.\d)\s*g$', cleaned_data):
                ##    weight_str = re.match(r'^ST,\+(\d{6}\.\d)\s*g$', cleaned_data).group(1)
                ##    print("weight_str1", weight_str)
                if cleaned_data and re.match(r'^ST,\+(\d+\.\d+)\s+g$', cleaned_data):
                    weight_str = re.match(r'^ST,\+(\d+\.\d+)\s+g$', cleaned_data).group(1)

                    try:
                        weight_value = float(weight_str)
                        target_value = int(weight_value * 100)
                        logger.info("Received weight data from %s: %s", ser.port, cleaned_data)

                        # Write the split 16-bit values to the PLC
                        converted_values = utility.split_32bit_to_16bit(target_value)
                        ## print(target_value)
                        ## print(converted_values)
                        pymc3e.batchwrite_wordunits(headdevice=headdevice, values=converted_values)

                        # Activate bit unit if not already active
                        if not bit_active:
                            pymc3e.batchwrite_bitunits(headdevice=bitunit, values=[1])
                            bit_active = True  # Mark the bit as active
                            logger.info("Bit unit activated")
                        
                        # Reset the last activation time for each signal received
                        last_activation_time = time.time()
                        logger.info("Last activation time reset")

                    except ValueError:
                        logger.error("Failed to convert weight data to float: %s", weight_str)

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

def smode_process_serial_data(ser, headdevice, bitunit, pymc3e, stop_event, logger):
    """Process incoming streaming data from the weighing scale."""
    buffer = b""  # Buffer for binary data
    last_weight = 0  # Track the last largest weight
    last_update_time = 0  # Time when the last weight update occurred

    while not stop_event.is_set():
        if ser.in_waiting > 0:
            data = ser.read(ser.in_waiting)
            buffer += data

            try:
                decoded_data = buffer.decode('ascii')
            except UnicodeDecodeError:
                logger.error("Could not decode data: %s", buffer.hex())
                buffer = b""  # Clear buffer on decode error
                continue  

            messages = decoded_data.split('\r\n')  # Split messages by line endings
            buffer = b""  # Reset buffer after splitting messages

            for message in messages:
                cleaned_data = message.strip()
                if cleaned_data and re.match(r'^ST,\+(\d+\.\d+)\s+g$', cleaned_data):
                    weight_str = re.match(r'^ST,\+(\d+\.\d+)\s+g$', cleaned_data).group(1)

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
                            logger.info("Received weight data from %s: %s", ser.port, cleaned_data)
                            converted_values = utility.split_32bit_to_16bit(last_weight)
                            pymc3e.batchwrite_wordunits(headdevice=headdevice, values=converted_values)

                            # Activate the bit unit
                            pymc3e.batchwrite_bitunits(headdevice=bitunit, values=[1])
                            last_update_time = time.time()  # Reset the update time
                            logger.info("Updated PLC with weight: %d and activated bit unit.", last_weight)

                    except ValueError:
                        logger.error("Failed to convert weight data to float: %s", weight_str)

        # Check if the 20-second timeout has elapsed without a larger weight
        current_time = time.time()
        if last_update_time and (current_time - last_update_time) >= 10:
            try:
                # Reset the PLC data and bit unit
                pymc3e.batchwrite_wordunits(headdevice=headdevice, values=[0, 0])
                pymc3e.batchwrite_bitunits(headdevice=bitunit, values=[0])
                last_update_time = 0  # Reset the update time
                logger.info("Reset PLC data and bit unit due to timeout.")
                last_weight = 0 # Reset last weight
            except pymc3e.mcprotocolerror.MCProtocolError as e:
                logger.error("Failed to reset PLC data: %s", e)

        time.sleep(0.1)  # Reduce CPU usage when no data is available