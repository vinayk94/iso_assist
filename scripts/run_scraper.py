import os
import sys
import asyncio
import logging
from dotenv import load_dotenv

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from src.scraper.crawler import ERCOTScraper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("scraper.log"),
        logging.StreamHandler()
    ]
)

async def main():
    scraper = ERCOTScraper()
    try:
        logging.info("Starting ERCOT RQ scraping process...")
        await scraper.start()
        logging.info("Scraping completed successfully!")
    except Exception as e:
        logging.error(f"Scraping failed: {e}")
        raise

if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main())