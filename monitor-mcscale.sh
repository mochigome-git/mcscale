#!/bin/bash

EXPECTED_COUNT=3
SERVICE_NAME="mcs-usb-monitor"
LOG_TAG="[USB Monitor][$SERVICE_NAME]"

# Count current ttyUSB devices
count=$(ls /dev/ttyUSB* 2>/dev/null | wc -l)

if [ "$count" -lt "$EXPECTED_COUNT" ]; then
    echo "$LOG_TAG Detected only $count USB devices. Expected $EXPECTED_COUNT."
    echo "$LOG_TAG Rebooting system due to missing USB devices..."

    # Optional: write to a log file for diagnostics
    echo "$(date) - [$SERVICE_NAME] USB device count $count < $EXPECTED_COUNT. Rebooting." >> /var/log/usb-monitor.log

    # Reboot the system
    sudo reboot
else
    echo "$LOG_TAG All $EXPECTED_COUNT USB devices present."
fi
