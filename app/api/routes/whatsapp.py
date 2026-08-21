# app/api/routes/whatsapp.py
"""
Webhook WhatsApp Business Cloud API — canal d'entrée "whatsapp" pour
le chatbot Liss Strike, branché sur le même moteur que le canal web
(dialogue_manager.handle_message), rien d'autre n'est dupliqué ici.

Deux endpoints exigés par Meta :
- GET  /webhook/whatsapp : vérification lors de la configuration du
  webhook dans l'interface Meta Developer (une seule fois, à la mise
  en place).
- POST /webhook/whatsapp : réception des messages entrants en continu
  + envoi de la réponse via l'API Graph.

Référence format JSON officiel (WhatsApp Cloud API, webhooks) :
https://developers.facebook.com/docs/whatsapp/cloud-api/webhooks/payload-examples
"""

import hashlib
import hmac
import logging

import httpx
from fastapi import APIRouter, Request, Response
from fastapi.responses import PlainTextResponse

from app.config import settings
from app.services.dialogue_manager import handle_message

router = APIRouter(prefix="/webhook/whatsapp", tags=["WhatsApp"])
logger = logging.getLogger(__name__)

GRAPH_API_VERSION = "v18.0"


@router.get("")
async def verify_webhook(request: Request):
    """
    Étape de vérification exigée par Meta lors de la configuration du
    webhook (Meta Developer > WhatsApp > Configuration > Webhook > Verify
    and save). Meta appelle ce endpoint en GET avec 3 query params
    (hub.mode, hub.verify_token, hub.challenge) et attend que
    hub.challenge soit renvoyé tel quel, en texte brut, SI
    hub.verify_token correspond à la valeur secrète qu'on a nous-même
    choisie et saisie dans leur interface (WHATSAPP_VERIFY_TOKEN).

    Les noms de params contiennent un point ("hub.mode") donc on lit
    directement request.query_params plutôt que des paramètres de
    fonction typés (qui ne peuvent pas s'appeler "hub.mode" en Python).
    """
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and settings.WHATSAPP_VERIFY_TOKEN and token == settings.WHATSAPP_VERIFY_TOKEN:
        logger.info("✅ Webhook WhatsApp vérifié par Meta")
        return PlainTextResponse(content=challenge or "", status_code=200)

    logger.warning(f"❌ Échec vérification webhook WhatsApp (mode={mode})")
    return Response(status_code=403)


def _verify_signature(raw_body: bytes, signature_header: str) -> bool:
    """
    Vérifie que la requête vient bien de Meta et n'a pas été altérée en
    chemin, via la signature HMAC-SHA256 du corps brut (header
    X-Hub-Signature-256), calculée avec le secret d'application
    (WHATSAPP_APP_SECRET, connu uniquement de nous et de Meta).

    Pourquoi c'est nécessaire : ce webhook est forcément une URL
    publique (Meta doit pouvoir l'appeler depuis internet). Sans cette
    vérification, n'importe qui connaissant l'URL pourrait poster de
    faux messages — usurper un client, déclencher des escalades
    bidon, faire consommer inutilement le quota Groq/ChromaDB, ou
    injecter du contenu arbitraire traité comme un vrai message client.
    """
    if not settings.WHATSAPP_APP_SECRET:
        logger.warning(
            "⚠️ WHATSAPP_APP_SECRET non configuré — signature NON vérifiée "
            "(acceptable uniquement en dev sans webhook public exposé)"
        )
        return True
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(
        settings.WHATSAPP_APP_SECRET.encode("utf-8"), raw_body, hashlib.sha256
    ).hexdigest()
    received = signature_header.removeprefix("sha256=")
    # compare_digest plutôt que == : évite une fuite d'info par timing
    # attack sur la comparaison caractère par caractère.
    return hmac.compare_digest(expected, received)


async def _send_whatsapp_message(to: str, text: str) -> None:
    """Envoie la réponse du bot au client via l'API Graph de Meta.
    Toute erreur ici est remontée à l'appelant (receive_message), qui
    la logue sans jamais faire échouer la réponse au webhook."""
    if not settings.WHATSAPP_ACCESS_TOKEN or not settings.WHATSAPP_PHONE_NUMBER_ID:
        logger.warning(
            "⚠️ WHATSAPP_ACCESS_TOKEN/WHATSAPP_PHONE_NUMBER_ID non configurés — "
            "envoi simulé (pas de compte WhatsApp Business réel pour l'instant)"
        )
        return

    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}"}
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text},
    }
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()


@router.post("")
async def receive_message(request: Request):
    """
    Réception des messages WhatsApp entrants.

    Retourne TOUJOURS 200 rapidement, même en cas d'erreur interne
    (parsing, RAG, envoi de la réponse...) : Meta désactive
    automatiquement un webhook qui répond trop lentement ou avec des
    erreurs répétées — mieux vaut logguer l'erreur côté serveur que de
    risquer une désactivation du canal entier.
    """
    raw_body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")

    if not _verify_signature(raw_body, signature):
        logger.warning("❌ Signature WhatsApp invalide — requête rejetée")
        return Response(status_code=403)

    try:
        payload = await request.json()
    except Exception:
        logger.warning("⚠️ Corps de requête WhatsApp non-JSON, ignoré")
        return Response(status_code=200)

    try:
        entry = (payload.get("entry") or [{}])[0]
        change = (entry.get("changes") or [{}])[0]
        value = change.get("value", {})
        messages = value.get("messages")

        if not messages:
            # Pas un message entrant : notification de statut (delivered,
            # read, sent...) ou autre événement du webhook. Rien à
            # traiter, mais ce n'est pas une erreur — Meta envoie ça en
            # continu et attend 200 à chaque fois.
            return Response(status_code=200)

        message_data = messages[0]
        from_number = message_data.get("from")
        text_body = (message_data.get("text") or {}).get("body")

        if not from_number or not text_body:
            # Message sans texte (image, audio, sticker, réaction...) —
            # non géré pour l'instant, on ignore proprement.
            logger.info("ℹ️ Message WhatsApp non-texte reçu, ignoré")
            return Response(status_code=200)

        result = await handle_message(
            message=text_body, session_id=from_number, channel="whatsapp"
        )

        try:
            await _send_whatsapp_message(from_number, result.response)
        except Exception as e:
            logger.error(f"❌ Échec envoi réponse WhatsApp à {from_number}: {e}")

    except Exception as e:
        logger.error(f"❌ Erreur traitement webhook WhatsApp: {e}", exc_info=True)

    return Response(status_code=200)
