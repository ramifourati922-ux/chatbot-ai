# tests/test_whatsapp_signature.py
"""
Webhook WhatsApp : aucune requête acceptée sans signature Meta vérifiée.

- WHATSAPP_APP_SECRET absent : toute requête POST est refusée (403), même
  signée (avant : acceptée sans vérification, avec un simple avertissement) ;
- canal WhatsApp configuré sans ce secret : l'API refuse de démarrer.
handle_message est remplacé par un bouchon : ni Groq, ni base, ni envoi.
"""

from types import SimpleNamespace

import httpx
import pytest
import pytest_asyncio

from app import main
from app.api.routes import whatsapp as wa_route
from app.config import Settings, settings
from app.main import app

PAYLOAD = {"entry": [{"changes": [{"value": {"messages": [
    {"from": "21600000088", "type": "text", "text": {"body": "bonjour"}}]}}]}]}  # numéro fictif

calls = []


async def _fake_handle_message(message, session_id=None, channel="web"):
    calls.append(session_id)
    return SimpleNamespace(response="écho", handled_by_agent=False)


@pytest.fixture(autouse=True)
def stub(monkeypatch):
    calls.clear()
    monkeypatch.setattr(wa_route, "handle_message", _fake_handle_message)
    monkeypatch.setattr(settings, "WHATSAPP_ACCESS_TOKEN", None)  # aucun envoi réel


@pytest_asyncio.fixture
async def client():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_signed_request_is_accepted(client, sign_whatsapp):
    body, headers = sign_whatsapp(PAYLOAD)
    assert (await client.post("/webhook/whatsapp", content=body, headers=headers)).status_code == 200
    assert calls == ["21600000088"]


@pytest.mark.asyncio
async def test_wrong_or_missing_signature_is_refused(client, sign_whatsapp):
    body, headers = sign_whatsapp(PAYLOAD)
    forged = {**headers, "X-Hub-Signature-256": "sha256=" + "0" * 64}
    assert (await client.post("/webhook/whatsapp", content=body, headers=forged)).status_code == 403
    unsigned = {"Content-Type": "application/json"}
    assert (await client.post("/webhook/whatsapp", content=body, headers=unsigned)).status_code == 403
    assert calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", [None, ""])
async def test_request_is_refused_when_app_secret_is_missing(client, sign_whatsapp, monkeypatch, missing):
    """Avant : sans secret, la requête était acceptée sans vérification."""
    body, headers = sign_whatsapp(PAYLOAD)  # même une requête « bien signée »
    monkeypatch.setattr(settings, "WHATSAPP_APP_SECRET", missing)
    assert (await client.post("/webhook/whatsapp", content=body, headers=headers)).status_code == 403
    assert calls == []


@pytest.mark.parametrize("configured", [
    {"WHATSAPP_VERIFY_TOKEN": "x"}, {"WHATSAPP_ACCESS_TOKEN": "x"}, {"WHATSAPP_PHONE_NUMBER_ID": "1"},
])
def test_whatsapp_channel_is_enabled_by_any_meta_identifier(configured):
    base = {"DATABASE_URL": "postgresql+asyncpg://x/y", "WHATSAPP_VERIFY_TOKEN": None,
            "WHATSAPP_ACCESS_TOKEN": None, "WHATSAPP_PHONE_NUMBER_ID": None}
    assert Settings(**{**base, **configured}).whatsapp_enabled is True
    assert Settings(**base).whatsapp_enabled is False


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", [None, ""])
async def test_api_refuses_to_start_when_whatsapp_is_configured_without_app_secret(monkeypatch, missing):
    async def accounts_ok():
        return "exists"

    import app.services.agent_auth as agent_auth
    monkeypatch.setattr(agent_auth, "bootstrap_admin_if_needed", accounts_ok)
    monkeypatch.setattr(settings, "WHATSAPP_VERIFY_TOKEN", "jeton-de-verification-de-test")
    monkeypatch.setattr(settings, "WHATSAPP_APP_SECRET", missing)
    with pytest.raises(RuntimeError, match="WHATSAPP_APP_SECRET"):
        async with main.lifespan(app):
            pass
