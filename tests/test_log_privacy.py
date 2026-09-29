# tests/test_log_privacy.py
"""
Journaux sans données personnelles ni secrets : journal SQL désactivé par
défaut (et sans valeurs même activé), identifiants masqués, erreurs HTTP
sans URL (jeton Messenger), paramètres sensibles masqués dans le journal
d'accès d'uvicorn, texte des messages jamais journalisé.
"""

import logging

import httpx
import pytest

from app.config import Settings
from app.db import database
from app.log_privacy import RedactQueryFilter, install_log_filters, mask_id, safe_error
from app.services.dialogue_manager import handle_message, wait_for_pending_persistence

PHONE = "21600000077"  # fictif (règle 216000000xx de cleanup_test_data.py)


def test_sql_echo_is_off_by_default_and_never_shows_values():
    assert Settings(DATABASE_URL="postgresql+asyncpg://x/y").SQL_ECHO is False
    assert database.engine.echo is False
    assert database.engine.sync_engine.hide_parameters is True


@pytest.mark.parametrize("identifier,expected", [
    ("21600000021", "216…21"),
    ("web:9d093a47-168f-43c1-981a-ab3120b4986a", "web:9d09…"),
    ("test-memory-41e3179d", "test…"),
    ("abc", "…"),
    (None, "…"),
])
def test_mask_id(identifier, expected):
    assert mask_id(identifier) == expected


def test_http_error_does_not_leak_the_url_nor_the_token():
    request = httpx.Request("POST", "https://graph.facebook.com/v18.0/me/messages?access_token=faux-jeton-test")
    with pytest.raises(httpx.HTTPStatusError) as raised:  # comme response.raise_for_status() dans messenger.py
        httpx.Response(400, request=request).raise_for_status()
    error = raised.value
    assert "faux-jeton-test" in str(error)  # le message d'origine contient bien le jeton
    assert safe_error(error) == "HTTP 400"
    assert "faux-jeton-test" not in safe_error(RuntimeError("échec ?access_token=faux-jeton-test&x=1"))


def test_uvicorn_access_log_masks_sensitive_query_parameters():
    record = logging.LogRecord(
        "uvicorn.access", logging.INFO, __file__, 1, '%s - "%s %s HTTP/%s" %d',
        ("2a03:2880::1", "GET", "/webhook/whatsapp?hub.mode=subscribe&hub.verify_token=mon-jeton&hub.challenge=42",
         "1.1", 200), None,
    )
    RedactQueryFilter().filter(record)
    line = record.getMessage()
    assert "mon-jeton" not in line and "hub.verify_token=***" in line and "hub.challenge=42" in line

    ws = logging.LogRecord("uvicorn.error", logging.INFO, __file__, 1, '%s - "WebSocket %s" [accepted]',
                           ("127.0.0.1", "/ws/abc?signature=0123456789abcdef"), None)
    RedactQueryFilter().filter(ws)
    assert "0123456789abcdef" not in ws.getMessage()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_dialogue_logs_neither_the_phone_number_nor_the_message(caplog):
    """Au niveau DEBUG (le plus bavard), avec les filtres de l'application."""
    install_log_filters()
    await database.engine.dispose(close=False)
    secret_text = "Bonjour"
    with caplog.at_level(logging.DEBUG):
        await handle_message(secret_text, session_id=PHONE, channel="whatsapp")
        await handle_message("et la garantie ?", session_id=PHONE, channel="whatsapp")
        await wait_for_pending_persistence()
    logs = "\n".join(r.getMessage() for r in caplog.records)
    leaks = sorted({(r.name, r.levelname) for r in caplog.records
                    if PHONE in r.getMessage() or "et la garantie" in r.getMessage()})
    assert leaks == []  # (journal, niveau) qui contiendraient le numéro ou le message
    assert "216…77" in logs  # identifiant masqué, toujours utile pour recouper
    await database.engine.dispose(close=False)


def test_httpx_request_log_masks_the_messenger_token():
    install_log_filters()
    record = logging.LogRecord("httpx", logging.INFO, __file__, 1, 'HTTP Request: %s %s "%s %d %s"',
                               # objet httpx.URL, comme dans le vrai journal de httpx
                               ("POST", httpx.URL("https://graph.facebook.com/v18.0/me/messages?access_token=faux-jeton-test"),
                                "HTTP/1.1", 200, "OK"), None)
    for f in logging.getLogger("httpx").filters:
        f.filter(record)
    assert "faux-jeton-test" not in record.getMessage()
    assert logging.getLogger("groq").level == logging.INFO
