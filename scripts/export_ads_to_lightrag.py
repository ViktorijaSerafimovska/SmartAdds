import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
ADS_FILE = BASE_DIR / "data" / "ads.json"
OUT_DIR = BASE_DIR / "lightrag_inputs"

OUT_DIR.mkdir(parents=True, exist_ok=True)


def slugify(value: str) -> str:
    value = (value or "").strip().lower()
    value = re.sub(r"[^a-zA-Z0-9а-шА-Ш]+", "-", value)
    value = value.strip("-")
    return value[:80] or "ad"


def main():
    if not ADS_FILE.exists():
        print(f"ads.json not found: {ADS_FILE}")
        return

    with open(ADS_FILE, "r", encoding="utf-8") as f:
        ads = json.load(f)

    for old_file in OUT_DIR.glob("*.txt"):
        old_file.unlink()

    count = 0

    for i, ad in enumerate(ads, start=1):
        title = str(ad.get("title") or "").strip()
        link = str(ad.get("link") or "").strip()
        source = str(ad.get("source") or "").strip()
        price = str(ad.get("price") or "").strip()
        description = str(ad.get("description") or "").strip()

        if not title or not link:
            continue

        content = f"""TITLE: {title}
PRICE: {price}
SOURCE: {source}
LINK: {link}
DESCRIPTION: {description}
TYPE: marketplace ad
"""

        filename = f"{i:06d}_{slugify(title)}.txt"
        with open(OUT_DIR / filename, "w", encoding="utf-8") as out:
            out.write(content)

        count += 1

    print(f"Exported {count} ads to {OUT_DIR}")


if __name__ == "__main__":
    main()