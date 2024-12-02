import subprocess
import time
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
            logger.error("Connection attempt %d failed. Retrying in %d seconds...", attempt + 1, delay)
            time.sleep(delay)
    raise ConnectionError("Failed to connect to PLC after multiple attempts.")

def ping_host(host, logger):
    """Ping the PLC to check if it is reachable."""
    try:
        # Specify the full path to the ping command
        ping_path = "/bin/ping"  # Change this path if necessary based on your system
        response = subprocess.run([ping_path, "-c", "1", host], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        if response.returncode == 0:
            return True
        else:
            logger.error("Ping failed to %s. Response: %s", host, response.stderr.decode())
            return False
    except Exception as e:
        logger.error("Error while pinging the host: %s", e)
        return False
        
def check_connection(pymc3e, plc_ip, plc_port, logger, retry_attempts=3, retry_delay=5):
    """Check if the PLC is still connected using ping."""
    try:
        # First, ping the PLC to check its availability
        if ping_host(plc_ip, logger):
            return True        
        else:
            logger.error("PLC is not reachable via ping. IP: %s", plc_ip)
            return False
    except Exception as e:
        logger.error("PLC connection lost: %s", e)
        
        # Attempt to reconnect if ping fails or if connection is lost
        for attempt in range(retry_attempts):
            logger.info("Attempting to reconnect to PLC...")
            try:
                pymc3e = initialize_connection(plc_ip, plc_port, logger)  # Attempt to reconnect
                return True
            except ConnectionError:
                logger.error("Reconnection attempt %d failed. Retrying in %d seconds...", attempt + 1, retry_delay)
                time.sleep(retry_delay)

        logger.critical("Failed to reconnect after %d attempts. Exiting...", retry_attempts)
        sys.exit(1)  # Exit if reconnection fails after multiple attempts