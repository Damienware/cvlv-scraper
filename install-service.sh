#!/bin/bash
# Install the CV.LV scraper as a systemd timer + service.
# Run as root from the project directory:
#   sudo bash install-service.sh
#
# The script auto-detects the project directory and the user who invoked sudo.
# To override the user, pass it as the first argument:
#   sudo bash install-service.sh myuser

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICE_USER="${1:-${SUDO_USER:-pi}}"
VENV_PYTHON="$PROJECT_DIR/venv/bin/python3"

echo "CV.LV Job Scraper — systemd service installer"
echo "================================================"
echo "Project directory : $PROJECT_DIR"
echo "Service user      : $SERVICE_USER"
echo ""

# ── Pre-flight checks ─────────────────────────────────────────────────────────

if [ "$EUID" -ne 0 ]; then
    echo "❌  Please run with sudo: sudo bash install-service.sh"
    exit 1
fi

if [ ! -f "$VENV_PYTHON" ]; then
    echo "❌  Virtual environment not found at $VENV_PYTHON"
    echo "    Create it first: python3 -m venv venv && venv/bin/pip install -r requirements.txt"
    exit 1
fi

if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo "❌  .env file not found — copy .env.example and fill in your values first."
    exit 1
fi

# ── Write service unit ────────────────────────────────────────────────────────

cat > /etc/systemd/system/cvlv-scraper.service << EOF
[Unit]
Description=CV.LV Job Scraper (single run)
After=network-online.target docker.service
Wants=network-online.target
Requires=docker.service

[Service]
Type=oneshot
User=$SERVICE_USER
WorkingDirectory=$PROJECT_DIR
EnvironmentFile=$PROJECT_DIR/.env
ExecStart=$VENV_PYTHON $PROJECT_DIR/run_once.py
StandardOutput=journal
StandardError=journal
SyslogIdentifier=cvlv-scraper

# Give the scraper up to 30 minutes before systemd kills it
TimeoutStartSec=1800
EOF

echo "✅  cvlv-scraper.service written"

# ── Write timer unit ──────────────────────────────────────────────────────────

cat > /etc/systemd/system/cvlv-scraper.timer << EOF
[Unit]
Description=Run CV.LV Job Scraper daily at 18:00
Requires=cvlv-scraper.service

[Timer]
# Fire every day at 18:00 local time
OnCalendar=*-*-* 18:00:00
# If the Pi was off at 18:00, catch up as soon as it boots
Persistent=true
Unit=cvlv-scraper.service

[Install]
WantedBy=timers.target
EOF

echo "✅  cvlv-scraper.timer written"

# ── Enable and start the timer ────────────────────────────────────────────────

systemctl daemon-reload
systemctl enable cvlv-scraper.timer
systemctl start  cvlv-scraper.timer

echo ""
echo "── Timer status ──────────────────────────────────────────────────────────"
systemctl status cvlv-scraper.timer --no-pager
echo ""
echo "── Next scheduled run ────────────────────────────────────────────────────"
systemctl list-timers cvlv-scraper.timer --no-pager
echo ""
echo "Done. The scraper will run automatically every day at 18:00."
echo ""
echo "Useful commands:"
echo "  journalctl -u cvlv-scraper -f              # follow scraper logs"
echo "  systemctl list-timers cvlv-scraper.timer   # next scheduled run"
echo "  systemctl start cvlv-scraper.service       # trigger a manual run now"
echo "  systemctl stop  cvlv-scraper.timer         # pause the schedule"
echo "  systemctl disable cvlv-scraper.timer       # remove from boot"
