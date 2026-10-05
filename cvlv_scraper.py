import os
import time
import random
import logging
from datetime import datetime
from typing import List, Dict, Optional
import schedule
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.firefox.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('cvlv_scraper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Realistic desktop user agents for rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:119.0) Gecko/20100101 Firefox/119.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:119.0) Gecko/20100101 Firefox/119.0",
]

# Search parameters
KEYWORDS = ["UI/UX", "designer", "dizaineris", "grafiskais dizaineris"]

# Location filter definitions for cv.lv
# Each entry: (display_name, url_params)
LOCATIONS = [
    ("Fully remote", "&workType%5B%5D=remote"),
    ("Hybrid",       "&workType%5B%5D=hybrid"),
    ("Rīga",         "&cities%5B%5D=R%C4%ABga"),
]

BASE_SEARCH_URL = "https://www.cv.lv/en/search"


class CVLVJobScraper:
    def __init__(self):
        self.driver = None
        self.sheets_client = None
        self.worksheet = None
        self.existing_jobs = set()  # set of job URLs

    # ------------------------------------------------------------------
    # Driver setup
    # ------------------------------------------------------------------

    def setup_driver(self):
        """Initialize Firefox WebDriver using containerized Selenium Grid."""
        firefox_options = Options()
        firefox_options.add_argument("--headless")
        firefox_options.add_argument("--width=1920")
        firefox_options.add_argument("--height=1080")

        # Rotate user agent per session
        ua = random.choice(USER_AGENTS)
        firefox_options.set_preference("general.useragent.override", ua)
        logger.info(f"Using user agent: {ua}")

        # Anti-detection preferences
        firefox_options.set_preference("dom.webdriver.enabled", False)
        firefox_options.set_preference("useAutomationExtension", False)
        firefox_options.set_preference("permissions.default.image", 2)      # Disable images
        firefox_options.set_preference("permissions.default.stylesheet", 2) # Disable stylesheets

        selenium_grid_url = os.getenv('SELENIUM_GRID_URL', 'http://localhost:4444/wd/hub')

        try:
            self.driver = webdriver.Remote(
                command_executor=selenium_grid_url,
                options=firefox_options
            )
            logger.info(f"Firefox WebDriver initialized via Selenium Grid at {selenium_grid_url}")
        except Exception as e:
            logger.error(f"Failed to connect to Selenium Grid at {selenium_grid_url}: {str(e)}")
            logger.info("Falling back to local Firefox WebDriver...")
            try:
                from selenium.webdriver.firefox.service import Service
                from webdriver_manager.firefox import GeckoDriverManager

                service = Service(GeckoDriverManager().install())
                self.driver = webdriver.Firefox(service=service, options=firefox_options)
                logger.info("Local Firefox WebDriver initialized successfully")
            except Exception as local_e:
                logger.error(f"Failed to initialize local Firefox: {str(local_e)}")
                logger.info("Make sure to start the containerized Firefox with: docker-compose up -d")
                raise

    # ------------------------------------------------------------------
    # Google Sheets setup
    # ------------------------------------------------------------------

    def setup_google_sheets(self):
        """Initialize Google Sheets connection."""
        try:
            scope = [
                'https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive'
            ]

            service_account_file = os.getenv('GOOGLE_SERVICE_ACCOUNT_FILE')
            if not service_account_file or not os.path.exists(service_account_file):
                raise FileNotFoundError("Google service account file not found")

            creds = ServiceAccountCredentials.from_json_keyfile_name(service_account_file, scope)
            self.sheets_client = gspread.authorize(creds)

            sheets_id = os.getenv('GOOGLE_SHEETS_ID')
            if not sheets_id:
                raise ValueError("Google Sheets ID not provided")

            spreadsheet = self.sheets_client.open_by_key(sheets_id)

            try:
                self.worksheet = spreadsheet.worksheet("CV.LV Jobs")
            except gspread.WorksheetNotFound:
                self.worksheet = spreadsheet.add_worksheet(title="CV.LV Jobs", rows="1000", cols="10")
                # Add headers
                self.worksheet.update('A1:E1', [['Job Title', 'Company', 'Location', 'Job URL', 'Date Added']])

            logger.info("Google Sheets connection established")

        except Exception as e:
            logger.error(f"Failed to setup Google Sheets: {str(e)}")
            raise

    # ------------------------------------------------------------------
    # Deduplication
    # ------------------------------------------------------------------

    def load_existing_jobs(self):
        """Load existing job URLs from the sheet to avoid duplicates."""
        try:
            records = self.worksheet.get_all_records()
            # Dedup by Job URL (column D, index 3 in 0-based headers)
            self.existing_jobs = {
                record['Job URL'].strip()
                for record in records
                if record.get('Job URL')
            }
            logger.info(f"Loaded {len(self.existing_jobs)} existing job URLs")
        except Exception as e:
            logger.error(f"Failed to load existing jobs: {str(e)}")
            self.existing_jobs = set()

    def is_new_job(self, job_url: str) -> bool:
        """Return True if the job URL has not been saved before."""
        return job_url.strip() not in self.existing_jobs

    # ------------------------------------------------------------------
    # Scrolling helper
    # ------------------------------------------------------------------

    def scroll_page_slowly(self):
        """Scroll the page in small random increments to simulate a human."""
        try:
            total_height = self.driver.execute_script("return document.body.scrollHeight")
            current_pos = 0
            while current_pos < total_height:
                increment = random.randint(100, 300)
                current_pos += increment
                self.driver.execute_script(f"window.scrollTo(0, {current_pos});")
                time.sleep(random.uniform(0.3, 0.8))
        except Exception as e:
            logger.error(f"Error during slow scroll: {str(e)}")

    # ------------------------------------------------------------------
    # Core scraping
    # ------------------------------------------------------------------

    def scrape_cvlv_jobs(self, keyword: str, location_name: str, location_params: str) -> List[Dict[str, str]]:
        """
        Scrape cv.lv for a single keyword + location combination.
        Iterates pages via offset param until no results or MAX_JOBS_PER_RUN reached.
        """
        jobs = []
        max_jobs = int(os.getenv('MAX_JOBS_PER_RUN', 100))
        offset = 0
        page_limit = 20

        import urllib.parse
        encoded_keyword = urllib.parse.quote(keyword)

        while len(jobs) < max_jobs:
            url = (
                f"{BASE_SEARCH_URL}"
                f"?limit={page_limit}&offset={offset}"
                f"&keywords%5B%5D={encoded_keyword}"
                f"{location_params}"
            )
            logger.info(f"Fetching: keyword='{keyword}' location='{location_name}' offset={offset} → {url}")

            try:
                self.driver.get(url)
                time.sleep(random.uniform(5, 12))  # Wait for page load

                self.scroll_page_slowly()

                # Find job cards container
                card_container_selectors = [
                    ".vacancies-list",
                    ".vacancy-list",
                    "ul[class*='vacancies']",
                    "[class*='vacancy-list']",
                ]

                container = None
                for sel in card_container_selectors:
                    try:
                        container = WebDriverWait(self.driver, 8).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, sel))
                        )
                        logger.info(f"Found job container with selector: {sel}")
                        break
                    except TimeoutException:
                        continue

                if not container:
                    logger.warning(
                        f"No job container found for keyword='{keyword}' "
                        f"location='{location_name}' offset={offset}. "
                        "Saving debug source."
                    )
                    self._save_debug_source("cvlv_debug_source.html")
                    break

                # Find individual job cards
                card_selectors = [
                    "li[class*='vacancy']",
                    ".vacancy-item",
                    "article[class*='vacancy']",
                    "[class*='vacancy-item']",
                    "li[class*='job']",
                ]

                cards = []
                for sel in card_selectors:
                    cards = self.driver.find_elements(By.CSS_SELECTOR, sel)
                    if cards:
                        logger.info(f"Found {len(cards)} job cards with selector: {sel}")
                        break

                if not cards:
                    logger.info(
                        f"No job cards on page (keyword='{keyword}', "
                        f"location='{location_name}', offset={offset}). "
                        "End of results."
                    )
                    self._save_debug_source("cvlv_debug_source.html")
                    break

                page_new_count = 0
                for i, card in enumerate(cards):
                    if len(jobs) >= max_jobs:
                        break
                    try:
                        job_data = self._extract_job_data(card, i, location_name)
                        if job_data is None:
                            continue
                        if self.is_new_job(job_data['job_url']):
                            jobs.append(job_data)
                            self.existing_jobs.add(job_data['job_url'])
                            page_new_count += 1
                            logger.info(f"New job: {job_data['title']} @ {job_data['company']}")
                        else:
                            logger.debug(f"Skipping duplicate: {job_data['job_url']}")
                    except Exception as e:
                        logger.error(f"Error extracting card {i}: {str(e)}")

                    time.sleep(random.uniform(3, 8))  # Delay between cards

                logger.info(
                    f"Page offset={offset}: {page_new_count} new jobs "
                    f"(total so far: {len(jobs)})"
                )

                # If fewer cards than the page limit were returned, we've hit the last page
                if len(cards) < page_limit:
                    logger.info("Last page reached (fewer results than page limit).")
                    break

                offset += page_limit

            except Exception as e:
                logger.error(
                    f"Error scraping page (keyword='{keyword}', "
                    f"location='{location_name}', offset={offset}): {str(e)}"
                )
                break

        logger.info(
            f"Finished keyword='{keyword}' location='{location_name}': "
            f"{len(jobs)} new jobs found."
        )
        return jobs

    def _extract_job_data(self, card, index: int, location_name: str) -> Optional[Dict[str, str]]:
        """Extract job data from a single job card element."""
        try:
            # --- Job title ---
            title_selectors = [
                "a[class*='vacancy__title']",
                ".vacancy__name a",
                "h3 a",
                "h2 a",
                ".vacancy-item__title a",
                "[class*='vacancy__name'] a",
            ]
            title = None
            title_href = None
            for sel in title_selectors:
                try:
                    el = card.find_element(By.CSS_SELECTOR, sel)
                    title = (el.text or el.get_attribute('textContent') or '').strip()
                    title_href = el.get_attribute('href')
                    if title:
                        logger.debug(f"Card {index}: title selector '{sel}' → '{title}'")
                        break
                except NoSuchElementException:
                    continue

            # Last-resort: first <a> in the card
            if not title:
                try:
                    el = card.find_element(By.TAG_NAME, 'a')
                    title = (el.text or el.get_attribute('textContent') or '').strip()
                    title_href = el.get_attribute('href')
                    logger.debug(f"Card {index}: fallback <a> title → '{title}'")
                except NoSuchElementException:
                    pass

            if not title:
                logger.warning(f"Card {index}: could not extract title, skipping.")
                return None

            # --- Company name ---
            company_selectors = [
                "[class*='company'] a",
                ".vacancy__employer",
                "[class*='employer']",
                "[class*='company-name']",
                "[class*='company__name']",
            ]
            company = "Company not found"
            for sel in company_selectors:
                try:
                    el = card.find_element(By.CSS_SELECTOR, sel)
                    val = (el.text or el.get_attribute('textContent') or '').strip()
                    if val:
                        company = val
                        logger.debug(f"Card {index}: company selector '{sel}' → '{company}'")
                        break
                except NoSuchElementException:
                    continue

            # --- Location tag ---
            location_selectors = [
                "[class*='location']",
                ".vacancy__location",
                "[class*='city']",
                "[class*='address']",
            ]
            location_tag = location_name  # fall back to the filter name
            for sel in location_selectors:
                try:
                    el = card.find_element(By.CSS_SELECTOR, sel)
                    val = (el.text or el.get_attribute('textContent') or '').strip()
                    if val:
                        location_tag = val
                        logger.debug(f"Card {index}: location selector '{sel}' → '{location_tag}'")
                        break
                except NoSuchElementException:
                    continue

            # --- Job URL ---
            job_url = title_href or ''
            if job_url and job_url.startswith('/'):
                job_url = 'https://www.cv.lv' + job_url
            if not job_url:
                logger.warning(f"Card {index}: no URL found for '{title}', skipping.")
                return None

            return {
                'title': title,
                'company': company,
                'location': location_tag,
                'job_url': job_url,
                'date_added': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            }

        except Exception as e:
            logger.error(f"Error extracting data from card {index}: {str(e)}")
            return None

    def _save_debug_source(self, filename: str):
        """Save the current page source for debugging purposes."""
        try:
            project_dir = os.path.dirname(os.path.abspath(__file__))
            path = os.path.join(project_dir, filename)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self.driver.page_source)
            logger.info(f"Debug page source saved to {path}")
        except Exception as e:
            logger.error(f"Could not save debug source: {str(e)}")

    # ------------------------------------------------------------------
    # Google Sheets write
    # ------------------------------------------------------------------

    def save_jobs_to_sheets(self, jobs: List[Dict[str, str]]):
        """Append new jobs to the Google Sheet."""
        if not jobs:
            logger.info("No new jobs to save")
            return

        try:
            rows_to_add = [
                [
                    job['title'],
                    job['company'],
                    job['location'],
                    job['job_url'],
                    job['date_added'],
                ]
                for job in jobs
            ]
            self.worksheet.append_rows(rows_to_add)
            logger.info(f"Successfully saved {len(jobs)} new jobs to Google Sheets")
        except Exception as e:
            logger.error(f"Failed to save jobs to Google Sheets: {str(e)}")

    # ------------------------------------------------------------------
    # Debug helper
    # ------------------------------------------------------------------

    def debug_cvlv_page(self):
        """Navigate to a sample search, save screenshot + source, log selectors."""
        logger.info("Starting CV.LV debug session...")
        try:
            self.setup_driver()
            url = "https://www.cv.lv/en/search?keywords%5B%5D=designer"
            logger.info(f"Navigating to: {url}")
            self.driver.get(url)
            time.sleep(random.uniform(5, 8))

            # Screenshot
            self.driver.save_screenshot("cvlv_debug.png")
            logger.info("Screenshot saved as cvlv_debug.png")

            # Page source
            with open("cvlv_page_source.html", "w", encoding="utf-8") as f:
                f.write(self.driver.page_source)
            logger.info("Page source saved as cvlv_page_source.html")

            logger.info(f"Page title: {self.driver.title}")
            logger.info(f"Current URL: {self.driver.current_url}")

            # Check job card selectors
            selectors_to_check = [
                ".vacancies-list",
                ".vacancy-list",
                "ul[class*='vacancies']",
                "li[class*='vacancy']",
                ".vacancy-item",
                "article[class*='vacancy']",
                "a[class*='vacancy__title']",
                ".vacancy__name a",
            ]
            for sel in selectors_to_check:
                elements = self.driver.find_elements(By.CSS_SELECTOR, sel)
                logger.info(f"Selector '{sel}': {len(elements)} elements found")

        except Exception as e:
            logger.error(f"Debug session error: {str(e)}")
        finally:
            if self.driver:
                self.driver.quit()
                logger.info("Debug session closed")

    # ------------------------------------------------------------------
    # Main run
    # ------------------------------------------------------------------

    def run_scraping_job(self):
        """Run one complete scraping cycle across all keyword × location combos."""
        logger.info("Starting CV.LV job scraping...")
        total_new = 0

        try:
            self.setup_driver()
            self.setup_google_sheets()
            self.load_existing_jobs()

            for keyword in KEYWORDS:
                for location_name, location_params in LOCATIONS:
                    logger.info(
                        f"--- Scraping: keyword='{keyword}' location='{location_name}' ---"
                    )
                    jobs = self.scrape_cvlv_jobs(keyword, location_name, location_params)
                    self.save_jobs_to_sheets(jobs)
                    total_new += len(jobs)

                    # Pause between combos (anti-detection)
                    time.sleep(random.uniform(10, 20))

            logger.info(f"Scraping completed. Total new jobs found: {total_new}")

        except Exception as e:
            logger.error(f"Error during scraping job: {str(e)}")
        finally:
            if self.driver:
                self.driver.quit()
                logger.info("WebDriver closed")

    def start_scheduler(self):
        """Start the scheduler to run once daily at 6 PM."""
        logger.info("Starting CV.LV job scraper scheduler (daily at 18:00)...")

        schedule.every().day.at("18:00").do(self.run_scraping_job)

        # Run once immediately on startup
        self.run_scraping_job()

        while True:
            schedule.run_pending()
            time.sleep(60)


if __name__ == "__main__":
    scraper = CVLVJobScraper()
    scraper.start_scheduler()
