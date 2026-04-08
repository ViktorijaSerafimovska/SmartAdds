import os
from typing import Any, Dict, Optional

import requests
from dotenv import load_dotenv

load_dotenv()
load_dotenv(".env.lightrag")

LIGHTRAG_URL = os.getenv("LIGHTRAG_URL", "http://127.0.0.1:9621").rstrip("/")
LIGHTRAG_API_KEY = os.getenv("LIGHTRAG_API_KEY", "").strip()
DEFAULT_QUERY_MODE = os.getenv("LIGHTRAG_QUERY_MODE", "mix").strip() or "mix"


def _headers() -> Dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if LIGHTRAG_API_KEY:
        headers["X-API-Key"] = LIGHTRAG_API_KEY
    return headers


def health_lightrag() -> bool:
    try:
        response = requests.get(f"{LIGHTRAG_URL}/health", timeout=10)
        return response.ok
    except Exception:
        return False


def trigger_scan() -> Dict[str, Any]:
    try:
        response = requests.post(
            f"{LIGHTRAG_URL}/documents/scan",
            headers=_headers(),
            timeout=120,
        )
        response.raise_for_status()
        if response.text.strip():
            return response.json()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def query_lightrag(
    query: str,
    mode: Optional[str] = None,
    only_need_context: bool = False,
) -> Dict[str, Any]:
    payload = {
        "query": query,
        "mode": mode or DEFAULT_QUERY_MODE,
        "only_need_context": only_need_context,
    }

    try:
        response = requests.post(
            f"{LIGHTRAG_URL}/query",
            headers=_headers(),
            json=payload,
            timeout=180,
        )
        response.raise_for_status()
        data = response.json()

        answer = (
            data.get("response")
            or data.get("answer")
            or data.get("result")
            or data.get("context")
            or ""
        )

        return {
            "ok": True,
            "answer": str(answer).strip(),
            "raw": data,
        }
    except Exception as e:
        return {
            "ok": False,
            "answer": "",
            "error": str(e),
            "raw": {},
        }


def format_lightrag_answer(result: Dict[str, Any]) -> str:
    if not result.get("ok"):
        return f"LightRAG momentalno ne e dostapen. Detali: {result.get('error', 'Unknown error')}"

    answer = (result.get("answer") or "").strip()
    if answer:
        return answer

    return "LightRAG ne vrati rezultat."