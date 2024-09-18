import serial
import time

# Set up serial communication parameters
dev = '/dev/ttyAMA0'  # Adjust the serial port if necessary
rate = 9600  # Ensure this matches your scale's specification
bytesize = serial.SEVENBITS
parity = serial.PARITY_EVEN
stopbits = serial.STOPBITS_ONE

try:
    # Initialize serial connection
    ser = serial.Serial(
        port=dev,
        baudrate=rate,
        bytesize=bytesize,
        parity=parity,
        stopbits=stopbits,
        timeout=1  # 1 second timeout
    )
    print(f"Opened serial port {dev} successfully.")

    # Send the command 'Q' followed by carriage return (CR) and line feed (LF)
    command = "Q\r\n"
    ser.write(command.encode('ascii'))  # Send command to the scale
    print(f"Command sent: {command.strip()}")

    # Give the scale some time to process and respond
    time.sleep(0.5)

    # Read the response from the scale
    response = ser.read(ser.in_waiting or 128)  # Read up to 128 bytes or all available bytes
    print(f"Raw response: {response}")

    # Decode the response to ASCII
    decoded_response = response.decode('ascii', errors='ignore').strip()
    print(f"Decoded response: {decoded_response}")

except serial.SerialException as e:
    print(f"Serial error: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
finally:
    ser.close()
    print("Serial connection closed.")
