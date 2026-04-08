import json
import re
import unicodedata
from pathlib import Path
from typing import List, Dict, Any, Optional

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


def extract_search_terms(query: str) -> List[str]:
    query = clean_search_prefix(query)

    stop_words = {
        "najdi", "mi", "te", "go", "gi", "baram", "барам", "sakam", "сакам",
        "daj", "pokazi", "покажи", "oglasi", "oglas", "za", "so", "od", "vo",
        "na", "me", "please", "prati", "prodazba", "prodazhba", "ad", "ads",
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


def _matches_all_terms(item_text: str, terms: List[str]) -> bool:
    for term in terms:
        if not _contains_word(item_text, term):
            return False
    return True


def _score_item(item: Dict[str, Any], terms: List[str]) -> float:
    text = item["searchable_text"]
    title = normalize_text(item["title"])
    score = 0.0

    for term in terms:
        if _contains_word(title, term):
            score += 100
        elif _contains_word(text, term):
            score += 40

    phrase = " ".join(terms).strip()
    if phrase and phrase in title:
        score += 160
    elif phrase and phrase in text:
        score += 70

    score -= len(item["tokens"]) * 0.03
    return score


def search_ads(query: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    query = clean_search_prefix(query)
    terms = extract_search_terms(query)

    print(f"[DEBUG] search query raw='{query}' terms={terms} total_ads={len(metadata)}")

    if not terms:
        return []

    results = []

    for item in metadata:
        text = item["searchable_text"]
        if _matches_all_terms(text, terms):
            score = _score_item(item, terms)
            results.append((score, item))

    results.sort(key=lambda x: (-x[0], x[1]["title"].lower()))

    items = [item for score, item in results]
    if limit is None or limit <= 0:
        return items
    return items[:limit]


def get_search_context(
    user_message: str,
    last_ads: Optional[List[Dict[str, Any]]] = None,
    last_query: str = "",
    intent: str = "chat",
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    last_ads = last_ads or []
    clean_message = clean_search_prefix(user_message)

    if intent == "chat":
        return {
            "ads": [],
            "used_last_ads": False,
            "detected_query": "",
            "intent": "chat",
        }

    if intent == "followup":
        return {
            "ads": slice_ads_for_request(user_message, last_ads),
            "used_last_ads": True,
            "detected_query": last_query,
            "intent": "followup",
        }

    current_results = search_ads(clean_message, limit=limit)

    return {
        "ads": current_results,
        "used_last_ads": False,
        "detected_query": clean_message,
        "intent": "search",
    }

#
# import json
# import re
# import unicodedata
# from difflib import SequenceMatcher
# from pathlib import Path
# from typing import List, Dict, Any, Optional
#
# BASE_DIR = Path(__file__).resolve().parent.parent
# DATA_FILE = BASE_DIR / "data" / "ads.json"
#
# metadata: List[Dict[str, Any]] = []
#
#
# def normalize_text(text: str) -> str:
#     text = text or ""
#     text = unicodedata.normalize("NFKC", text)
#     text = text.lower().strip()
#     text = re.sub(r"\s+", " ", text)
#     return text
#
#
# def tokenize(text: str) -> List[str]:
#     text = normalize_text(text)
#     return re.findall(r"[a-zA-Zа-шА-Ш0-9]+", text)
#
#
# def similarity(a: str, b: str) -> float:
#     return SequenceMatcher(None, a, b).ratio()
#
#
# def clean_search_prefix(query: str) -> str:
#     query = (query or "").strip()
#
#     prefixes = [
#         "ai:", "комбинирај:", "kombiniraj:",
#         "najdi", "најди", "baram", "барам",
#         "pobaraj", "mi treba", "ми треба", "sakam", "сакам",
#         "pokazi", "покажи", "show me", "find me", "i need",
#         "looking for", "im searching for", "searching for", "i want"
#     ]
#
#     q = query
#     lower = q.lower()
#
#     changed = True
#     while changed:
#         changed = False
#         for prefix in prefixes:
#             if lower.startswith(prefix + " "):
#                 q = q[len(prefix):].strip()
#                 lower = q.lower()
#                 changed = True
#
#     return q
#
#
# def load_data():
#     global metadata
#
#     if not DATA_FILE.exists():
#         print(f"Data file not found: {DATA_FILE}")
#         metadata = []
#         return
#
#     with open(DATA_FILE, "r", encoding="utf-8") as f:
#         data = json.load(f)
#
#     cleaned = []
#     seen = set()
#
#     for item in data:
#         title = str(item.get("title") or "").strip()
#         link = str(item.get("link") or "").strip()
#         source = str(item.get("source") or "").strip() or "unknown"
#         price = str(item.get("price") or "").strip()
#         description = str(item.get("description") or "").strip()
#
#         if not title or not link:
#             continue
#
#         key = (title.lower(), link.lower())
#         if key in seen:
#             continue
#         seen.add(key)
#
#         searchable_text = f"{title} {description} {source} {price}".strip()
#         tokens = tokenize(searchable_text)
#
#         cleaned.append({
#             "title": title,
#             "link": link,
#             "source": source,
#             "price": price,
#             "description": description,
#             "searchable_text": normalize_text(searchable_text),
#             "token_set": set(tokens),
#             "tokens": tokens,
#         })
#
#     metadata = cleaned
#     print(f"Loaded {len(metadata)} ads from {DATA_FILE}")
#
#
# def extract_search_terms(query: str) -> List[str]:
#     query = clean_search_prefix(query)
#
#     stop_words = {
#         "najdi", "mi", "te", "go", "gi", "baram", "барам", "sakam", "сакам",
#         "daj", "pokazi", "покажи", "oglasi", "oglas", "za", "so", "od", "vo",
#         "na", "me", "please", "prati", "prodazba", "prodazhba", "ad", "ads",
#         "recommend", "compare", "preporachaj", "sporedi", "objasni",
#         "najdobar", "najdobra", "najdobro", "the", "a", "an",
#         "site", "samo", "koj", "koja", "sto", "што", "which", "best", "top",
#         "prvite", "first", "all", "rank", "ranking", "podredi",
#         "rangiraj", "sortiraj", "analysis", "analiza",
#         "find", "search", "show", "need", "looking", "want",
#         "for", "im", "searching", "i",
#         "zdravo", "hello", "hi", "hey", "kako", "si", "како"
#     }
#
#     words = tokenize(query)
#     return [w for w in words if w not in stop_words and len(w) > 1]
#
#
# def fuzzy_token_match(term: str, token_set: set[str], threshold: float = 0.90) -> bool:
#     if term in token_set:
#         return True
#
#     for token in token_set:
#         if abs(len(term) - len(token)) > 1:
#             continue
#         if similarity(term, token) >= threshold:
#             return True
#     return False
#
#
# def count_term_matches(terms: List[str], item: Dict[str, Any]) -> Dict[str, int]:
#     title_norm = normalize_text(item["title"])
#     title_tokens = set(tokenize(title_norm))
#     token_set = item["token_set"]
#     searchable_text = item["searchable_text"]
#
#     title_exact = 0
#     token_exact = 0
#     substring = 0
#     fuzzy = 0
#
#     for term in terms:
#         if term in title_tokens:
#             title_exact += 1
#         elif term in token_set:
#             token_exact += 1
#         elif re.search(rf"\b{re.escape(term)}\b", searchable_text):
#             substring += 1
#         elif fuzzy_token_match(term, token_set):
#             fuzzy += 1
#
#     return {
#         "title_exact": title_exact,
#         "token_exact": token_exact,
#         "substring": substring,
#         "fuzzy": fuzzy,
#     }
#
#
# def is_relevant_match(terms: List[str], item: Dict[str, Any]) -> bool:
#     matches = count_term_matches(terms, item)
#
#     strong_matches = matches["title_exact"] + matches["token_exact"]
#     weak_matches = matches["substring"] + matches["fuzzy"]
#     total_matches = strong_matches + weak_matches
#
#     if not terms:
#         return False
#
#     if len(terms) == 1:
#         return total_matches >= 1
#
#     if len(terms) == 2:
#         # za 2 termini, bara oba ili eden mnogu silen vo title + eden drug
#         return total_matches >= 2 and strong_matches >= 1
#
#     # za 3+ termini, bara barem 60% od terminite i minimum 2 silni poklapanja
#     needed = max(2, int(len(terms) * 0.6 + 0.5))
#     return total_matches >= needed and strong_matches >= 2
#
#
# def score_item(query_normalized: str, terms: List[str], item: Dict[str, Any]) -> float:
#     matches = count_term_matches(terms, item)
#     title_norm = normalize_text(item["title"])
#     searchable_text = item["searchable_text"]
#     title_tokens = set(tokenize(item["title"]))
#
#     score = 0.0
#
#     score += matches["title_exact"] * 100
#     score += matches["token_exact"] * 45
#     score += matches["substring"] * 20
#     score += matches["fuzzy"] * 8
#
#     if query_normalized == title_norm:
#         score += 300
#
#     if title_norm.startswith(query_normalized):
#         score += 150
#
#     if query_normalized in title_norm:
#         score += 80
#
#     if query_normalized in searchable_text:
#         score += 35
#
#     title_term_hits = sum(1 for term in terms if term in title_tokens)
#     score += title_term_hits * 35
#
#     matched_total = (
#         matches["title_exact"]
#         + matches["token_exact"]
#         + matches["substring"]
#         + matches["fuzzy"]
#     )
#     if matched_total >= len(terms):
#         score += 70
#
#     score -= len(item["tokens"]) * 0.10
#     return score
#
#
# def search_ads(query: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
#     query = clean_search_prefix(query)
#     terms = extract_search_terms(query)
#     query_normalized = normalize_text(query)
#
#     if not terms:
#         return []
#
#     results = []
#
#     for item in metadata:
#         if not is_relevant_match(terms, item):
#             continue
#
#         score = score_item(query_normalized, terms, item)
#         results.append((score, item))
#
#     results.sort(key=lambda x: (-x[0], x[1]["title"].lower()))
#
#     items = [item for score, item in results]
#     if limit is None or limit <= 0:
#         return items
#     return items[:limit]
#
#
# def parse_requested_count(text: str, default: Optional[int] = None) -> Optional[int]:
#     text = normalize_text(text)
#
#     m = re.search(r"\b(\d+)\b", text)
#     if m:
#         try:
#             return int(m.group(1))
#         except Exception:
#             return default
#
#     mapping = {
#         "eden": 1, "edna": 1, "one": 1,
#         "dva": 2, "dve": 2, "two": 2,
#         "tri": 3, "three": 3,
#         "cetiri": 4, "четири": 4, "four": 4,
#         "pet": 5, "пет": 5, "five": 5,
#         "shest": 6, "шест": 6, "six": 6,
#         "sedum": 7, "седум": 7, "seven": 7,
#         "osum": 8, "осум": 8, "eight": 8,
#         "devet": 9, "девет": 9, "nine": 9,
#         "deset": 10, "десет": 10, "ten": 10,
#         "site": 999999, "all": 999999,
#     }
#
#     for k, v in mapping.items():
#         if k in text:
#             return v
#
#     return default
#
#
# def slice_ads_for_request(user_message: str, ads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
#     if not ads:
#         return []
#
#     text = normalize_text(user_message)
#
#     if "site" in text or "all" in text:
#         return ads
#
#     count = parse_requested_count(text)
#     if count:
#         return ads[:count]
#
#     return ads
#
#
# def get_search_context(
#     user_message: str,
#     last_ads: Optional[List[Dict[str, Any]]] = None,
#     last_query: str = "",
#     intent: str = "chat",
#     limit: Optional[int] = None,
# ) -> Dict[str, Any]:
#     last_ads = last_ads or []
#     clean_message = clean_search_prefix(user_message)
#
#     if intent == "chat":
#         return {
#             "ads": [],
#             "used_last_ads": False,
#             "detected_query": "",
#             "intent": "chat",
#         }
#
#     if intent == "followup":
#         return {
#             "ads": slice_ads_for_request(user_message, last_ads),
#             "used_last_ads": True,
#             "detected_query": last_query,
#             "intent": "followup",
#         }
#
#     current_results = search_ads(clean_message, limit=limit)
#
#     return {
#         "ads": current_results,
#         "used_last_ads": False,
#         "detected_query": clean_message,
#         "intent": "search",
#     }
#
#
#
#
#
#
# #test 2
# # import json
# # import re
# # import unicodedata
# # from pathlib import Path
# # from typing import List, Dict, Any
# #
# # BASE_DIR = Path(__file__).resolve().parent.parent
# # DATA_FILE = BASE_DIR / "data" / "ads.json"
# #
# # metadata: List[Dict[str, Any]] = []
# #
# #
# # def normalize_text(text: str) -> str:
# #     text = text or ""
# #     text = unicodedata.normalize("NFKC", text)
# #     text = text.lower().strip()
# #     text = re.sub(r"\s+", " ", text)
# #     return text
# #
# #
# # def tokenize(text: str) -> List[str]:
# #     text = normalize_text(text)
# #     return re.findall(r"[a-zA-Zа-шА-Ш0-9]+", text)
# #
# #
# # def load_data():
# #     global metadata
# #
# #     if not DATA_FILE.exists():
# #         print(f"Data file not found: {DATA_FILE}")
# #         metadata = []
# #         return
# #
# #     with open(DATA_FILE, "r", encoding="utf-8") as f:
# #         data = json.load(f)
# #
# #     cleaned = []
# #     seen = set()
# #
# #     for item in data:
# #         title = (item.get("title") or "").strip()
# #         link = (item.get("link") or "").strip()
# #         source = (item.get("source") or "").strip() or "unknown"
# #
# #         if not title or not link:
# #             continue
# #
# #         key = (title.lower(), link.lower())
# #         if key in seen:
# #             continue
# #         seen.add(key)
# #
# #         title_normalized = normalize_text(title)
# #         title_tokens = tokenize(title)
# #
# #         cleaned.append({
# #             "title": title,
# #             "link": link,
# #             "source": source,
# #             "title_normalized": title_normalized,
# #             "tokens": title_tokens,
# #             "token_set": set(title_tokens),
# #         })
# #
# #     metadata = cleaned
# #     print(f"Loaded {len(metadata)} ads from {DATA_FILE}")
# #
# #
# # def is_greeting(text: str) -> bool:
# #     text = normalize_text(text)
# #     greetings = {
# #         "zdravo", "zdr", "hello", "hi", "hey", "cao", "чао", "здраво",
# #         "zdravo kako si", "kako si", "kako si?"
# #     }
# #     return text in greetings
# #
# #
# # def extract_search_terms(query: str) -> List[str]:
# #     stop_words = {
# #         "najdi", "mi", "te", "go", "gi", "baram", "sakam", "daj",
# #         "pokazi", "oglasi", "oglas", "za", "so", "od", "vo", "na",
# #         "me", "please", "prati"
# #     }
# #     words = tokenize(query)
# #     return [w for w in words if w not in stop_words]
# #
# #
# # def contains_exact_sequence(title_tokens: List[str], terms: List[str]) -> bool:
# #     if not terms or len(terms) > len(title_tokens):
# #         return False
# #
# #     n = len(terms)
# #     for i in range(len(title_tokens) - n + 1):
# #         if title_tokens[i:i + n] == terms:
# #             return True
# #     return False
# #
# #
# # def search_ads(query: str) -> List[Dict[str, Any]]:
# #     terms = extract_search_terms(query)
# #     query_normalized = normalize_text(query)
# #
# #     if not terms:
# #         return []
# #
# #     results = []
# #
# #     for item in metadata:
# #         token_set = item["token_set"]
# #         title_tokens = item["tokens"]
# #         title_normalized = item["title_normalized"]
# #
# #         # сите зборови мора да постојат како точни token-и
# #         if not all(term in token_set for term in terms):
# #             continue
# #
# #         score = 0
# #
# #         if title_normalized == query_normalized:
# #             score += 10000
# #
# #         if contains_exact_sequence(title_tokens, terms):
# #             score += 5000
# #
# #         if query_normalized in title_normalized:
# #             score += 1000
# #
# #         if title_tokens[:len(terms)] == terms:
# #             score += 500
# #
# #         score -= len(title_tokens) * 3
# #         score -= len(title_normalized) * 0.05
# #
# #         results.append((score, item))
# #
# #     results.sort(key=lambda x: (-x[0], x[1]["title"].lower()))
# #     return [item for score, item in results]
# #
# #
# # def format_results(results: List[Dict[str, Any]], query: str) -> str:
# #     if not results:
# #         return f"Не најдов огласи што точно одговараат на: {query}"
# #
# #     answer = [f"Најдов {len(results)} огласи што точно одговараат на: {query}", ""]
# #
# #     for idx, item in enumerate(results, start=1):
# #         answer.append(
# #             f"{idx}. [{item['title']}]({item['link']}) - izvor: {item['source']}"
# #         )
# #
# #     return "\n".join(answer)
# #
# #
# # def get_top_ads_context(query: str, limit: int = 10) -> List[Dict[str, Any]]:
# #     return search_ads(query)[:limit]
# #
# #
# # def ask_question(query: str) -> str:
# #     query = (query or "").strip()
# #
# #     if is_greeting(query):
# #         return "Здраво! Прати ми што бараш и ќе пребарам низ огласите."
# #
# #     if not metadata:
# #         return "Податоците не се вчитани. Прво пушти scraper, па рестартирај backend."
# #
# #     results = search_ads(query)
# #     return format_results(results, query)
# #
#
# #staveno e i ova na git
# # import json
# # import re
# # import unicodedata
# # from pathlib import Path
# # from typing import List, Dict, Any
# #
# # BASE_DIR = Path(__file__).resolve().parent.parent
# # DATA_FILE = BASE_DIR / "data" / "ads.json"
# #
# # metadata: List[Dict[str, Any]] = []
# #
# #
# # def normalize_text(text: str) -> str:
# #     text = text or ""
# #     text = unicodedata.normalize("NFKC", text)
# #     text = text.lower().strip()
# #     text = re.sub(r"\s+", " ", text)
# #     return text
# #
# #
# # def tokenize(text: str) -> List[str]:
# #     text = normalize_text(text)
# #     return re.findall(r"[a-zA-Zа-шА-Ш0-9]+", text)
# #
# #
# # def load_data():
# #     global metadata
# #
# #     if not DATA_FILE.exists():
# #         print(f"Data file not found: {DATA_FILE}")
# #         metadata = []
# #         return
# #
# #     with open(DATA_FILE, "r", encoding="utf-8") as f:
# #         data = json.load(f)
# #
# #     cleaned = []
# #     seen = set()
# #
# #     for item in data:
# #         title = (item.get("title") or "").strip()
# #         link = (item.get("link") or "").strip()
# #         source = (item.get("source") or "").strip()
# #
# #         if not title or not link:
# #             continue
# #
# #         key = (title.lower(), link.lower())
# #         if key in seen:
# #             continue
# #         seen.add(key)
# #
# #         title_normalized = normalize_text(title)
# #         title_tokens = tokenize(title)
# #
# #         cleaned.append({
# #             "title": title,
# #             "link": link,
# #             "source": source or "unknown",
# #             "title_normalized": title_normalized,
# #             "tokens": title_tokens,
# #             "token_set": set(title_tokens),
# #         })
# #
# #     metadata = cleaned
# #     print(f"Loaded {len(metadata)} ads from {DATA_FILE}")
# #
# #
# # def is_greeting(text: str) -> bool:
# #     text = normalize_text(text)
# #     greetings = {
# #         "zdravo", "zdr", "hello", "hi", "hey", "cao", "чао", "здраво",
# #         "zdravo kako si", "kako si", "kako si?"
# #     }
# #     return text in greetings
# #
# #
# # def extract_search_terms(query: str) -> List[str]:
# #     stop_words = {
# #         "najdi", "mi", "te", "go", "gi", "baram", "sakam", "daj",
# #         "pokazi", "oglasi", "oglas", "za", "so", "od", "vo", "na",
# #         "me", "please", "prati"
# #     }
# #
# #     words = tokenize(query)
# #     return [w for w in words if w not in stop_words]
# #
# #
# # def contains_exact_sequence(title_tokens: List[str], terms: List[str]) -> bool:
# #     if not terms or len(terms) > len(title_tokens):
# #         return False
# #
# #     n = len(terms)
# #     for i in range(len(title_tokens) - n + 1):
# #         if title_tokens[i:i + n] == terms:
# #             return True
# #     return False
# #
# #
# # def search_ads(query: str) -> List[Dict[str, Any]]:
# #     terms = extract_search_terms(query)
# #     query_normalized = normalize_text(query)
# #
# #     if not terms:
# #         return []
# #
# #     results = []
# #
# #     for item in metadata:
# #         token_set = item["token_set"]
# #         title_tokens = item["tokens"]
# #         title_normalized = item["title_normalized"]
# #
# #         # SITE termini mora da postojat kako TOCHNI tokeni
# #         # ova znaci 11 nema da match-ne 110 / 112 / 2011 / 118
# #         if not all(term in token_set for term in terms):
# #             continue
# #
# #         score = 0
# #
# #         # exact title
# #         if title_normalized == query_normalized:
# #             score += 10000
# #
# #         # exact sequence vo naslov
# #         if contains_exact_sequence(title_tokens, terms):
# #             score += 5000
# #
# #         # cela fraza vo naslov
# #         if query_normalized in title_normalized:
# #             score += 1000
# #
# #         # naslov pocnuva so query
# #         if title_tokens[:len(terms)] == terms:
# #             score += 500
# #
# #         # pokratki naslovi nagore
# #         score -= len(title_tokens) * 3
# #         score -= len(title_normalized) * 0.05
# #
# #         results.append((score, item))
# #
# #     results.sort(key=lambda x: (-x[0], x[1]["title"].lower()))
# #     return [item for score, item in results]
# #
# #
# # def format_results(results: List[Dict[str, Any]], query: str) -> str:
# #     if not results:
# #         return f"Не најдов огласи што точно одговараат на: {query}"
# #
# #     answer = [f"Најдов {len(results)} огласи што точно одговараат на: {query}", ""]
# #
# #     for idx, item in enumerate(results, start=1):
# #         answer.append(
# #             f"{idx}. [{item['title']}]({item['link']}) - izvor: {item['source']}"
# #         )
# #
# #     return "\n".join(answer)
# #
# #
# # def ask_question(query: str) -> str:
# #     query = (query or "").strip()
# #
# #     if is_greeting(query):
# #         return "Здраво! Прати ми што бараш и ќе пребарам низ огласите."
# #
# #     if not metadata:
# #         return "Податоците не се вчитани. Прво пушти scraper, па рестартирај backend."
# #
# #     results = search_ads(query)
# #     return format_results(results, query)
