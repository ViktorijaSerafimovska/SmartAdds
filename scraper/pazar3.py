import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

BASE_URL = "https://www.pazar3.mk"
START_URL = "https://www.pazar3.mk/oglasi"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}


def looks_like_ad_link(href: str) -> bool:
    if not href:
        return False

    href = href.strip().lower()

    bad_parts = [
        "javascript:",
        "#",
        "/login",
        "/registracija",
        "/kontakt",
        "/help",
        "/profile",
        "/poraki",
        "/koshnichka",
    ]
    if any(x in href for x in bad_parts):
        return False

    if "/oglasi/" not in href:
        return False

    noisy_parts = [
        "?page=",
        "/q-",
        "/prodazba-kupuvanje",
        "/izdavanje-iznajmuvanje",
        "/baram-za-iznajmuvanje",
    ]
    if any(x in href for x in noisy_parts):
        return False

    return True


def extract_ads_from_page(html: str):
    soup = BeautifulSoup(html, "html.parser")
    ads = []
    seen = set()

    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        title = a.get_text(" ", strip=True)

        if not title or len(title) < 5:
            continue

        full_link = urljoin(BASE_URL, href)

        if not looks_like_ad_link(full_link):
            continue

        key = (title.lower(), full_link.lower())
        if key in seen:
            continue
        seen.add(key)

        ads.append({
            "title": title,
            "link": full_link,
            "source": "pazar3"
        })

    return ads


def scrape(max_pages: int = 100, delay: float = 1.0):
    all_ads = []
    global_seen = set()

    for page in range(1, max_pages + 1):
        if page == 1:
            url = START_URL
        else:
            url = f"{START_URL}?Page={page}"

        print(f"[Pazar3] Scraping page {page}: {url}")

        try:
            response = requests.get(url, headers=HEADERS, timeout=25)
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

        all_ads.extend(new_ads)
        time.sleep(delay)

    return all_ads


