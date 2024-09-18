import serial

dev = "/dev/serial0"  # Device name
rate = 9600  # Baud rate (bps)
bytesize = serial.SEVENBITS  # Data bits (8 bits per byte)
parity = serial.PARITY_EVEN  # Parity check (None, Even, Odd, Mark, Space)
stopbits = serial.STOPBITS_ONE  # Stop bits (1, 1.5, or 2)

try:
    # Open serial port with additional settings
    ser = serial.Serial(
        port=dev,
        baudrate=rate,
        bytesize=bytesize,
        parity=parity,
        stopbits=stopbits,
        timeout=None  # Blocking mode; wait indefinitely for input
    )
    print(f"Opened serial port {dev} successfully. Listening for data...")

    # Continuous listening loop
    while True:
        # Read data from serial port
        res = ser.readline()
        if res:  # If data is received
            res = res.decode(errors='ignore')  # Decode to string, ignore errors if any
            print(f"Received: {res}")

except serial.SerialException as e:
    print(f"Error opening or communicating with serial port: {e}")
except KeyboardInterrupt:
    print("Interrupted by user. Exiting...")
finally:
    if 'ser' in locals() and ser.is_open:
        ser.close()
        print(f"Closed serial port {dev}.")
