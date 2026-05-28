import os
import re
from typing import List, Dict, Any

import requests
from dotenv import load_dotenv

import json

load_dotenv()

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "127.0.0.1")
OLLAMA_URL = f"http://{OLLAMA_HOST}:11434/api/generate"
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:latest")


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
        "im searching for", "searching for", "i want",
        # price / currency signals
        "evra", "евра", "eur", "€", "mkd", "denari", "денари", "cena", "цена",
        "poevtina", "поевтина", "poeftina", "евтин", "evtin",
        # product condition
        "polovna", "половна", "nova", "нова", "dobra sostojba", "rabotna",
        # common product categories in Macedonian
        "kola", "кола", "auto", "автомобил", "automobil", "vozilo", "возило",
        "stan", "стан", "apartman", "куќа", "kuka",
        "laptop", "telefon", "телефон", "mobilen", "мобилен", "kompjuter",
        "televizor", "фрижидер", "masina", "машина",
    ]

    if any(word in text for word in greeting_words):
        return "chat"

    if any(word in text for word in followup_words):
        return "followup" if last_ads else "chat"

    if any(word in text for word in search_words):
        return "search"

    # If the message contains a number it is almost certainly a product query
    # (price, year, size, quantity).
    if re.search(r"\d+", text):
        return "search"

    # Short noun-phrase queries with no explicit keyword still go to search.
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

        line = f"{i}. {title} | {source}"
        if price:
            line += f" | {price}"
        if description:
            line += f" | {description[:100]}"
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


def _call_ollama(prompt: str, timeout: int = 120) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt.strip(),
        "stream": False,
        "keep_alive": "10m",
        "options": {
            "temperature": 0.1,
            "top_p": 0.9,
            "num_predict": 180,
            "num_ctx": 2048,
        },
    }
    response = requests.post(OLLAMA_URL, json=payload, timeout=timeout)
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

        preview = build_ads_context(ads, limit=15)
        if lang == "mk":
            prompt = f"""Ти си SmartAdds AI асистент за огласи.
Барање: {detected_query or user_message}
Прикажани огласи ({len(ads)} вкупно):
{preview}
Напиши 1-2 реченици: опиши што е најдено, спомни ценовен опсег само ако цените се видливи погоре. Не измислувај бројки. Само македонски."""
        else:
            prompt = f"""You are SmartAdds AI.
Search: {detected_query or user_message}
Ads shown ({len(ads)} total):
{preview}
Write 1-2 sentences: describe what was found, mention price range only if prices are visible above. Do not invent numbers. English only."""

        try:
            return _call_ollama(prompt, timeout=15)
        except Exception:
            q = detected_query or user_message
            return (
                f"Најдов {len(ads)} огласи за '{q}'."
                if lang == "mk"
                else f"Found {len(ads)} ads for '{q}'."
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
        return _call_ollama(prompt, timeout=180)
    except Exception:
        return (
            "AI анализата моментално не е достапна. Огласите се прикажани."
            if lang == "mk"
            else "AI analysis is currently unavailable. The ads are shown above."
        )
