import time
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

BASE_URL = "https://m.reklama5.mk"
START_URL = "https://m.reklama5.mk/Search"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 10; Mobile) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Mobile Safari/537.36"
    ),
    "Accept-Language": "mk-MK,mk;q=0.9,en-US;q=0.8,en;q=0.7",
}


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def is_bad_title(title: str) -> bool:
    t = title.lower()
    bad = [
        "company",
        "services",
        "page",
        "help",
        "register",
        "verification",
        "about reklama5",
        "terms of use",
        "cookie policy",
        "i agree",
        "new announcement",
        "all categories",
        "premium member",
        "copyright",
        "powered by",
        "next page",
    ]
    return any(x in t for x in bad)


def extract_ads_from_page(html: str):
    soup = BeautifulSoup(html, "html.parser")
    ads = []
    seen = set()

    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        title = normalize_text(a.get_text(" ", strip=True))

        if not href or not title or len(title) < 4:
            continue

        if is_bad_title(title):
            continue

        href_lower = href.lower()
        if any(x in href_lower for x in [
            "/search",
            "/login",
            "/register",
            "/contact",
            "/help",
            "/faq",
            "/marketing",
            "/verification",
            "facebook.com",
            "instagram.com",
            "#",
            "javascript:"
        ]):
            continue

        full_link = urljoin(BASE_URL, href)

        looks_like_ad = (
            "addetails" in href_lower
            or re.search(r"/\d{5,}", href_lower) is not None
            or re.search(r"ad=\d{5,}", href_lower) is not None
        )

        if not looks_like_ad:
            continue

        key = (title.lower(), full_link.lower())
        if key in seen:
            continue
        seen.add(key)

        ads.append({
            "title": title,
            "link": full_link,
            "source": "reklama5"
        })

    return ads


def scrape(max_pages: int = 200, delay: float = 1.0):
    all_ads = []
    global_seen = set()
    session = requests.Session()
    session.headers.update(HEADERS)

    for page in range(1, max_pages + 1):
        if page == 1:
            url = START_URL
        else:
            url = f"{START_URL}?page={page}"

        print(f"[Reklama5] Scraping page {page}: {url}")

        try:
            response = session.get(url, timeout=25)
            response.raise_for_status()
        except Exception as e:
            print(f"[Reklama5] Request error on page {page}: {e}")
            break

        page_ads = extract_ads_from_page(response.text)

        new_ads = []
        for ad in page_ads:
            key = (ad["title"].lower(), ad["link"].lower())
            if key not in global_seen:
                global_seen.add(key)
                new_ads.append(ad)

        print(f"[Reklama5] Found {len(page_ads)} ads, new: {len(new_ads)}")

        if not new_ads:
            print(f"[Reklama5] No new ads on page {page}. Stopping.")
            break

        all_ads.extend(new_ads)
        time.sleep(delay)

    return all_ads
