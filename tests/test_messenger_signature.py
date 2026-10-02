# tests/test_messenger_signature.py
"""
Webhook Messenger : aucune requête acceptée sans signature Meta vérifiée,
comme pour WhatsApp (tests/test_whatsapp_signature.py).

- MESSENGER_APP_SECRET absent : toute requête POST est refusée (403), même
  signée (avant : acceptée sans vérification, avec un simple avertissement) ;
- canal Messenger configuré sans ce secret : l'API refuse de démarrer ;
- écho des messages envoyés par la page (is_echo) : jamais traité, sinon
  le bot se répondrait à lui-même en boucle.
handle_message est remplacé par un bouchon : ni Groq, ni base, ni envoi.
"""

import hashlib
import hmac
import json
from types import SimpleNamespace

import httpx
import pytest
import pytest_asyncio

from app import main
from app.api.routes import messenger as ms_route
from app.config import Settings, settings
from app.main import app

TEST_SECRET = "cle-de-test-webhook-messenger"
PSID = "9900000000000001"  # fictif


def _payload(text="bonjour", is_echo=False):
    message = {"mid": "m_1", "text": text}
    if is_echo:
        message["is_echo"] = True
    return {"object": "page", "entry": [{"messaging": [{"sender": {"id": PSID}, "message": message}]}]}


def _signed(payload, secret=TEST_SECRET):
    body = json.dumps(payload).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return body, {"Content-Type": "application/json", "X-Hub-Signature-256": f"sha256={signature}"}


calls, sent = [], []


async def _fake_handle_message(message, session_id=None, channel="web"):
    calls.append((session_id, channel))
    return SimpleNamespace(response="écho", handled_by_agent=False)


async def _fake_send(psid, text):
    sent.append(psid)


@pytest.fixture(autouse=True)
def stub(monkeypatch):
    calls.clear()
    sent.clear()
    monkeypatch.setattr(ms_route, "handle_message", _fake_handle_message)
    monkeypatch.setattr(ms_route, "_send_messenger_message", _fake_send)  # aucun envoi réel
    monkeypatch.setattr(settings, "MESSENGER_APP_SECRET", TEST_SECRET)


@pytest_asyncio.fixture
async def client():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def _post(client, body, headers):
    return (await client.post("/webhook/messenger", content=body, headers=headers)).status_code


@pytest.mark.asyncio
async def test_signed_request_is_accepted(client):
    assert await _post(client, *_signed(_payload())) == 200
    assert calls == [(PSID, "messenger")]
    assert sent == [PSID]


@pytest.mark.asyncio
async def test_wrong_or_missing_signature_is_refused(client):
    body, headers = _signed(_payload())
    assert await _post(client, body, {**headers, "X-Hub-Signature-256": "sha256=" + "0" * 64}) == 403
    assert await _post(client, body, {"Content-Type": "application/json"}) == 403
    assert await _post(client, *_signed(_payload(), secret="un-autre-secret")) == 403
    assert calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", [None, ""])
async def test_request_is_refused_when_app_secret_is_missing(client, monkeypatch, missing):
    """Avant : sans secret, la requête était acceptée sans vérification."""
    body, headers = _signed(_payload())  # même une requête « bien signée »
    monkeypatch.setattr(settings, "MESSENGER_APP_SECRET", missing)
    assert await _post(client, body, headers) == 403
    assert calls == []


@pytest.mark.asyncio
async def test_echo_of_the_page_own_message_is_ignored(client):
    assert await _post(client, *_signed(_payload("réponse du bot", is_echo=True))) == 200
    assert calls == [] and sent == []  # ni traitement ni réponse : pas de boucle


@pytest.mark.parametrize("configured", [{"MESSENGER_VERIFY_TOKEN": "x"}, {"MESSENGER_PAGE_ACCESS_TOKEN": "x"}])
def test_messenger_channel_is_enabled_by_any_meta_identifier(configured):
    base = {"DATABASE_URL": "postgresql+asyncpg://x/y", "MESSENGER_VERIFY_TOKEN": None,
            "MESSENGER_PAGE_ACCESS_TOKEN": None}
    assert Settings(**{**base, **configured}).messenger_enabled is True
    assert Settings(**base).messenger_enabled is False


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", [None, ""])
async def test_api_refuses_to_start_when_messenger_is_configured_without_app_secret(monkeypatch, missing):
    async def accounts_ok():
        return "exists"

    import app.services.agent_auth as agent_auth
    monkeypatch.setattr(agent_auth, "bootstrap_admin_if_needed", accounts_ok)
    monkeypatch.setattr(settings, "WHATSAPP_PHONE_NUMBER_ID", None)  # isole le contrôle Messenger
    monkeypatch.setattr(settings, "WHATSAPP_ACCESS_TOKEN", None)
    monkeypatch.setattr(settings, "WHATSAPP_VERIFY_TOKEN", None)
    monkeypatch.setattr(settings, "MESSENGER_VERIFY_TOKEN", "jeton-de-verification-de-test")
    monkeypatch.setattr(settings, "MESSENGER_APP_SECRET", missing)
    with pytest.raises(RuntimeError, match="MESSENGER_APP_SECRET"):
        async with main.lifespan(app):
            pass
