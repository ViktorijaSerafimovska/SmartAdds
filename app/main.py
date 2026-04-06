from pathlib import Path
from typing import List, Dict, Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.rag_engine import load_data, ask_question

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="SmartAdds")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class ChatRequest(BaseModel):
    message: str
    history: List[Dict[str, Any]] = Field(default_factory=list)


@app.on_event("startup")
def startup_event():
    load_data()


@app.get("/")
def serve_ui():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat")
def chat(request: ChatRequest):
    user_message = request.message.strip()
    conversation_history = request.history or []

    if not user_message:
        return {
            "answer": "Прати ми текст за да можам да ти помогнам.",
            "history": conversation_history
        }

    answer = ask_question(user_message)

    conversation_history.append({"role": "user", "content": user_message})
    conversation_history.append({"role": "assistant", "content": answer})

    return {
        "answer": answer,
        "history": conversation_history
    }