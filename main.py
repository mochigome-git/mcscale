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
import subprocess
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
            logger.info("Connected to PLC successfully.")
            return pymc3e
        except TimeoutError:
            logger.error("Connection attempt %d failed. Retrying in %d seconds...", attempt + 1, delay)
            time.sleep(delay)
    raise ConnectionError("Failed to connect to PLC after multiple attempts.")

def ping_host(host):
    """Ping the PLC to check if it is reachable."""
    try:
        # Specify the full path to the ping command
        ping_path = "/bin/ping"  # Change this path if necessary based on your system
        response = subprocess.run([ping_path, "-c", "1", host], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        if response.returncode == 0:
            return True
        else:
            logger.error("Ping failed to %s. Response: %s", host, response.stderr.decode())
            return False
    except Exception as e:
        logger.error("Error while pinging the host: %s", e)
        return False
        
def check_connection(pymc3e, plc_ip, plc_port, retry_attempts=3, retry_delay=5):
    """Check if the PLC is still connected using ping."""
    try:
        # First, ping the PLC to check its availability
        if ping_host(plc_ip):
            return True        
        else:
            logger.error("PLC is not reachable via ping. IP: %s", plc_ip)
            return False
    except Exception as e:
        logger.error("PLC connection lost: %s", e)
        
        # Attempt to reconnect if ping fails or if connection is lost
        for attempt in range(retry_attempts):
            logger.info("Attempting to reconnect to PLC...")
            try:
                pymc3e = initialize_connection(plc_ip, plc_port)  # Attempt to reconnect
                return True
            except ConnectionError:
                logger.error("Reconnection attempt %d failed. Retrying in %d seconds...", attempt + 1, retry_delay)
                time.sleep(retry_delay)

        logger.critical("Failed to reconnect after %d attempts. Exiting...", retry_attempts)
        sys.exit(1)  # Exit if reconnection fails after multiple attempts
        
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

def smode_process_serial_data(ser, headdevice, bitunit, pymc3e, stop_event):
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


def main(pymc3e, PLC_IP, PLC_PORT):
    """Main function to run the PLC connection and data processing."""
    utility.initialize_serial_connections(serial_ports, bytesize='SEVENBITS')
    stop_event = threading.Event()
    data_queue = queue.Queue()  # Create a queue for incoming data processing

    def worker():
        while not stop_event.is_set():
            try:
                ser, headdevice, bitunit = data_queue.get(timeout=2)  # Block until there's data or timeout
                smode_process_serial_data(ser, headdevice, bitunit, pymc3e, stop_event)

            except queue.Empty:
                continue  # Continue if the queue is empty
            except Exception:
                sys.exit(1)
    # Start a pool of worker threads
    num_worker_threads = 10  # Adjust based on your needs
    threads = [threading.Thread(target=worker) for _ in range(num_worker_threads)]
    for thread in threads:
        thread.start()

    try:
        while True:
            if not check_connection(pymc3e, PLC_IP, PLC_PORT):
                logger.critical("PLC connection lost. Exiting program.")
                break  # Exit the loop if the connection is lost

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
    main(pymc3e,PLC_IP, PLC_PORT)
