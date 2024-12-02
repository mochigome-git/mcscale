
import time
import sys
import logging
import serial

# Map string values to the corresponding `serial` constants
bytesize_map = {
    'FIVEBITS': serial.FIVEBITS,
    'SIXBITS': serial.SIXBITS,
    'SEVENBITS': serial.SEVENBITS,
    'EIGHTBITS': serial.EIGHTBITS
}

parity_map = {
    'NONE': serial.PARITY_NONE,
    'EVEN': serial.PARITY_EVEN,
    'ODD': serial.PARITY_ODD,
    'MARK': serial.PARITY_MARK,
    'SPACE': serial.PARITY_SPACE
}

stopbits_map = {
    'ONE': serial.STOPBITS_ONE,
    'TWO': serial.STOPBITS_TWO
}

def initialize_serial_connections(serial_ports, baudrate=19200, bytesize='SEVENBITS', parity='EVEN', stopbits='ONE', timeout=1):
    """
    Initializes serial connections for all ports in the serial_ports dictionary.

    Serial communication settings:
    
    Parameters
    ----------
    serial_ports : dict
        Dictionary of serial ports where the key is the port name and the value is a serial object.

    baudrate : int, optional
        Communication speed in baud, default is 9600.
    
    bytesize : str, optional
        Number of data bits ('FIVEBITS', 'SIXBITS', 'SEVENBITS', 'EIGHTBITS'), default is 'SEVENBITS'.
    
    parity : str, optional
        Parity check ('NONE', 'EVEN', 'ODD', 'MARK', 'SPACE'), default is 'EVEN'.
    
    stopbits : str, optional
        Number of stop bits ('ONE', 'TWO'), default is 'ONE'.
    
    timeout : float, optional
        Timeout in seconds for the serial connection, default is 1 second.
    
    Raises
    ------
    SerialException
        If a port fails to open.
    """

    # Configure logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    for port in serial_ports.keys():
        try:
            ser = serial.Serial(
                port=port,
                baudrate=baudrate,
                bytesize=bytesize_map.get(bytesize, serial.SEVENBITS),
                parity=parity_map.get(parity, serial.PARITY_EVEN),
                stopbits=stopbits_map.get(stopbits, serial.STOPBITS_ONE),
                timeout=timeout
            )
            serial_ports[port] = ser
            logging.info("Opened serial port %s successfully.", port)
        except serial.SerialException as e:
            logging.error("Failed to open serial port %s: %s", port, e)
            serial_ports[port] = None  # Mark as None to retry later
    
    return serial_ports

def send_ping_token(ser, max_retries=3):
    """
    Sends a PING token to check if the device on the serial port is ready to receive data.
    If the device responds with any content, it is treated as a valid response.
    
    Parameters
    ----------
    ser : serial.Serial
        The serial object representing the port to be checked.
    
    max_retries : int
        Maximum number of retries for the PING check if the device doesn't respond.
    
    Returns
    -------
    bool
        True if the device responds with any content, False otherwise.
    """
    retries = 0
    while retries < max_retries:
        try:
            # Send a PING token (optional: depending on how your device is set up)
            #ping_token = b'PING'  # PING token;
            #ser.write(ping_token)
            response = ser.readline()  # Read the response from the device
            
            # Check if the response contains any data (non-empty response)
            if response.strip():  # strip() removes any leading/trailing whitespace or newline
                # logging.info("Valid response from %s: %s", ser.name, response.decode('utf-8'))
                return True
            
            # Log if the response is empty
            #logging.warning("Empty response from %s", ser.name)
        
        except Exception as e:
            logging.error("Failed to send PING token to %s: %s", ser.name, e)
        
        retries += 1
        time.sleep(15)  # Wait a bit before retrying
    
    # If retries are exhausted and no valid response, return False
    return False

def monitor_serial_ports(serial_ports, stop_event=None):
    """
    Monitors the state of serial ports, ensuring they remain open and reconnects if a port is closed.
    
    Parameters
    ----------
    serial_ports : dict
        Dictionary of serial ports where the key is the port name and the value is a serial object.
    
    stop_event : threading.Event
        Used to signal the monitoring thread to stop.
    """
    while not stop_event.is_set():
        all_ports_open = True  # Flag to track the health of all ports
        
        for port in list(serial_ports.keys()):
            ser = serial_ports[port]
            
            # Check if the port is not initialized or not open
            if ser is None or not ser.is_open:
                logging.warning("Serial port %s is not open. Attempting to reconnect.", port)
                
                try:
                    # Attempt to reopen the serial port
                    ser.open()
                    logging.info("Reconnected serial port %s.", port)
                except Exception as e:
                    # If reconnection fails, log the error and exit
                    logging.critical("Failed to reconnect serial port %s: %s. Exiting program.", port, e)
                    sys.exit(1)
            
            # Check if the device on the port is ready using the PING token
            if ser is not None and ser.is_open:
                if send_ping_token(ser):
                    logging.debug("Serial port %s is open, healthy, and responsive.", port)
                else:
                    logging.warning("Serial port %s is open, but the device is not responding to PING. Attempting to reconnect.", port)
                    try:
                        ser.close()
                        ser.open()
                        logging.info("Reconnected serial port %s after failed PING response.", port)
                    except Exception as e:
                        logging.critical("Failed to reconnect serial port %s after failed PING: %s. Exiting program.", port, e)
                        sys.exit(1)  # Exit if PING fails and reconnection is unsuccessful
                        
            # Flag if any port is not healthy
            if ser is None or not ser.is_open:
                all_ports_open = False
        
        # If all ports are open and healthy, print a success message (optional)
        if all_ports_open:
            #logging.info("All serial ports are open, healthy, and responsive.")
            continue
        time.sleep(1)  # Check status periodically