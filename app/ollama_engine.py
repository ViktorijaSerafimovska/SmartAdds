
from typing import List, Dict, Any
import requests

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
OLLAMA_MODEL = "llama3.2:1b"
# ili:
# OLLAMA_MODEL = "qwen2.5:7b"


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
        "zdravo", "драво", "hello", "hi", "hey",
        "добар ден", "dobar den", "добро утро", "kako si", "како си", "how are you"
    ]

    search_words = [
        "baram", "барам", "najdi", "најди", "pokazi", "покажи",
        "find", "search", "show me", "oglasi", "oglas", "ads",
        "mi treba", "ми треба", "сакам", "i need", "looking for",
        "im searching for", "searching for", "i want"
    ]

    followup_words = [
        "sporedi", "compare", "preporachaj", "recommend",
        "koj e najdobar", "which is best", "rank", "rangiraj",
        "podredi", "prvite", "first", "site", "all", "najeftin",
        "najskap", "objasni", "analiza", "which one", "best one",
        "kaj e podobar", "koe e podobro"
    ]

    if any(word in text for word in greeting_words):
        return "chat"

    if any(word in text for word in followup_words) and last_ads:
        return "followup"

    if any(word in text for word in search_words):
        return "search"

    words = text.split()
    if text and len(words) <= 8:
        return "search"

    return "chat"


def local_chat_reply(user_message: str, lang: str) -> str:
    text = (user_message or "").strip().lower()

    if lang == "mk":
        if any(x in text for x in ["zdravo", "драво", "hello", "hi", "hey", "добар ден", "dobar den"]):
            return "Здраво 👋 Кажи ми што бараш и ќе ти најдам огласи од базата."
        if "kako si" in text or "како си" in text:
            return "Добро сум, фала 😊 Пиши ми што бараш и ќе пребарам низ огласите."
        return "Тука сум. Кажи ми што бараш и ќе проверам во базата."
    else:
        if any(x in text for x in ["hello", "hi", "hey"]):
            return "Hello 👋 Tell me what you are looking for and I will search the ads database."
        if "how are you" in text:
            return "I’m good, thanks. Tell me what you want to search for."
        return "I’m here. Tell me what you need."


def format_ads_response(ads: List[Dict[str, Any]], lang: str) -> str:
    if not ads:
        return "Не најдов релевантни огласи во базата." if lang == "mk" else "No relevant ads found in the database."

    if lang == "mk":
        return f"Најдов {len(ads)} релевантни огласи."
    return f"I found {len(ads)} relevant ads."


def build_ads_context(ads: List[Dict[str, Any]]) -> str:
    if not ads:
        return "NO_ADS_FOUND"

    lines = []
    for i, ad in enumerate(ads, start=1):
        title = str(ad.get("title", "")).strip()
        source = str(ad.get("source", "")).strip()
        link = str(ad.get("link", "")).strip()
        price = str(ad.get("price", "")).strip()
        description = str(ad.get("description", "")).strip()

        line = f"{i}. title={title} | source={source} | link={link}"
        if price:
            line += f" | price={price}"
        if description:
            line += f" | description={description[:250]}"
        lines.append(line)

    return "\n".join(lines)


def build_history_context(history: List[Dict[str, Any]], max_items: int = 8) -> str:
    if not history:
        return "NO_HISTORY"

    trimmed = history[-max_items:]
    parts = []

    for msg in trimmed:
        role = msg.get("role", "user").upper()
        content = (msg.get("content") or "").strip()
        if content:
            parts.append(f"{role}: {content}")

    return "\n".join(parts) if parts else "NO_HISTORY"


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

    if intent == "search":
        return format_ads_response(ads, lang)

    if intent == "followup" and not ads:
        return "Немам претходни огласи за споредба. Прво побарај нешто." if lang == "mk" else "I don't have previous ads to compare yet. Search for something first."

    ads_context = build_ads_context(ads)
    history_context = build_history_context(history)

    if lang == "mk":
        prompt = f"""
Ти си SmartAdds AI.

Корисникот бара follow-up анализа врз веќе најдени огласи.

Порака:
{user_message}

Историја:
{history_context}

Тема:
{detected_query or "Нема"}

Огласи:
{ads_context}

Правила:
- одговори само врз основа на огласите
- не измислувај детали
- ако корисникот бара споредба, спореди ги јасно
- ако бара препорака, кажи кој е подобар само од достапните податоци
- одговори на македонски
"""
    else:
        prompt = f"""
You are SmartAdds AI.

The user wants a follow-up analysis based on already found ads.

Message:
{user_message}

History:
{history_context}

Topic:
{detected_query or "None"}

Ads:
{ads_context}

Rules:
- answer only from the ads
- do not invent details
- if the user asks for comparison, compare clearly
- if the user asks for recommendation, recommend only from available data
- reply in English
"""

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt.strip(),
        "stream": False,
        "options": {
            "temperature": 0.1,
            "top_p": 0.9,
        }
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=120)
        response.raise_for_status()
        data = response.json()
        answer = (data.get("response") or "").strip()

        if not answer:
            return "Нема одговор од AI моделот." if lang == "mk" else "No answer from AI model."

        return answer

    except Exception as e:
        return (
            f"AI сервисот не е достапен за анализа. Детали: {e}"
            if lang == "mk"
            else f"AI service is unavailable for analysis. Details: {e}"
        )




#vtora verzija so bugarski
# from typing import List, Dict, Any
# import requests
#
# OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
# OLLAMA_MODEL = "llama3.2:1b"
#
#
# def build_ads_context(ads: List[Dict[str, Any]]) -> str:
#     if not ads:
#         return "Нема пронајдени огласи."
#
#     lines = []
#     for i, ad in enumerate(ads, start=1):
#         lines.append(
#             f"{i}. Наслов: {ad['title']} | Извор: {ad['source']} | Линк: {ad['link']}"
#         )
#     return "\n".join(lines)
#
#
# def ask_ollama(user_message: str, ads: List[Dict[str, Any]]) -> str:
#     ads_context = build_ads_context(ads)
#
#     system_prompt = (
#         "Ти си SmartAdds AI асистент. "
#         "Одговарај кратко, јасно и корисно на македонски јазик. "
#         "Ако има дадени огласи, користи ги само нив како контекст. "
#         "Не измислувај огласи, цени, детали или линкови. "
#         "Ако нема доволно податоци, кажи дека нема доволно податоци во резултатите."
#     )
#
#     user_prompt = (
#         f"Корисничко барање:\n{user_message}\n\n"
#         f"Пронајдени огласи:\n{ads_context}\n\n"
#         "Одговори му на корисникот. Ако бара споредба, препорака или анализа, "
#         "направи ја врз база на огласите."
#     )
#
#     payload = {
#         "model": OLLAMA_MODEL,
#         "messages": [
#             {"role": "system", "content": system_prompt},
#             {"role": "user", "content": user_prompt}
#         ],
#         "stream": False
#     }
#
#     try:
#         response = requests.post(OLLAMA_URL, json=payload, timeout=120)
#         response.raise_for_status()
#         data = response.json()
#         return data.get("message", {}).get("content", "").strip() or "Нема одговор од AI моделот."
#     except Exception as e:
#         return f"AI сервисот не е достапен. Провери дали Ollama работи. Детали: {e}"

# from typing import List, Dict, Any
# import requests
#
# OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
# OLLAMA_MODEL = "llama3.1"
#
#
# def build_ads_context(ads: List[Dict[str, Any]]) -> str:
#     if not ads:
#         return "Nema pronajdeni oglasi."
#
#     lines = []
#     for i, ad in enumerate(ads, start=1):
#         lines.append(
#             f"{i}. Naslov: {ad['title']} | Izvor: {ad['source']} | Link: {ad['link']}"
#         )
#     return "\n".join(lines)
#
#
# def ask_ollama(user_message: str, ads: List[Dict[str, Any]]) -> str:
#     ads_context = build_ads_context(ads)
#
#     system_prompt = (
#         "Ti si SmartAdds AI asistent. "
#         "Odgovaraj kratko, jasno i korisno na makedonski jazik. "
#         "Koristi GI SAMO oglasite dadeni vo kontekstot. "
#         "Ne izmislivaj oglasi, ceni ili linkovi. "
#         "Ako nema dovolno podatoci, kazi deka nema dovolno podatoci vo rezultatite."
#     )
#
#     user_prompt = (
#         f"Korisnicko baranje:\n{user_message}\n\n"
#         f"Pronajdeni oglasi:\n{ads_context}\n\n"
#         "Pomogni mu na korisnikot so kratka analiza ili preporaka vrz osnova na oglasite."
#     )
#
#     payload = {
#         "model": OLLAMA_MODEL,
#         "messages": [
#             {"role": "system", "content": system_prompt},
#             {"role": "user", "content": user_prompt},
#         ],
#         "stream": False
#     }
#
#     try:
#         response = requests.post(OLLAMA_URL, json=payload, timeout=120)
#         response.raise_for_status()
#         data = response.json()
#         return data.get("message", {}).get("content", "").strip() or "Нема одговор од AI моделот."
#     except Exception as e:
#         return f"AI сервисот не е достапен. Провери дали Ollama работи. Детали: {e}"