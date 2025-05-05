"""
This module handles serial communication with PLC devices, processes incoming data,
and interacts with the pymcprotocol library for reading and writing data to PLCs.

Modules:
- threading: For concurrent execution and handling of serial data processing.
- time: For managing timing and delays.
- logging: For logging messages and errors.
- sys: For system-specific parameters and functions.
- pymcprotocol: For communication with PLC devices using the MC Protocol 3E.
- utility: Custom utility functions for data handling.
"""

import threading
import time
import logging
import sys
import queue
import socket
import os
import connect
import utility
import process

# Logging config
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def main(pymc3e, PLC_IP, PLC_PORT):
    """Main orchestration logic."""
    # Set up serial communication
    serial_ports = {"/dev/ttyUSB0": None, "/dev/ttyUSB1": None, "/dev/ttyUSB2": None}
    utility.initialize_serial_connections(serial_ports)

    port_device_map = utility.parse_serial_ports_config(os.getenv("SERIAL_PORTS", ""))
    data_queue = queue.Queue()
    stop_event = threading.Event()
    states = {
        port: {"buffer": b"", "last_weight": 0, "last_update_time": 0}
        for port in port_device_map
    }

    # Start monitor thread
    monitor_thread = threading.Thread(
        target=utility.monitor_serial_ports,
        args=(data_queue, serial_ports, port_device_map, states, stop_event),
        daemon=True,
    )
    monitor_thread.start()

    # Start worker threads
    threads = [
        threading.Thread(target=utility.worker, args=(pymc3e, data_queue, stop_event, logger), daemon=True)
        for _ in range(10)
    ]

    for thread in threads:
        thread.start()

    # Main PLC connection watchdog loop
    try:
        while not stop_event.is_set():
            if not connect.check_connection(pymc3e, PLC_IP, PLC_PORT, logger):
                logger.critical("PLC connection lost. Initiating shutdown...")
                stop_event.set()
            time.sleep(0.1)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received. Shutting down...")
        stop_event.set()
    except Exception as e:
        logger.critical("Unexpected error: %s", e)
        stop_event.set()

    # Shutdown
    monitor_thread.join()
    for thread in threads:
        thread.join()

    for ser in serial_ports.values():
        if ser and ser.is_open:
            try:
                ser.flush()
                ser.close()
            except Exception as e:
                logger.warning("Error closing serial port: %s", e)

    if pymc3e:
        try:
            pymc3e.close()
            logger.info("PLC connection closed.")
        except Exception as e:
            logger.warning("Error while closing PLC connection: %s", e)

    logger.info("Shutdown complete.")
    sys.exit(1)


if __name__ == "__main__":
    try:
        PLC_IP = os.getenv("PLC_IP")
        PLC_PORT = int(os.getenv("PLC_PORT", "0"))

        if not PLC_IP or not PLC_PORT:
            logger.critical("PLC_IP or PLC_PORT not configured.")
            sys.exit(1)

        pymc3e = connect.initialize_connection(PLC_IP, PLC_PORT, logger)
        main(pymc3e, PLC_IP, PLC_PORT)

    except Exception as e:
        logger.critical("Startup failed: %s", e)
        sys.exit(1)
