import json
import re
import unicodedata
from pathlib import Path
from typing import List, Dict, Any

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = BASE_DIR / "data" / "ads.json"

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


def load_data():
    global metadata

    if not DATA_FILE.exists():
        print(f"Data file not found: {DATA_FILE}")
        metadata = []
        return

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    cleaned = []
    seen = set()

    for item in data:
        title = (item.get("title") or "").strip()
        link = (item.get("link") or "").strip()
        source = (item.get("source") or "").strip()

        if not title or not link:
            continue

        key = (title.lower(), link.lower())
        if key in seen:
            continue
        seen.add(key)

        title_normalized = normalize_text(title)
        title_tokens = tokenize(title)

        cleaned.append({
            "title": title,
            "link": link,
            "source": source or "unknown",
            "title_normalized": title_normalized,
            "tokens": title_tokens,
            "token_set": set(title_tokens),
        })

    metadata = cleaned
    print(f"Loaded {len(metadata)} ads from {DATA_FILE}")


def is_greeting(text: str) -> bool:
    text = normalize_text(text)
    greetings = {
        "zdravo", "zdr", "hello", "hi", "hey", "cao", "чао", "здраво",
        "zdravo kako si", "kako si", "kako si?"
    }
    return text in greetings


def extract_search_terms(query: str) -> List[str]:
    stop_words = {
        "najdi", "mi", "te", "go", "gi", "baram", "sakam", "daj",
        "pokazi", "oglasi", "oglas", "za", "so", "od", "vo", "na",
        "me", "please", "prati"
    }

    words = tokenize(query)
    return [w for w in words if w not in stop_words]


def contains_exact_sequence(title_tokens: List[str], terms: List[str]) -> bool:
    if not terms or len(terms) > len(title_tokens):
        return False

    n = len(terms)
    for i in range(len(title_tokens) - n + 1):
        if title_tokens[i:i + n] == terms:
            return True
    return False


def search_ads(query: str) -> List[Dict[str, Any]]:
    terms = extract_search_terms(query)
    query_normalized = normalize_text(query)

    if not terms:
        return []

    results = []

    for item in metadata:
        token_set = item["token_set"]
        title_tokens = item["tokens"]
        title_normalized = item["title_normalized"]

        # SITE termini mora da postojat kako TOCHNI tokeni
        # ova znaci 11 nema da match-ne 110 / 112 / 2011 / 118
        if not all(term in token_set for term in terms):
            continue

        score = 0

        # exact title
        if title_normalized == query_normalized:
            score += 10000

        # exact sequence vo naslov
        if contains_exact_sequence(title_tokens, terms):
            score += 5000

        # cela fraza vo naslov
        if query_normalized in title_normalized:
            score += 1000

        # naslov pocnuva so query
        if title_tokens[:len(terms)] == terms:
            score += 500

        # pokratki naslovi nagore
        score -= len(title_tokens) * 3
        score -= len(title_normalized) * 0.05

        results.append((score, item))

    results.sort(key=lambda x: (-x[0], x[1]["title"].lower()))
    return [item for score, item in results]


def format_results(results: List[Dict[str, Any]], query: str) -> str:
    if not results:
        return f"Не најдов огласи што точно одговараат на: {query}"

    answer = [f"Најдов {len(results)} огласи што точно одговараат на: {query}", ""]

    for idx, item in enumerate(results, start=1):
        answer.append(
            f"{idx}. [{item['title']}]({item['link']}) - izvor: {item['source']}"
        )

    return "\n".join(answer)


def ask_question(query: str) -> str:
    query = (query or "").strip()

    if is_greeting(query):
        return "Здраво! Прати ми што бараш и ќе пребарам низ огласите."

    if not metadata:
        return "Податоците не се вчитани. Прво пушти scraper, па рестартирај backend."

    results = search_ads(query)
    return format_results(results, query)
