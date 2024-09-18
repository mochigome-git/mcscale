import serial
import time

# Define the serial port and baud rate
serial_port = "/dev/ttyS10"  # Default UART port on Raspberry Pi
baud_rate = 9600

def initialize_serial():
    # Initialize serial communication
    ser = serial.Serial(serial_port, baud_rate, timeout=1)
    
    if ser.isOpen():
        print(f"Serial port {serial_port} opened successfully at {baud_rate} baud rate.")
    else:
        print(f"Failed to open serial port {serial_port}.")
    
    return ser

def read_serial_data(ser):
    try:
        while True:
            # Read data from the serial port
            if ser.in_waiting > 0:
                data = ser.readline().decode('utf-8').rstrip()
                print(f"Received: {data}")

    except KeyboardInterrupt:
        print("Program terminated")

    finally:
        ser.close()

if __name__ == "__main__":
    ser = initialize_serial()
    if ser:
        read_serial_data(ser)
