# import sys
# from pathlib import Path
#
# CURRENT_DIR = Path(__file__).resolve().parent
#
# if str(CURRENT_DIR) not in sys.path:
#     sys.path.insert(0, str(CURRENT_DIR))
#
# import pazar3
# import reklama5
#
# from app.database.db import engine, Base
# from app.database.repository import save_ads_to_db
#
# # Create tables automatically
# Base.metadata.create_all(bind=engine)
#
#
# def scrape_all():
#
#     ads = []
#
#     try:
#         pazar3_ads = pazar3.scrape(max_pages=150, delay=1.0)
#
#         print(f"Pazar3 total: {len(pazar3_ads)}")
#
#         ads.extend(pazar3_ads)
#
#     except Exception as e:
#         print(f"Pazar3 scrape error: {e}")
#
#     try:
#         reklama5_ads = reklama5.scrape(max_pages=300, delay=1.0)
#
#         print(f"Reklama5 total: {len(reklama5_ads)}")
#
#         ads.extend(reklama5_ads)
#
#     except Exception as e:
#         print(f"Reklama5 scrape error: {e}")
#
#     unique = []
#     seen = set()
#
#     for ad in ads:
#
#         title = (ad.get("title") or "").strip()
#         link = (ad.get("link") or "").strip()
#         source = (ad.get("source") or "").strip()
#
#         if not title or not link:
#             continue
#
#         key = (title.lower(), link.lower())
#
#         if key in seen:
#             continue
#
#         seen.add(key)
#
#         unique.append({
#             "title": title,
#             "link": link,
#             "source": source,
#             "price": (ad.get("price") or "").strip(),
#             "description": (ad.get("description") or "").strip(),
#         })
#
#     save_ads_to_db(unique)
#
#     print(f"Saved {len(unique)} ads to database")
#
#
# if __name__ == "__main__":
#     scrape_all()

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
        pazar3.scrape(max_pages=50, delay=1.0)
    except Exception as e:
        print(f"Pazar3 scrape error: {e}")

    try:
        reklama5.scrape(max_pages=50, delay=1.0)
    except Exception as e:
        print(f"Reklama5 scrape error: {e}")

    print("All scraping finished")


if __name__ == "__main__":
    scrape_all()