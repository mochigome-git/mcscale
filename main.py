import pymcprotocol
import utility
import threading
import time
import logging
import sys

# Configure logging to include date and time
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,  # Set the logging level to INFO or higher
    format='%(asctime)s - %(levelname)s - %(message)s',  # Include timestamp, log level, and message
    datefmt='%Y-%m-%d %H:%M:%S'  # Specify date and time format
)

def initialize_connection(plc_ip, plc_port):
    pymc3e = pymcprotocol.Type3E()
    pymc3e.connect(plc_ip, plc_port)
    return pymc3e

# Initialize the single PLC connection
if __name__ == "__main__":
    plc_ip = "192.168.3.61"
    plc_port = 5014
    pymc3e = initialize_connection(plc_ip, plc_port)
    logger = logging.getLogger(__name__)

def process_serial_data(ser, headdevice, bitunit, stop_event):
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
                    logger.info("Received weight data: %s", decoded_data)

                    # Check if the weight data ends with 'g' and remove it
                    if decoded_data.endswith('g'):
                        weight_data = decoded_data.rstrip('g').strip()
                        # print(f"Raw weight data extracted: {weight_data}")

                        # Remove any unwanted characters (e.g., leading '+') and convert to float
                        weight_data = weight_data.lstrip('ST,+')  # Remove leading '+'
                        
                        try:
                            weight_value = float(weight_data)  # Convert to float
                            target_value = int(weight_value * 10)  # Convert to integer by multiplying by 10
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
                            logging.error("Invalid weight data format: %s", weight_data)

                except UnicodeDecodeError:
                    print(f"Could not decode data: {buffer.hex()}")

                buffer = b""  # Clear buffer after processing data

def main():
    # Set up serial communication
    serial_ports = {
        "/dev/ttyUSB0": None,
        # "/dev/ttyUSB1": None,
        # "/dev/ttyUSB2": None
    }

    # Initialize the serial ports
    utility.initialize_serial_connections(serial_ports, bytesize='SEVENBITS')

    # Mapping of serial ports to PLC head devices and bit units
    port_to_headdevice_and_bitunit = {
        "/dev/ttyUSB0": ("D6364", "M3300"),
        # "/dev/ttyUSB1": ("D6464", "M3400"),
        # "/dev/ttyUSB2": ("D6564", "M3500")
    }

    stop_event = threading.Event()

    try:
        while True:
            for port, (headdevice, bitunit) in port_to_headdevice_and_bitunit.items():
                ser = serial_ports[port]
                if ser and ser.in_waiting > 0:  # Check for new data
                    if stop_event.is_set():
                        stop_event.clear()  # Clear stop_event to process new data

                    # Start new thread to handle the new data
                    process_thread = threading.Thread(
                        target=process_serial_data, 
                        args=(ser, headdevice, bitunit, stop_event)
                    )
                    process_thread.start()
                    process_thread.join()  # Wait for the process to finish before processing more data

    except KeyboardInterrupt:
        logger.info("Terminating program.")
    finally:
        for ser in serial_ports.values():
            if ser is not None:
                ser.close()
        logger.info("All serial connections closed.")
        pymc3e.close()
        logger.info("PLC connection closed.")

if __name__ == "__main__":
    main()
