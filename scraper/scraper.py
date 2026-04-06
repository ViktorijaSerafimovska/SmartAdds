import json
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

import pazar3
import reklama5

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "ads.json"


def scrape_all():
    ads = []

    try:
        pazar3_ads = pazar3.scrape(max_pages=150, delay=1.0)
        print(f"Pazar3 total: {len(pazar3_ads)}")
        ads.extend(pazar3_ads)
    except Exception as e:
        print(f"Pazar3 scrape error: {e}")

    try:
        reklama5_ads = reklama5.scrape(max_pages=300, delay=1.0)
        print(f"Reklama5 total: {len(reklama5_ads)}")
        ads.extend(reklama5_ads)
    except Exception as e:
        print(f"Reklama5 scrape error: {e}")

    unique = []
    seen = set()

    for ad in ads:
        title = (ad.get("title") or "").strip()
        link = (ad.get("link") or "").strip()
        source = (ad.get("source") or "").strip()

        if not title or not link:
            continue

        key = (title.lower(), link.lower())
        if key in seen:
            continue
        seen.add(key)

        unique.append({
            "title": title,
            "link": link,
            "source": source
        })

    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(unique, f, ensure_ascii=False, indent=2)

    print(f"Saved {len(unique)} total ads to {DATA_FILE}")


if __name__ == "__main__":
    scrape_all()
