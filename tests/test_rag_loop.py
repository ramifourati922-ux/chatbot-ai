# tests/test_rag_loop.py
"""
Compteur de boucle RAG : seuls les échecs réels comptent.

Bug constaté en préparant la démo : le compteur augmentait à CHAQUE
question RAG, même bien répondue, donc un client qui posait 3 bonnes
questions d'affilée était transféré ("je n'arrive pas à répondre").

Le LLM est remplacé par une réponse fixe (monkeypatch de
dialogue_manager.ask) : tests déterministes, sans quota Groq. La
recherche RAG est réelle (ChromaDB peuplé requis), sur des questions
bien couvertes, donc au-dessus du seuil de confiance.
"""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import delete

from app.db import database
from app.models import User
from app.services import dialogue_manager
from app.services.dialogue_manager import RAG_LOOP_THRESHOLD, handle_message, wait_for_pending_persistence
from app.services.rag import vector_store


def _kb_indexed():
    try:
        return vector_store.count() > 0
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _kb_indexed(), reason="ChromaDB non peuplé")

# Questions bien couvertes par la base (confiance > seuil, pas d'escalade)
QUESTIONS = [
    "Quels sont les frais de livraison ?",
    "Quel est le délai pour retourner un produit ?",
    "Quels moyens de paiement acceptez-vous ?",
    "Quelle est la durée de garantie sur les instruments de mesure ?",
    "Livrez-vous en dehors de Tunis ?",
]
GOOD_ANSWER = "La livraison est gratuite dès 150 DT d'achat."
NO_INFO_ANSWER = "Je n’ai pas d’information précise sur ce point. Je peux vous mettre en relation avec un conseiller."


@pytest.fixture
def llm_answers(monkeypatch):
    """Remplace le LLM ; le test pousse les réponses à renvoyer, dans l'ordre."""
    answers = []
    monkeypatch.setattr(dialogue_manager, "ask", lambda *args, **kwargs: answers.pop(0))
    return answers


@pytest_asyncio.fixture
async def session_id():
    await database.engine.dispose(close=False)  # une boucle asyncio par test, cf. test_conversation_persistence
    sid = f"test-ragloop-{uuid.uuid4().hex[:8]}"
    yield sid
    await wait_for_pending_persistence()
    async with database.AsyncSessionLocal() as db:
        await db.execute(delete(User).where(User.external_id == sid))
        await db.commit()
    await database.engine.dispose(close=False)


async def _ask_all(session_id, n):
    return [await handle_message(q, session_id=session_id, channel="web") for q in QUESTIONS[:n]]


@pytest.mark.asyncio
async def test_good_answers_in_a_row_do_not_escalate(session_id, llm_answers):
    """Le bug : 3 bonnes réponses d'affilée déclenchaient repeated_rag_failure."""
    llm_answers.extend([GOOD_ANSWER] * (RAG_LOOP_THRESHOLD + 2))
    results = await _ask_all(session_id, RAG_LOOP_THRESHOLD + 2)
    assert [r.escalated for r in results] == [False] * (RAG_LOOP_THRESHOLD + 2)
    assert all(r.response == GOOD_ANSWER for r in results)


@pytest.mark.asyncio
async def test_consecutive_no_info_answers_escalate(session_id, llm_answers):
    """Vrais échecs : le 3e "je n'ai pas l'information" d'affilée est remplacé
    par un transfert, puis le compteur repart de zéro."""
    llm_answers.extend([NO_INFO_ANSWER] * RAG_LOOP_THRESHOLD + [GOOD_ANSWER])
    results = await _ask_all(session_id, RAG_LOOP_THRESHOLD + 1)

    assert [r.escalated for r in results[:RAG_LOOP_THRESHOLD - 1]] == [False] * (RAG_LOOP_THRESHOLD - 1)
    assert results[RAG_LOOP_THRESHOLD - 2].response == NO_INFO_ANSWER
    last_failure = results[RAG_LOOP_THRESHOLD - 1]
    assert last_failure.escalated is True
    assert last_failure.escalation_reason == "repeated_rag_failure"
    assert last_failure.response == dialogue_manager._get_escalation_message("repeated_rag_failure", "fr")
    assert results[-1].escalated is False  # compteur remis à zéro après le transfert


@pytest.mark.asyncio
async def test_informative_answer_resets_the_failure_streak(session_id, llm_answers):
    """Échec, échec, bonne réponse, échec, échec : jamais 3 échecs
    CONSÉCUTIFS, donc pas de transfert."""
    llm_answers.extend([NO_INFO_ANSWER, NO_INFO_ANSWER, GOOD_ANSWER, NO_INFO_ANSWER, NO_INFO_ANSWER])
    results = await _ask_all(session_id, 5)
    assert not any(r.escalated for r in results)
    ctx = await dialogue_manager._session_manager.get_context(session_id)
    assert ctx["rag_attempts_count"] == 2


# --- Détection des réponses "je n'ai pas l'information" ---

@pytest.mark.parametrize("answer", [
    # Réponses réelles du LLM relevées pendant les tests (apostrophes typographiques incluses)
    "Je n’ai pas d’information précise concernant l’existence d’un magasin Liss Strike à Sfax.",
    "Je ne trouve pas d'information dans notre base concernant la disponibilité de piles 18650.",
    "le catalogue que j’ai sous les yeux ne mentionne pas de moteur NEMA 17, donc je ne dispose pas de son prix.",
    "I’m sorry, but I don’t have the specific warranty details for our programmable boards.",
    "ما عنديش معلومات على ثمن الطابعة 3D في قاعدة المعطيات الحالية.",
    # Formulations du prompt système et variantes courantes
    "Je n'ai pas cette information précise.",
    "I do not have enough information about that.",
    "ليس لدي معلومات حول هذا الموضوع.",
    "ma3andich ma3loumet 3al produit hedha",
])
def test_no_info_answer_detected(answer):
    assert dialogue_manager._is_no_info_answer(answer)


@pytest.mark.parametrize("answer", [
    "La livraison est gratuite dès 150 DT d'achat.",
    # Réponse négative mais informative : ce n'est pas un échec
    "Nous livrons uniquement en Tunisie, dans les 24 gouvernorats. La livraison en Algérie n’est malheureusement pas proposée.",
    # Refus hors sujet : garde-fou, pas un échec du RAG
    "Je suis désolé, mais je ne peux répondre qu'aux questions relatives à Liss Strike.",
    "The multimeters are covered by a 12-month warranty against any manufacturing defects.",
    "مدة الضمان على أجهزة القياس هي 12 شهرًا ضد أي عيب في الصنع.",
])
def test_informative_or_refusal_answer_not_counted_as_failure(answer):
    assert not dialogue_manager._is_no_info_answer(answer)
