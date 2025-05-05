## Steps to Read Serial Data from GPIO 15
Enable the Serial Port on Raspberry Pi: By default, the Raspberry Pi uses its serial port for console messages. To use it for serial communication, you need to disable the serial console.

- Open the Raspberry Pi configuration tool:
```bash
sudo raspi-config
```

- Go to Interfacing Options -> Serial.
- When asked, "Would you like a login shell to be accessible over serial?" select No.
- When asked, "Would you like the serial port hardware to be enabled?" select Yes.
- Exit the configuration tool and reboot your Raspberry Pi
