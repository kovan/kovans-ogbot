#!/bin/bash
# OGBot Launcher Script for Linux/Mac

echo "Starting Kovan's OGBot (Clojure Edition)..."

# Check if Leiningen is installed
if ! command -v lein &> /dev/null; then
    echo "Error: Leiningen not found!"
    echo "Please install Leiningen from https://leiningen.org/"
    exit 1
fi

# Create necessary directories
mkdir -p files/config
mkdir -p files/botdata
mkdir -p files/log
mkdir -p debug

# Run the bot
if [ "$1" = "--no-gui" ] || [ "$1" = "--console" ]; then
    lein run --no-gui
else
    lein run
fi
