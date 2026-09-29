# tests/test_chat_session_signature.py
"""
POST /chat/ : identifiant de session attribué et signé par le serveur,
comme pour /ws (voir app/api/web_session.py).

Avant : le session_id était choisi par le client et accepté tel quel ;
qui connaissait l'identifiant d'un autre client web pouvait reprendre sa
session (son historique, transmis au LLM). Désormais :
- sans session_id : le serveur en attribue un et renvoie sa signature ;
- avec session_id : la signature correspondante est exigée, sinon 403 et
  rien n'est traité.
handle_message est remplacé par un bouchon : ni Groq, ni Redis, ni base.
"""

import uuid
from types import SimpleNamespace

import httpx
import pytest
import pytest_asyncio

from app.api import rate_limit
from app.api.routes import chat as chat_route
from app.api.web_session import sign_client_id
from app.config import settings
from app.main import app

calls = []


async def _fake_handle_message(message, session_id=None, channel="web"):
    calls.append(session_id)
    return SimpleNamespace(
        response="écho", intent="general", confidence=0.9, sources=[], processing_time_ms=1,
        escalated=False, escalation_reason=None, handled_by_agent=False,
    )


@pytest.fixture(autouse=True)
def stub(monkeypatch):
    calls.clear()
    monkeypatch.setattr(chat_route, "handle_message", _fake_handle_message)
    rate_limit.reset()
    yield
    rate_limit.reset()


@pytest_asyncio.fixture
async def client():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def _post(client, **fields):
    return await client.post("/chat/", json={"message": "bonjour", **fields})


@pytest.mark.asyncio
async def test_server_issues_a_signed_session_and_accepts_it_back(client):
    first = (await _post(client)).json()
    uuid.UUID(first["session_id"])  # identifiant aléatoire attribué par le serveur
    assert first["session_signature"] == sign_client_id(first["session_id"])
    again = await _post(client, session_id=first["session_id"], session_signature=first["session_signature"])
    assert again.status_code == 200
    assert again.json()["session_id"] == first["session_id"]  # même conversation
    assert calls == [f"web:{first['session_id']}"] * 2


@pytest.mark.asyncio
async def test_each_new_session_gets_its_own_id(client):
    first, second = (await _post(client)).json(), (await _post(client)).json()
    assert first["session_id"] != second["session_id"]


@pytest.mark.asyncio
async def test_session_from_get_chat_session_is_valid_on_post_chat(client):
    """Même clé que /ws : l'identifiant de GET /chat/session vaut aussi ici."""
    session = (await client.get("/chat/session")).json()
    response = await _post(client, session_id=session["client_id"], session_signature=session["signature"])
    assert response.status_code == 200
    assert calls == [f"web:{session['client_id']}"]


@pytest.mark.asyncio
@pytest.mark.parametrize("signature", [None, "", "0" * 64, "fausse"])
async def test_session_id_without_valid_signature_is_refused(client, signature):
    """L'ancien fonctionnement : un identifiant choisi par le client."""
    fields = {"session_id": str(uuid.uuid4())}
    if signature is not None:
        fields["session_signature"] = signature
    response = await _post(client, **fields)
    assert response.status_code == 403
    assert calls == []  # aucun message traité


@pytest.mark.asyncio
async def test_signature_of_another_session_is_refused(client):
    """Un client qui connaît sa propre signature ne peut pas l'utiliser pour
    l'identifiant d'un autre client (deviné ou volé)."""
    mine = (await _post(client)).json()
    calls.clear()
    for other in (str(uuid.uuid4()), mine["session_id"] + "x", "21600000099"):
        response = await _post(client, session_id=other, session_signature=mine["session_signature"])
        assert response.status_code == 403
    assert calls == []


@pytest.mark.asyncio
async def test_signature_depends_on_the_configured_secret(client, monkeypatch):
    signed_with_other_key = (await _post(client)).json()
    monkeypatch.setattr(settings, "WS_SESSION_SECRET", "une-autre-cle-secrete")
    response = await _post(client, session_id=signed_with_other_key["session_id"],
                           session_signature=signed_with_other_key["session_signature"])
    assert response.status_code == 403
