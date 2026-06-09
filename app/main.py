#
# from pathlib import Path
# from typing import List, Dict, Any
#
# from fastapi import FastAPI
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.staticfiles import StaticFiles
# from fastapi.responses import FileResponse
# from pydantic import BaseModel, Field
#
# from app.chat.rag_engine import load_data, metadata
# from app.chat.ollama_engine import ask_ollama, detect_intent
# from app.mcp.mcp_controller import router as mcp_router
# import app.mcp.mcp_client as mcp_client
#
#
# from apscheduler.schedulers.background import BackgroundScheduler
# from app.crawler.scraper import scrape_all
#
# BASE_DIR = Path(__file__).resolve().parent
# STATIC_DIR = BASE_DIR / "static"
#
# app = FastAPI(title="SmartAdds AI")
#
# app.include_router(mcp_router)
#
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )
#
# app.mount(
#     "/static",
#     StaticFiles(directory=str(STATIC_DIR)),
#     name="static"
# )
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
# # @app.on_event("startup")
# # def startup_event():
# #     print("\n==============================")
# #     print("Starting SmartAdds AI")
# #     print("MCP MODE ENABLED")
# #     print("==============================\n")
# #
# #     try:
# #         load_data()
# #         print(f"[STARTUP] Ads loaded: {len(metadata)}")
# #     except Exception as e:
# #         print(f"[STARTUP ERROR] Failed to load ads: {e}")
# @app.on_event("startup")
# def startup_event():
#
#     print("\n==============================")
#     print("Starting SmartAdds AI")
#     print("MCP MODE ENABLED")
#     print("==============================\n")
#
#     load_data()
#
#     scheduler = BackgroundScheduler()
#
#     scheduler.add_job(
#         scrape_all,
#         "interval",
#         hours=1
#     )
#
#     scheduler.start()
#
#     print("[SCHEDULER] Started")
#
# @app.get("/")
# def serve_ui():
#     return FileResponse(str(STATIC_DIR / "index.html"))
#
#
# @app.get("/health")
# def health():
#     return {
#         "status": "ok",
#         "mcp_enabled": True
#     }
#
#
# @app.get("/status")
# def status():
#     try:
#         from app.search.semantic_engine import is_ready
#         semantic_ready = is_ready()
#     except Exception:
#         semantic_ready = False
#
#     return {
#         "semantic_ready": semantic_ready,
#         "ads_count": len(metadata),
#         "mcp_enabled": True,
#         "chat_uses_mcp": True
#     }
#
#
# @app.post("/chat")
# def chat(request: ChatRequest):
#     user_message = (request.message or "").strip()
#     conversation_history = request.history or []
#     last_ads = request.last_ads or []
#     last_query = request.last_query or ""
#
#     if not user_message:
#         return {
#             "answer": "Прати ми порака за да можам да ти помогнам.",
#             "history": conversation_history,
#             "last_ads": last_ads,
#             "last_query": last_query,
#             "ads": [],
#             "source_mode": "none",
#             "search_mode": "none",
#             "price_filter": None,
#         }
#
#     print("\n================ CHAT REQUEST ================")
#     print(f"[CHAT] User message: {user_message}")
#     print(f"[CHAT] Received last_ads: {len(last_ads)}")
#     print(f"[CHAT] Received last_query: {last_query}")
#
#     intent = detect_intent(
#         user_message,
#         last_ads=last_ads
#     )
#
#     print(f"[CHAT] Detected intent: {intent}")
#
#     ads = []
#     used_last_ads = False
#     detected_query = user_message
#     resolved_intent = intent
#     search_mode = "mcp"
#     price_filter = None
#
#     if intent == "search":
#         try:
#             print("[CHAT] Search intent detected")
#             print("[CHAT] Calling MCP client, NOT database directly")
#
#             ads = mcp_client.search_ads(
#                 query=user_message,
#                 limit=20
#             )
#
#
#             print(f"[CHAT] MCP returned ads: {len(ads)}")
#
#             last_ads = ads
#             last_query = user_message
#
#         except Exception as e:
#             print(f"[CHAT MCP ERROR] {e}")
#             ads = []
#
#     elif intent == "followup":
#         print("[CHAT] Follow-up intent detected")
#         print("[CHAT] Using previous ads from frontend state")
#
#         ads = last_ads
#         used_last_ads = True
#         detected_query = last_query or user_message
#         search_mode = "previous_results"
#
#         print(f"[CHAT] Follow-up ads count: {len(ads)}")
#
#     else:
#         print("[CHAT] Normal chat detected, MCP not called")
#         ads = []
#         search_mode = "none"
#
#     print("[CHAT] Sending ads to Ollama")
#     print(f"[CHAT] Ads sent to Ollama: {len(ads)}")
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
#     conversation_history.append({
#         "role": "user",
#         "content": user_message
#     })
#
#     conversation_history.append({
#         "role": "assistant",
#         "content": answer
#     })
#
#     print("[CHAT] Response ready")
#     print("=============================================\n")
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

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from passlib.context import CryptContext

from apscheduler.schedulers.background import BackgroundScheduler

from app.database.db import SessionLocal, engine, Base
import app.database.models
from app.database.models import User, SavedSearch, Notification, Ad

from app.chat.rag_engine import load_data, metadata
from app.chat.ollama_engine import ask_ollama, detect_intent
from app.mcp.mcp_controller import router as mcp_router
import app.mcp.mcp_client as mcp_client

from app.crawler.scraper import scrape_all

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

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
scheduler = BackgroundScheduler()


class ChatRequest(BaseModel):
    message: str
    history: List[Dict[str, Any]] = Field(default_factory=list)
    last_ads: List[Dict[str, Any]] = Field(default_factory=list)
    last_query: str = ""
    source_filter: str = ""


class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class SaveSearchRequest(BaseModel):
    user_id: int
    query: str


@app.on_event("startup")
def startup_event():
    print("\n==============================")
    print("Starting SmartAdds AI")
    print("MCP MODE ENABLED")
    print("==============================\n")

    Base.metadata.create_all(bind=engine)

    try:
        load_data()
        print(f"[STARTUP] Ads loaded: {len(metadata)}")
    except Exception as e:
        print(f"[STARTUP ERROR] Failed to load ads: {e}")

    if not scheduler.running:
        scheduler.add_job(
            scrape_all,
            "interval",
            hours=1,
            id="scrape_job",
            replace_existing=True
        )

        scheduler.start()
        print("[SCHEDULER] Started")


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

@app.post("/register")
def register(request: RegisterRequest):
    db = SessionLocal()

    try:
        existing_email = db.query(User).filter(User.email == request.email).first()
        if existing_email:
            raise HTTPException(status_code=400, detail="Email already exists")

        existing_username = db.query(User).filter(User.username == request.username).first()
        if existing_username:
            raise HTTPException(status_code=400, detail="Username already exists")

        try:
            password = request.password.strip()

            if len(password.encode("utf-8")) > 72:
                raise HTTPException(
                    status_code=400,
                    detail="Password must be shorter than 72 bytes"
                )

            password_hash = pwd_context.hash(password)
        except Exception as e:
            print(f"[REGISTER HASH ERROR] {e}")
            raise HTTPException(status_code=500, detail=f"Password hash error: {str(e)}")

        user = User(
            username=request.username,
            email=request.email,
            password_hash=password_hash
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        return {
            "message": "User registered successfully",
            "user_id": user.id,
            "username": user.username,
            "email": user.email
        }

    except HTTPException:
        raise

    except Exception as e:
        db.rollback()
        print(f"[REGISTER ERROR] {e}")
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        db.close()


@app.post("/login")
def login(request: LoginRequest):
    db = SessionLocal()

    try:
        user = db.query(User).filter(User.email == request.email).first()

        if not user:
            raise HTTPException(status_code=401, detail="Invalid email or password")

        try:
            password = request.password.strip()

            if len(password.encode("utf-8")) > 72:
                raise HTTPException(
                    status_code=401,
                    detail="Invalid email or password"
                )
            password_ok = pwd_context.verify(
                request.password,
                user.password_hash
            )
        except Exception as e:
            print(f"[LOGIN HASH ERROR] {e}")
            raise HTTPException(status_code=401, detail="Invalid email or password")

        if not password_ok:
            raise HTTPException(status_code=401, detail="Invalid email or password")

        return {
            "message": "Login successful",
            "user_id": user.id,
            "username": user.username,
            "email": user.email
        }

    except HTTPException:
        raise

    except Exception as e:
        print(f"[LOGIN ERROR] {e}")
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        db.close()


@app.post("/saved-searches")
def save_search(request: SaveSearchRequest):
    db = SessionLocal()

    try:
        user = db.query(User).filter(User.id == request.user_id).first()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        query = request.query.strip()

        if not query:
            raise HTTPException(status_code=400, detail="Query cannot be empty")

        saved_search = SavedSearch(
            user_id=request.user_id,
            query=query
        )

        db.add(saved_search)
        db.commit()
        db.refresh(saved_search)

        return {
            "message": "Search saved successfully",
            "id": saved_search.id,
            "user_id": saved_search.user_id,
            "query": saved_search.query
        }

    finally:
        db.close()


@app.get("/saved-searches/{user_id}")
def get_saved_searches(user_id: int):
    db = SessionLocal()

    try:
        searches = (
            db.query(SavedSearch)
            .filter(SavedSearch.user_id == user_id)
            .order_by(SavedSearch.created_at.desc())
            .all()
        )

        return [
            {
                "id": search.id,
                "user_id": search.user_id,
                "query": search.query,
                "created_at": search.created_at
            }
            for search in searches
        ]

    finally:
        db.close()


@app.get("/notifications/{user_id}")
def get_notifications(user_id: int):
    db = SessionLocal()

    try:
        notifications = (
            db.query(Notification, Ad)
            .join(Ad, Notification.ad_id == Ad.id)
            .filter(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
            .all()
        )

        result = []

        for notification, ad in notifications:
            result.append({
                "id": notification.id,
                "message": notification.message,
                "is_read": notification.is_read,
                "created_at": notification.created_at,
                "ad": {
                    "id": ad.id,
                    "title": ad.title,
                    "description": ad.description,
                    "price": ad.price,
                    "link": ad.link,
                    "source": ad.source
                }
            })

        return result

    finally:

        db.close()


@app.post("/notifications/{notification_id}/read")
def mark_notification_as_read(notification_id: int):
    db = SessionLocal()

    try:
        notification = (
            db.query(Notification)
            .filter(Notification.id == notification_id)
            .first()
        )

        if not notification:
            raise HTTPException(status_code=404, detail="Notification not found")

        notification.is_read = True
        db.commit()

        return {
            "message": "Notification marked as read"
        }

    finally:
        db.close()


@app.post("/scrape-now")
def scrape_now():
    scrape_all()

    return {
        "message": "Scraping finished"
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
