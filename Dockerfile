# Image de l'API FastAPI (le reste des services est dans docker-compose.yml).
# Construction : docker build -t lissstrike-api .
# Lancement    : docker compose --profile api up -d api   (voir docker-compose.yml)
#   ou         : docker run --env-file .env -p 8000:8000 lissstrike-api
#   (dans le conteneur, "localhost" désigne le conteneur lui-même : faire
#   pointer DATABASE_URL, REDIS_URL et CHROMA_HOST vers les services, par
#   exemple host.docker.internal ou le nom du service Compose)
#
# Même version de Python que le venv de développement (3.13).
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/app/.cache/huggingface

WORKDIR /app

# PyTorch version CPU, comme en intégration continue (.github/workflows/tests.yml) :
# évite les bibliothèques CUDA, inutiles sans GPU
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
COPY requirements.txt .
# greenlet : requis par SQLAlchemy en asynchrone ; installé d'office sous
# Windows, mais pas par pip dans cette image Linux
RUN pip install --no-cache-dir -r requirements.txt greenlet

# Utilisateur sans privilèges, créé AVANT le téléchargement des modèles :
# un « chown -R » après coup recopierait les ~1 Go de modèles dans une
# nouvelle couche. Seul le cache des modèles lui appartient ; le code reste
# en lecture seule (l'application n'écrit rien dans /app).
RUN useradd --create-home appuser && mkdir -p /app/.cache && chown appuser /app/.cache
USER appuser

# Modèles locaux téléchargés à la construction, pas au premier démarrage
# (mêmes noms que app/services/rag/embedding_service.py et reranker.py).
# HF_HUB_DISABLE_XET=1 : le protocole Xet de Hugging Face peut bloquer le
# téléchargement (constaté à la construction, voir aussi .env.example)
RUN HF_HUB_DISABLE_XET=1 python -c "from sentence_transformers import SentenceTransformer, CrossEncoder; \
SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'); \
CrossEncoder('cross-encoder/mmarco-mMiniLMv2-L12-H384-v1')"

# Fichiers lus à l'exécution : pages (static/), intentions apprises
# (data/intents/exemples.json), catalogue pour les statistiques (produits.csv)
COPY app ./app
COPY static ./static
COPY alembic ./alembic
COPY alembic.ini .
COPY data/intents ./data/intents
COPY data/knowledge_base/ecommerce/produits.csv ./data/knowledge_base/ecommerce/produits.csv

EXPOSE 8000

# Santé : GET /health (app/main.py). Pas de curl dans l'image slim : Python.
# start-period long : préchargement des modèles et de l'index BM25 au démarrage.
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
