#!/bin/bash

# CV.LV Job Scraper - Cron Job Setup Script
# This script helps you set up a cron job to run the scraper daily at 6 PM

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_PATH="$SCRIPT_DIR/venv/bin/python3"
SCRIPT_PATH="$SCRIPT_DIR/run_once.py"
LOG_PATH="$SCRIPT_DIR/cvlv_scraper.log"

echo "CV.LV Job Scraper - Cron Job Setup"
echo "======================================"
echo ""
echo "Script directory: $SCRIPT_DIR"
echo "Python path: $PYTHON_PATH"
echo "Script path: $SCRIPT_PATH"
echo "Log path: $LOG_PATH"
echo ""

# Check if virtual environment exists
if [ ! -f "$PYTHON_PATH" ]; then
    echo "❌ Virtual environment not found at: $PYTHON_PATH"
    echo "Please make sure you've set up the virtual environment first."
    exit 1
fi

# Check if run_once.py exists
if [ ! -f "$SCRIPT_PATH" ]; then
    echo "❌ Script not found at: $SCRIPT_PATH"
    exit 1
fi

echo "✅ All files found!"
echo ""

# Generate the cron job line (runs daily at 6 PM)
CRON_LINE="0 18 * * * cd $SCRIPT_DIR && $PYTHON_PATH $SCRIPT_PATH >> $LOG_PATH 2>&1"

echo "Cron job line to add:"
echo "====================="
echo "$CRON_LINE"
echo ""

echo "To set up the CV.LV cron job:"
echo "1. Run: crontab -e"
echo "2. Add the line above to run the CV.LV scraper daily at 6 PM"
echo "3. Save and exit"
echo ""

echo "To check if the CV.LV cron job is running:"
echo "- View logs: tail -f $LOG_PATH"
echo "- List cron jobs: crontab -l"
echo ""

echo "Alternative: Run this command to add the cron job automatically:"
echo "(crontab -l 2>/dev/null; echo \"$CRON_LINE\") | crontab -"
