# tests/test_semantic_intent.py
"""
Intentions apprises sur des phrases d'exemple (app/services/semantic_intent.py),
consultées seulement si aucune règle ne tranche et si INTENT_MODEL_ENABLED.

Tests unitaires (sans modèle, sans service) :
- jeux de données : chaque intention a ses exemples dans les 4 langues, et
  les jeux de calibration et de mesure ne recopient aucun exemple ;
- décision : contre-exemple ou ressemblance sous le seuil → None ; seuil
  plus strict pour un transfert ;
- branchement dans dialogue_manager : interrupteur coupé = comportement
  d'origine ; les règles restent prioritaires ; une panne du modèle ne
  casse rien ; aide, transfert et suivi de commande reprennent les
  traitements existants. Session en mémoire, recherche RAG remplacée.

Tests d'intégration (vrai modèle d'embeddings) : exemples demandés
reconnus, contre-exemples jamais transférés, mesure sur test.json tenue.
"""

import json
import unicodedata
from pathlib import Path

import pytest

from app.config import settings
from app.services import dialogue_manager, semantic_intent
from app.services.session_manager import SessionManager

DATA = Path(__file__).resolve().parents[1] / "data" / "intents"
LANGUAGES = ("fr", "en", "ar", "tn")


def _normalized(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return " ".join("".join(c for c in text if c.isalnum() or c.isspace()).split())


def _messages(name: str) -> list:
    return json.loads((DATA / name).read_text(encoding="utf-8"))["messages"]


# ── Jeux de données ─────────────────────────────────────────────────────

def test_every_learned_intent_has_examples_in_every_language():
    data = json.loads(semantic_intent.EXAMPLES_PATH.read_text(encoding="utf-8"))
    for intent in (*semantic_intent.LEARNED_INTENTS, semantic_intent.NEGATIVE):
        assert set(data[intent]) == set(LANGUAGES), intent
        assert all(len(phrases) >= 6 for phrases in data[intent].values()), intent


def test_calibration_and_test_sets_never_copy_an_example():
    """Sinon la mesure serait faussée : le modèle reconnaîtrait sa propre copie."""
    examples = {_normalized(text) for _, text in semantic_intent.load_examples()}
    dev = {_normalized(m["text"]) for m in _messages("dev.json")}
    test = {_normalized(m["text"]) for m in _messages("test.json")}
    assert not examples & dev
    assert not examples & test
    assert not dev & test


# ── Décision (exemple le plus proche + seuil) ──────────────────────────

def _nearest_returns(monkeypatch, intent, score):
    monkeypatch.setattr(semantic_intent, "nearest",
                        lambda text: semantic_intent.LearnedIntent(intent, score, "exemple"))


@pytest.mark.parametrize("intent, score, expected", [
    ("general", 0.99, None),              # contre-exemple : question pour le RAG
    ("help", 0.70, "help"),
    ("help", 0.55, None),                 # sous le seuil
    ("order_tracking", 0.65, "order_tracking"),
    ("human_agent", 0.75, None),          # transfert : seuil plus strict
    ("human_agent", 0.90, "human_agent"),
    ("frustration", 0.80, None),
    ("frustration", 0.86, "frustration"),
])
def test_decision_uses_the_threshold_of_the_intent(monkeypatch, intent, score, expected):
    monkeypatch.setattr(settings, "INTENT_SIMILARITY_THRESHOLD", 0.62)
    monkeypatch.setattr(settings, "INTENT_ESCALATION_THRESHOLD", 0.82)
    _nearest_returns(monkeypatch, intent, score)
    match = semantic_intent.classify("message")
    assert (match.intent if match else None) == expected


def test_nearest_picks_the_closest_example(monkeypatch):
    vectors = {"aide": [1.0, 0.0, 0.0], "humain": [0.0, 1.0, 0.0], "question": [0.0, 0.0, 1.0],
               "aidez moi": [0.9, 0.1, 0.0]}
    monkeypatch.setattr(semantic_intent, "load_examples",
                        lambda: [("help", "aide"), ("human_agent", "humain"), ("general", "question")])
    monkeypatch.setattr(semantic_intent, "_embed_batch", lambda texts: [vectors[t] for t in texts])
    monkeypatch.setattr(semantic_intent, "_embed", lambda text: vectors[text])
    semantic_intent.reset()
    try:
        match = semantic_intent.nearest("aidez moi")
        assert (match.intent, match.example) == ("help", "aide")
        assert match.score == pytest.approx(0.9 / (0.81 + 0.01) ** 0.5, abs=1e-4)
    finally:
        semantic_intent.reset()


# ── Branchement dans dialogue_manager ──────────────────────────────────

@pytest.fixture
def engine(monkeypatch):
    """Session en mémoire, recherche RAG vide (confiance 0 → transfert
    low_rag_confidence, sans appel au LLM)."""
    sessions = SessionManager()
    sessions._redis_available = False
    monkeypatch.setattr(dialogue_manager, "_session_manager", sessions)
    monkeypatch.setattr(dialogue_manager.retriever, "search", lambda query, top_k=4, type_filter=None: [])
    monkeypatch.setattr(settings, "INTENT_MODEL_ENABLED", True)

    def learned(intent, score=0.95):
        monkeypatch.setattr(semantic_intent, "classify",
                            lambda text: semantic_intent.LearnedIntent(intent, score, "exemple"))
    return learned


def _never_called(text):
    raise AssertionError("le modèle ne doit pas être consulté")


@pytest.mark.asyncio
async def test_switch_off_keeps_the_original_behaviour(engine, monkeypatch):
    monkeypatch.setattr(settings, "INTENT_MODEL_ENABLED", False)
    monkeypatch.setattr(semantic_intent, "classify", _never_called)
    result = await dialogue_manager._handle_message("i need your help", "test-intent-off", "web")
    assert result.escalation_reason == "low_rag_confidence"  # comme avant : RAG, puis confiance nulle
    assert result.intent_source is None


@pytest.mark.asyncio
async def test_rules_keep_priority_over_the_model(engine, monkeypatch):
    monkeypatch.setattr(semantic_intent, "classify", _never_called)
    result = await dialogue_manager._handle_message("je veux parler à un conseiller", "test-intent-rule", "web")
    assert result.escalated and result.escalation_reason == "explicit"
    assert result.intent_source == "regle"


@pytest.mark.asyncio
async def test_learned_help_gets_the_help_answer(engine):
    engine("help")
    result = await dialogue_manager._handle_message("je veux plus des informations", "test-intent-help", "web")
    assert result.intent == "help" and not result.escalated
    assert result.response == dialogue_manager.HELP_MESSAGES["fr"]
    assert result.intent_source == "modele"


@pytest.mark.asyncio
async def test_learned_escalation_transfers_with_the_usual_message(engine):
    engine("frustration")
    result = await dialogue_manager._handle_message("vous êtes vraiment pénibles", "test-intent-frus", "web")
    assert result.escalated and result.escalation_reason == "frustration"
    assert result.response == dialogue_manager.ESCALATION_MESSAGES["frustration"]["fr"]
    assert result.intent_source == "modele"


@pytest.mark.asyncio
async def test_learned_order_tracking_asks_for_the_order_number(engine):
    engine("order_tracking")
    result = await dialogue_manager._handle_message("mon colis n'arrive pas", "test-intent-order", "web")
    assert result.intent == "order_tracking" and not result.escalated
    assert "CMD-2026-00123" in result.response  # relance : demande du numéro


@pytest.mark.asyncio
async def test_model_failure_falls_back_to_the_rules(engine, monkeypatch):
    def broken(text):
        raise RuntimeError("modèle indisponible")
    monkeypatch.setattr(semantic_intent, "classify", broken)
    result = await dialogue_manager._handle_message("i need your help", "test-intent-broken", "web")
    assert result.escalation_reason == "low_rag_confidence"
    assert result.intent_source is None


# ── Intégration : vrai modèle d'embeddings ─────────────────────────────

@pytest.mark.integration
@pytest.mark.parametrize("text", ["i need your help", "nhebek t3awani", "je veux plus des informations"])
def test_vague_requests_are_recognized_as_help(text):
    match = semantic_intent.classify(text)
    assert match is not None and match.intent == "help"


@pytest.mark.integration
@pytest.mark.parametrize("text", [
    "cet écran LCD est vraiment nul",                      # critique de produit, pas du service
    "je veux un agent de nettoyage pour circuits imprimés",
    "el capteur hedha ma ye5demch mli",                    # panne de produit en arabizi
    "do you sell servo motors?",
])
def test_hard_negatives_are_never_transferred(text):
    match = semantic_intent.classify(text)
    assert match is None or match.intent not in semantic_intent.ESCALATION_INTENTS


@pytest.mark.integration
def test_no_general_question_of_dev_or_test_is_transferred():
    for message in _messages("dev.json") + _messages("test.json"):
        if message["intent"] == "general":
            match = semantic_intent.classify(message["text"])
            assert match is None or match.intent not in semantic_intent.ESCALATION_INTENTS, message["text"]
