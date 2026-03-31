# app/main.py — Version complète avec routes

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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

app.include_router(users.router)
app.include_router(chat.router)


@app.get("/", tags=["System"])
async def root():
    return {"message": "Bienvenue sur le Chatbot IA API", "docs": "/docs"}


@app.get("/health", tags=["System"])
async def health_check():
    return {"status": "healthy", "version": "1.0.0"}