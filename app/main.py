# app/main.py — Version complète avec routes

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Chatbot IA Intelligent",
    description="API du chatbot SAV + E-commerce",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Inclure les routes ─────────────────────────────────────
from app.api.routes import users
from app.api.routes import chat
from app.api.routes import whatsapp
from app.api.routes import messenger
from app.api.routes import websocket

app.include_router(users.router)
app.include_router(chat.router)
app.include_router(whatsapp.router)
app.include_router(messenger.router)
app.include_router(websocket.router)


@app.get("/", tags=["System"])
async def root():
    return {"message": "Bienvenue sur le Chatbot IA API", "docs": "/docs"}


@app.get("/health", tags=["System"])
async def health_check():
    return {"status": "healthy", "version": "1.0.0"}


# ── Interface de démo (Tâche 4) ─────────────────────────────
# Une route dédiée plutôt qu'un StaticFiles générique : on n'a qu'un
# seul fichier statique pour l'instant, pas de dossier entier à exposer.
_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@app.get("/chat-demo", tags=["System"])
async def chat_demo():
    return FileResponse(_STATIC_DIR / "chat.html")