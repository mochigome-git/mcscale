import serial

def initialize_serial_connections(serial_ports, baudrate=9600, bytesize='EIGHTBITS', parity='EVEN', stopbits='ONE', timeout=1):
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
            serial_ports[port] = ser  # Store the initialized Serial object
            print(f"Opened serial port {port} successfully.")
        except serial.SerialException as e:
            print(f"Failed to open serial port {port}: {e}")
