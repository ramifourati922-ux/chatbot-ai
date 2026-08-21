# app/api/routes/websocket.py
"""
Canal WebSocket — chat web temps réel, branché sur le même
dialogue_manager.handle_message() que web (HTTP), whatsapp et
messenger. Utilisé par static/chat.html (Tâche 4) mais utilisable par
n'importe quel client WebSocket.

Différence avec POST /chat/ : la connexion reste ouverte, chaque
message est traité et répondu immédiatement sans round-trip HTTP
complet à chaque tour — plus adapté à une interface de chat "live"
qu'à des appels API ponctuels.

Le ConnectionManager ne stocke QUE les connexions WebSocket actives en
mémoire (par client_id) — c'est un détail de transport propre à ce
process serveur, pas de l'état métier. L'état de conversation
(historique, compteur anti-boucle) continue de vivre dans Redis via
session_manager, exactement comme pour les autres canaux : si le
serveur redémarre, les connexions WebSocket tombent (le client doit se
reconnecter) mais la session/l'historique survit.
"""

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.dialogue_manager import handle_message

router = APIRouter(tags=["WebSocket"])
logger = logging.getLogger(__name__)


class ConnectionManager:
    """Registre en mémoire des connexions WebSocket actives, par
    client_id. Pas besoin de Redis ici : une connexion WebSocket est
    intrinsèquement liée à un process serveur unique (contrairement à
    la session de conversation, qui doit survivre à un redémarrage et
    être partageable entre plusieurs canaux/process)."""

    def __init__(self):
        self._connections: dict[str, WebSocket] = {}

    async def connect(self, client_id: str, websocket: WebSocket):
        await websocket.accept()
        self._connections[client_id] = websocket
        logger.info(f"🔌 WebSocket connecté : {client_id} ({len(self._connections)} actif(s))")

    def disconnect(self, client_id: str):
        self._connections.pop(client_id, None)
        logger.info(f"🔌 WebSocket déconnecté : {client_id} ({len(self._connections)} actif(s))")


manager = ConnectionManager()


@router.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """
    Boucle de vie d'une connexion WebSocket : accepte, reçoit les
    messages texte du client un par un, appelle handle_message() avec
    client_id comme session_id (cohérent : même client_id → même
    session → historique et compteur anti-boucle conservés d'un
    message à l'autre), renvoie la réponse complète en JSON (mêmes
    champs que ChatResponse pour l'endpoint HTTP existant).
    """
    await manager.connect(client_id, websocket)
    try:
        while True:
            message = await websocket.receive_text()

            result = await handle_message(
                message=message, session_id=client_id, channel="web"
            )

            await websocket.send_json({
                "response": result.response,
                "session_id": result.session_id,
                "intent": result.intent,
                "confidence": result.confidence,
                "sources": [s for s in result.sources if s],
                "processing_time_ms": result.processing_time_ms,
                "escalated": result.escalated,
                "escalation_reason": result.escalation_reason,
            })
    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        # Une erreur inattendue ne doit pas laisser le socket dans un
        # état incohérent côté serveur — on nettoie le registre puis on
        # relance pour qu'elle soit visible dans les logs (contrairement
        # aux webhooks Meta, il n'y a pas de contrainte "toujours 200"
        # ici : le client WebSocket verra la connexion se fermer).
        logger.error(f"❌ Erreur WebSocket client={client_id}: {e}", exc_info=True)
        manager.disconnect(client_id)
        raise
