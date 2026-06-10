import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent

if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

import pazar3
import reklama5

from app.database.db import engine, Base

Base.metadata.create_all(bind=engine)


def scrape_all():
    try:
        pazar3.scrape(max_pages=56, delay=1.0)
    except Exception as e:
        print(f"Pazar3 scrape error: {e}")

    try:
        reklama5.scrape(max_pages=56, delay=1.0)
    except Exception as e:
        print(f"Reklama5 scrape error: {e}")

    print("All scraping finished")


if __name__ == "__main__":
    scrape_all()