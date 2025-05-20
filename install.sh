#!/bin/bash

# Exit on error
set -e

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "Please run as root (sudo)"
    exit 1
fi

# Configuration
BOT_DIR="/home/ec2-user/rss-bot"
SERVICE_USER="ec2-user"
PYTHON_PATH="/usr/bin/python3"

# Create bot directory if it doesn't exist
mkdir -p "$BOT_DIR"

# Copy files to bot directory
cp rss_discord_bot.py "$BOT_DIR/"
cp config.yaml "$BOT_DIR/"
cp requirements.txt "$BOT_DIR/"

# Install Python dependencies
pip3 install -r requirements.txt

# Create and configure systemd service file
cat > /etc/systemd/system/rss-bot.service << EOL
[Unit]
Description=RSS Bot Service
After=network.target

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$BOT_DIR
ExecStart=$PYTHON_PATH $BOT_DIR/rss_discord_bot.py
Restart=on-failure
Environment=PYTHONUNBUFFERED=1
Environment=DISCORD_TOKEN=${DISCORD_TOKEN}

[Install]
WantedBy=multi-user.target
EOL

# Create and configure systemd timer file
cat > /etc/systemd/system/rss-bot.timer << EOL
[Unit]
Description=Run RSS Bot twice a week at 12:15 PM Denver time

[Timer]
OnCalendar=Tue,Fri 12:15:00 America/Denver
AccuracySec=1m
Persistent=true
RandomizedDelaySec=300

[Install]
WantedBy=timers.target
EOL

# Set proper permissions
chown -R $SERVICE_USER:$SERVICE_USER "$BOT_DIR"
chmod 755 "$BOT_DIR"
chmod 644 "$BOT_DIR"/*

# Reload systemd
systemctl daemon-reload

# Enable and start the service and timer
systemctl enable rss-bot.service
systemctl enable rss-bot.timer
systemctl start rss-bot.timer

# Check status
echo "Checking service status..."
systemctl status rss-bot.timer
echo "Checking timer status..."
systemctl status rss-bot.service

echo "Installation complete! The RSS bot will run every Tuesday and Friday at 12:15 PM Denver time."
echo "To check logs: journalctl -u rss-bot.service"
echo "To check timer status: systemctl status rss-bot.timer" 