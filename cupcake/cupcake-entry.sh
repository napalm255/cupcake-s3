#!/bin/bash

# Check if crond is installed
if ! command -v crond &> /dev/null
then
    echo "crond could not be found"
    exit 1
fi

# Check if uvicorn is installed
if ! command -v uvicorn &> /dev/null
then
    echo "uvicorn could not be found"
    exit 1
fi

# Set the timezone
if [ -n "$TZ" ]; then
    echo "Setting timezone to $TZ..."
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime
    echo $TZ > /etc/timezone
fi

# Start cron service
echo "Starting cron service..."
crond -s

# Start the web service
echo "Starting the web service..."
uvicorn cupcake:app --host 0.0.0.0 --port ${PORT:-3124} --reload
