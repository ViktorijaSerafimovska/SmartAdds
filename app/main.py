from pathlib import Path
from typing import List, Dict, Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.rag_engine import load_data, get_search_context
from app.ollama_engine import ask_ollama, detect_intent

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="SmartAdds AI")

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
    last_ads: List[Dict[str, Any]] = Field(default_factory=list)
    last_query: str = ""


@app.on_event("startup")
def startup_event():
    print("Starting SmartAdds AI...")
    load_data()


@app.get("/")
def serve_ui():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/health")
def health():
    return {"status": "ok"}


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
        }

    intent = detect_intent(user_message, last_ads=last_ads)

    context = get_search_context(
        user_message=user_message,
        last_ads=last_ads,
        last_query=last_query,
        intent=intent,
        limit=None,  # mnogu vazno: vrakja site matching oglasi
    )

    ads = context["ads"]
    used_last_ads = context["used_last_ads"]
    detected_query = context["detected_query"]
    resolved_intent = context["intent"]

    if resolved_intent == "search":
        if ads:
            answer = f"Најдов {len(ads)} релевантни огласи."
        else:
            answer = "Не најдов релевантни огласи во базата."

        last_ads = ads
        last_query = detected_query or user_message

        conversation_history.append({"role": "user", "content": user_message})
        conversation_history.append({"role": "assistant", "content": answer})

        return {
            "answer": answer,
            "history": conversation_history,
            "last_ads": last_ads,
            "last_query": last_query,
            "ads": ads,
            "source_mode": "custom_search",
        }

    answer = ask_ollama(
        user_message=user_message,
        ads=ads,
        history=conversation_history,
        detected_query=detected_query,
        used_last_ads=used_last_ads,
        intent=resolved_intent,
    )

    if resolved_intent == "followup" and last_ads:
        last_query = last_query or detected_query

    conversation_history.append({"role": "user", "content": user_message})
    conversation_history.append({"role": "assistant", "content": answer})

    return {
        "answer": answer,
        "history": conversation_history,
        "last_ads": last_ads,
        "last_query": last_query,
        "ads": ads if resolved_intent == "followup" else [],
        "source_mode": resolved_intent,
    }

# from pathlib import Path
# from typing import List, Dict, Any
#
# from fastapi import FastAPI
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.staticfiles import StaticFiles
# from fastapi.responses import FileResponse
# from pydantic import BaseModel, Field
#
# from app.rag_engine import load_data, get_search_context
# from app.ollama_engine import ask_ollama, detect_intent
#
# BASE_DIR = Path(__file__).resolve().parent
# STATIC_DIR = BASE_DIR / "static"
#
# app = FastAPI(title="SmartAdds AI")
#
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
#         }
#
#     intent = detect_intent(user_message, last_ads=last_ads)
#
#     context = get_search_context(
#         user_message=user_message,
#         last_ads=last_ads,
#         last_query=last_query,
#         intent=intent,
#         limit=None,  # vrati gi site
#     )
#
#     ads = context["ads"]
#     used_last_ads = context["used_last_ads"]
#     detected_query = context["detected_query"]
#     intent = context["intent"]
#
#     answer = ask_ollama(
#         user_message=user_message,
#         ads=ads,
#         history=conversation_history,
#         detected_query=detected_query,
#         used_last_ads=used_last_ads,
#         intent=intent,
#     )
#
#     if intent == "search":
#         last_ads = ads
#         last_query = detected_query or user_message
#     elif intent == "followup" and last_ads:
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
#         "ads": ads,
#     }
#
#
# # from pathlib import Path
# # from typing import List, Dict, Any
# #
# # from fastapi import FastAPI
# # from fastapi.middleware.cors import CORSMiddleware
# # from fastapi.staticfiles import StaticFiles
# # from fastapi.responses import FileResponse
# # from pydantic import BaseModel, Field
# #
# # from app.rag_engine import load_data, ask_question, get_top_ads_context
# # from app.ollama_engine import ask_ollama
# #
# # BASE_DIR = Path(__file__).resolve().parent
# # STATIC_DIR = BASE_DIR / "static"
# #
# # app = FastAPI(title="SmartAdds AI")
# #
# # app.add_middleware(
# #     CORSMiddleware,
# #     allow_origins=["*"],
# #     allow_credentials=True,
# #     allow_methods=["*"],
# #     allow_headers=["*"],
# # )
# #
# # app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
# #
# #
# # class ChatRequest(BaseModel):
# #     message: str
# #     history: List[Dict[str, Any]] = Field(default_factory=list)
# #
# #
# # def classify_message(message: str) -> str:
# #     text = (message or "").lower().strip()
# #
# #     ai_triggers = [
# #         "спореди", "sporedi",
# #         "препорачај", "preporachaj",
# #         "објасни", "objasni",
# #         "кој е подобар", "koj e podobar",
# #         "што мислиш", "sto mislish",
# #         "анализа", "analiza",
# #         "совет", "sovet",
# #         "дали вреди", "dali vredi",
# #         "што да земам", "sto da zemam",
# #     ]
# #
# #     search_triggers = [
# #         "najdi", "барaм", "baram", "sakam", "покажи", "pokazi",
# #         "iphone", "samsung", "stan", "bmw", "golf", "mercedes"
# #     ]
# #
# #     if any(trigger in text for trigger in ai_triggers):
# #         return "ai"
# #
# #     if any(trigger in text for trigger in search_triggers):
# #         return "search"
# #
# #     # default: нека иде преку hybrid
# #     return "hybrid"
# #
# #
# # @app.on_event("startup")
# # def startup_event():
# #     print("Starting SmartAdds AI...")
# #     load_data()
# #
# #
# # @app.get("/")
# # def serve_ui():
# #     return FileResponse(str(STATIC_DIR / "index.html"))
# #
# #
# # @app.get("/health")
# # def health():
# #     return {"status": "ok"}
# #
# #
# # @app.post("/chat")
# # def chat(request: ChatRequest):
# #     user_message = request.message.strip()
# #     conversation_history = request.history or []
# #
# #     if not user_message:
# #         return {
# #             "answer": "Прати ми текст за да можам да ти помогнам.",
# #             "history": conversation_history
# #         }
# #
# #     mode = classify_message(user_message)
# #
# #     if mode == "search":
# #         answer = ask_question(user_message)
# #
# #     elif mode == "ai":
# #         ads = get_top_ads_context(user_message, limit=10)
# #         answer = ask_ollama(user_message, ads)
# #
# #     else:
# #         # hybrid: прво зема релевантни огласи, па AI одговара врз нив
# #         ads = get_top_ads_context(user_message, limit=10)
# #
# #         if ads:
# #             answer = ask_ollama(user_message, ads)
# #         else:
# #             answer = ask_question(user_message)
# #
# #     conversation_history.append({"role": "user", "content": user_message})
# #     conversation_history.append({"role": "assistant", "content": answer})
# #
# #     return {
# #         "answer": answer,
# #         "history": conversation_history
# #     }
#
#
# #ova beshe vtoroto prebaruvanje
# # from pathlib import Path
# # from typing import List, Dict, Any
# #
# # from fastapi import FastAPI
# # from fastapi.middleware.cors import CORSMiddleware
# # from fastapi.staticfiles import StaticFiles
# # from fastapi.responses import FileResponse
# # from pydantic import BaseModel, Field
# #
# # from app.rag_engine import load_data, ask_question, get_top_ads_context
# # from app.ollama_engine import ask_ollama
# #
# # BASE_DIR = Path(__file__).resolve().parent
# # STATIC_DIR = BASE_DIR / "static"
# #
# # app = FastAPI(title="SmartAdds AI")
# #
# # app.add_middleware(
# #     CORSMiddleware,
# #     allow_origins=["*"],
# #     allow_credentials=True,
# #     allow_methods=["*"],
# #     allow_headers=["*"],
# # )
# #
# # app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
# #
# #
# # class ChatRequest(BaseModel):
# #     message: str
# #     history: List[Dict[str, Any]] = Field(default_factory=list)
# #
# #
# # def should_use_ai(message: str) -> bool:
# #     text = (message or "").lower()
# #     triggers = [
# #         "objasni",
# #         "sporedi",
# #         "preporachaj",
# #         "koj e podobar",
# #         "koja e razlikata",
# #         "ai ",
# #         "sovet",
# #         "analiza",
# #         "sto mislish",
# #     ]
# #     return any(trigger in text for trigger in triggers)
# #
# #
# # @app.on_event("startup")
# # def startup_event():
# #     load_data()
# #
# #
# # @app.get("/")
# # def serve_ui():
# #     return FileResponse(str(STATIC_DIR / "index.html"))
# #
# #
# # @app.get("/health")
# # def health():
# #     return {"status": "ok"}
# #
# #
# # @app.post("/chat")
# # def chat(request: ChatRequest):
# #     user_message = request.message.strip()
# #     conversation_history = request.history or []
# #
# #     if not user_message:
# #         return {
# #             "answer": "Прати ми текст за да можам да ти помогнам.",
# #             "history": conversation_history
# #         }
# #
# #     if should_use_ai(user_message):
# #         ads = get_top_ads_context(user_message, limit=10)
# #         answer = ask_ollama(user_message, ads)
# #     else:
# #         answer = ask_question(user_message)
# #
# #     conversation_history.append({"role": "user", "content": user_message})
# #     conversation_history.append({"role": "assistant", "content": answer})
# #
# #     return {
# #         "answer": answer,
# #         "history": conversation_history
# #     }
#
#
# # Ставено е ова на гит
# # from pathlib import Path
# # from typing import List, Dict, Any
# #
# # from fastapi import FastAPI
# # from fastapi.middleware.cors import CORSMiddleware
# # from fastapi.staticfiles import StaticFiles
# # from fastapi.responses import FileResponse
# # from pydantic import BaseModel, Field
# #
# # from app.rag_engine import load_data, ask_question
# #
# # BASE_DIR = Path(__file__).resolve().parent
# # STATIC_DIR = BASE_DIR / "static"
# #
# # app = FastAPI(title="SmartAdds")
# #
# # app.add_middleware(
# #     CORSMiddleware,
# #     allow_origins=["*"],
# #     allow_credentials=True,
# #     allow_methods=["*"],
# #     allow_headers=["*"],
# # )
# #
# # app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
# #
# #
# # class ChatRequest(BaseModel):
# #     message: str
# #     history: List[Dict[str, Any]] = Field(default_factory=list)
# #
# #
# # @app.on_event("startup")
# # def startup_event():
# #     load_data()
# #
# #
# # @app.get("/")
# # def serve_ui():
# #     return FileResponse(str(STATIC_DIR / "index.html"))
# #
# #
# # @app.get("/health")
# # def health():
# #     return {"status": "ok"}
# #
# #
# # @app.post("/chat")
# # def chat(request: ChatRequest):
# #     user_message = request.message.strip()
# #     conversation_history = request.history or []
# #
# #     if not user_message:
# #         return {
# #             "answer": "Прати ми текст за да можам да ти помогнам.",
# #             "history": conversation_history
# #         }
# #
# #     answer = ask_question(user_message)
# #
# #     conversation_history.append({"role": "user", "content": user_message})
# #     conversation_history.append({"role": "assistant", "content": answer})
# #
# #     return {
# #         "answer": answer,
# #         "history": conversation_history
# #     }