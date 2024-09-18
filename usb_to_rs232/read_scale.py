import serial

# Set up serial communication on the correct serial port
# Adjust based on your Raspberry Pi configuration
"""
common communication option: ttyACM0, ttyUSB0, serial0, ttyAMA0
"""
dev = '/dev/ttyUSB0' 
rate = 9600  # Adjust according to your scale's specifications
bytesize = serial.SEVENBITS  # Data bits (7 bits per byte)
"""
Parity Check option: None, Even, Odd, Mark, Space
"""
parity = serial.PARITY_EVEN  # Parity check (Even)
"""
Stop bits option: 1, 1.5 or 2
"""
stopbits = serial.STOPBITS_ONE  # Stop bits (1 stop bit)

try:
    # Initialize serial connection
    ser = serial.Serial(
        port=dev,
        baudrate=rate,
        bytesize=bytesize,
        parity=parity,
        stopbits=stopbits,
        timeout=1
    )
    print(f"Opened serial port {dev} successfully. Listening for data...")

    buffer = b""  # Use a byte buffer for binary data

    while True:
        if ser.in_waiting > 0:  # Check if there is data waiting in the buffer
            data = ser.read(ser.in_waiting)
            buffer += data  # Append binary data to buffer

            # Print raw and hex format for debugging
            print(f"Raw data received: {data}")
            print(f"Buffer in hex format: {buffer.hex()}")

            # Check if the buffer contains the CRLF terminator
            if b'\r\n' in buffer:
                try:
                    # Decode buffer to ASCII and strip terminators
                    decoded_data = buffer.decode('ascii').strip()
                    print(f"Received weight data: {decoded_data}")

                    # Check if the weight data ends with 'g' and remove it
                    if decoded_data.endswith('g'):
                        weight_data = decoded_data.rstrip('g').strip()
                        print(f"Extracted weight data: {weight_data}")
                        # Process or publish the weight_data as needed

                except UnicodeDecodeError:
                    print(f"Could not decode data: {buffer.hex()}")

                buffer = b""  # Clear buffer after processing data

except serial.SerialException as e:
    print(f"Serial error: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
finally:
    ser.close()
    print("Serial connection closed.")