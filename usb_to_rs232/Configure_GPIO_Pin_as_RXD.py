import pigpio

# Replace with the GPIO pin you want to use for RXD
RX_PIN = 17  # GPIO 17 is an example; replace it with your desired pin

# Initialize pigpio
pi = pigpio.pi()

if not pi.connected:
    print("Failed to connect to pigpio daemon")
    exit()

# Set up the pin for software-based serial communication
pi.set_mode(RX_PIN, pigpio.INPUT)  # Set RX_PIN as input
pi.bb_serial_read_open(RX_PIN, 9600)  # Open the pin for serial reading at 9600 baud rate

try:
    while True:
        (count, data) = pi.bb_serial_read(RX_PIN)  # Read data from the software RX pin
        if count > 0:
            print("Received:", data.decode("utf-8", errors="ignore"))
except KeyboardInterrupt:
    print("Stopping serial read")

# Clean up
pi.bb_serial_read_close(RX_PIN)
pi.stop()
