import gpiod

# Define the GPIO pin
GPIO_CHIP = "/dev/gpiochip0"
RTX_PIN = 15  # GPIO 15 (BCM)

def wait_for_signal(pin):
    # Open the GPIO chip
    chip = gpiod.Chip(GPIO_CHIP)
    # Get the GPIO line
    line = chip.get_line(pin)

    # Request the GPIO line as an input with an event listener
    line.request(consumer="gpio_reader", type=gpiod.LINE_REQ_EV_BOTH_EDGES)

    try:
        print(f"Waiting for signal on GPIO {pin}...")
        while True:
            # Wait for an event (signal change)
            event = line.event_wait(sec=10)  # Adjust the timeout as needed
            if event:
                # Read the event details
                event = line.event_read()
                value = line.get_value()
                print(f"GPIO {pin} event detected! Value: {value}")

    except KeyboardInterrupt:
        print("Program terminated")

    finally:
        # Release the line and close the chip
        line.release()
        chip.close()

if __name__ == "__main__":
    wait_for_signal(RTX_PIN)
