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
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from app.services.agent_auth import AuthenticatedAgent, authenticate

REALM = "Liss Strike - conseillers"
# auto_error=True : sans en-tête Authorization, FastAPI répond déjà 401
# avec WWW-Authenticate (le navigateur affiche son invite de connexion).
_security = HTTPBasic(realm=REALM)


async def require_agent(credentials: HTTPBasicCredentials = Depends(_security)) -> AuthenticatedAgent:
    agent = await authenticate(credentials.username, credentials.password)
    if agent is None:
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
