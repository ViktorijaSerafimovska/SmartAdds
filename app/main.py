from pathlib import Path
from typing import List, Dict, Any

import hashlib
import secrets
import hmac

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from apscheduler.schedulers.background import BackgroundScheduler

from app.database.db import SessionLocal, engine, Base
import app.database.models
from app.database.models import User, SavedSearch, Notification, Ad

import app.chat.search_engine as rag_engine
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

scheduler = BackgroundScheduler()


def hash_password(password: str) -> str:
    password = password.strip()

    salt = secrets.token_hex(16)
    iterations = 100_000

    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations
    ).hex()

    return f"pbkdf2_sha256${iterations}${salt}${password_hash}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations, salt, password_hash = stored_hash.split("$")

        if algorithm != "pbkdf2_sha256":
            return False

        new_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.strip().encode("utf-8"),
            salt.encode("utf-8"),
            int(iterations)
        ).hex()

        return hmac.compare_digest(new_hash, password_hash)

    except Exception:
        return False


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
        rag_engine.load_data()
        print(f"[STARTUP] Ads loaded: {len(rag_engine.metadata)}")
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
        "ads_count": len(rag_engine.metadata),
        "mcp_enabled": True,
        "chat_uses_mcp": True
    }


@app.post("/register")
def register(request: RegisterRequest):
    db = SessionLocal()

    try:
        username = request.username.strip()
        email = request.email.strip().lower()
        password = request.password.strip()

        if not username or not email or not password:
            raise HTTPException(status_code=400, detail="All fields are required")

        if len(password) < 4:
            raise HTTPException(status_code=400, detail="Password is too short")

        existing_email = db.query(User).filter(User.email == email).first()
        if existing_email:
            raise HTTPException(status_code=400, detail="Email already exists")

        existing_username = db.query(User).filter(User.username == username).first()
        if existing_username:
            raise HTTPException(status_code=400, detail="Username already exists")

        hashed_password = hash_password(password)

        user = User(
            username=username,
            email=email,
            password_hash=hashed_password
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        print(f"[REGISTER] User registered: {email}")

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
        email = request.email.strip().lower()
        password = request.password.strip()

        if not email or not password:
            raise HTTPException(status_code=400, detail="Email and password are required")

        user = db.query(User).filter(User.email == email).first()

        if not user:
            raise HTTPException(status_code=401, detail="Invalid email or password")

        if not verify_password(password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid email or password")

        print(f"[LOGIN] User logged in: {email}")

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


@app.delete("/saved-searches/{search_id}")
def delete_saved_search(search_id: int):
    db = SessionLocal()

    try:
        saved_search = (
            db.query(SavedSearch)
            .filter(SavedSearch.id == search_id)
            .first()
        )

        if not saved_search:
            raise HTTPException(status_code=404, detail="Saved search not found")

        db.delete(saved_search)
        db.commit()

        return {
            "message": "Saved search deleted successfully"
        }

    finally:
        db.close()


@app.post("/notifications/read-all/{user_id}")
def mark_all_notifications_as_read(user_id: int):
    db = SessionLocal()

    try:
        notifications = (
            db.query(Notification)
            .filter(Notification.user_id == user_id)
            .all()
        )

        for notification in notifications:
            notification.is_read = True

        db.commit()

        return {
            "message": "All notifications marked as read",
            "count": len(notifications)
        }

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

    try:
        rag_engine.load_data()
    except Exception as e:
        print(f"[SCRAPE RELOAD ERROR] {e}")

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