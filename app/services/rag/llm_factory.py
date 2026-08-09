# app/services/rag/llm_factory.py
"""
Factory pour le LLM (Groq, gratuit).

Modèle principal : openai/gpt-oss-120b
    - Publié en open-weight par OpenAI sur Hugging Face, servi par Groq.
    - Remplace `llama-3.1-70b-versatile` (cité dans le brief initial)
      qui n'existe plus sur Groq depuis janvier 2025, et son successeur
      `llama-3.3-70b-versatile` qui est lui-même retiré le 16/08/2026.
      → gpt-oss-120b est le remplacement officiellement recommandé par Groq.
    - Supporte bien le français et l'anglais. Pour l'arabe (littéraire),
      correct sans être parfait. Pour le tunisien, voir les limites déjà
      discutées : le system prompt impose explicitement la langue de
      réponse plutôt que de compter sur une détection automatique par
      le LLM (moins fiable, surtout pour un dialecte).

Modèle de secours : openai/gpt-oss-20b
    - Utilisé automatiquement si le modèle principal renvoie une erreur
      de rate-limit (429) ou est indisponible.
"""

import logging
from functools import lru_cache
from typing import Optional

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from groq import RateLimitError, APIStatusError

from app.config import settings

logger = logging.getLogger(__name__)

# Instructions de langue injectées dans le system prompt. On ne compte
# PAS sur le LLM pour deviner tout seul la langue de réponse — on la
# lui impose explicitement, à partir du résultat de language_detector.py.
_LANGUAGE_INSTRUCTIONS = {
    "fr": "Réponds UNIQUEMENT en français.",
    "en": "Réponds UNIQUEMENT en anglais (respond ONLY in English).",
    "ar": "أجب حصراً باللغة العربية الفصحى.",
    "tn": (
        "Réponds UNIQUEMENT en dialecte tunisien (تونسي), dans la même "
        "écriture que le client (lettres arabes s'il a écrit en arabe, "
        "arabizi/latin s'il a écrit en arabizi). N'utilise PAS l'arabe "
        "littéraire ni le français."
    ),
}

BASE_SYSTEM_PROMPT = (
    "Tu es l'assistant IA du service client de \"Liss Strike\", une "
    "boutique tunisienne spécialisée dans l'électronique et les "
    "composants pour makers (cartes programmables, capteurs, modules, "
    "outillage, impression 3D...). Tu aides les clients pour le SAV "
    "(retours, remboursements, livraison, réclamations, garantie) et "
    "les questions e-commerce (produits, prix, disponibilité, paiement). "
    "Sois concis, poli et professionnel.\n\n"
    "RÈGLE ABSOLUE — NE JAMAIS INVENTER : tu n'as accès à aucune base de "
    "commandes, stock ou prix réelle pour l'instant, uniquement au "
    "'Contexte utile' fourni ci-dessous (extrait de la base de "
    "connaissances). N'invente JAMAIS un numéro de commande, une date de "
    "livraison, un statut d'expédition, un lien de suivi, un prix, une "
    "durée de garantie ou une disponibilité qui ne figure pas explicitement "
    "dans ce contexte.\n\n"
    "SI LE CONTEXTE NE RÉPOND PAS À LA QUESTION précise posée (même s'il "
    "parle d'un sujet proche) : dis-le clairement au client (ex: \"je n'ai "
    "pas cette information précise\") et propose de vérifier ou de le "
    "mettre en relation avec un conseiller — NE COMBLE JAMAIS le vide avec "
    "une estimation, une moyenne, ou une réponse 'généralement correcte' "
    "basée sur tes connaissances générales. Une réponse honnête "
    "'je ne sais pas' vaut toujours mieux qu'une information inventée, "
    "même plausible.\n\n"
    "PÉRIMÈTRE STRICT — HORS-SUJET : tu réponds UNIQUEMENT aux questions "
    "liées à Liss Strike (SAV, commandes, livraison, garantie, produits "
    "électroniques, paiement). Si la question du client n'a AUCUN rapport "
    "avec ces sujets (exemples : recettes de cuisine, actualité, "
    "questions personnelles sur toi-même, culture générale, ou tout autre "
    "sujet totalement hors du domaine e-commerce/SAV électronique), réponds "
    "poliment que tu ne peux aider que sur les sujets liés à Liss Strike. "
    "Ne tente JAMAIS de répondre avec tes connaissances générales sur un "
    "sujet hors-scope, même si tu connais la réponse."
)


@lru_cache()
def _get_client(model: str) -> ChatGroq:
    """Un client ChatGroq par modèle, réutilisé entre les appels (lru_cache)."""
    if not settings.GROQ_API_KEY or settings.GROQ_API_KEY == "your_groq_api_key_here":
        raise RuntimeError(
            "GROQ_API_KEY manquante ou non renseignée dans .env. "
            "Récupère une clé gratuite sur https://console.groq.com/keys"
        )
    return ChatGroq(
        api_key=settings.GROQ_API_KEY,
        model=model,
        temperature=0.3,   # peu de créativité : on veut des réponses fiables, pas "inventives"
        max_tokens=1024,
        timeout=15,
    )


def get_llm(model: Optional[str] = None) -> ChatGroq:
    """Retourne un client ChatGroq configuré. Par défaut : modèle principal."""
    return _get_client(model or settings.GROQ_MODEL)


def build_messages(user_text: str, language: str, extra_context: str = "") -> list:
    """Construit la liste de messages (system + user) pour l'appel LLM."""
    lang_instruction = _LANGUAGE_INSTRUCTIONS.get(language, _LANGUAGE_INSTRUCTIONS["fr"])
    system_content = f"{BASE_SYSTEM_PROMPT}\n\n{lang_instruction}"
    if extra_context:
        system_content += f"\n\nContexte utile (base de connaissances) :\n{extra_context}"

    return [
        SystemMessage(content=system_content),
        HumanMessage(content=user_text),
    ]


def ask(user_text: str, language: str = "fr", extra_context: str = "") -> str:
    """
    Envoie un message au LLM et retourne sa réponse texte.
    Bascule automatiquement sur le modèle de secours si le modèle
    principal est rate-limité ou indisponible.
    """
    messages = build_messages(user_text, language, extra_context)

    try:
        llm = get_llm(settings.GROQ_MODEL)
        response = llm.invoke(messages)
        return response.content
    except (RateLimitError, APIStatusError) as e:
        logger.warning(
            f"⚠️ Modèle principal '{settings.GROQ_MODEL}' indisponible ({e}), "
            f"bascule sur '{settings.GROQ_FALLBACK_MODEL}'"
        )
        llm = get_llm(settings.GROQ_FALLBACK_MODEL)
        response = llm.invoke(messages)
        return response.content
