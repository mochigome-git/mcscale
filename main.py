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

# Configure logging to include date and time
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,  # Set the logging level to INFO or higher
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Set up serial communication
serial_ports = {"/dev/ttyUSB0": None, "/dev/ttyUSB1": None, "/dev/ttyUSB2": None}

# Mapping of serial ports to PLC head devices and bit units
port_to_headdevice_and_bitunit = {
    "/dev/ttyUSB0": ("D6364", "M3300"),
    "/dev/ttyUSB1": ("D6464", "M3400"),
    "/dev/ttyUSB2": ("D6564", "M3500"),
}


def main(pymc3e, PLC_IP, PLC_PORT):
    """Main function to run the PLC connection and data processing."""
    utility.initialize_serial_connections(serial_ports)

    # Shared queue for producer (monitoring) and consumer (worker) threads
    data_queue = queue.Queue()

    # Stop event for graceful shutdown
    stop_event = threading.Event()

    # State tracking for each port
    states = {
        port: {"buffer": b"", "last_weight": 0, "last_update_time": 0}
        for port in port_to_headdevice_and_bitunit
    }

    # Worker function (consumer)
    def worker():
        while not stop_event.is_set():
            try:
                ser, headdevice, bitunit, states = data_queue.get(timeout=1)
                context = {
                    "ser": ser,
                    "headdevice": headdevice,
                    "bitunit": bitunit,
                    "pymc3e": pymc3e,
                    "logger": logger,
                    "state": states,
                    "stop_event": stop_event,
                }
                process.smode_process_serial_data(context)
                data_queue.task_done()

            except queue.Empty:
                continue  # No data to process, continue loop

            except (ValueError, socket.error) as e:
                logger.error("Worker encountered an unexpected error: %s", e)
                stop_event.set()  # Signal all threads to stop
                break

    # Start a pool of worker threads
    num_worker_threads = 10
    threads = [
        threading.Thread(target=worker, daemon=True) for _ in range(num_worker_threads)
    ]
    for thread in threads:
        thread.start()

    # Monitor function (producer)
    def monitor():
        while not stop_event.is_set():
            try:
                for port, (
                    headdevice,
                    bitunit,
                ) in port_to_headdevice_and_bitunit.items():
                    ser = serial_ports[port]
                    if ser and ser.is_open and ser.in_waiting > 0:
                        data_queue.put((ser, headdevice, bitunit, states[port]))

                time.sleep(0.1)

            except (ValueError, socket.error) as e:
                logger.error("Monitor encountered an error: %s", e)
                stop_event.set()  # Trigger shutdown if the monitor fails critically
                break

    # Uncomment to use utility.monitor_serial_ports to check the heathly status
    # def monitor():
    #     while not stop_event.is_set():
    #         try:
    #             utility.monitor_serial_ports(serial_ports, port_to_headdevice_and_bitunit, states, data_queue, stop_event, logger)
    #         except Exception as e:
    #             logger.error(f"Monitor encountered an error: {e}")
    #         time.sleep(0.1)  # Reduce CPU usage in the monitor thread

    monitor_thread = threading.Thread(target=monitor, daemon=True)
    monitor_thread.start()

    # Main loop: Check PLC connection
    try:
        while not stop_event.is_set():
            if not connect.check_connection(pymc3e, PLC_IP, PLC_PORT, logger):
                logger.critical("PLC connection lost. Initiating shutdown...")
                stop_event.set()
                break

            time.sleep(0.1)

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received. Shutting down gracefully...")
        stop_event.set()

    except (ValueError, socket.error) as e:
        logger.critical("Specific error occurred: %s", e)
        stop_event.set()

    finally:
        # Ensure all threads shut down gracefully
        monitor_thread.join()
        for thread in threads:
            thread.join()

        # Close serial ports
        for ser in serial_ports.values():
            if ser is not None:
                ser.close()
        logger.info("All serial connections closed.")

        # Close PLC connection
        pymc3e.close()
        logger.info("PLC connection closed.")
        sys.exit(0)


if __name__ == "__main__":
    try:
        PLC_IP = os.getenv("PLC_IP")
        PLC_PORT = int(os.getenv("PLC_PORT"))

        # Validate environment variables
        if not PLC_IP or not PLC_PORT:
            logger.critical("PLC_IP or PLC_PORT is not set correctly in the .env file.")
            sys.exit(1)

        pymc3e = connect.initialize_connection(PLC_IP, PLC_PORT, logger)
        main(pymc3e, PLC_IP, PLC_PORT)

    except (ValueError, socket.error) as e:
        logger.critical("Program failed to start due to: %s", e)
        sys.exit(1)
