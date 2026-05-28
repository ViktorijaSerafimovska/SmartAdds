
from pathlib import Path
from typing import List, Dict, Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.chat.rag_engine import load_data, metadata
from app.chat.ollama_engine import ask_ollama, detect_intent
from app.mcp.mcp_controller import router as mcp_router
import app.mcp.mcp_client as mcp_client

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="SmartAdds AI")

app.include_router(mcp_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount(
    "/static",
    StaticFiles(directory=str(STATIC_DIR)),
    name="static"
)


class ChatRequest(BaseModel):
    message: str
    history: List[Dict[str, Any]] = Field(default_factory=list)
    last_ads: List[Dict[str, Any]] = Field(default_factory=list)
    last_query: str = ""
    source_filter: str = ""


@app.on_event("startup")
def startup_event():
    print("\n==============================")
    print("Starting SmartAdds AI")
    print("MCP MODE ENABLED")
    print("==============================\n")

    try:
        load_data()
        print(f"[STARTUP] Ads loaded: {len(metadata)}")
    except Exception as e:
        print(f"[STARTUP ERROR] Failed to load ads: {e}")


@app.get("/")
def serve_ui():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/health")
def health():
    return {
        "status": "ok",
        "mcp_enabled": True
    }


@app.get("/status")
def status():
    try:
        from app.search.semantic_engine import is_ready
        semantic_ready = is_ready()
    except Exception:
        semantic_ready = False

    return {
        "semantic_ready": semantic_ready,
        "ads_count": len(metadata),
        "mcp_enabled": True,
        "chat_uses_mcp": True
    }


@app.post("/chat")
def chat(request: ChatRequest):
    user_message = (request.message or "").strip()
    conversation_history = request.history or []
    last_ads = request.last_ads or []
    last_query = request.last_query or ""

    if not user_message:
        return {
            "answer": "Прати ми порака за да можам да ти помогнам.",
            "history": conversation_history,
            "last_ads": last_ads,
            "last_query": last_query,
            "ads": [],
            "source_mode": "none",
            "search_mode": "none",
            "price_filter": None,
        }

    print("\n================ CHAT REQUEST ================")
    print(f"[CHAT] User message: {user_message}")
    print(f"[CHAT] Received last_ads: {len(last_ads)}")
    print(f"[CHAT] Received last_query: {last_query}")

    intent = detect_intent(
        user_message,
        last_ads=last_ads
    )

    print(f"[CHAT] Detected intent: {intent}")

    ads = []
    used_last_ads = False
    detected_query = user_message
    resolved_intent = intent
    search_mode = "mcp"
    price_filter = None

    if intent == "search":
        try:
            print("[CHAT] Search intent detected")
            print("[CHAT] Calling MCP client, NOT database directly")

            ads = mcp_client.search_ads(
                query=user_message,
                limit=20
            )


            print(f"[CHAT] MCP returned ads: {len(ads)}")

            last_ads = ads
            last_query = user_message

        except Exception as e:
            print(f"[CHAT MCP ERROR] {e}")
            ads = []

    elif intent == "followup":
        print("[CHAT] Follow-up intent detected")
        print("[CHAT] Using previous ads from frontend state")

        ads = last_ads
        used_last_ads = True
        detected_query = last_query or user_message
        search_mode = "previous_results"

        print(f"[CHAT] Follow-up ads count: {len(ads)}")

    else:
        print("[CHAT] Normal chat detected, MCP not called")
        ads = []
        search_mode = "none"

    print("[CHAT] Sending ads to Ollama")
    print(f"[CHAT] Ads sent to Ollama: {len(ads)}")

    answer = ask_ollama(
        user_message=user_message,
        ads=ads,
        history=conversation_history,
        detected_query=detected_query,
        used_last_ads=used_last_ads,
        intent=resolved_intent,
    )

    conversation_history.append({
        "role": "user",
        "content": user_message
    })

    conversation_history.append({
        "role": "assistant",
        "content": answer
    })

    print("[CHAT] Response ready")
    print("=============================================\n")

    return {
        "answer": answer,
        "history": conversation_history,
        "last_ads": last_ads,
        "last_query": last_query,
        "ads": ads if resolved_intent in ("search", "followup") else [],
        "source_mode": resolved_intent,
        "search_mode": search_mode,
        "price_filter": price_filter,
    }