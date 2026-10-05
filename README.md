# CV.LV Job Scraper

A Python-based web scraper that automatically collects design job listings from cv.lv — searching for UI/UX, designer, dizaineris, and grafiskais dizaineris roles across Fully Remote, Hybrid, and Rīga locations. Results are saved to Google Sheets daily at 6 PM. Designed to run on a Raspberry Pi.

## Features

- 🔍 Scrapes cv.lv for UI/UX and design jobs across 3 locations
- 📊 Saves job data to Google Sheets automatically
- 🐳 Uses containerized Firefox via Docker for reliable scraping
- 🚫 Avoids duplicate entries by checking existing job URLs
- ⏰ Runs once daily at 6 PM via cron
- 🛡️ Anti-detection: rotating user agents, random delays, no images/CSS
- 🍓 Designed for Raspberry Pi (ARM64)

## Prerequisites

- Raspberry Pi OS (64-bit)
- Docker (installed on the Pi)
- Python 3.x
- Google Cloud Service Account with Sheets API access
- Google Sheets document for storing job data

## Setup Instructions

### 1. Install Docker on Raspberry Pi

```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
# Log out and back in for group changes to take effect
```

### 2. Set Up Python Environment

1. **Navigate to the project directory**:
   ```bash
   cd ~/cvlv-scraper
   ```

2. **Create a virtual environment**:
   ```bash
   python3 -m venv venv
   ```

3. **Activate and install dependencies**:
   ```bash
   source venv/bin/activate
   pip install -r requirements.txt
   ```

### 3. Configure Environment Variables

1. **Copy the example file**:
   ```bash
   cp .env.example .env
   ```

2. **Edit `.env`** with your actual values:
   ```bash
   nano .env
   ```

   Fill in:
   - `GOOGLE_SHEETS_ID` — the long ID from your Google Sheets URL
   - `GOOGLE_SERVICE_ACCOUNT_FILE` — absolute path to your service account JSON key
   - `SELENIUM_GRID_URL` — leave as `http://localhost:4444/wd/hub`
   - `MAX_JOBS_PER_RUN` — max jobs per keyword/location combo (default: 100)

### 4. Start Docker Containers

```bash
docker compose up -d
```

Wait ~10 seconds for the containers to be ready, then verify:

```bash
docker compose ps
```

You should see `selenium-hub` and `selenium-firefox` both running.

### 5. Test the Setup

```bash
source venv/bin/activate

# Test connections
python3 run_scraper.py --test

# Run once to verify scraping works
python3 run_scraper.py --once
```

Expected output for `--test`:
```
✓ Google Sheets connection successful
✓ Firefox WebDriver setup successful
✓ All systems ready!
```

### 6. Set Up Automated Scheduling via Cron

#### Option A: Automatic Setup
```bash
chmod +x setup_cron.sh
bash setup_cron.sh

# Add the cron job automatically (runs daily at 6 PM)
(crontab -l 2>/dev/null; echo "0 18 * * * cd /home/pi/cvlv-scraper && /home/pi/cvlv-scraper/venv/bin/python3 /home/pi/cvlv-scraper/run_once.py >> /home/pi/cvlv-scraper/cvlv_scraper.log 2>&1") | crontab -
```

#### Option B: Manual Setup
```bash
crontab -e

# Add this line to run daily at 6 PM:
0 18 * * * cd /home/pi/cvlv-scraper && /home/pi/cvlv-scraper/venv/bin/python3 /home/pi/cvlv-scraper/run_once.py >> /home/pi/cvlv-scraper/cvlv_scraper.log 2>&1
```

## Raspberry Pi / ARM64 Notes

The official `selenium/node-firefox:4.15.0` image may not support ARM64.
If `docker compose up` fails with a platform error, replace the image in `docker-compose.yml`:

```yaml
  firefox:
    image: seleniarm/node-firefox:4.15.0   # ARM64-native image
```

The [seleniarm images](https://github.com/seleniumhq-community/docker-seleniarm) are community-maintained ARM64 builds of the official Selenium Docker images and are a drop-in replacement.

Also replace the hub image if needed:

```yaml
  selenium-hub:
    image: seleniarm/hub:4.15.0
```

## Usage

| Command | Description |
|---------|-------------|
| `python3 run_scraper.py --test` | Test connections (Google Sheets + WebDriver) |
| `python3 run_scraper.py --once` | Run scraper once |
| `python3 run_scraper.py --debug` | Debug cv.lv page access, saves cvlv_debug.png |
| `python3 run_scraper.py` | Start scheduler (runs daily at 6 PM) |
| `python3 run_once.py` | Single run (designed for cron jobs) |

## Monitoring

1. **Check cron job status**:
   ```bash
   crontab -l
   ```

2. **View real-time logs**:
   ```bash
   tail -f cvlv_scraper.log
   ```

3. **Check recent log entries**:
   ```bash
   tail -20 cvlv_scraper.log
   ```

4. **View Docker container logs**:
   ```bash
   docker compose logs
   ```

## Troubleshooting

### 1. Docker Not Running
**Error**: `Connection refused` when testing WebDriver
**Solution**:
```bash
docker compose down
docker compose up -d
```

### 2. Google Sheets Connection Failed
**Error**: `Google service account file not found`
**Solution**:
- Verify the service account JSON file exists at the path in `.env`
- Confirm the service account has Editor access to the Google Sheet

### 3. Cron Job Not Running
```bash
# Check if cron service is running
sudo service cron status

# Start if needed
sudo service cron start

# Verify the job is added
crontab -l
```

### 4. Virtual Environment Issues
```bash
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 5. ARM64 / Raspberry Pi Image Error
**Error**: `no matching manifest for linux/arm64/v8`
**Solution**: Replace both images in `docker-compose.yml` with the `seleniarm` variants (see [Raspberry Pi / ARM64 Notes](#raspberry-pi--arm64-notes) above).

### 6. No Jobs Found / Debug Mode
If the scraper runs but finds no jobs, use debug mode to inspect what cv.lv is returning:

```bash
python3 run_scraper.py --debug
```

This saves:
- `cvlv_debug.png` — screenshot of the page
- `cvlv_page_source.html` — raw HTML source
- `cvlv_debug_source.html` — source saved when no cards are found mid-scrape

## Configuration

### Environment Variables (`.env`)

| Variable | Description | Example |
|----------|-------------|---------|
| `GOOGLE_SHEETS_ID` | Google Sheets document ID | `1JjEwtaNeSlwfkZr1T_4P9rOJrAjFyZKIs22cKEGfb50` |
| `GOOGLE_SERVICE_ACCOUNT_FILE` | Path to service account JSON | `/home/pi/cvlv-scraper/service-account-key.json` |
| `SELENIUM_GRID_URL` | Selenium Grid endpoint | `http://localhost:4444/wd/hub` |
| `MAX_JOBS_PER_RUN` | Maximum jobs per keyword/location combo | `100` |

### Cron Schedule Options

| Schedule | Cron Expression | Description |
|----------|----------------|-------------|
| Daily at 6 PM | `0 18 * * *` | **Default** |
| Every hour | `0 * * * *` | Top of each hour |
| Twice daily | `0 9,18 * * *` | 9 AM and 6 PM |
| Every 2 hours | `0 */2 * * *` | Every 2 hours |

## Quick Start Checklist

- [ ] Docker installed and running on Raspberry Pi
- [ ] Virtual environment created and activated
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] `.env` file configured with Sheets ID and service account path
- [ ] Docker containers running (`docker compose up -d`)
- [ ] Test passes (`python3 run_scraper.py --test`)
- [ ] Single run works (`python3 run_once.py`)
- [ ] Cron job configured (`crontab -l`)

## File Structure

```
├── cvlv_scraper.py         # Core scraper logic
├── run_scraper.py          # CLI runner with --once / --test / --debug flags
├── run_once.py             # Single-run script for cron jobs
├── setup_cron.sh           # Cron job setup helper
├── docker-compose.yml      # Docker container configuration
├── .env.example            # Environment variable template
├── requirements.txt        # Python dependencies (pinned)
├── cvlv_scraper.log        # Scraper execution logs
└── README.md               # This file
```
