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
from app.log_privacy import install_log_filters

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
# Journaux sans secrets ni conversations : paramètres sensibles masqués
# (uvicorn, httpx), journal DEBUG de Groq coupé (voir app/log_privacy.py)
install_log_filters()


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
    # Comptes conseillers (table agents) : si aucun n'existe, compte admin
    # d'amorçage créé depuis ADMIN_USERNAME / ADMIN_PASSWORD. Bloquant si la
    # table est vide et ADMIN_PASSWORD absent : personne ne pourrait se
    # connecter à /admin. PostgreSQL injoignable : avertissement seulement
    # (même logique que le reste de l'API, qui démarre sans la base).
    from app.services.agent_auth import bootstrap_admin_if_needed
    try:
        bootstrap = await bootstrap_admin_if_needed()
    except Exception as e:
        bootstrap = None
        logger.warning(f"⚠️ Comptes conseillers non vérifiés (PostgreSQL injoignable ?) : {e}")
    if bootstrap == "missing_password":
        raise RuntimeError(
            "Aucun compte conseiller en base et ADMIN_PASSWORD manquant : définissez "
            "ADMIN_USERNAME et ADMIN_PASSWORD dans le fichier .env (voir .env.example) "
            "pour créer le premier compte admin du tableau de bord (/admin)."
        )
    # Bloquant : canal WhatsApp configuré sans secret d'application, les
    # signatures Meta ne pourraient pas être vérifiées. Plutôt que d'exposer
    # un webhook public qui accepterait de faux messages, on refuse de démarrer.
    if settings.whatsapp_enabled and not settings.WHATSAPP_APP_SECRET:
        raise RuntimeError(
            "WHATSAPP_APP_SECRET manquant alors que le canal WhatsApp est configuré "
            "(WHATSAPP_PHONE_NUMBER_ID / WHATSAPP_ACCESS_TOKEN / WHATSAPP_VERIFY_TOKEN) : "
            "renseignez le secret de l'application Meta dans le fichier .env (voir .env.example)."
        )
    # Même règle pour Messenger.
    if settings.messenger_enabled and not settings.MESSENGER_APP_SECRET:
        raise RuntimeError(
            "MESSENGER_APP_SECRET manquant alors que le canal Messenger est configuré "
            "(MESSENGER_PAGE_ACCESS_TOKEN / MESSENGER_VERIFY_TOKEN) : "
            "renseignez le secret de l'application Meta dans le fichier .env (voir .env.example)."
        )
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

# Liste explicite (CORS_ALLOWED_ORIGINS) : un site tiers ne peut pas lire
# les réponses de l'API depuis le navigateur d'un visiteur. Ne concerne
# ni les WebSockets (les navigateurs n'y appliquent pas CORS) ni les
# clients hors navigateur (curl, webhooks Meta).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Limitation de débit (décorateurs sur /chat/ et /users/, voir rate_limit.py)
from slowapi.errors import RateLimitExceeded
from app.api.rate_limit import limiter, rate_limit_exceeded_handler

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# ── Inclure les routes ─────────────────────────────────────
from app.api.routes import users
from app.api.routes import chat
from app.api.routes import whatsapp
from app.api.routes import messenger
from app.api.routes import websocket
from app.api.routes import admin
from app.api.routes import agents

app.include_router(users.router)
app.include_router(chat.router)
app.include_router(whatsapp.router)
app.include_router(messenger.router)
app.include_router(websocket.router)
app.include_router(admin.router)
app.include_router(agents.router)


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