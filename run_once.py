#!/usr/bin/env python3
"""
CV.LV Job Scraper - Single Run / For use with cron jobs
"""
import sys
import os
from cvlv_scraper import CVLVJobScraper


def main():
    """Run the scraper once"""
    scraper = CVLVJobScraper()

    try:
        print("Starting single scraper run...")
        scraper.run_scraping_job()
        print("Scraper run completed successfully")
        return 0
    except Exception as e:
        print(f"Scraper run failed: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
