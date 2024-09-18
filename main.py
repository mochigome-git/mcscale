import pymcprotocol
import utility
import time

# Initialize the single PLC connection
plc_ip = "192.168.3.61"
plc_port = 5014
pymc3e = pymcprotocol.Type3E()
pymc3e.connect(plc_ip, plc_port)

def process_serial_data(ser, headdevice, bitunit):
    buffer = b""  # Buffer for binary data
    while True:
        if ser.in_waiting > 0:
            data = ser.read(ser.in_waiting)
            buffer += data

            # Print raw and hex format for debugging
            print(f"Raw data received from {ser.port}: {data}")
            print(f"Buffer in hex format: {buffer.hex()}")

            if b'\r\n' in buffer:
                try:
                    # Decode buffer to ASCII and strip terminators
                    decoded_data = buffer.decode('ascii').strip()
                    print(f"Received weight data: {decoded_data}")

                    # Check if the weight data ends with 'g' and remove it
                    if decoded_data.endswith('g'):
                        weight_data = decoded_data.rstrip('g').strip()
                        print(f"Raw weight data extracted: {weight_data}")

                        # Remove any unwanted characters (e.g., leading '+') and convert to float
                        weight_data = weight_data.lstrip('ST,+')  # Remove leading '+'
                        
                        try:
                            weight_value = float(weight_data)  # Convert to float
                            target_value = int(weight_value * 10)  # Convert to integer by multiplying by 10
                            print(f"Target value: {target_value}")

                            # Convert target_value to 32-bit format and split into 16-bit words
                            converted_values = utility.split_32bit_to_16bit(target_value)
                            print(f"Converted values (32-bit split into 16-bit): {converted_values}")

                            # Write the split 16-bit values to the PLC
                            pymc3e.batchwrite_wordunits(headdevice=headdevice, values=converted_values)
                            
                            # Write to the specified bit unit
                            pymc3e.batchwrite_bitunits(headdevice=bitunit, values=[1])
                            
                            # Sleep for 2 seconds
                            time.sleep(12)
                            
                            # After the delay, write to PLC
                            pymc3e.batchwrite_bitunits(headdevice=bitunit, values=[0])
                            pymc3e.batchwrite_wordunits(headdevice=headdevice, values=[0, 0])
                            # print(f"PLC {headdevice} and bit unit {bitunit} updated after delay.")
                        except ValueError:
                            print(f"Invalid weight data format: {weight_data}")

                except UnicodeDecodeError:
                    print(f"Could not decode data: {buffer.hex()}")

                buffer = b""  # Clear buffer after processing data

def main():
    # Set up serial communication
    serial_ports = {
        "/dev/ttyUSB0": None,
        #"/dev/ttyUSB1": None,
        #"/dev/ttyUSB2": None
    }

    # Initialize the serial port
    utility.initialize_serial_connections(serial_ports, bytesize='SEVENBITS')

    # Example mapping of serial ports to PLC head devices and bit units
    port_to_headdevice_and_bitunit = {
        "/dev/ttyUSB0": ("D6464", "M3400"),
       # "/dev/ttyUSB1": ("D6464", "M3400"),
       # "/dev/ttyUSB2": ("D6564", "M3500")
    }

    try:
        while True:
            for port, (headdevice, bitunit) in port_to_headdevice_and_bitunit.items():
                ser = serial_ports[port]
                process_serial_data(ser, headdevice, bitunit)

    except KeyboardInterrupt:
        print("Terminating program.")
    finally:
        for ser in serial_ports.values():
            ser.close()
        print("All serial connections closed.")
        pymc3e.close()
        print("PLC connection closed.")

if __name__ == "__main__":
    main()
