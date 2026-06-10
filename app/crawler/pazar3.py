import re
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from app.database.repository import save_ads_to_db

#Tuka go dodavame ova za save match
from app.search.matcher import match_new_ads

BASE_URL = "https://www.pazar3.mk"
START_URL = "https://www.pazar3.mk/oglasi"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}


def extract_ads_from_page(html: str):
    soup = BeautifulSoup(html, "html.parser")
    ads = []
    seen = set()

    for card in soup.find_all("div", class_="row-listing"):
        title_tag = card.find("h2")
        if not title_tag:
            continue
        a_tag = title_tag.find("a", href=True)
        if not a_tag:
            continue

        href = a_tag.get("href", "").strip()
        # Individual ads use /oglas/ (singular); /oglasi/ links are category pages
        if not href or "/oglas/" not in href or "/oglasi/" in href:
            continue

        full_link = urljoin(BASE_URL, href)
        title = (a_tag.get("title") or a_tag.get_text(" ", strip=True)).strip()
        if not title or len(title) < 5:
            continue

        price_el = card.find(class_="list-price")
        price = price_el.get_text(strip=True) if price_el else ""

        key = (title.lower(), full_link.lower())
        if key in seen:
            continue
        seen.add(key)

        ads.append({
            "title": title,
            "link": full_link,
            "source": "pazar3",
            "price": price,
            "description": "",
        })

    return ads


def scrape(max_pages: int = 10, delay: float = 1.0):

    global_seen = set()

    for page in range(1, max_pages + 1):
        url = START_URL if page == 1 else f"{START_URL}?Page={page}"
        print(f"[Pazar3] Scraping page {page}: {url}")

        try:
            response = requests.get(url, headers=HEADERS, timeout=50)
            response.raise_for_status()
        except Exception as e:
            print(f"[Pazar3] Request error on page {page}: {e}")
            break

        page_ads = extract_ads_from_page(response.text)
        new_ads = []
        for ad in page_ads:
            key = (ad["title"].lower(), ad["link"].lower())
            if key not in global_seen:
                global_seen.add(key)
                new_ads.append(ad)

        print(f"[Pazar3] Found {len(page_ads)} ads, new: {len(new_ads)}")

        if not new_ads:
            print(f"[Pazar3] No new ads on page {page}. Stopping.")
            break

        # all_ads.extend(new_ads)
        # save_ads_to_db(new_ads)

#tuka go dodadovme ova
        saved_ads = save_ads_to_db(new_ads)

        if saved_ads:
            match_new_ads(saved_ads)

        time.sleep(delay)

    # return all_ads
    print("[Pazar3] Scraping finished")


# if __name__ == "__main__":
#     results = scrape(max_pages=10, delay=1.0)
#     print(f"Total ads scraped: {len(results)}")
#     for ad in results[:10]:
#         print(ad)

if __name__ == "__main__":
    scrape(max_pages=10, delay=1.0)