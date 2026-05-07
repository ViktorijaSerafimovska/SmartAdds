import json
import re
import unicodedata
from pathlib import Path
from typing import List, Dict, Any, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = BASE_DIR / "data" / "ads.json"

SEARCH_LIMIT = 50  # max ads returned to the UI (client paginates)
AI_CONTEXT_LIMIT = 15  # ads passed to Ollama for analysis
KEYWORD_PREFER_MAX_TERMS = 3
MKD_TO_EUR = 61.5  # approximate exchange rate for price comparison

metadata: List[Dict[str, Any]] = []


def normalize_text(text: str) -> str:
    text = text or ""
    text = unicodedata.normalize("NFKC", text)
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def tokenize(text: str) -> List[str]:
    text = normalize_text(text)
    return re.findall(r"[a-zA-Zа-шА-Ш0-9]+", text)


def clean_search_prefix(query: str) -> str:
    query = (query or "").strip()

    prefixes = [
        "ai:", "комбинирај:", "kombiniraj:",
        "najdi", "најди", "baram", "барам",
        "pobaraj", "mi treba", "ми треба", "sakam", "сакам",
        "pokazi", "покажи", "show me", "find me", "i need",
        "looking for", "im searching for", "searching for", "i want"
    ]

    q = query
    lower = q.lower()
    changed = True
    while changed:
        changed = False
        for prefix in prefixes:
            if lower.startswith(prefix + " "):
                q = q[len(prefix):].strip()
                lower = q.lower()
                changed = True

    return q


def load_data():
    global metadata

    if not DATA_FILE.exists():
        print(f"[ERROR] Data file not found: {DATA_FILE}")
        metadata = []
        return

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    cleaned = []
    seen = set()

    for item in data:
        title = str(item.get("title") or "").strip()
        link = str(item.get("link") or "").strip()
        source = str(item.get("source") or "").strip() or "unknown"
        price = str(item.get("price") or "").strip()
        description = str(item.get("description") or "").strip()

        if not title or not link:
            continue

        key = (title.lower(), link.lower())
        if key in seen:
            continue
        seen.add(key)

        searchable_text = f"{title} {description} {source} {price}".strip()

        cleaned.append({
            "title": title,
            "link": link,
            "source": source,
            "price": price,
            "description": description,
            "searchable_text": normalize_text(searchable_text),
            "tokens": tokenize(searchable_text),
        })

    metadata = cleaned
    print(f"[OK] Loaded {len(metadata)} ads from {DATA_FILE}")

    # Build semantic index in background after keyword data is ready
    try:
        from app.semantic_engine import load_semantic_index
        load_semantic_index(metadata)
    except Exception as exc:
        print(f"[Semantic] Index build failed (semantic search disabled): {exc}")


def extract_search_terms(query: str) -> List[str]:
    query = clean_search_prefix(query)

    stop_words = {
        "najdi", "mi", "te", "go", "gi", "baram", "барам", "sakam", "сакам",
        "daj", "pokazi", "покажи", "oglasi", "oglas", "za", "so", "od", "vo",
        "na", "do", "me", "please", "prati", "prodazba", "prodazhba", "ad", "ads",
        "recommend", "compare", "preporachaj", "sporedi", "objasni",
        "najdobar", "najdobra", "najdobro", "the", "a", "an",
        "site", "samo", "koj", "koja", "sto", "што", "which", "best", "top",
        "prvite", "first", "all", "rank", "ranking", "podredi",
        "rangiraj", "sortiraj", "analysis", "analiza",
        "find", "search", "show", "need", "looking", "want",
        "for", "im", "searching", "i",
        "zdravo", "hello", "hi", "hey", "kako", "si", "како",
        "daj", "prikazi", "покажи"
    }

    words = tokenize(query)
    return [w for w in words if w not in stop_words and len(w) > 0]


def parse_requested_count(text: str, default: Optional[int] = None) -> Optional[int]:
    text = normalize_text(text)

    m = re.search(r"\b(\d+)\b", text)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            return default

    mapping = {
        "eden": 1, "edna": 1, "one": 1,
        "dva": 2, "dve": 2, "two": 2,
        "tri": 3, "three": 3,
        "cetiri": 4, "четири": 4, "four": 4,
        "pet": 5, "пет": 5, "five": 5,
        "shest": 6, "шест": 6, "six": 6,
        "sedum": 7, "седум": 7, "seven": 7,
        "osum": 8, "осум": 8, "eight": 8,
        "devet": 9, "девет": 9, "nine": 9,
        "deset": 10, "десет": 10, "ten": 10,
        "site": 999999, "all": 999999,
    }

    for k, v in mapping.items():
        if k in text:
            return v

    return default


def slice_ads_for_request(user_message: str, ads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not ads:
        return []

    text = normalize_text(user_message)

    if "site" in text or "all" in text:
        return ads

    count = parse_requested_count(text)
    if count:
        return ads[:count]

    return ads


def _contains_word(text: str, term: str) -> bool:
    return re.search(rf"\b{re.escape(term)}\b", text) is not None


def _score_item(item: Dict[str, Any], terms: List[str], query_normalized: str) -> float:
    text = item["searchable_text"]
    title = normalize_text(item["title"])
    score = 0.0

    matched_terms = 0
    for term in terms:
        if _contains_word(title, term):
            score += 100
            matched_terms += 1
        elif _contains_word(text, term):
            score += 40
            matched_terms += 1

    if not matched_terms:
        return 0.0

    # Bonus for matching all terms
    if matched_terms == len(terms):
        score += 80

    # Phrase match bonus
    phrase = " ".join(terms).strip()
    if phrase and phrase in title:
        score += 200
    elif phrase and phrase in text:
        score += 80

    # Full query in title
    if query_normalized and query_normalized in title:
        score += 120

    # Partial match ratio bonus (rewards matching more of the query)
    ratio = matched_terms / len(terms)
    score *= (0.4 + 0.6 * ratio)

    return score


def _min_required_matches(num_terms: int) -> int:
    if num_terms <= 2:
        return num_terms      # 1-term: need 1, 2-term: need both
    if num_terms <= 4:
        return num_terms - 1  # 3-term: need 2, 4-term: need 3
    return max(3, int(num_terms * 0.6))  # 5+: need 60%


def search_ads(query: str, limit: Optional[int] = SEARCH_LIMIT) -> List[Dict[str, Any]]:
    query = clean_search_prefix(query)
    terms = extract_search_terms(query)
    query_normalized = normalize_text(query)

    print(f"[DEBUG] search query='{query}' terms={terms} total_ads={len(metadata)}")

    if not terms:
        return []

    min_matches = _min_required_matches(len(terms))
    results = []

    for item in metadata:
        text = item["searchable_text"]
        title = normalize_text(item["title"])

        matched = sum(
            1 for t in terms
            if _contains_word(title, t) or _contains_word(text, t)
        )

        if matched < min_matches:
            continue

        score = _score_item(item, terms, query_normalized)
        if score > 0:
            results.append((score, item))

    results.sort(key=lambda x: (-x[0], x[1]["title"].lower()))

    items = [item for score, item in results]
    if limit is None or limit <= 0:
        return items
    return items[:limit]


def _make_semantic_query(query: str) -> str:
    """Strip price/currency/condition noise before semantic encoding.

    Phrases like "do 5000 evra" and "dobra sostojba" appear in every
    second-hand ad regardless of category, causing the model to match
    apartments and machines alongside actual products.
    """
    q = re.sub(r'\bdo\s+\d[\d\s]*', '', query, flags=re.IGNORECASE)
    q = re.sub(r'\b\d[\d\s]*\s*(?:evra|евра|eur|mkd|мкд|ден|€)\b', '', q, flags=re.IGNORECASE)
    q = re.sub(r'\b(?:evra|евра|eur|mkd|мкд|€)\b', '', q, flags=re.IGNORECASE)
    q = re.sub(r'\bvo\b', '', q, flags=re.IGNORECASE)
    q = re.sub(
        r'\b(?:dobra|dobro|dobri|sostojba|rabotna|nova|novo|novi|stara|staro)\b',
        '', q, flags=re.IGNORECASE,
    )
    q = re.sub(r'\s+', ' ', q).strip()
    return q or query


def extract_price_limit(query: str):
    """Returns (max_price, is_monthly, query_currency) from the query."""
    text = normalize_text(query)
    is_monthly = any(w in text for w in [
        "mesecno", "месечно", "kirija", "кирија", "pod kirija", "najam",
        "iznajmuvanje", "rent", "monthly", "per month",
    ])
    if any(m in text for m in ["evra", "евра", "eur", "€"]):
        query_currency = "eur"
    elif any(m in text for m in ["ден", "den", "mkd", "денари"]):
        query_currency = "mkd"
    else:
        query_currency = None

    m = re.search(r'(\d[\d\s]{0,6}\d|\d{1,7})\s*(?:evra|евра|eur|ден|den|mkd|€)', text)
    if m:
        try:
            return int(re.sub(r'\s+', '', m.group(1))), is_monthly, query_currency
        except ValueError:
            pass
    return None, is_monthly, query_currency


def _parse_ad_price(price_str: str):
    """Returns (amount, is_monthly, currency) parsed from an ad's price field."""
    if not price_str:
        return None, False, None
    text = price_str.lower()
    is_monthly = any(w in text for w in ["месечно", "mesecno", "/мес", "/mes", "monthly"])
    if any(m in text for m in ["eur", "евр", "еур", "€", "evra", "evro"]):
        currency = "eur"
    elif any(m in text for m in ["мкд", "mkd", "ден", "денар"]):
        currency = "mkd"
    else:
        currency = None
    nums = re.findall(r'\d[\d\s]*\d|\d', price_str)
    for n in nums:
        cleaned = re.sub(r'\s+', '', n)
        try:
            return int(cleaned), is_monthly, currency
        except ValueError:
            continue
    return None, False, currency


def filter_by_price(
    ads: List[Dict[str, Any]],
    max_price: Optional[int],
    is_monthly_query: bool,
    query_currency: Optional[str] = None,
) -> List[Dict[str, Any]]:
    if max_price is None:
        return ads

    filtered = []
    for ad in ads:
        amount, is_monthly_ad, ad_currency = _parse_ad_price(ad.get("price", ""))

        if amount is None:
            filtered.append(ad)
            continue

        # Purchase query: skip monthly-rental listings entirely
        if not is_monthly_query and is_monthly_ad:
            continue

        # Rental query: skip purchase-price listings (very high amounts)
        if is_monthly_query and not is_monthly_ad and amount > 5000:
            continue

        # Currency-aware comparison
        compare = float(amount)
        if query_currency == "eur" and ad_currency == "mkd":
            compare = amount / MKD_TO_EUR
        elif query_currency == "mkd" and ad_currency == "eur":
            compare = amount * MKD_TO_EUR

        if compare <= max_price:
            filtered.append(ad)

    return filtered if filtered else ads


def get_search_context(
    user_message: str,
    last_ads: Optional[List[Dict[str, Any]]] = None,
    last_query: str = "",
    intent: str = "chat",
    limit: Optional[int] = None,
    source_filter: str = "",
) -> Dict[str, Any]:
    last_ads = last_ads or []
    clean_message = clean_search_prefix(user_message)

    if intent == "chat":
        return {
            "ads": [],
            "used_last_ads": False,
            "detected_query": "",
            "intent": "chat",
            "search_mode": "none",
        }

    if intent == "followup":
        return {
            "ads": slice_ads_for_request(user_message, last_ads),
            "used_last_ads": True,
            "detected_query": last_query,
            "intent": "followup",
            "search_mode": "none",
        }

    search_limit = limit if limit is not None else SEARCH_LIMIT
    terms = extract_search_terms(clean_message)
    max_price, is_monthly, query_currency = extract_price_limit(clean_message)

    # Use semantic for long queries — it handles Macedonian Latin/Cyrillic
    # cross-script matching (keyword misses ads written in the other script).
    use_semantic = len(terms) > KEYWORD_PREFER_MAX_TERMS

    if use_semantic:
        try:
            from app.semantic_engine import semantic_search, is_ready
            if is_ready():
                semantic_q = _make_semantic_query(clean_message)
                print(f"[DEBUG] semantic_query='{semantic_q}'")
                current_results = semantic_search(semantic_q, limit=search_limit)
                search_mode = "semantic"
                # If threshold excluded too many results, supplement with keyword.
                if len(current_results) < 5:
                    kw_results = search_ads(clean_message, limit=search_limit)
                    seen = {a["link"] for a in current_results}
                    current_results += [a for a in kw_results if a["link"] not in seen]
            else:
                current_results = search_ads(clean_message, limit=search_limit)
                search_mode = "keyword"
        except Exception as exc:
            print(f"[Semantic] Search failed, falling back to keyword: {exc}")
            current_results = search_ads(clean_message, limit=search_limit)
            search_mode = "keyword"
    else:
        current_results = search_ads(clean_message, limit=search_limit)
        search_mode = "keyword"

    if max_price is not None:
        before = len(current_results)
        current_results = filter_by_price(current_results, max_price, is_monthly, query_currency)
        print(f"[DEBUG] price filter max={max_price} monthly={is_monthly} currency={query_currency} {before}->{len(current_results)} ads")

    if source_filter and source_filter.lower() != "all":
        current_results = [a for a in current_results if a.get("source", "").lower() == source_filter.lower()]

    print(f"[DEBUG] search_mode={search_mode} terms={len(terms)} results={len(current_results)}")

    return {
        "ads": current_results,
        "used_last_ads": False,
        "detected_query": clean_message,
        "intent": "search",
        "search_mode": search_mode,
        "price_filter": {"max": max_price, "monthly": is_monthly} if max_price else None,
    }
