# app/api/rate_limit.py
"""
Limitation de débit par adresse IP : POST /chat/, /users/ et /ws.

- HTTP : slowapi (décorateurs sur les routes, réponse 429).
- WebSocket : slowapi ne s'applique qu'aux requêtes HTTP (son décorateur
  exige un objet Request) → compteurs manuels ci-dessous : connexions
  simultanées par IP, et messages par IP sur une fenêtre glissante, avec
  le même moteur (bibliothèque `limits`) et le même stockage que slowapi.

Stockage en mémoire : propre à ce processus (un seul worker uvicorn),
remis à zéro au redémarrage. Les limites sont lues dans la configuration
à chaque requête (valeurs du .env, modifiables dans les tests).

Clé = IP de la connexion TCP (request.client.host). Derrière un proxy
(ngrok…), tous les visiteurs partagent l'IP du proxy, donc la même
limite. X-Forwarded-For n'est pas lu : n'importe quel client peut le
falsifier pour contourner la limite.
"""

from collections import Counter

from fastapi import Request
from fastapi.responses import JSONResponse
from limits import parse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import settings

# Fenêtre glissante plutôt que fixe : pas de rafale possible à cheval
# sur deux fenêtres (20 requêtes en fin de minute + 20 au début de la suivante).
limiter = Limiter(key_func=get_remote_address, strategy="moving-window")


def chat_limit() -> str:
    return settings.RATE_LIMIT_CHAT


def users_limit() -> str:
    return settings.RATE_LIMIT_USERS


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": f"Trop de requêtes (limite : {exc.detail}). Réessayez dans un instant."},
    )


# ── WebSocket ───────────────────────────────────────────────────────────

WS_POLICY_VIOLATION = 1008  # code de fermeture WebSocket standard (RFC 6455)

_ws_connections: Counter = Counter()


def ws_connection_opened(ip: str) -> bool:
    """Enregistre une connexion ; False si l'IP a déjà atteint le maximum
    de connexions simultanées (la connexion n'est alors pas comptée)."""
    if _ws_connections[ip] >= settings.RATE_LIMIT_WS_CONNECTIONS:
        return False
    _ws_connections[ip] += 1
    return True


def ws_connection_closed(ip: str) -> None:
    _ws_connections[ip] -= 1
    if _ws_connections[ip] <= 0:
        del _ws_connections[ip]


def ws_message_allowed(ip: str) -> bool:
    """Compte un message ; False au-delà de RATE_LIMIT_WS_MESSAGES (toutes
    les connexions de l'IP confondues : en ouvrir d'autres ne contourne pas
    la limite)."""
    return limiter.limiter.hit(parse(settings.RATE_LIMIT_WS_MESSAGES), "ws-messages", ip)


def reset() -> None:
    """Remet tous les compteurs à zéro (tests)."""
    limiter.reset()
    _ws_connections.clear()
