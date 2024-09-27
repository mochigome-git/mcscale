"""
This module handles serial communication with PLC devices, processes incoming data,
and interacts with the pymcprotocol library for reading and writing data to PLCs.

Modules:
- threading: For concurrent execution and handling of serial data processing.
- time: For managing timing and delays.
- logging: For logging messages and errors.
- sys: For system-specific parameters and functions.
- pymcprotocol: For communication with PLC devices using the MC Protocol 3E.
- utility: Custom utility functions for data handling.
"""

import threading
import time
import logging
import sys
import re
import queue
import pymcprotocol
import utility

# Configure logging to include date and time
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,  # Set the logging level to INFO or higher
    format='%(asctime)s - %(levelname)s - %(message)s',  # Include timestamp, log level, and message
    datefmt='%Y-%m-%d %H:%M:%S'  # Specify date and time format
)
logger = logging.getLogger(__name__)

# Set up serial communication
serial_ports = {
    "/dev/ttyUSB0": None,
    "/dev/ttyUSB1": None,
    "/dev/ttyUSB2": None
}

# Mapping of serial ports to PLC head devices and bit units
port_to_headdevice_and_bitunit = {
    "/dev/ttyUSB0": ("D6364", "M3300"),
    "/dev/ttyUSB1": ("D6464", "M3400"),
    "/dev/ttyUSB2": ("D6564", "M3500")
}

def initialize_connection(plc_ip, plc_port, retries=5, delay=2):
    """Initialize connection to PLC with retries."""
    pymc3e = pymcprotocol.Type3E()
    for attempt in range(retries):
        try:
            pymc3e.connect(plc_ip, plc_port)
            return pymc3e
        except TimeoutError:
            logger.error("Connection attempt %d failed. Retrying in %d seconds...", attempt + 1, delay)
            time.sleep(delay)
    raise ConnectionError("Failed to connect to PLC after multiple attempts.")

def process_serial_data(ser, headdevice, bitunit, pymc3e, stop_event):
    """Process incoming serial data."""
    buffer = b""  # Buffer for binary data
    while not stop_event.is_set(): 
        if ser.in_waiting > 0:
            data = ser.read(ser.in_waiting)
            buffer += data

            # Print raw and hex format for debugging
            # print(f"Raw data received from {ser.port}: {data}")
            # print(f"Buffer in hex format: {buffer.hex()}")

            if b'\r\n' in buffer:
                try:
                    # Decode buffer to ASCII and strip terminators
                    decoded_data = buffer.decode('ascii').strip()
                    logger.info("Received weight data from %s : %s", ser.port, decoded_data)

                    # Clean up the data by removing duplicate 'ST,' and unwanted characters
                    cleaned_data = re.sub(r'(ST,)+', 'ST,', decoded_data)
                    
                    # Use regex to match valid weight data format 'ST,+000000 g' with optional whitespace after the number
                    match = re.search(r'ST,\+(\d{1,6}(\.\d)?)\s*g', cleaned_data)
                    if match:
                        weight_str = match.group(1)
                        try:
                            weight_value = float(weight_str)  # Convert to float
                            target_value = int(weight_value * 10)  # Convert to int & multiplying by 10
                            # logger.info("Target value: %s", target_value)

                            # Convert target_value to 32-bit format and split into 16-bit words
                            converted_values = utility.split_32bit_to_16bit(target_value)
                            # print(f"Converted values (32-bit split into 16-bit): {converted_values}")

                            # Write the split 16-bit values to the PLC
                            pymc3e.batchwrite_wordunits(headdevice=headdevice, values=converted_values)

                            # Write to the specified bit unit
                            pymc3e.batchwrite_bitunits(headdevice=bitunit, values=[1])
                            
                            # Wait for up to 11 seconds, checking for new data or stop_event every 0.5 seconds
                            total_sleep_time = 0
                            while total_sleep_time < 11:
                                if stop_event.is_set() or ser.in_waiting > 0:
                                    break
                                time.sleep(0.5)  # Check more frequently to reduce delay
                                total_sleep_time += 0.5

                            pymc3e.batchwrite_bitunits(headdevice=bitunit, values=[0])
                            pymc3e.batchwrite_wordunits(headdevice=headdevice, values=[0, 0])
                            # print(f"PLC {headdevice} and bit unit {bitunit} updated after delay.")
                        except ValueError:
                            logging.error("Failed to convert weight data to float: %s", weight_str)
                    else:
                        logging.error("Invalid weight data format after cleanup: %s", cleaned_data)

                except UnicodeDecodeError:
                    logger.error("Could not decode data: %s", buffer.hex())

                buffer = b""  # Clear buffer after processing data
        else:
            time.sleep(0.1)  # Reduce CPU usage when no data is available

def main(pymc3e):
    """Main function to run the PLC connection and data processing."""
    utility.initialize_serial_connections(serial_ports, bytesize='SEVENBITS')
    stop_event = threading.Event()
    data_queue = queue.Queue()  # Create a queue for incoming data processing

    def worker():
        while not stop_event.is_set():
            try:
                ser, headdevice, bitunit = data_queue.get(timeout=1)  # Block until there's data or timeout
                process_serial_data(ser, headdevice, bitunit, pymc3e, stop_event)
            except queue.Empty:
                continue  # Continue if the queue is empty

    # Start a pool of worker threads
    num_worker_threads = 4  # Adjust based on your needs
    threads = [threading.Thread(target=worker) for _ in range(num_worker_threads)]
    for thread in threads:
        thread.start()

    try:
        while True:
            for port, (headdevice, bitunit) in port_to_headdevice_and_bitunit.items():
                ser = serial_ports[port]
                if ser and ser.in_waiting > 0:  # Check for new data
                    if stop_event.is_set():
                        stop_event.clear()

                    # Add serial data processing task to the queue
                    data_queue.put((ser, headdevice, bitunit))

            time.sleep(0.1)  # Reduce CPU usage in the main loop

    except KeyboardInterrupt:
        logger.info("Terminating program.")
    finally:
        stop_event.set()  # Signal worker threads to stop
        for thread in threads:
            thread.join()  # Wait for all worker threads to finish
        for ser in serial_ports.values():
            if ser is not None:
                ser.close()
        logger.info("All serial connections closed.")
        pymc3e.close()
        logger.info("PLC connection closed.")

if __name__ == "__main__":
    PLC_IP = "192.168.3.61"
    PLC_PORT = 5014
    pymc3e = initialize_connection(PLC_IP, PLC_PORT)
    main(pymc3e)
