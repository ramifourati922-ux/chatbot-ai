# tests/test_order_tracking.py
"""
Suivi de commande : détection de l'intent, extraction du numéro, réponse
lue en base pour chaque statut, commande introuvable, message sans numéro
(une seule relance, puis transfert), non-régression escalade / politesse /
RAG. Le LLM n'est jamais appelé : il est remplacé par une fonction qui
échoue si on l'appelle.
"""

import uuid
from datetime import date
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import delete, text

from app.db import database
from app.models import Order, User
from app.services import dialogue_manager, order_tracking
from app.services.dialogue_manager import handle_message, wait_for_pending_persistence
from app.services.intent_classifier import Category, IntentClassifier, extract_order_number

clf = IntentClassifier()

# Numéros réservés aux tests (année 2099), un par statut
TEST_ORDERS = {
    "recue": ("CMD-2099-00001", date(2099, 1, 10)),
    "en_preparation": ("CMD-2099-00002", date(2099, 1, 11)),
    "expediee": ("CMD-2099-00003", date(2099, 1, 12)),
    "livree": ("CMD-2099-00004", date(2099, 1, 5)),
    "annulee": ("CMD-2099-00005", None),
}
EXPECTED_LABEL = {"recue": "reçue", "en_preparation": "en préparation", "expediee": "expédiée",
                  "livree": "livrée", "annulee": "annulée"}


# ── Détection et extraction (sans base) ────────────────────────────────

@pytest.mark.parametrize("text,expected", [
    ("CMD-2026-00123", "CMD-2026-00123"),
    ("cmd-2026-00123", "CMD-2026-00123"),
    ("CMD 2026 00123", "CMD-2026-00123"),
    ("CMD202600123", "CMD-2026-00123"),
    ("où en est ma commande CMD-2026-00042 svp", "CMD-2026-00042"),
    ("CMD-26-123", None),
    ("CMD12345", None),
    ("commande 2026-00123", None),
    ("XCMD-2026-00123", None),
])
def test_order_number_extraction(text, expected):
    assert extract_order_number(text) == expected


@pytest.mark.parametrize("text", [
    "Où est ma commande ?",
    "où en est ma commande CMD-2026-00123",
    "CMD-2026-00123",
    "Je voudrais le suivi de ma commande",
    "suivi de commande",
    "quel est le statut de ma commande ?",
    "ma commande n'est pas arrivée",
    "quand vais-je recevoir ma commande ?",
    "Where is my order?",
    "track my order please",
    "order status",
    "my order hasn't arrived",
])
def test_order_tracking_intent_detected(text):
    result = clf.classify(text)
    assert result.category == Category.ORDER_TRACKING
    assert result.intent == "order_tracking"
    assert result.requires_escalation is False


def test_order_number_is_added_to_entities():
    assert clf.classify("où est ma commande cmd 2026 00123 ?").entities["order_reference"] == "CMD-2026-00123"


@pytest.mark.parametrize("text", [
    "Comment passer une commande ?",
    "Quel est le délai de livraison ?",
    "Puis-je annuler une commande ?",
    "je veux commander un arduino",
    "how do I place an order?",
    "la commande de moteur fonctionne comment ?",
    "Avez-vous l'Arduino Uno ?",
    "CMD-26-123",
])
def test_general_questions_are_not_order_tracking(text):
    assert clf.classify(text).category != Category.ORDER_TRACKING


@pytest.mark.parametrize("text,reason", [
    ("Je veux parler à un agent humain, où est ma commande ?", "explicit"),
    ("j'en ai marre, où est ma commande CMD-2026-00123", "frustration"),
])
def test_escalation_still_takes_priority(text, reason):
    assert clf.classify(text).escalation_reason == reason


@pytest.mark.parametrize("text", ["Bonjour", "merci", "hello"])
def test_small_talk_unchanged(text):
    assert clf.classify(text).category == Category.SMALL_TALK


# ── Formatage (sans base) ──────────────────────────────────────────────

def _order(status, eta=date(2026, 10, 12)):
    return Order(order_number="CMD-2026-00123", status=status, total=Decimal("89.90"), estimated_delivery=eta,
                 items=[{"name": "Arduino Uno R3", "quantity": 1}, {"name": "Capteur DHT22", "quantity": 2}])


def test_formatted_order_contains_the_facts():
    text = order_tracking.format_order(_order("expediee"), "fr")
    assert "CMD-2026-00123" in text and "expédiée" in text
    assert "1 × Arduino Uno R3, 2 × Capteur DHT22" in text
    assert "89,90 DT" in text and "12/10/2026" in text


def test_delivered_and_cancelled_orders_have_no_estimated_date():
    assert "12/10/2026" not in order_tracking.format_order(_order("livree"), "fr")
    cancelled = order_tracking.format_order(_order("annulee"), "fr")
    assert "12/10/2026" not in cancelled and "conseiller" in cancelled


def test_english_formatting():
    text = order_tracking.format_order(_order("en_preparation"), "en")
    assert "being prepared" in text and "89.90 TND" in text


# ── Parcours complet avec la base (sans LLM) ───────────────────────────

@pytest_asyncio.fixture
async def orders(monkeypatch):
    """Commandes de test en base ; le LLM échoue s'il est appelé."""
    def no_llm(*args, **kwargs):
        raise AssertionError("le suivi de commande ne doit pas appeler le LLM")

    monkeypatch.setattr(dialogue_manager, "ask", no_llm)
    await database.engine.dispose(close=False)
    try:
        async with database.AsyncSessionLocal() as db:
            await db.execute(text("select 1 from orders limit 1"))
    except Exception as e:
        pytest.skip(f"PostgreSQL ou table orders indisponible : {e}")
    numbers = [n for n, _ in TEST_ORDERS.values()]
    prefix = f"test-order-{uuid.uuid4().hex[:8]}-"
    async with database.AsyncSessionLocal() as db:
        await db.execute(delete(Order).where(Order.order_number.in_(numbers)))
        customer = User(external_id=f"{prefix}client", channel="web")
        db.add(customer)
        await db.flush()
        for status, (number, eta) in TEST_ORDERS.items():
            db.add(Order(order_number=number, user_id=customer.id, status=status, total=Decimal("47.80"),
                         items=[{"name": "Capteur DHT22", "quantity": 2}], estimated_delivery=eta))
        await db.commit()
    yield prefix
    await wait_for_pending_persistence()
    async with database.AsyncSessionLocal() as db:
        await db.execute(delete(Order).where(Order.order_number.in_(numbers)))
        await db.execute(delete(User).where(User.external_id.like(f"{prefix}%")))
        await db.commit()
    await database.engine.dispose(close=False)


async def _say(session_id, message):
    return await handle_message(message, session_id=session_id, channel="web")


@pytest.mark.asyncio
@pytest.mark.parametrize("status", list(TEST_ORDERS))
async def test_found_order_is_answered_from_the_database(orders, status):
    number, eta = TEST_ORDERS[status]
    result = await _say(f"{orders}s-{status}", f"où est ma commande {number} ?")
    assert result.intent == "order_tracking" and result.escalated is False and result.sources == []
    assert number in result.response and EXPECTED_LABEL[status] in result.response
    if eta and status not in ("livree", "annulee"):
        assert eta.strftime("%d/%m/%Y") in result.response


@pytest.mark.asyncio
async def test_number_alone_after_a_prompt_is_found(orders):
    session = f"{orders}relance-ok"
    first = await _say(session, "où est ma commande ?")
    assert "CMD-2026-00123" in first.response and first.escalated is False  # demande du numéro
    second = await _say(session, "CMD-2099-00003")
    assert "expédiée" in second.response and second.escalated is False


@pytest.mark.asyncio
async def test_unknown_number_prompts_once_then_escalates(orders):
    session = f"{orders}inconnu"
    first = await _say(session, "où est ma commande CMD-2099-99999 ?")
    assert "CMD-2099-99999" in first.response and first.escalated is False
    second = await _say(session, "CMD-2099-99998")
    assert second.escalated is True and second.escalation_reason == "order_tracking"


@pytest.mark.asyncio
async def test_no_number_prompts_once_then_escalates(orders):
    session = f"{orders}sans-numero"
    first = await _say(session, "Où est ma commande ?")
    assert first.escalated is False and "numéro" in first.response
    second = await _say(session, "ma commande n'est toujours pas arrivée")
    assert second.escalated is True and second.escalation_reason == "order_tracking"


@pytest.mark.asyncio
async def test_changing_topic_clears_the_pending_prompt(orders):
    session = f"{orders}autre-sujet"
    await _say(session, "Où est ma commande ?")
    await _say(session, "merci")  # autre sujet : la relance est oubliée
    again = await _say(session, "Où est ma commande ?")
    assert again.escalated is False  # nouvelle demande du numéro, pas de transfert


@pytest.mark.asyncio
async def test_database_error_escalates(orders, monkeypatch):
    async def broken(number):
        raise RuntimeError("PostgreSQL indisponible")

    monkeypatch.setattr(order_tracking, "find_order", broken)
    result = await _say(f"{orders}panne", "où est ma commande CMD-2099-00001 ?")
    assert result.escalated is True and result.escalation_reason == "order_tracking"


@pytest.mark.asyncio
async def test_english_request_gets_an_english_answer(orders):
    result = await _say(f"{orders}en", "Where is my order CMD-2099-00003?")
    assert "shipped" in result.response and "Order CMD-2099-00003" in result.response


@pytest.mark.asyncio
async def test_escalation_to_admin_is_listed_with_its_reason(orders):
    session = f"{orders}admin"
    await _say(session, "Où est ma commande ?")
    await _say(session, "où est ma commande ?")
    await wait_for_pending_persistence()
    async with database.AsyncSessionLocal() as db:
        status = (await db.execute(text(
            "select c.status from conversations c join users u on u.id = c.user_id where u.external_id = :e"),
            {"e": session})).scalar_one()
    assert status == "escalated"
