# app/api/web_session.py
"""
Identifiant de session des canaux web (WebSocket /ws et POST /chat/).

Le client web choisit librement son identifiant. Sans préfixe, il
pouvait prendre celui d'une session WhatsApp (le numéro de téléphone) ou
Messenger (le PSID) et rejoindre cette conversation : même clé Redis,
donc même historique, transmis au LLM.

Le préfixe "web:" est ajouté par la route selon le canal réel (la route
appelée), jamais selon ce que le client déclare. Les identifiants
WhatsApp et Messenger, fournis par Meta, restent inchangés : ce sont des
chiffres, ils ne commencent jamais par "web:", donc les deux espaces de
noms ne peuvent pas se recouvrir. Le client continue de voir son
identifiant sans préfixe.

Pour le WebSocket, l'identifiant est en plus attribué par le serveur
(GET /chat/session) et signé (HMAC-SHA256) : /ws refuse un identifiant
sans la signature correspondante. Un client ne peut donc ni choisir son
identifiant ni reprendre celui d'un autre en le devinant.
"""

import hashlib
import hmac
import logging
import secrets
import uuid

from app.config import settings

logger = logging.getLogger(__name__)

WEB_SESSION_PREFIX = "web:"

# Sans WS_SESSION_SECRET dans .env : clé aléatoire propre à ce processus.
# Sûre (personne ne la connaît), mais les identifiants déjà attribués ne
# sont plus valides après un redémarrage (rechargement de la page), et
# plusieurs processus serveur ne partageraient pas la même clé.
_EPHEMERAL_SECRET = secrets.token_hex(32)
if not settings.WS_SESSION_SECRET:
    logger.warning("⚠️ WS_SESSION_SECRET non défini : clé aléatoire de session WebSocket, "
                   "valable jusqu'au prochain redémarrage")


def web_session_id(client_session_id: str) -> str:
    return f"{WEB_SESSION_PREFIX}{client_session_id}"


def _secret() -> bytes:
    return (settings.WS_SESSION_SECRET or _EPHEMERAL_SECRET).encode("utf-8")


def sign_client_id(client_id: str) -> str:
    return hmac.new(_secret(), client_id.encode("utf-8"), hashlib.sha256).hexdigest()


def new_signed_client_id() -> tuple:
    """(client_id, signature) : identifiant aléatoire attribué par le serveur."""
    client_id = str(uuid.uuid4())
    return client_id, sign_client_id(client_id)


def client_id_signature_valid(client_id: str, signature: str | None) -> bool:
    # compare_digest : durée de comparaison indépendante du contenu
    return bool(signature) and hmac.compare_digest(sign_client_id(client_id), signature)
