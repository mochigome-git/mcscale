
import os
import time
import sys
import logging
import serial

# -----------------------------------------------------------------------------
# Fallback serial settings (used when a value is missing or invalid in .env)
# -----------------------------------------------------------------------------
DEFAULT_SERIAL_SETTINGS = {
    "baudrate": 19200,
    "bytesize": "SEVENBITS",
    "parity": "EVEN",
    "stopbits": "ONE",
    "timeout": 1.0,
}

# Map string values to the corresponding `serial` constants.
# Both the long names and short aliases are accepted (e.g. SEVENBITS or 7).
bytesize_map = {
    'FIVEBITS': serial.FIVEBITS, '5': serial.FIVEBITS,
    'SIXBITS': serial.SIXBITS, '6': serial.SIXBITS,
    'SEVENBITS': serial.SEVENBITS, '7': serial.SEVENBITS,
    'EIGHTBITS': serial.EIGHTBITS, '8': serial.EIGHTBITS,
}

parity_map = {
    'NONE': serial.PARITY_NONE, 'N': serial.PARITY_NONE,
    'EVEN': serial.PARITY_EVEN, 'E': serial.PARITY_EVEN,
    'ODD': serial.PARITY_ODD, 'O': serial.PARITY_ODD,
    'MARK': serial.PARITY_MARK, 'M': serial.PARITY_MARK,
    'SPACE': serial.PARITY_SPACE, 'S': serial.PARITY_SPACE,
}

stopbits_map = {
    'ONE': serial.STOPBITS_ONE, '1': serial.STOPBITS_ONE,
    'ONE_POINT_FIVE': serial.STOPBITS_ONE_POINT_FIVE, '1.5': serial.STOPBITS_ONE_POINT_FIVE,
    'TWO': serial.STOPBITS_TWO, '2': serial.STOPBITS_TWO,
}


def _env(name):
    """Return a cleaned env value, or None if unset/empty."""
    value = os.getenv(name)
    if value is None:
        return None
    value = value.strip().strip('"').strip("'").strip()
    return value or None


def load_serial_settings():
    """
    Load serial settings from environment variables, falling back to
    DEFAULT_SERIAL_SETTINGS for anything missing or invalid.

    Environment variables
    ---------------------
    SERIAL_BAUDRATE : int     e.g. 9600, 19200
    SERIAL_BYTESIZE : str     FIVEBITS|SIXBITS|SEVENBITS|EIGHTBITS (or 5|6|7|8)
    SERIAL_PARITY   : str     NONE|EVEN|ODD|MARK|SPACE (or N|E|O|M|S)
    SERIAL_STOPBITS : str     ONE|ONE_POINT_FIVE|TWO (or 1|1.5|2)
    SERIAL_TIMEOUT  : float   seconds, e.g. 1 or 0.5
    """
    settings = dict(DEFAULT_SERIAL_SETTINGS)

    # Baudrate
    raw = _env("SERIAL_BAUDRATE")
    if raw is not None:
        try:
            baud = int(raw)
            if baud <= 0:
                raise ValueError
            settings["baudrate"] = baud
        except ValueError:
            logging.warning("Invalid SERIAL_BAUDRATE=%r, using fallback %s",
                            raw, settings["baudrate"])

    # Bytesize / parity / stopbits
    for key, env_name, mapping in (
        ("bytesize", "SERIAL_BYTESIZE", bytesize_map),
        ("parity", "SERIAL_PARITY", parity_map),
        ("stopbits", "SERIAL_STOPBITS", stopbits_map),
    ):
        raw = _env(env_name)
        if raw is None:
            continue
        if raw.upper() in mapping:
            settings[key] = raw.upper()
        else:
            logging.warning("Invalid %s=%r, using fallback %s (allowed: %s)",
                            env_name, raw, settings[key], ", ".join(mapping))

    # Timeout
    raw = _env("SERIAL_TIMEOUT")
    if raw is not None:
        try:
            timeout = float(raw)
            if timeout < 0:
                raise ValueError
            settings["timeout"] = timeout
        except ValueError:
            logging.warning("Invalid SERIAL_TIMEOUT=%r, using fallback %s",
                            raw, settings["timeout"])

    return settings


def initialize_serial_connections(serial_ports, baudrate=None, bytesize=None,
                                  parity=None, stopbits=None, timeout=None):
    """
    Initializes serial connections for all ports in the serial_ports dictionary.

    Priority for each setting:
        1. Argument passed to this function
        2. Value from .env (SERIAL_BAUDRATE, SERIAL_BYTESIZE, ...)
        3. DEFAULT_SERIAL_SETTINGS fallback

    Parameters
    ----------
    serial_ports : dict
        Dictionary of serial ports where the key is the port name and the value is a serial object.
    baudrate, bytesize, parity, stopbits, timeout : optional
        Explicit overrides. Leave as None to use .env / fallback values.

    Raises
    ------
    SerialException
        If a port fails to open.
    """

    # Configure logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    env_settings = load_serial_settings()
    baudrate = baudrate if baudrate is not None else env_settings["baudrate"]
    bytesize = (bytesize or env_settings["bytesize"]).upper()
    parity = (parity or env_settings["parity"]).upper()
    stopbits = (stopbits or env_settings["stopbits"]).upper()
    timeout = timeout if timeout is not None else env_settings["timeout"]

    logging.info(
        "Serial settings: baudrate=%s, bytesize=%s, parity=%s, stopbits=%s, timeout=%s",
        baudrate, bytesize, parity, stopbits, timeout,
    )

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
                logging.info("Valid response from %s: %s", ser.name, response.decode('utf-8'))
                return True
            
            # Log if the response is empty
            #logging.warning("Empty response from %s", ser.name)
        
        except Exception as e:
            logging.error("Failed to send PING token to %s: %s", ser.name, e)
        
        retries += 1
        time.sleep(5)  # Wait a bit before retrying
    
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
