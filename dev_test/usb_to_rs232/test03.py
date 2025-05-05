import serial

# Replace '/dev/ttyUSB0' with your USB port name
usb_port = '/dev/serial0'  
baud_rate = 9600  # Adjust the baud rate to match your device

# Initialize serial connection
ser = serial.Serial(usb_port, baud_rate, timeout=1)

try:
    while True:
        if ser.in_waiting > 0:
            # Read data from the USB port
            data = ser.readline().decode('utf-8').strip()
            print(f"Received: {data}")

except KeyboardInterrupt:
    print("Exiting...")
finally:
    # Close the serial connection
    ser.close()
