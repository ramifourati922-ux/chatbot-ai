# app/api/auth.py
"""
Authentification HTTP Basic des conseillers (routes /admin et /users/).

Chaque conseiller a ses propres identifiants, vérifiés contre la table
agents (voir app/services/agent_auth.py). Le conseiller authentifié est
fourni aux routes : les réponses, prises en main et résolutions lui sont
rattachées (traçabilité).

- require_agent : tout conseiller actif (rôles "conseiller" et "admin") ;
- require_admin : rôle "admin" seulement (gestion des comptes, /users/).

HTTP Basic transmet les identifiants encodés (base64), non chiffrés :
HTTPS obligatoire en production.

Essais de mot de passe : après RATE_LIMIT_LOGIN_FAILURES échecs (par IP
ou par identifiant), toute tentative est refusée en 429, mot de passe
correct compris, jusqu'à la fin de la fenêtre (voir rate_limit.py).
"""

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from app.api import rate_limit
from app.services.agent_auth import AuthenticatedAgent, authenticate

REALM = "Liss Strike - conseillers"
# auto_error=True : sans en-tête Authorization, FastAPI répond déjà 401
# avec WWW-Authenticate (le navigateur affiche son invite de connexion).
_security = HTTPBasic(realm=REALM)


async def require_agent(request: Request,
                        credentials: HTTPBasicCredentials = Depends(_security)) -> AuthenticatedAgent:
    ip = request.client.host if request.client else "inconnue"
    if rate_limit.login_blocked(ip, credentials.username):
        # Vérifié AVANT le mot de passe : pendant le blocage, même le bon
        # mot de passe est refusé (sinon le blocage ne ralentirait rien).
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Trop de tentatives de connexion échouées. Réessayez dans quelques minutes.",
        )
    agent = await authenticate(credentials.username, credentials.password)
    if agent is None:
        rate_limit.login_failed(ip, credentials.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiants incorrects",
            headers={"WWW-Authenticate": f'Basic realm="{REALM}"'},
        )
    return agent


async def require_admin(agent: AuthenticatedAgent = Depends(require_agent)) -> AuthenticatedAgent:
    if agent.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Réservé au rôle admin")
    return agent
