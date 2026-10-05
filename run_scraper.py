"""
CV.LV Job Scraper Runner
Simple script to run the scraper once or start the scheduler
"""

import sys
import argparse
from cvlv_scraper import CVLVJobScraper


def main():
    parser = argparse.ArgumentParser(description='CV.LV Job Scraper')
    parser.add_argument('--once', action='store_true',
                        help='Run scraper once instead of starting scheduler')
    parser.add_argument('--test', action='store_true',
                        help='Test the setup without running scraper')
    parser.add_argument('--debug', action='store_true',
                        help='Debug CV.LV page access and save screenshots')

    args = parser.parse_args()

    scraper = CVLVJobScraper()

    if args.test:
        print("Testing setup...")
        try:
            scraper.setup_google_sheets()
            print("✓ Google Sheets connection successful")
            scraper.setup_driver()
            print("✓ Firefox WebDriver setup successful")
            scraper.driver.quit()
            print("✓ All systems ready!")
        except Exception as e:
            print(f"✗ Setup test failed: {str(e)}")
            sys.exit(1)

    elif args.debug:
        print("Running debug session...")
        scraper.debug_cvlv_page()
        print("Debug complete. Check cvlv_debug.png and cvlv_page_source.html")

    elif args.once:
        print("Running scraper once...")
        scraper.run_scraping_job()

    else:
        print("Starting scheduler (runs daily at 6 PM)...")
        scraper.start_scheduler()


if __name__ == "__main__":
    main()
