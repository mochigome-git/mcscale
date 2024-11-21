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

            buffer = b""  # Reset buffer

        # Check if the bit should be set to false (0) after 10 seconds from the last activation
        current_time = time.time()
        if bit_active and (current_time - last_activation_time) >= 10:
            try:
                pymc3e.batchwrite_bitunits(headdevice=bitunit, values=[0])
                bit_active = False  # Reset the bit status
                logger.info("Bit unit set to 0 after 10 seconds from last signal")
            except pymc3e.mcprotocolerror.MCProtocolError as e:
                logger.error("Failed to set bit to 0: %s", e)

        time.sleep(0.1)  # Reduce CPU usage when no data is available


def main(pymc3e):
    """Main function to run the PLC connection and data processing."""
    utility.initialize_serial_connections(serial_ports, bytesize='SEVENBITS')
    stop_event = threading.Event()
    data_queue = queue.Queue()  # Create a queue for incoming data processing

    def worker():
        while not stop_event.is_set():
            try:
                ser, headdevice, bitunit = data_queue.get(timeout=2)  # Block until there's data or timeout
                process_serial_data(ser, headdevice, bitunit, pymc3e, stop_event)
            except queue.Empty:
                continue  # Continue if the queue is empty

    # Start a pool of worker threads
    num_worker_threads = 10  # Adjust based on your needs
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

    except Exception as e:
        logger.critical("Terminating program: %s", e)
        sys.exit(1)
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
        sys.exit(1)

if __name__ == "__main__":
    PLC_IP = "192.168.3.61"
    PLC_PORT = 5014
    pymc3e = initialize_connection(PLC_IP, PLC_PORT)
    main(pymc3e)
