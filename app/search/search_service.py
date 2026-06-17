import re
import unicodedata
from sqlalchemy import or_

from app.database.db import SessionLocal
from app.database.models import Ad
from app.search.semantic_engine import semantic_search, is_ready
from app.chat.search_engine import (
    extract_price_limit,
    clean_search_prefix,
)

SEMANTIC_THRESHOLD = 0.70
STRONG_SEMANTIC_THRESHOLD = 0.78

NEGATIVE_WORDS = [
    "otkup", "откуп", "servis", "сервис", "rent", "iznajmuvanje",
    "hemisko", "procena", "isplata", "delovi", "guma", "bandazi",
    "rezervna", "prikolka"
]

STOP_WORDS = {
    "baram", "барам", "sakam", "сакам", "najdi", "најди",
    "mi", "treba", "ми", "треба", "vo", "во", "za", "за",
    "do", "до", "so", "со", "oglasi", "oglas"
}


def normalize_text(text: str) -> str:
    text = text or ""
    text = unicodedata.normalize("NFKC", text)
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def tokenize(text: str):
    return re.findall(r"[a-zA-Zа-шА-Ш0-9]+", normalize_text(text))


def query_terms(query: str):
    return [t for t in tokenize(query) if t not in STOP_WORDS and len(t) > 1]


def contains_whole_word(text: str, term: str) -> bool:
    return re.search(rf"(^|\W){re.escape(term)}($|\W)", text, re.IGNORECASE) is not None


def ad_to_dict(ad: Ad):
    return {
        "title": ad.title,
        "description": ad.description,
        "price": ad.price,
        "link": ad.link,
        "source": ad.source,
    }


def ad_text(ad: dict) -> str:
    return normalize_text(" ".join([
        str(ad.get("title") or ""),
        str(ad.get("description") or ""),
        str(ad.get("price") or ""),
        str(ad.get("source") or ""),
    ]))

def numbers_in_text(text: str):
    return re.findall(r"\d+", (text or "").lower())


def passes_strict_number_guard(query: str, ad: dict) -> bool:
    query_numbers = numbers_in_text(query)

    if not query_numbers:
        return True

    text = ad_text(ad)
    ad_numbers = numbers_in_text(text)

    for number in query_numbers:
        if number not in ad_numbers:
            return False

    return True

def keyword_evidence_score(query: str, ad: dict) -> int:
    text = ad_text(ad)
    title = normalize_text(ad.get("title", ""))
    terms = query_terms(query)

    score = 0

    for term in terms:
        if contains_whole_word(title, term):
            score += 20
        elif contains_whole_word(text, term):
            score += 8

    for bad in NEGATIVE_WORDS:
        if bad in text:
            score -= 15

    return score


def passes_price(query: str, ad: dict) -> bool:
    max_price, is_monthly, query_currency = extract_price_limit(query)

    if max_price is None:
        return True

    price = normalize_text(ad.get("price", ""))

    if not price:
        return True

    nums = re.findall(r"\d[\d\s]*\d|\d+", price)
    if not nums:
        return True

    try:
        amount = int(re.sub(r"\s+", "", nums[0]))
    except Exception:
        return True

    is_mkd = any(x in price for x in ["mkd", "мкд", "ден", "den"])
    is_eur = any(x in price for x in ["eur", "евр", "€", "evra"])

    compare = float(amount)

    if query_currency == "eur" and is_mkd:
        compare = amount / 61.5
    elif query_currency == "mkd" and is_eur:
        compare = amount * 61.5

    return compare <= max_price

LOCATION_ALIASES = {
    "skopje": ["skopje", "скопје"],
    "скопје": ["skopje", "скопје"],

    "ohrid": ["ohrid", "охрид"],
    "охрид": ["ohrid", "охрид"],

    "bitola": ["bitola", "битола"],
    "битола": ["bitola", "битола"],

    "tetovo": ["tetovo", "тetovo", "тетово"],
    "тетово": ["tetovo", "тетово"],

    "gostivar": ["gostivar", "гостивар"],
    "гостивар": ["gostivar", "гостивар"],

    "kumanovo": ["kumanovo", "куманово"],
    "куманово": ["kumanovo", "куманово"],

    "prilep": ["prilep", "прилеп"],
    "прилеп": ["prilep", "прилеп"],

    "struga": ["struga", "струга"],
    "струга": ["struga", "струга"],

    "centar": ["centar", "центар", "bunjakovec", "буњаковец", "debar maalo", "дебар маало"],
    "центар": ["centar", "центар", "bunjakovec", "буњаковец", "debar maalo", "дебар маало"],

    "aerodrom": ["aerodrom", "аеродром"],
    "аеродром": ["aerodrom", "аеродром"],

    "karpos": ["karpos", "karpoš", "карпош"],
    "карпош": ["karpos", "karpoš", "карпош"],

    "kisela voda": ["kisela voda", "кисела вода"],
    "кисела вода": ["kisela voda", "кисела вода"],
}


def extract_location_terms(query: str):
    q = normalize_text(query)
    found = []

    for key, aliases in LOCATION_ALIASES.items():
        if any(alias in q for alias in aliases):
            found.append(key)

    return found


def passes_location(query: str, ad: dict) -> bool:
    locations = extract_location_terms(query)

    if not locations:
        return True

    text = ad_text(ad)

    for location in locations:
        aliases = LOCATION_ALIASES.get(location, [location])

        if any(alias in text for alias in aliases):
            return True

    return False


def keyword_search_db(query: str, limit: int = 20):
    db = SessionLocal()

    try:
        terms = query_terms(query)

        if not terms:
            return []

        filters = []
        for term in terms:
            filters.append(Ad.title.ilike(f"%{term}%"))
            filters.append(Ad.description.ilike(f"%{term}%"))

        rows = db.query(Ad).filter(or_(*filters)).limit(limit * 10).all()

        scored = []

        for ad in rows:
            item = ad_to_dict(ad)
            score = keyword_evidence_score(query, item)

            if score <= 0:
                continue

            if not passes_price(query, item):
                continue

            if not passes_strict_number_guard(query, item):
                continue

            if not passes_location(query, item):
                continue

            scored.append((score, item))

        scored.sort(key=lambda x: -x[0])

        return [item for _, item in scored[:limit]]

    finally:
        db.close()


def search_ads(query: str, limit: int = 20):
    clean_query = clean_search_prefix(query)

    semantic_items = []

    if is_ready():
        try:
            semantic_items = semantic_search(
                query=clean_query,
                limit=limit * 5,
                threshold=SEMANTIC_THRESHOLD
            )
        except Exception as e:
            print(f"[Semantic Error] {e}")
            semantic_items = []

    scored = []

    for item in semantic_items:
        semantic_score = float(item.get("_semantic_score", 0))
        evidence_score = keyword_evidence_score(clean_query, item)

        if semantic_score < STRONG_SEMANTIC_THRESHOLD and evidence_score <= 0:
            continue

        if not passes_price(clean_query, item):
            continue

        if not passes_strict_number_guard(clean_query, item):
            continue

        if not passes_location(clean_query, item):
            continue

        final_score = semantic_score * 100 + evidence_score
        scored.append((final_score, item))

    scored.sort(key=lambda x: -x[0])
    results = [item for _, item in scored]

    if len(results) < limit:
        keyword_results = keyword_search_db(clean_query, limit=limit)

        seen = {item.get("link") for item in results}

        for item in keyword_results:
            if item.get("link") not in seen:
                results.append(item)
                seen.add(item.get("link"))

            if len(results) >= limit:
                break

    return results[:limit]