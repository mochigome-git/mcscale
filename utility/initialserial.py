
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
            else:
                # Log that the port is healthy (open)
                logging.debug("Serial port %s is open and healthy.", port)
                
            # Ensure that any issues are flagged by setting the flag to False if necessary
            if ser is None or not ser.is_open:
                all_ports_open = False
        
        # If all ports are open and healthy, print a success message
        if all_ports_open:
            #logging.info("All serial ports are open and functioning correctly.")
            continue
        
        time.sleep(1)  