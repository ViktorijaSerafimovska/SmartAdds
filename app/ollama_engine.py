from typing import List, Dict, Any
import requests

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
OLLAMA_MODEL = "llama3.1:latest"


def detect_language(text: str) -> str:
    text = (text or "").lower()

    mk_chars = set("абвгдѓежзѕијклљмнњопрстќуфхцчџш")
    if any(ch in mk_chars for ch in text):
        return "mk"

    mk_words = [
        "baram", "najdi", "preporachaj", "sporedi", "objasni", "sakam",
        "mi treba", "najdobar", "najeftin", "site", "prvite",
        "koj", "koja", "sto", "dali", "oglasi", "zdravo", "kako si",
        "барам", "најди", "сакам", "покажи", "здраво", "како си"
    ]
    if any(word in text for word in mk_words):
        return "mk"

    return "en"


def detect_intent(user_message: str, last_ads: List[Dict[str, Any]] = None) -> str:
    text = (user_message or "").strip().lower()
    last_ads = last_ads or []

    greeting_words = [
        "zdravo", "hello", "hi", "hey",
        "добар ден", "dobar den", "добро утро", "kako si", "како си", "how are you"
    ]

    followup_words = [
        "sporedi", "compare", "preporachaj", "recommend",
        "koj e najdobar", "which is best", "rank", "rangiraj",
        "podredi", "prvite", "first", "najeftin", "najskap",
        "objasni", "analiza", "which one", "best one",
        "kaj e podobar", "koe e podobro", "koj e najeftin",
        "koe e najdobro", "which is cheaper",
    ]

    search_words = [
        "baram", "барам", "najdi", "најди", "pokazi", "покажи",
        "find", "search", "show me", "oglasi", "oglas", "ads",
        "mi treba", "ми треба", "сакам", "i need", "looking for",
        "im searching for", "searching for", "i want"
    ]

    if any(word in text for word in greeting_words):
        return "chat"

    if any(word in text for word in followup_words):
        # If we have prior ads, treat as follow-up; otherwise chat so AI can explain
        return "followup" if last_ads else "chat"

    if any(word in text for word in search_words):
        return "search"

    # Short messages with no intent signals: treat as search only if ≤ 4 words
    # (single keywords or short noun phrases). Longer ambiguous messages go to chat.
    words = text.split()
    if 1 <= len(words) <= 4:
        return "search"

    return "chat"


def local_chat_reply(user_message: str, lang: str) -> str:
    text = (user_message or "").strip().lower()

    if lang == "mk":
        if any(x in text for x in ["zdravo", "hello", "hi", "hey", "добар ден", "dobar den"]):
            return "Здраво! Кажи ми што бараш и ќе ти најдам огласи од базата."
        if "kako si" in text or "како си" in text:
            return "Добро сум, фала! Пиши ми што бараш и ќе пребарам низ огласите."
        if any(x in text for x in ["sporedi", "compare", "najeftin", "preporachaj"]):
            return "Прво пребарај нешто, па ќе можам да споредам или препорачам."
        return "Тука сум. Кажи ми што бараш и ќе проверам во базата."
    else:
        if any(x in text for x in ["hello", "hi", "hey"]):
            return "Hello! Tell me what you are looking for and I will search the ads."
        if "how are you" in text:
            return "I'm good, thanks! Tell me what you want to search for."
        if any(x in text for x in ["compare", "recommend", "cheapest"]):
            return "Search for something first, then I can compare or recommend."
        return "I'm here. Tell me what you need."


def build_ads_context(ads: List[Dict[str, Any]], limit: int = 15) -> str:
    if not ads:
        return "NO_ADS_FOUND"

    lines = []
    for i, ad in enumerate(ads[:limit], start=1):
        title = str(ad.get("title", "")).strip()
        source = str(ad.get("source", "")).strip()
        link = str(ad.get("link", "")).strip()
        price = str(ad.get("price", "")).strip()
        description = str(ad.get("description", "")).strip()

        line = f"{i}. {title} | {source} | {link}"
        if price:
            line += f" | {price}"
        if description:
            line += f" | {description[:120]}"
        lines.append(line)

    return "\n".join(lines)


def build_history_context(history: List[Dict[str, Any]], max_items: int = 6) -> str:
    if not history:
        return ""

    parts = []
    for msg in history[-max_items:]:
        role = msg.get("role", "user").upper()
        content = (msg.get("content") or "").strip()
        if content:
            parts.append(f"{role}: {content}")

    return "\n".join(parts)


def _call_ollama(prompt: str) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt.strip(),
        "stream": False,
        "keep_alive": "10m",
        "options": {
            "temperature": 0.1,
            "top_p": 0.9,
            "num_predict": 220,
            "num_ctx": 2048,
        },
    }
    response = requests.post(OLLAMA_URL, json=payload, timeout=35)
    response.raise_for_status()
    return (response.json().get("response") or "").strip()


def ask_ollama(
    user_message: str,
    ads: List[Dict[str, Any]],
    history: List[Dict[str, Any]] = None,
    detected_query: str = "",
    used_last_ads: bool = False,
    intent: str = "chat",
) -> str:
    history = history or []
    lang = detect_language(user_message)

    if intent == "chat":
        return local_chat_reply(user_message, lang)

    if intent == "followup" and not ads:
        return (
            "Немам претходни огласи за споредба. Прво побарај нешто."
            if lang == "mk"
            else "No previous ads to compare. Search for something first."
        )

    ads_context = build_ads_context(ads, limit=15)
    history_context = build_history_context(history)

    if intent == "search":
        if not ads:
            return (
                "Не најдов огласи во базата за твоето барање."
                if lang == "mk"
                else "No ads found in the database for your query."
            )

        if lang == "mk":
            prompt = f"""Ти си SmartAdds AI асистент за огласи.

Корисникот бара: {detected_query or user_message}
Најдени се {len(ads)} огласи. Прикажани се првите {min(len(ads), 15)}:

{ads_context}

Одговори со 1-2 реченици: кажи колку огласи се најдени и дај краток преглед (цени, категории, извори ако се достапни). Одговори на македонски. Не наведувај ги сите линкови."""
        else:
            prompt = f"""You are SmartAdds AI, an ads search assistant.

User searched for: {detected_query or user_message}
Found {len(ads)} ads. Showing the first {min(len(ads), 15)}:

{ads_context}

Reply in 1-2 sentences: state how many ads were found and give a brief overview (prices, categories, sources if available). Reply in English. Do not list all links."""

        try:
            return _call_ollama(prompt)
        except Exception:
            return (
                f"Најдов {len(ads)} огласи." if lang == "mk" else f"Found {len(ads)} ads."
            )

    # followup intent
    if lang == "mk":
        prompt = f"""Ти си SmartAdds AI асистент.

Корисникот бара следна анализа врз веќе најдени огласи.

Порака: {user_message}
{f"Историја:{chr(10)}{history_context}" if history_context else ""}
Тема: {detected_query or "Нема"}

Огласи:
{ads_context}

Правила:
- одговори само врз основа на огласите
- не измислувај детали
- ако бара споредба, спореди јасно и кратко
- ако бара препорака, препорачај само врз достапни податоци
- ако бара најевтин, користи ја price вредноста само ако е достапна
- ако нема доволно податоци, кажи го тоа
- одговори на македонски"""
    else:
        prompt = f"""You are SmartAdds AI assistant.

The user wants follow-up analysis on already found ads.

Message: {user_message}
{f"History:{chr(10)}{history_context}" if history_context else ""}
Topic: {detected_query or "None"}

Ads:
{ads_context}

Rules:
- answer only from the ads provided
- do not invent details
- if asked to compare, compare clearly and briefly
- if asked for recommendation, recommend only from available data
- if asked for cheapest, use price only if available
- if there is not enough data, say so
- reply in English"""

    try:
        return _call_ollama(prompt)
    except Exception:
        return (
            "AI анализата моментално не е достапна. Огласите се прикажани."
            if lang == "mk"
            else "AI analysis is currently unavailable. The ads are shown above."
        )
