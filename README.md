# Serial Communication with PLC on Raspberry Pi 5

This repository contains code for managing serial communication and interacting with a PLC (Programmable Logic Controller) using a Raspberry Pi 5. The code handles reading data from serial devices and writing data to a PLC.

## Requirements

- ```Raspberry Pi 5```: The code is designed to run on a Raspberry Pi 5.
- ```Python```: Ensure Python is installed on your Raspberry Pi. You can install it using:
```bash
  sudo apt-get update
  sudo apt-get install python3
```
Required Packages: 
- ```pyserial```: Used for serial communication
- ```pymcprotocol```: Used for communication with the PLC. More details check [senrust/pymcprotocol](https://github.com/senrust/pymcprotocol)

## Installation
#### 1. Install pyserial:
```bash
pip install pyserial
```
#### 2. Install pymcprotocol: For installing pymcprotocol, use the following command to break system package constraints:
```bash
sudo pip install --break-system-packages pymcprotocol
```
#### 3. Check if FTDI Driver is Already Installed

1. **Check for the FTDI driver module**  
    ```bash
    lsmod | grep ftdi_sio
    ```

2. **Load the driver manually (if not detected)**  
    ```bash
    sudo modprobe ftdi_sio
    ```

3. **Check if the device is detected**  
    ```bash
    dmesg | grep ttyUSB
    ```

4. **Install required packages (if necessary)**  
    ```bash
    sudo apt update
    sudo apt install build-essential dkms linux-headers-$(uname -r)
    ```

5. **List available serial ports**  
    ```bash
    ls /dev/ttyUSB*
    ```


## Usage
1. Set up your serial ports in the ```serial_ports``` dictionary.
2. Configure the PLC connection with the appropriate IP and port.
3. Run the script:
```bash
python3 main.py
```

## Notes
- Ensure that your serial devices are connected properly and the paths in the serial_ports dictionary are correctly specified.
- Modify the pymc3e.connect() parameters to match your PLC’s IP address and port.

## License
This project is licensed under the Apache License - see the [```LICENSE```](LICENSE) file for details.
