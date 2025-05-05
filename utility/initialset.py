from typing import Dict, Tuple
import logging
import queue
import time
import socket
import threading

logger = logging.getLogger(__name__)

def parse_serial_ports_config(env_value: str) -> Dict[str, Tuple[str, str]]:
    """Parses the SERIAL_PORTS environment variable."""
    mapping = {}
    for entry in env_value.split(";"):
        if not entry.strip():
            continue
        try:
            port, devices = entry.strip().split(":", 1)
            headdevice, bitunit = devices.split(",")
            headdevice = headdevice.lstrip("/")
            bitunit = bitunit.strip()
            mapping[port.strip()] = (headdevice, bitunit)
        except ValueError as e:
            logger.warning(f"Skipping invalid SERIAL_PORTS entry: {entry} - {e}")
    return mapping


def monitor_serial_ports( data_queue, serial_ports, port_device_map, states, stop_event):
    while not stop_event.is_set():
        try:
            for port, (headdevice, bitunit) in port_device_map.items():
                ser = serial_ports[port]
                if ser and ser.is_open and ser.in_waiting > 0:
                    data_queue.put((ser, headdevice, bitunit, states[port]))
            time.sleep(0.1)
        except (ValueError, socket.error) as e:
            logger.error("Monitor encountered an error: %s", e)
            stop_event.set()
            break


def worker(pymc3e, data_queue, stop_event, logger):
    import process  # import here to avoid circular imports
    while not stop_event.is_set():
        try:
            ser, headdevice, bitunit, state = data_queue.get(timeout=1)
            context = {
                "ser": ser,
                "headdevice": headdevice,
                "bitunit": bitunit,
                "pymc3e": pymc3e,
                "logger": logger,
                "state": state,
                "stop_event": stop_event,
            }
            process.smode_process_serial_data(context)
            data_queue.task_done()
        except queue.Empty:
            continue
        except (ValueError, socket.error) as e:
            logger.error("Worker encountered error: %s", e)
            stop_event.set()
            break
