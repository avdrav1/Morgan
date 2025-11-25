#!/bin/bash

#######################################
# Setup Log Rotation Cron Job
#######################################
# This script sets up a cron job to automatically rotate logs daily.
#
# Usage: sudo ./scripts/setup-log-rotation-cron.sh

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "========================================="
echo "Setup Log Rotation Cron Job"
echo "========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Error: This script must be run as root (use sudo)${NC}"
    exit 1
fi

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Path to the log rotation script
ROTATE_SCRIPT="$PROJECT_DIR/scripts/rotate-logs.sh"

# Check if rotation script exists
if [ ! -f "$ROTATE_SCRIPT" ]; then
    echo -e "${RED}Error: Log rotation script not found at $ROTATE_SCRIPT${NC}"
    exit 1
fi

# Make sure the script is executable
chmod +x "$ROTATE_SCRIPT"

# Create cron job entry
CRON_JOB="0 2 * * * cd $PROJECT_DIR && $ROTATE_SCRIPT >> /var/log/log-rotation.log 2>&1"

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "$ROTATE_SCRIPT"; then
    echo -e "${YELLOW}Cron job for log rotation already exists${NC}"
    echo ""
    echo "Current cron jobs:"
    crontab -l | grep "$ROTATE_SCRIPT"
    echo ""
    read -p "Do you want to update it? (y/n) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 0
    fi
    # Remove existing cron job
    crontab -l | grep -v "$ROTATE_SCRIPT" | crontab -
fi

# Add new cron job
(crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -

echo -e "${GREEN}Cron job added successfully!${NC}"
echo ""
echo "Cron job details:"
echo "  Schedule: Daily at 2:00 AM"
echo "  Script: $ROTATE_SCRIPT"
echo "  Log file: /var/log/log-rotation.log"
echo ""
echo "Current cron jobs:"
crontab -l
echo ""

# Create log file for cron output
touch /var/log/log-rotation.log
chmod 644 /var/log/log-rotation.log

echo -e "${GREEN}Setup completed!${NC}"
echo ""
echo "To view log rotation logs:"
echo "  tail -f /var/log/log-rotation.log"
echo ""
echo "To manually run log rotation:"
echo "  $ROTATE_SCRIPT"
echo ""
echo "To remove the cron job:"
echo "  crontab -e"
echo "  (then delete the line containing 'rotate-logs.sh')"
echo ""
echo "========================================="
