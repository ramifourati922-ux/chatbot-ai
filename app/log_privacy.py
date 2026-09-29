# app/log_privacy.py
"""
Journaux sans données personnelles ni secrets.

- mask_id : un identifiant de session peut être le numéro de téléphone
  (WhatsApp) ou le PSID (Messenger) du client. Les journaux n'en gardent
  qu'un extrait, suffisant pour recouper deux lignes d'une même session.
- safe_error : les erreurs HTTP de httpx contiennent l'URL complète, qui
  porte le jeton d'accès pour Messenger (?access_token=...). On n'en garde
  que le type et le code HTTP.
- RedactQueryFilter : le journal d'accès d'uvicorn écrit les paramètres
  d'URL (hub.verify_token du webhook Meta, signature de session WebSocket),
  et httpx écrit l'URL de chaque requête sortante, dès le niveau INFO
  (jeton ?access_token=... de l'API Messenger) ; leurs valeurs sont masquées.
- Le journal DEBUG de la bibliothèque Groq contient la requête envoyée au
  LLM, donc toute la conversation : il est plafonné au niveau INFO, même
  si le reste de l'application passe en DEBUG.

Le texte des messages des clients n'est jamais journalisé (seulement en
base, où il est nécessaire).
"""

import logging
import re

import httpx

_SENSITIVE_QUERY = re.compile(r"((?:hub\.verify_token|hub_verify_token|access_token|signature)=)[^&\s\"]+")


def mask_id(identifier) -> str:
    """"21600000021" → "216…21" ; "web:9d093a47-…" → "web:9d09…" ;
    un identifiant court est remplacé par "…"."""
    value = str(identifier or "")
    prefix = "web:" if value.startswith("web:") else ""
    bare = value[len(prefix):]
    if len(bare) <= 6:
        return f"{prefix}…"
    if bare.isdigit():
        return f"{prefix}{bare[:3]}…{bare[-2:]}"
    return f"{prefix}{bare[:4]}…"


def safe_error(error: Exception) -> str:
    """Description d'une erreur sans URL, jeton ni contenu de réponse."""
    if isinstance(error, httpx.HTTPStatusError):
        return f"HTTP {error.response.status_code}"
    if isinstance(error, httpx.HTTPError):
        return type(error).__name__
    return _SENSITIVE_QUERY.sub(r"\1***", f"{type(error).__name__}: {error}")


def _redact_arg(value):
    """Chaîne, ou objet dont le texte porte un paramètre sensible (httpx
    journalise un objet httpx.URL, pas une chaîne)."""
    if value is None or isinstance(value, (int, float, bool)):
        return value
    text = value if isinstance(value, str) else str(value)
    redacted = _SENSITIVE_QUERY.sub(r"\1***", text)
    return redacted if (redacted != text or isinstance(value, str)) else value


class RedactQueryFilter(logging.Filter):
    """Masque les valeurs des paramètres sensibles dans les journaux d'uvicorn."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple):
            record.args = tuple(_redact_arg(a) for a in record.args)
        if isinstance(record.msg, str):
            record.msg = _SENSITIVE_QUERY.sub(r"\1***", record.msg)
        return True


def install_log_filters() -> None:
    for name in ("uvicorn.access", "uvicorn.error", "httpx"):
        logger = logging.getLogger(name)
        if not any(isinstance(f, RedactQueryFilter) for f in logger.filters):
            logger.addFilter(RedactQueryFilter())
    logging.getLogger("groq").setLevel(logging.INFO)
