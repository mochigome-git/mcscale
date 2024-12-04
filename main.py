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
import connect
import utility
import process

# Configure logging to include date and time
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,  # Set the logging level to INFO or higher
    format='%(asctime)s - %(levelname)s - %(message)s',  # Include timestamp, log level, and message
    datefmt='%Y-%m-%d %H:%M:%S'  # Specify date and time format
)
logger = logging.getLogger(__name__)

# Set up serial communication
serial_ports = {
    "/dev/ttyUSB0": None,
    "/dev/ttyUSB1": None,
    "/dev/ttyUSB2": None
}

# Mapping of serial ports to PLC head devices and bit units
port_to_headdevice_and_bitunit = {
    "/dev/ttyUSB0": ("D6364", "M3300"),
    "/dev/ttyUSB1": ("D6464", "M3400"),
    "/dev/ttyUSB2": ("D6564", "M3500")
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
                ser, headdevice, bitunit, states = data_queue.get(timeout=1)  # Block until there's data or timeout
                
                # Prepare the context dictionary with all necessary data
                context = {
                    "ser": ser,
                    "headdevice": headdevice,
                    "bitunit": bitunit,
                    "pymc3e": pymc3e,
                    "logger": logger,
                    "state": states,  # State specific to this port
                    "stop_event": stop_event  # Pass the stop_event here
                }

                # Pass the context to the processing function
                process.smode_process_serial_data(context)
                data_queue.task_done()
            except queue.Empty:
                continue  # Continue if the queue is empty
            except Exception as e:
                logger.error("Worker encountered an unexpected error: %s", e)


    # Start a pool of worker threads
    num_worker_threads = 10
    threads = [threading.Thread(target=worker, daemon=True) for _ in range(num_worker_threads)]
    for thread in threads:
        thread.start()

    # Monitor function (producer)
    def monitor():
        while not stop_event.is_set():
            for port, (headdevice, bitunit) in port_to_headdevice_and_bitunit.items():
                ser = serial_ports[port]
                if ser and ser.is_open and ser.in_waiting > 0:  # Check for new data
                    try:
                        # Enqueue serial port data for processing
                        data_queue.put((ser, headdevice, bitunit, states[port]))
                    except queue.Full:
                        logger.warning("Data queue is full. Dropping new data.")
            time.sleep(0.1)  # Reduce CPU usage in the monitor thread

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

    try:
        # Main loop: Check PLC connection
        while True:
            if not connect.check_connection(pymc3e, PLC_IP, PLC_PORT, logger):
                logger.critical("PLC connection lost. Exiting program.")
                break  # Exit the loop if the connection is lost

            time.sleep(0.1)  # Reduce CPU usage in the main loop

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received. Shutting down gracefully...")
    except Exception as e:
        logger.critical("Terminating program due to unexpected error: %s", e)
    finally:
        stop_event.set()  # Signal worker threads to stop
        monitor_thread.join()  # Wait for the monitor thread to finish
        for thread in threads:
            thread.join()  # Wait for all worker threads to finish
        for ser in serial_ports.values():
            if ser is not None:
                ser.close()
        logger.info("All serial connections closed.")
        pymc3e.close()
        logger.info("PLC connection closed.")
        sys.exit(0)

if __name__ == "__main__":
    PLC_IP = "192.168.3.61"
    PLC_PORT = 5014
    pymc3e = connect.initialize_connection(PLC_IP, PLC_PORT, logger)
    main(pymc3e, PLC_IP, PLC_PORT)