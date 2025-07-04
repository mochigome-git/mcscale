import subprocess
import time
import socket
import sys
import pymcprotocol


def initialize_connection(plc_ip, plc_port, logger, retries=5, delay=2):
    """Initialize connection to PLC with retries."""
    pymc3e = pymcprotocol.Type3E()
    for attempt in range(retries):
        try:
            pymc3e.connect(plc_ip, plc_port)
            logger.info("Connected to PLC successfully.")
            return pymc3e
        except TimeoutError:
            logger.error(
                "Connection attempt %d failed. Retrying in %d seconds...",
                attempt + 1,
                delay,
            )
            time.sleep(delay)
    raise ConnectionError("Failed to connect to PLC after multiple attempts.")


def ping_host(host, logger, retries=3, timeout=5):
    """Ping the PLC to check if it is reachable with retries and timeout."""
    ping_path = "/bin/ping"  

    for attempt in range(1, retries + 1):
        try:
            result = subprocess.run(
                [ping_path, "-c", "1", "-W", str(timeout), host],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            logger.warning("Ping attempt %d to %s failed. Response: %s", attempt, host, e.stderr.decode())
        except (ValueError, socket.error) as e:
            logger.error("Unexpected error while pinging the host: %s", e)
            break  # Do not retry on unexpected internal errors

        time.sleep(1)  # Optional: wait 1 second before retrying

    return False


def check_connection(pymc3e, plc_ip, plc_port, logger, retry_attempts=8, retry_delay=5):
    """Check if the PLC is still connected using ping."""
    try:
        # First, ping the PLC to check its availability
        if ping_host(plc_ip, logger):
            return True

        logger.error("PLC is not reachable via ping. IP: %s", plc_ip)
        return False

    except (ValueError, socket.error) as e:
        logger.error("PLC connection lost: %s", e)

        # Attempt to reconnect if ping fails or if connection is lost
        for attempt in range(retry_attempts):
            logger.info("Attempting to reconnect to PLC...")
            try:
                pymc3e = initialize_connection(
                    plc_ip, plc_port, logger
                )  # Attempt to reconnect
                return True
            except ConnectionError:
                logger.error(
                    "Reconnection attempt %d failed. Retrying in %d seconds...",
                    attempt + 1,
                    retry_delay,
                )
                time.sleep(retry_delay)

        logger.critical(
            "Failed to reconnect after %d attempts. Exiting...", retry_attempts
        )
        raise ConnectionError("PLC not reachable after retries.")

