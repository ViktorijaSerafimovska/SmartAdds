# from pathlib import Path
# from typing import List, Dict, Any
#
# from fastapi import FastAPI
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.staticfiles import StaticFiles
# from fastapi.responses import FileResponse
# from pydantic import BaseModel, Field
#
# from app.chat.rag_engine import load_data, get_search_context
# from app.chat.ollama_engine import ask_ollama, detect_intent
# from app.mcp.mcp_controller import router as mcp_router
#
# BASE_DIR = Path(__file__).resolve().parent
# STATIC_DIR = BASE_DIR / "static"
#
# app = FastAPI(title="SmartAdds AI")
#
# app.include_router(mcp_router)
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )
#
# app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
#
#
# class ChatRequest(BaseModel):
#     message: str
#     history: List[Dict[str, Any]] = Field(default_factory=list)
#     last_ads: List[Dict[str, Any]] = Field(default_factory=list)
#     last_query: str = ""
#     source_filter: str = ""
#
#
# @app.on_event("startup")
# def startup_event():
#     print("Starting SmartAdds AI...")
#     load_data()
#
#
# @app.get("/")
# def serve_ui():
#     return FileResponse(str(STATIC_DIR / "index.html"))
#
#
# @app.get("/health")
# def health():
#     return {"status": "ok"}
#
#
# @app.get("/status")
# def status():
#     from app.chat.rag_engine import metadata
#     try:
#         from app.search.semantic_engine import is_ready
#         semantic_ready = is_ready()
#     except Exception:
#         semantic_ready = False
#     return {"semantic_ready": semantic_ready, "ads_count": len(metadata)}
#
#
# @app.post("/chat")
# def chat(request: ChatRequest):
#     user_message = (request.message or "").strip()
#     conversation_history = request.history or []
#     last_ads = request.last_ads or []
#     last_query = request.last_query or ""
#     source_filter = (request.source_filter or "").strip().lower()
#
#     if not user_message:
#         return {
#             "answer": "Прати ми порака за да можам да ти помогнам.",
#             "history": conversation_history,
#             "last_ads": last_ads,
#             "last_query": last_query,
#             "ads": [],
#             "source_mode": "none",
#         }
#
#     intent = detect_intent(user_message, last_ads=last_ads)
#
#     context = get_search_context(
#         user_message=user_message,
#         last_ads=last_ads,
#         last_query=last_query,
#         intent=intent,
#         source_filter=source_filter,
#     )
#
#     ads = context["ads"]
#     used_last_ads = context["used_last_ads"]
#     detected_query = context["detected_query"]
#     resolved_intent = context["intent"]
#     search_mode = context.get("search_mode", "keyword")
#     price_filter = context.get("price_filter")
#
#     answer = ask_ollama(
#         user_message=user_message,
#         ads=ads,
#         history=conversation_history,
#         detected_query=detected_query,
#         used_last_ads=used_last_ads,
#         intent=resolved_intent,
#     )
#
#     if resolved_intent == "search":
#         last_ads = ads
#         last_query = detected_query or user_message
#     elif resolved_intent == "followup" and last_ads:
#         last_query = last_query or detected_query
#
#     conversation_history.append({"role": "user", "content": user_message})
#     conversation_history.append({"role": "assistant", "content": answer})
#
#     return {
#         "answer": answer,
#         "history": conversation_history,
#         "last_ads": last_ads,
#         "last_query": last_query,
#         "ads": ads if resolved_intent in ("search", "followup") else [],
#         "source_mode": resolved_intent,
#         "search_mode": search_mode,
#         "price_filter": price_filter,
#     }

from pathlib import Path
from typing import List, Dict, Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.chat.rag_engine import (
    load_data,
    get_search_context,
    metadata,
)

from app.chat.ollama_engine import (
    ask_ollama,
    detect_intent,
)

from app.mcp.mcp_controller import router as mcp_router

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="SmartAdds AI")

# -----------------------------
# ROUTERS
# -----------------------------

app.include_router(mcp_router)

# -----------------------------
# CORS
# -----------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# STATIC FILES
# -----------------------------

app.mount(
    "/static",
    StaticFiles(directory=str(STATIC_DIR)),
    name="static"
)

# -----------------------------
# STARTUP
# -----------------------------

@app.on_event("startup")
def startup_event():

    print("\n==============================")
    print("Starting SmartAdds AI...")
    print("==============================\n")

    try:
        load_data()

        print(f"[OK] Ads loaded successfully: {len(metadata)}")

    except Exception as e:

        print(f"[ERROR] Failed to load ads: {e}")

# -----------------------------
# REQUEST MODEL
# -----------------------------

class ChatRequest(BaseModel):

    message: str

    history: List[Dict[str, Any]] = Field(default_factory=list)

    last_ads: List[Dict[str, Any]] = Field(default_factory=list)

    last_query: str = ""

    source_filter: str = ""

# -----------------------------
# ROUTES
# -----------------------------

@app.get("/")
def serve_ui():

    return FileResponse(
        str(STATIC_DIR / "index.html")
    )

@app.get("/health")
def health():

    return {
        "status": "ok"
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
    }

# -----------------------------
# CHAT
# -----------------------------

@app.post("/chat")
def chat(request: ChatRequest):

    user_message = (request.message or "").strip()

    conversation_history = request.history or []

    last_ads = request.last_ads or []

    last_query = request.last_query or ""

    source_filter = (
        request.source_filter or ""
    ).strip().lower()

    if not user_message:

        return {
            "answer": "Прати ми порака за да можам да ти помогнам.",
            "history": conversation_history,
            "last_ads": last_ads,
            "last_query": last_query,
            "ads": [],
            "source_mode": "none",
        }

    print(f"\n[CHAT] User message: {user_message}")

    # -----------------------------
    # DETECT INTENT
    # -----------------------------

    intent = detect_intent(
        user_message,
        last_ads=last_ads
    )

    print(f"[DEBUG] Intent: {intent}")

    # -----------------------------
    # SEARCH CONTEXT
    # -----------------------------

    context = get_search_context(
        user_message=user_message,
        last_ads=last_ads,
        last_query=last_query,
        intent=intent,
        source_filter=source_filter,
    )

    ads = context["ads"]

    used_last_ads = context["used_last_ads"]

    detected_query = context["detected_query"]

    resolved_intent = context["intent"]

    search_mode = context.get(
        "search_mode",
        "keyword"
    )

    price_filter = context.get(
        "price_filter"
    )

    print(f"[DEBUG] Found ads: {len(ads)}")
    print(f"[DEBUG] Search mode: {search_mode}")

    # -----------------------------
    # OLLAMA RESPONSE
    # -----------------------------

    answer = ask_ollama(
        user_message=user_message,
        ads=ads,
        history=conversation_history,
        detected_query=detected_query,
        used_last_ads=used_last_ads,
        intent=resolved_intent,
    )

    # -----------------------------
    # UPDATE MEMORY
    # -----------------------------

    if resolved_intent == "search":

        last_ads = ads

        last_query = (
            detected_query
            or user_message
        )

    elif resolved_intent == "followup" and last_ads:

        last_query = (
            last_query
            or detected_query
        )

    # -----------------------------
    # UPDATE CHAT HISTORY
    # -----------------------------

    conversation_history.append({
        "role": "user",
        "content": user_message
    })

    conversation_history.append({
        "role": "assistant",
        "content": answer
    })

    # -----------------------------
    # RESPONSE
    # -----------------------------

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