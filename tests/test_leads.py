# tests/test_leads.py
"""
Prospects (leads) : clients qui se sont renseignés sur un produit
(app/services/analytics.build_leads, routes /admin/leads et /admin/leads.csv).

- build_leads est une fonction pure : testée sur des échanges construits à
  la main et un petit catalogue ;
- un test d'intégration insère de vrais échanges en base (sans appel au
  LLM) et vérifie la route JSON et l'export CSV.
"""

import csv
import io
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import delete

from app.api.routes.admin import _csv_cell
from app.services.analytics import MessageRow, build_leads

NOW = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)
CATALOG = {
    "LS-CP-000001": {"name": "Carte Arduino Uno R3", "category": "Cartes Programmables", "price_dt": 63.18},
    "LS-MO-000017": {"name": "Moteur pas-à-pas NEMA17", "category": "Moteurs & Roues", "price_dt": 45.0},
    "LS-CA-000003": {"name": "Capteur ultrason HC-SR04", "category": "Capteurs", "price_dt": 6.5},
}


def exchange(customer, question, sources, minutes=0, channel="whatsapp", conv=None, **metadata):
    """Une question du client et la réponse RAG du bot qui la suit."""
    conv = conv or f"conv-{customer}"
    at = NOW - timedelta(hours=1) + timedelta(minutes=minutes)
    return [
        MessageRow(conv, channel, "user", question, {"language": "fr"}, None, at, customer),
        MessageRow(conv, channel, "assistant", "réponse", {"intent": "general", "sources": sources, **metadata},
                   1200, at + timedelta(seconds=2), customer),
    ]


def test_product_question_makes_a_lead_with_named_products():
    leads = build_leads(exchange("21600000011", "Avez-vous l'Arduino Uno ?", ["LS-CP-000001", "LS-CA-000003"]), CATALOG)
    [lead] = leads
    assert lead["customer_id"] == "21600000011" and lead["channel"] == "whatsapp"
    assert lead["recontactable"] is True
    assert lead["purchase_intent"] is False  # simple renseignement
    assert [p["name"] for p in lead["products"]] == ["Carte Arduino Uno R3", "Capteur ultrason HC-SR04"]
    assert lead["products"][0]["price_dt"] == 63.18


def test_policy_question_that_only_brought_up_products_is_not_a_lead():
    """« garantie ? » : la politique est la 1re source, les produits suivants sont du bruit."""
    assert build_leads(exchange("c1", "Quelle est la durée de la garantie ?",
                                ["sav/garantie.txt", "LS-CP-000001"]), CATALOG) == []


def test_purchase_intent_counts_even_when_a_policy_comes_first():
    [lead] = build_leads(exchange("c1", "Quel est le prix du NEMA17 ?", ["ecommerce/paiement.txt", "LS-MO-000017"]), CATALOG)
    assert lead["purchase_intent"] is True
    assert lead["products"][0]["sku"] == "LS-MO-000017"


@pytest.mark.parametrize("question", ["b9adeh el arduino ?", "بكم الأردوينو؟", "how much is the arduino?",
                                      "Est-il disponible en stock ?"])
def test_purchase_intent_in_the_four_languages(question):
    [lead] = build_leads(exchange("c1", question, ["LS-CP-000001"]), CATALOG)
    assert lead["purchase_intent"] is True


def test_questions_of_a_customer_are_aggregated_and_most_cited_products_first():
    messages = (exchange("c1", "Avez-vous le NEMA17 ?", ["LS-MO-000017"], 0)
                + exchange("c1", "Et le capteur ultrason ?", ["LS-CA-000003", "LS-MO-000017"], 5)
                + exchange("c1", "Le NEMA17 est-il en stock ?", ["LS-MO-000017"], 10))
    [lead] = build_leads(messages, CATALOG)
    assert lead["product_questions"] == 3
    assert lead["purchase_intent"] is True  # « en stock » à la 3e question
    assert lead["last_question"] == "Le NEMA17 est-il en stock ?"
    assert [p["sku"] for p in lead["products"]] == ["LS-MO-000017", "LS-CA-000003"]


def test_leads_with_purchase_intent_come_first_then_most_recent():
    messages = (exchange("ancien-intention", "prix de l'arduino ?", ["LS-CP-000001"], 0)
                + exchange("recent", "Avez-vous l'Arduino ?", ["LS-CP-000001"], 30)
                + exchange("recent-intention", "combien coûte l'arduino ?", ["LS-CP-000001"], 20))
    assert [lead["customer_id"] for lead in build_leads(messages, CATALOG)] == \
        ["recent-intention", "ancien-intention", "recent"]


def test_web_customer_is_not_recontactable():
    [lead] = build_leads(exchange("web:abc", "Avez-vous l'Arduino ?", ["LS-CP-000001"], channel="web"), CATALOG)
    assert lead["recontactable"] is False


def test_transfers_politeness_and_unknown_products_are_ignored():
    messages = (exchange("c1", "Je veux un humain", ["LS-CP-000001"], escalated=True, escalation_reason="explicit")
                + exchange("c2", "Avez-vous ce produit ?", ["LS-ZZ-999999"])   # absent du catalogue
                + exchange("c3", "merci", ["LS-CP-000001"], intent="thanks"))
    assert build_leads(messages, CATALOG) == []


@pytest.mark.parametrize("value,expected", [
    ("=HYPERLINK(\"http://x\")", "'=HYPERLINK(\"http://x\")"),
    ("+33 1 23", "'+33 1 23"), ("-2+3", "'-2+3"), ("@SUM(A1)", "'@SUM(A1)"),
    ("Avez-vous l'Arduino ?", "Avez-vous l'Arduino ?"), (None, ""), (3, "3"),
])
def test_csv_cells_cannot_become_spreadsheet_formulas(value, expected):
    assert _csv_cell(value) == expected


@pytest.mark.asyncio
async def test_leads_routes_on_real_history(agent_accounts):
    from app.db import database
    from app.db.repositories.conversation_repository import ConversationRepository
    from app.db.repositories.user_repository import UserRepository
    from app.main import app
    from app.models import User

    customer = f"test-leads-{uuid.uuid4()}"
    now = datetime.now(timezone.utc)
    await database.engine.dispose(close=False)
    try:
        async with database.AsyncSessionLocal() as db:
            user, _ = await UserRepository(db).get_or_create(customer, "whatsapp")
            repo = ConversationRepository(db)
            conv = await repo.create(user.id, "whatsapp")
            await repo.add_message(conv.id, "user", "=Quel est le prix de l'Arduino Uno ?", {"language": "fr"},
                                   created_at=now - timedelta(seconds=5))
            await repo.add_message(conv.id, "assistant", "63,18 DT.",
                                   {"intent": "general", "sources": ["LS-CP-000001"], "escalated": False},
                                   processing_time_ms=1300, created_at=now - timedelta(seconds=3))
            await db.commit()

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            auth = agent_accounts.conseiller.auth
            assert (await client.get("/admin/leads")).status_code == 401  # réservé aux conseillers
            leads = (await client.get("/admin/leads?days=1&limit=1000", auth=auth)).json()
            [lead] = [item for item in leads if item["customer_id"] == customer]
            assert lead["purchase_intent"] is True and lead["recontactable"] is True
            assert lead["products"][0]["sku"] == "LS-CP-000001"
            stats = (await client.get("/admin/stats?days=1", auth=auth)).json()
            assert stats["leads"]["total"] >= 1 and stats["leads"]["purchase_intent"] >= 1

            response = await client.get("/admin/leads.csv?days=1", auth=auth)
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/csv")
            assert "attachment" in response.headers["content-disposition"]
            rows = list(csv.reader(io.StringIO(response.text.lstrip("﻿")), delimiter=";"))
            assert rows[0][0] == "client"
            [row] = [r for r in rows if r[0] == customer]
            assert row[1] == "whatsapp" and row[7] == "oui"
            assert row[9].startswith("'=")  # formule neutralisée
    finally:
        async with database.AsyncSessionLocal() as db:
            await db.execute(delete(User).where(User.external_id == customer))
            await db.commit()
        await database.engine.dispose(close=False)
