# tests/test_welcome_menu.py
"""
Menu d'accueil avec boutons (app/services/welcome_menu.py), sur les trois
canaux : site (GET /chat/menu), WhatsApp (message interactif « liste »),
Messenger (réponses rapides).

- chaque bouton envoie une question que le moteur traite comme prévu
  (bonne langue ; commande → suivi de commande, conseiller → transfert) ;
- le menu n'est proposé qu'après une salutation, jamais pendant un
  transfert ni quand un conseiller a la main ;
- un clic sur WhatsApp ou Messenger arrive au bot sous la forme de la
  question du bouton, pas de son titre.
handle_message et les envois Meta sont remplacés par des bouchons : ni
Groq, ni base, ni envoi réel.
"""

import hashlib
import hmac
import json
from types import SimpleNamespace

import httpx
import pytest
import pytest_asyncio

from app.api.routes import messenger as ms_route
from app.api.routes import whatsapp as wa_route
from app.config import settings
from app.main import app
from app.services import welcome_menu
from app.services.intent_classifier import IntentClassifier
from app.services.language_detector import detect_language

LANGUAGES = ("fr", "en", "ar", "tn")
EXPECTED_INTENT = {"commande": "order_tracking", "conseiller": "human_agent"}  # les autres : RAG


# ── Contenu du menu ─────────────────────────────────────────────────────

@pytest.mark.parametrize("language", LANGUAGES)
def test_menu_has_every_topic_with_short_labels(language):
    options = welcome_menu.menu(language)
    assert [o["id"].split(":")[1] for o in options] == list(welcome_menu.TOPICS)
    # Messenger : 20 caractères au plus par titre (WhatsApp : 24)
    assert all(0 < len(o["label"]) <= 20 for o in options)
    assert len({o["id"] for o in options}) == len(options)


def test_unknown_language_falls_back_to_french():
    assert welcome_menu.menu("de") == welcome_menu.menu("fr")
    assert welcome_menu.menu(None) == welcome_menu.menu("fr")


@pytest.mark.parametrize("language", LANGUAGES)
def test_button_id_gives_back_its_question(language):
    for option in welcome_menu.menu(language):
        assert welcome_menu.question_for(option["id"]) == option["question"]


@pytest.mark.parametrize("option_id", [None, "", "livraison", "menu:", "menu:livraison", "menu:inconnu:fr",
                                       "menu:livraison:de", "menu:livraison:fr:x", "autre:livraison:fr"])
def test_unknown_button_id_gives_no_question(option_id):
    assert welcome_menu.question_for(option_id) is None


# ── Chaque question est traitée comme prévu par le moteur ──────────────

@pytest.mark.parametrize("language", LANGUAGES)
def test_each_question_is_understood_in_its_language(language):
    classifier = IntentClassifier()
    for option in welcome_menu.menu(language):
        topic = option["id"].split(":")[1]
        assert detect_language(option["question"]) == language, option["question"]
        intent = classifier.classify(option["question"]).intent
        assert intent == EXPECTED_INTENT.get(topic, "general"), option["question"]


@pytest.mark.parametrize("text", [
    "أين طلبيتي؟", "أين وصلت طلبيتي؟", "تتبع طلبي", "win wselt el commande mte3i ?",
    "win commande mta3i", "وين الكوموند متاعي",
])
def test_order_tracking_is_understood_in_arabic_and_tunisian(text):
    assert IntentClassifier().classify(text).intent == "order_tracking"


@pytest.mark.parametrize("text", ["كيف أطلب منتجا؟", "nheb n3adi commande", "ما هي طرق الدفع المتاحة؟"])
def test_other_order_questions_still_go_to_the_rag(text):
    assert IntentClassifier().classify(text).intent == "general"


EXPECTED_SOURCE = {"livraison": "sav/livraison.txt", "retours": "sav/retours.txt",
                   "garantie": "sav/garantie.txt", "paiement": "ecommerce/paiement.txt"}


@pytest.mark.integration  # ChromaDB et modèles du RAG (pas de Groq)
@pytest.mark.parametrize("language", LANGUAGES)
def test_each_rag_question_finds_its_policy_above_the_threshold(language):
    """Une question du menu ne doit ni transférer le client (confiance sous
    le seuil) ni ramener des fiches produits au lieu de la bonne politique."""
    from app.services.rag import retriever
    for option in welcome_menu.menu(language):
        topic = option["id"].split(":")[1]
        if topic not in EXPECTED_SOURCE:
            continue
        hits = retriever.search(option["question"], 4)
        assert retriever.get_best_confidence(hits) >= retriever.get_confidence_threshold(hits), option["question"]
        assert EXPECTED_SOURCE[topic] in [h["metadata"].get("source") for h in hits[:2]], option["question"]


# ── Quand proposer le menu ──────────────────────────────────────────────

@pytest.mark.parametrize("result, expected", [
    (SimpleNamespace(intent="greeting", escalated=False, handled_by_agent=False), True),
    (SimpleNamespace(intent="thanks", escalated=False, handled_by_agent=False), False),
    (SimpleNamespace(intent="general", escalated=False, handled_by_agent=False), False),
    (SimpleNamespace(intent="greeting", escalated=True, handled_by_agent=False), False),
    (SimpleNamespace(intent="greeting", escalated=False, handled_by_agent=True), False),
    (SimpleNamespace(response="écho"), False),  # résultat incomplet : pas de menu
])
def test_menu_is_offered_only_after_a_greeting(result, expected):
    assert welcome_menu.should_offer(result) is expected


# ── Site : GET /chat/menu ────────────────────────────────────────────────

@pytest_asyncio.fixture
async def client():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_site_menu_route(client):
    data = (await client.get("/chat/menu")).json()
    assert data["intro"] == welcome_menu.intro("fr")
    assert data["options"] == welcome_menu.menu("fr")
    tn = (await client.get("/chat/menu", params={"language": "tn"})).json()
    assert tn["options"] == welcome_menu.menu("tn")


# ── WhatsApp et Messenger ────────────────────────────────────────────────

handled, posted = [], []


def _greeting(language="tn"):
    return SimpleNamespace(response="Aslema !", intent="greeting", language=language,
                           escalated=False, handled_by_agent=False)


@pytest.fixture
def bot_answers(monkeypatch):
    """Remplace handle_message ; renvoie la fonction qui fixe la prochaine réponse."""
    handled.clear()
    posted.clear()
    answer = {"result": SimpleNamespace(response="réponse", intent="general", language="fr",
                                        escalated=False, handled_by_agent=False)}

    async def fake_handle_message(message, session_id=None, channel="web"):
        handled.append((message, channel))
        return answer["result"]

    monkeypatch.setattr(wa_route, "handle_message", fake_handle_message)
    monkeypatch.setattr(ms_route, "handle_message", fake_handle_message)
    return lambda result: answer.update(result=result)


def _whatsapp_payload(message: dict) -> dict:
    return {"entry": [{"changes": [{"value": {"messages": [{"from": "21600000088", **message}]}}]}]}  # fictif


@pytest.fixture
def whatsapp_outbox(monkeypatch):
    async def fake_post(payload):
        posted.append(payload)
    monkeypatch.setattr(wa_route, "_post_to_whatsapp", fake_post)  # aucun envoi réel


@pytest.mark.asyncio
async def test_whatsapp_greeting_is_answered_with_the_list_menu(client, sign_whatsapp, bot_answers, whatsapp_outbox):
    bot_answers(_greeting("tn"))
    body, headers = sign_whatsapp(_whatsapp_payload({"type": "text", "text": {"body": "aslema"}}))
    assert (await client.post("/webhook/whatsapp", content=body, headers=headers)).status_code == 200
    [message] = posted
    assert message["type"] == "interactive" and message["interactive"]["type"] == "list"
    assert message["interactive"]["body"]["text"].startswith("Aslema !")
    rows = message["interactive"]["action"]["sections"][0]["rows"]
    assert [r["id"] for r in rows] == [o["id"] for o in welcome_menu.menu("tn")]
    assert len(rows) <= 10 and all(len(r["title"]) <= 24 for r in rows)  # limites Meta


@pytest.mark.asyncio
async def test_whatsapp_other_answers_stay_plain_text(client, sign_whatsapp, bot_answers, whatsapp_outbox):
    body, headers = sign_whatsapp(_whatsapp_payload({"type": "text", "text": {"body": "garantie ?"}}))
    assert (await client.post("/webhook/whatsapp", content=body, headers=headers)).status_code == 200
    assert posted == [{"to": "21600000088", "type": "text", "text": {"body": "réponse"}}]


@pytest.mark.asyncio
async def test_whatsapp_list_choice_reaches_the_bot_as_the_button_question(client, sign_whatsapp, bot_answers,
                                                                            whatsapp_outbox):
    choice = {"type": "interactive", "interactive": {
        "type": "list_reply", "list_reply": {"id": "menu:livraison:tn", "title": "Livraison"}}}
    body, headers = sign_whatsapp(_whatsapp_payload(choice))
    assert (await client.post("/webhook/whatsapp", content=body, headers=headers)).status_code == 200
    assert handled == [(welcome_menu.question_for("menu:livraison:tn"), "whatsapp")]


@pytest.mark.asyncio
async def test_whatsapp_unknown_interactive_reply_is_ignored(client, sign_whatsapp, bot_answers, whatsapp_outbox):
    choice = {"type": "interactive", "interactive": {"type": "button_reply", "button_reply": {"id": "autre"}}}
    body, headers = sign_whatsapp(_whatsapp_payload(choice))
    assert (await client.post("/webhook/whatsapp", content=body, headers=headers)).status_code == 200
    assert handled == [] and posted == []


MESSENGER_SECRET = "cle-de-test-webhook-messenger"
PSID = "9900000000000001"  # fictif


def _signed_messenger(message: dict):
    payload = {"object": "page", "entry": [{"messaging": [{"sender": {"id": PSID}, "message": message}]}]}
    body = json.dumps(payload).encode("utf-8")
    signature = hmac.new(MESSENGER_SECRET.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return body, {"Content-Type": "application/json", "X-Hub-Signature-256": f"sha256={signature}"}


@pytest.fixture
def messenger_outbox(monkeypatch):
    monkeypatch.setattr(settings, "MESSENGER_APP_SECRET", MESSENGER_SECRET)

    async def fake_send(psid, text, quick_replies=None):
        posted.append({"text": text, "quick_replies": quick_replies})
    monkeypatch.setattr(ms_route, "_send_messenger_message", fake_send)  # aucun envoi réel


@pytest.mark.asyncio
async def test_messenger_greeting_is_answered_with_quick_replies(client, bot_answers, messenger_outbox):
    bot_answers(_greeting("fr"))
    body, headers = _signed_messenger({"mid": "m_1", "text": "bonjour"})
    assert (await client.post("/webhook/messenger", content=body, headers=headers)).status_code == 200
    [message] = posted
    replies = message["quick_replies"]
    assert [r["payload"] for r in replies] == [o["id"] for o in welcome_menu.menu("fr")]
    assert len(replies) <= 13 and all(r["content_type"] == "text" and len(r["title"]) <= 20 for r in replies)


@pytest.mark.asyncio
async def test_messenger_quick_reply_reaches_the_bot_as_the_button_question(client, bot_answers, messenger_outbox):
    body, headers = _signed_messenger({"mid": "m_2", "text": "Garantie",
                                       "quick_reply": {"payload": "menu:garantie:fr"}})
    assert (await client.post("/webhook/messenger", content=body, headers=headers)).status_code == 200
    assert handled == [(welcome_menu.question_for("menu:garantie:fr"), "messenger")]
    assert posted == [{"text": "réponse", "quick_replies": None}]  # réponse sans menu
