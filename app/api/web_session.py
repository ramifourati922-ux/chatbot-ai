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
"""

WEB_SESSION_PREFIX = "web:"


def web_session_id(client_session_id: str) -> str:
    return f"{WEB_SESSION_PREFIX}{client_session_id}"
