# app/api/routes/messenger.py
"""
Webhook Facebook Messenger Platform — canal d'entrée "messenger" pour
le chatbot Liss Strike, branché sur le même dialogue_manager.handle_message()
que les canaux web et whatsapp (voir routes/whatsapp.py pour le
webhook jumeau côté WhatsApp — même principe général, format Meta
différent).

Deux endpoints exigés par Meta :
- GET  /webhook/messenger : vérification lors de la configuration du
  webhook dans l'interface Meta Developer.
- POST /webhook/messenger : réception des messages entrants + envoi
  de la réponse via la Messenger Send API.

Référence format JSON officiel (Messenger Platform, webhook events) :
https://developers.facebook.com/docs/messenger-platform/webhooks
"""

import hashlib
import hmac
import logging

import httpx
from fastapi import APIRouter, Request, Response
from fastapi.responses import PlainTextResponse

from app.config import settings
from app.services.dialogue_manager import handle_message

router = APIRouter(prefix="/webhook/messenger", tags=["Messenger"])
logger = logging.getLogger(__name__)

GRAPH_API_VERSION = "v18.0"


@router.get("")
async def verify_webhook(request: Request):
    """
    Vérification du webhook (Meta Developer > Messenger > Configuration
    du webhook). Même principe que WhatsApp : Meta appelle GET avec
    hub.mode/hub.verify_token/hub.challenge, on renvoie hub.challenge
    tel quel en texte brut si le token correspond à MESSENGER_VERIFY_TOKEN
    (volontairement distinct de WHATSAPP_VERIFY_TOKEN — chaque produit
    Meta a sa propre configuration de webhook, même si les 2 peuvent
    vivre sur la même app Meta Developer).
    """
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and settings.MESSENGER_VERIFY_TOKEN and token == settings.MESSENGER_VERIFY_TOKEN:
        logger.info("✅ Webhook Messenger vérifié par Meta")
        return PlainTextResponse(content=challenge or "", status_code=200)

    logger.warning(f"❌ Échec vérification webhook Messenger (mode={mode})")
    return Response(status_code=403)


def _verify_signature(raw_body: bytes, signature_header: str) -> bool:
    """Même vérification et même raison que pour WhatsApp (voir
    routes/whatsapp.py::_verify_signature) : le webhook est une URL
    publique, seule la signature HMAC-SHA256 (secret MESSENGER_APP_SECRET)
    garantit que la requête vient bien de Meta et n'a pas été altérée."""
    if not settings.MESSENGER_APP_SECRET:
        logger.warning(
            "⚠️ MESSENGER_APP_SECRET non configuré — signature NON vérifiée "
            "(acceptable uniquement en dev sans webhook public exposé)"
        )
        return True
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(
        settings.MESSENGER_APP_SECRET.encode("utf-8"), raw_body, hashlib.sha256
    ).hexdigest()
    received = signature_header.removeprefix("sha256=")
    return hmac.compare_digest(expected, received)


async def _send_messenger_message(psid: str, text: str) -> None:
    """Envoie la réponse du bot via la Messenger Send API. Contrairement
    à l'API Graph WhatsApp (token en header Authorization), la Send API
    Messenger attend le token en query param access_token — c'est le
    format documenté par Meta, pas un choix arbitraire."""
    if not settings.MESSENGER_PAGE_ACCESS_TOKEN:
        logger.warning(
            "⚠️ MESSENGER_PAGE_ACCESS_TOKEN non configuré — envoi simulé "
            "(pas de Page Facebook réelle configurée pour l'instant)"
        )
        return

    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/me/messages"
    payload = {
        "recipient": {"id": psid},
        "message": {"text": text},
    }
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            url,
            params={"access_token": settings.MESSENGER_PAGE_ACCESS_TOKEN},
            json=payload,
        )
        response.raise_for_status()


@router.post("")
async def receive_message(request: Request):
    """
    Réception des messages Messenger entrants. Retourne TOUJOURS 200
    rapidement, même en cas d'erreur interne — mêmes raisons que pour
    WhatsApp (Meta désactive un webhook trop lent ou trop en erreur).
    """
    raw_body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")

    if not _verify_signature(raw_body, signature):
        logger.warning("❌ Signature Messenger invalide — requête rejetée")
        return Response(status_code=403)

    try:
        payload = await request.json()
    except Exception:
        logger.warning("⚠️ Corps de requête Messenger non-JSON, ignoré")
        return Response(status_code=200)

    try:
        entry = (payload.get("entry") or [{}])[0]
        messaging_events = entry.get("messaging") or []

        if not messaging_events:
            # Pas d'événement de message (peut arriver sur d'autres
            # types d'entry) — rien à traiter, mais pas une erreur.
            return Response(status_code=200)

        event = messaging_events[0]
        psid = (event.get("sender") or {}).get("id")
        message_data = event.get("message") or {}
        text_body = message_data.get("text")

        if message_data.get("is_echo"):
            # Écho d'un message envoyé PAR la page (ex: notre propre
            # réponse renvoyée en écho par Messenger) — jamais un
            # message client, à ignorer pour éviter une boucle infinie.
            return Response(status_code=200)

        if not psid or not text_body:
            # Événement sans texte (postback de bouton, media, "seen",
            # "delivery"...) — non géré pour l'instant, ignoré proprement.
            logger.info("ℹ️ Événement Messenger non-texte reçu, ignoré")
            return Response(status_code=200)

        result = await handle_message(
            message=text_body, session_id=psid, channel="messenger"
        )

        try:
            await _send_messenger_message(psid, result.response)
        except Exception as e:
            logger.error(f"❌ Échec envoi réponse Messenger à {psid}: {e}")

    except Exception as e:
        logger.error(f"❌ Erreur traitement webhook Messenger: {e}", exc_info=True)

    return Response(status_code=200)
