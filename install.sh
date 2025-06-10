#!/bin/bash

# Exit on error
set -e

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "Please run as root"
    exit 1
fi

# Configuration
BOT_DIR="/home/ec2-user/rss-discord-bot"
SERVICE_FILE="rss-bot.service"
TIMER_FILE="rss-bot.timer"

# Create directory if it doesn't exist
mkdir -p "$BOT_DIR"

# Copy files
cp rss_discord_bot.py "$BOT_DIR/"
cp config.yaml "$BOT_DIR/"
cp requirements.txt "$BOT_DIR/"
cp .env "$BOT_DIR/"

# Install Python dependencies
pip3 install -r requirements.txt

# Install service and timer
cp "$SERVICE_FILE" /etc/systemd/system/
cp "$TIMER_FILE" /etc/systemd/system/

# Reload systemd
systemctl daemon-reload

# Enable and start the timer
systemctl enable rss-bot.timer
systemctl start rss-bot.timer

echo "Installation complete!" 