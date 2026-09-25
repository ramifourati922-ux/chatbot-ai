"""
Toutes les variables d'environnement centralisées ici.
Pydantic Settings valide automatiquement les types.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Chatbot IA"
    DEBUG: bool = False
    SECRET_KEY: str = "change-this-secret"

    # Base de données
    DATABASE_URL: str
    POSTGRES_DB: str = "chatbot_db"
    POSTGRES_USER: str = "chatbot_user"
    POSTGRES_PASSWORD: str = "secret123"

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # Groq (Phase 3 — LLM gratuit, PAS d'OpenAI)
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "openai/gpt-oss-120b"
    GROQ_FALLBACK_MODEL: str = "openai/gpt-oss-20b"

    # ChromaDB (Phase 3 — Vector DB pour le RAG)
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8001
    CHROMA_COLLECTION_NAME: str = "liss_strike_kb"

    # Embeddings (Phase 3 — local, gratuit, multilingue FR/EN/AR)
    EMBEDDING_MODEL: str = "paraphrase-multilingual-MiniLM-L12-v2"

    # Stratégie de recherche RAG (voir retriever.search) :
    #   "advanced" = hybride + reranking cross-encoder (défaut)
    #   "hybrid"   = BM25 + dense + RRF seul (hybrid_retriever.py)
    #   "basic"    = dense seul d'origine
    # Les 3 modes restent sélectionnables pour l'évaluation RAGas avant/après.
    RAG_RETRIEVAL_MODE: str = "advanced"

    # Reranking (Advanced RAG) — cross-encoder MULTILINGUE, voir reranker.py
    RERANKER_MODEL: str = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
    RERANKER_MAX_LENGTH: int = 512
    # Candidats remontés par la recherche hybride avant reranking
    RERANK_CANDIDATES: int = 20

    # Seuil de confiance RAG (= 1 - distance cosinus du meilleur hit)
    # en dessous duquel on escalade automatiquement plutôt que de
    # risquer une hallucination du LLM (voir dialogue_manager.py).
    # Utilisé dans les 3 modes tant que RAG_CONFIDENCE_SIGNAL="cosine"
    # (défaut), voir retriever.get_best_confidence.
    #
    # Revérifié à l'étape 3 Advanced RAG (scripts/calibrate_threshold.py,
    # détail dans CHANGELOG_ADVANCED_RAG.md) : produits légitimes
    # 0.368-0.745 dans les 3 modes → 0.35 reste sous toutes les
    # questions produit (marge réduite à 0.018). En revanche le cosinus
    # ne sépare pas tous les hors-sujet (déjà le cas avant, cf. Figures
    # 23-24) : "recette du couscous" = 0.500,
    # "capitale de la France" = 0.363 → seuls 2 hors-sujet sur 4 sont
    # sous le seuil (les autres restent couverts par le garde-fou
    # hors-sujet du prompt système).
    #
    # Calibré empiriquement, PAS la valeur générique 0.7 du cahier des
    # charges : mesuré sur 10 vraies questions produit (10 catégories
    # différentes du catalogue) + 4 questions hors-sujet.
    #   - Questions produit légitimes : confiance entre 0.391 et 0.745
    #     → avec un seuil à 0.7, 8 des 10 auraient escaladé À TORT
    #       (chunks produits courts = moins de recouvrement sémantique
    #       avec une question en langage naturel que les chunks de
    #       politique, rédigés en phrases complètes ; ce n'est pas un
    #       signe de mauvais match, juste un artefact du format).
    #   - Questions "rien de pertinent trouvé" (ex: hors du domaine
    #     électronique/SAV ET sans aucun chunk proche) : confiance
    #     ~0.27-0.28.
    # 0.35 se place sous TOUTES les questions produit testées (marge
    # de 0.04) et au-dessus des cas "rien de pertinent" (marge
    # ~0.07-0.08).
    #
    # LIMITE CONNUE, découverte lors des tests d'intégration (voir
    # dialogue_manager.py, étape 8, pour le détail) : l'intention
    # initiale était que ce seuil rattrape spécifiquement les questions
    # DANS le domaine électronique/SAV mais mal couvertes par le RAG
    # (cf. le cas documenté où une question tunisienne sur la garantie
    # capteurs avait fait halluciner le LLM). En pratique, sur ~18
    # questions candidates testées (fr + tunisien, services obscurs
    # variés), AUCUNE question dans le domaine n'est descendue sous ce
    # seuil — le catalogue de ~11 000 produits est trop large, même des
    # questions sur des services inventés trouvent un match partiel.
    # Seules des questions clairement HORS domaine (score ~0.27-0.30, ou
    # hits vides = 0.0) déclenchent ce mécanisme dans les faits, ce qui
    # le fait largement chevaucher le garde-fou hors-sujet du prompt
    # système (llm_factory.BASE_SYSTEM_PROMPT) plutôt que de couvrir un
    # cas distinct. Il reste utile comme filet de sécurité supplémentaire
    # (rapide, pas d'appel LLM) et pour le cas hits vides, mais ne pas
    # présenter ce mécanisme comme isolant finement les 2 scénarios.
    RAG_CONFIDENCE_THRESHOLD: float = 0.35

    # Signal de confiance en mode advanced (étape 3 Advanced RAG) :
    #   "cosine"   (défaut) : 1 - distance cosinus, seuil RAG_CONFIDENCE_THRESHOLD
    #   "reranker" : score cross-encoder du meilleur hit (0-1), seuil
    #                RAG_RERANK_CONFIDENCE_THRESHOLD
    # Mesures (40 questions fr/en/ar/tn) : le score reranker sépare
    # beaucoup mieux — hors-sujet 0.000-0.039, légitimes avec le bon
    # chunk en top-1 ≥ 0.051, légitimes ar/tn avec un MAUVAIS chunk en
    # top-1 0.002-0.047 (escaladés au lieu d'envoyer un contexte faux au
    # LLM : c'est le cas "dans le domaine mais mal couvert" que le
    # cosinus n'isole pas, voir LIMITE CONNUE ci-dessus).
    # PAS activé par défaut : régression sur
    # test_normal_product_criticism_does_not_escalate ("ce produit est
    # nul" = 0.041 < 0.045 → escalade), et aucun seuil ne sépare cette
    # critique (0.041) de "recette du couscous" (0.039). Marges trop
    # étroites sur un petit échantillon → à trancher avec RAGas (étape 4).
    RAG_CONFIDENCE_SIGNAL: str = "cosine"
    RAG_RERANK_CONFIDENCE_THRESHOLD: float = 0.045

    # WhatsApp (Phase 5)
    WHATSAPP_PHONE_NUMBER_ID: Optional[str] = None
    WHATSAPP_ACCESS_TOKEN: Optional[str] = None
    WHATSAPP_VERIFY_TOKEN: Optional[str] = None
    # Secret d'application Meta — sert à vérifier la signature
    # X-Hub-Signature-256 des webhooks entrants (voir routes/whatsapp.py).
    WHATSAPP_APP_SECRET: Optional[str] = None

    # Messenger (Phase 5)
    MESSENGER_PAGE_ACCESS_TOKEN: Optional[str] = None
    MESSENGER_VERIFY_TOKEN: Optional[str] = None
    MESSENGER_APP_SECRET: Optional[str] = None

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings():
    return Settings()


settings = get_settings()