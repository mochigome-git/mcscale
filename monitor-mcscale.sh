#!/bin/bash

CONTAINER_NAME="mcscale-mcscale-1"
LOG_TAG="[MCScale Watchdog]"

echo "$LOG_TAG Monitoring Docker container: $CONTAINER_NAME"

while true; do
  STATUS=$(docker inspect -f '{{.State.Running}}' "$CONTAINER_NAME" 2>/dev/null)

  if [ "$STATUS" != "true" ]; then
    echo "$LOG_TAG Container is not running! Attempting restart and USB reset..."

    # Reset all USB devices (requires root)
    for usb_dev in /sys/bus/usb/devices/*; do
    echo "${usb_dev##*/}" | sudo tee /sys/bus/usb/drivers/usb/unbind
    echo "${usb_dev##*/}" | sudo tee /sys/bus/usb/drivers/usb/bind
    done

    # Restart container
    docker compose -f docker-compose-production.yml restart "$CONTAINER_NAME"
    sleep 5
  fi

  sleep 10  # check every 10 seconds
done
