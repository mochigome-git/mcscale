import serial
import time

# Serial port configuration
SERIAL_PORT = '/dev/ttyAMA0'  # Adjust based on your Raspberry Pi's configuration
BAUD_RATE = 9600

def initialize_serial():
    """Initialize the serial connection."""
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    if ser.isOpen():
        print(f"Serial port {SERIAL_PORT} opened successfully at {BAUD_RATE} baud rate.")
    else:
        print(f"Failed to open serial port {SERIAL_PORT}.")
    return ser

def read_scale_data(ser):
    """Read and print data from the serial port."""
    weight = ""
    while ser.in_waiting > 0:
        char = ser.read().decode('ascii', errors='ignore') 
        if char == '\n':
            print(f"Weight: {weight}")
            weight = ""  # Reset for next reading
        else:
            weight += char

if __name__ == "__main__":
    # Initialize Serial Communication
    ser = initialize_serial()

    try:
        while True:
            # Read data from the scale
            read_scale_data(ser)
            time.sleep(0.1)  # Adjust sleep as needed for reading frequency

    except KeyboardInterrupt:
        print("Program terminated")

    finally:
        ser.close()
