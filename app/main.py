# app/main.py — Version complète avec routes

import asyncio
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import logging

from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _preload_rag():
    """
    Charge au démarrage ce qui coûte cher au premier appel : modèle
    d'embeddings, index BM25 (6-20 s, lu depuis ChromaDB) et reranker.
    Sans ça, la toute première question d'un client paie ce temps.
    """
    from app.services.rag import embedding_service, hybrid_retriever, reranker

    t0 = time.time()
    embedding_service.embed("warmup")
    if settings.RAG_RETRIEVAL_MODE in ("hybrid", "advanced"):
        hybrid_retriever._get_index()
    if settings.RAG_RETRIEVAL_MODE == "advanced":
        reranker.warmup()
    logger.info(f"✅ RAG préchargé (mode={settings.RAG_RETRIEVAL_MODE}) en {time.time() - t0:.1f}s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Non bloquant en cas d'échec (ex: ChromaDB pas encore démarré) :
    # l'API démarre quand même, les composants se chargeront au premier appel.
    try:
        await asyncio.to_thread(_preload_rag)
    except Exception as e:
        logger.warning(f"⚠️ Préchargement RAG échoué, chargement différé au premier appel : {e}")
    yield


app = FastAPI(
    lifespan=lifespan,
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