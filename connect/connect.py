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



def ping_host(host, logger, timeout_sec=5, max_attempts=3):
    """Ping the PLC with timeout and retries."""
    ping_cmd = ["ping", "-c", "1", "-W", str(timeout_sec), host]
    
    for attempt in range(1, max_attempts + 1):
        try:
            result = subprocess.run(
                ping_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,  # Ensures proper string decoding
                timeout=timeout_sec + 1,   # Extra buffer time
            )
            
            if result.returncode == 0:
                logger.info(f"Successfully pinged {host} (Attempt {attempt}/{max_attempts})")
                return True
            else:
                logger.warning(f"Ping attempt {attempt}/{max_attempts} failed for {host}. Error: {result.stderr or result.stdout}")
        
        except subprocess.TimeoutExpired:
            logger.warning(f"Ping attempt {attempt}/{max_attempts} to {host} timed out after {timeout_sec} sec")
        except Exception as e:
            logger.error(f"Unexpected error pinging {host}: {str(e)}")
        
        if attempt < max_attempts:
            time.sleep(1)  # Small delay before retry
    
    logger.error(f"All {max_attempts} ping attempts to {host} failed")
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

