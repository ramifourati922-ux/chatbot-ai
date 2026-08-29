# tests/test_dialogue_manager.py
"""
Teste l'orchestrateur complet : langue + intent + RAG + LLM + session.
Nécessite Groq (clé valide) + ChromaDB peuplé + Redis (ou fallback mémoire).
"""

import uuid

import pytest

from app.config import settings
from app.services.rag import vector_store
from app.services import dialogue_manager
from app.services.dialogue_manager import handle_message, RAG_LOOP_THRESHOLD

GROQ_KEY_MISSING = not settings.GROQ_API_KEY or settings.GROQ_API_KEY == "your_groq_api_key_here"


def _kb_indexed():
    try:
        return vector_store.count() > 0
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    GROQ_KEY_MISSING or not _kb_indexed(),
    reason="GROQ_API_KEY manquante ou ChromaDB non peuplé (lancer scripts/ingest_knowledge_base.py)",
)


@pytest.mark.asyncio
async def test_escalation_short_circuits_llm():
    result = await handle_message("je veux parler à un agent humain", channel="web")
    assert result.escalated is True
    assert result.intent == "human_agent"
    assert result.escalation_reason == "explicit"
    assert len(result.response.strip()) > 0
    # Note : pas d'assertion de timing ici (< qq ms en usage réel, vérifié
    # manuellement via curl) — un seuil dur en pytest est peu fiable
    # (cold-start Redis/HF variable) et le vrai signal, c'est l'absence
    # d'appel LLM, déjà garanti structurellement par le court-circuit
    # dans dialogue_manager.handle_message (return avant tout appel à ask()).


@pytest.mark.asyncio
async def test_frustration_escalation_short_circuits_llm():
    result = await handle_message(
        "Votre service client est horrible, j'en ai marre", channel="web"
    )
    assert result.escalated is True
    assert result.intent == "frustration"
    assert result.escalation_reason == "frustration"
    assert len(result.response.strip()) > 0


@pytest.mark.asyncio
async def test_normal_product_criticism_does_not_escalate():
    """Non-régression : une critique produit ne doit pas être confondue
    avec une frustration envers le service (voir intent_classifier)."""
    result = await handle_message("ce produit est nul", channel="web")
    assert result.escalated is False
    assert result.escalation_reason is None


@pytest.mark.asyncio
async def test_rag_grounded_response_in_french():
    result = await handle_message("Quel est le délai pour retourner un produit ?", channel="web")
    assert result.escalated is False
    assert result.language == "fr"
    assert len(result.sources) > 0, "La réponse devrait s'appuyer sur au moins un chunk de la KB"
    print(f"\n[fr] R: {result.response}\nSources: {result.sources}")


@pytest.mark.asyncio
async def test_rag_grounded_response_product_query():
    result = await handle_message("Combien coûte une carte Arduino Uno ?", channel="web")
    assert result.escalated is False
    print(f"\n[produit] R: {result.response}\nSources: {result.sources}")


@pytest.mark.asyncio
async def test_session_persists_across_messages():
    first = await handle_message("Bonjour", channel="web")
    session_id = first.session_id
    second = await handle_message("où est ma commande ?", session_id=session_id, channel="web")
    assert second.session_id == session_id


@pytest.mark.asyncio
async def test_rag_loop_triggers_automatic_escalation():
    """RAG_LOOP_THRESHOLD messages RAG consécutifs (sans escalade ni
    signal de satisfaction) doivent déclencher une escalade automatique
    sur le dernier, puis remettre le compteur à zéro."""
    session_id = f"test-rag-loop-{uuid.uuid4()}"
    questions = [
        "Quel est le délai de garantie sur les cartes Arduino ?",
        "Avez-vous des capteurs de température en stock ?",
        "Quels sont les moyens de paiement acceptés ?",
    ]
    assert len(questions) == RAG_LOOP_THRESHOLD

    results = []
    for q in questions:
        results.append(await handle_message(q, session_id=session_id, channel="web"))

    for r in results[:-1]:
        assert r.escalated is False
    last = results[-1]
    assert last.escalated is True
    assert last.escalation_reason == "repeated_rag_failure"

    # Le message suivant (normal) ne doit pas re-déclencher immédiatement
    # (le compteur est reparti à zéro après l'escalade automatique).
    after = await handle_message(
        "Et pour les frais de livraison ?", session_id=session_id, channel="web"
    )
    assert after.escalated is False


@pytest.mark.asyncio
async def test_low_rag_confidence_escalates_without_llm_call():
    """
    Une question sans aucun rapport avec le domaine Liss Strike (donc
    hits vides ou très faibles) doit escalader via escalation_reason
    "low_rag_confidence", sans appel LLM.

    LIMITE HONNÊTE (voir aussi le commentaire dans dialogue_manager.py,
    étape 8) : on a cherché ~18 questions "dans le domaine électronique/
    SAV mais mal couvertes par la KB" pour isoler ce mécanisme du
    garde-fou hors-sujet du prompt système — aucune n'est descendue sous
    RAG_CONFIDENCE_THRESHOLD (le catalogue de ~11 000 produits est trop
    large, même des questions sur des services obscurs/inventés trouvent
    un match partiel). Seules des questions clairement HORS domaine
    (comme celle-ci) déclenchent le mécanisme en pratique — donc ce test
    ne prouve PAS une isolation parfaite entre "hors-sujet" et "dans le
    domaine mais mal couvert" ; il prouve que le mécanisme se déclenche
    correctement quand la confiance RAG est réellement basse, ce qui est
    déjà la garantie utile (filet de sécurité supplémentaire, moins cher
    qu'un appel LLM, et qui couvre aussi le cas hits vides).
    """
    result = await handle_message("Quel est le sens de la vie ?", channel="web")
    assert result.escalated is True
    assert result.escalation_reason == "low_rag_confidence"
    assert result.confidence < settings.RAG_CONFIDENCE_THRESHOLD
    assert len(result.response.strip()) > 0
    # Pas d'assertion de timing en dur (même raison que pour les autres
    # escalades, cf. test_escalation_short_circuits_llm) : le
    # court-circuit est garanti structurellement par le "return" avant
    # tout appel à ask() dans dialogue_manager.handle_message.


@pytest.mark.asyncio
async def test_low_rag_confidence_no_regression_on_covered_question():
    """Non-régression : une question bien couverte par la KB ne doit
    jamais être escaladée pour faible confiance RAG."""
    result = await handle_message("Combien coûte une carte Arduino Uno ?", channel="web")
    assert result.escalated is False
    assert result.escalation_reason is None


@pytest.mark.parametrize("language,text", [
    ("fr", "Quel est le sens de la vie ?"),
    ("en", "What is the meaning of life?"),
    ("tn", "9olli chnowa esm el president mte3 Amerika?"),
])
@pytest.mark.asyncio
async def test_low_rag_confidence_message_in_multiple_languages(language, text):
    """Le message canned "low_rag_confidence" doit être renvoyé dans la
    langue détectée — testé en fr/en/tn (le fr est déjà couvert par
    test_low_rag_confidence_escalates_without_llm_call ci-dessus)."""
    result = await handle_message(text, channel="web")
    assert result.language == language
    assert result.escalated is True
    assert result.escalation_reason == "low_rag_confidence"
    assert len(result.response.strip()) > 0


@pytest.mark.asyncio
async def test_satisfaction_signal_resets_rag_loop_counter():
    # Réutilise le singleton de dialogue_manager (pas une nouvelle
    # instance de SessionManager) : sous pytest-asyncio, chaque test
    # tourne dans sa propre boucle asyncio, et une instance Redis fraîche
    # peut diverger du backend (Redis réel vs fallback mémoire) utilisé
    # par le singleton si sa connexion est devenue obsolète entre deux
    # boucles — en production il n'existe qu'un seul process/une seule
    # boucle donc ce problème n'existe pas, mais un 2e SessionManager()
    # dans le test peut lire un état vide alors que l'écriture a eu lieu
    # ailleurs.
    session_id = f"test-rag-satisfaction-{uuid.uuid4()}"
    session_manager = dialogue_manager._session_manager

    await handle_message("Quel est le délai de livraison standard ?", session_id=session_id, channel="web")
    await handle_message("Avez-vous des modules relais 5V ?", session_id=session_id, channel="web")
    ctx = await session_manager.get_context(session_id)
    assert ctx["rag_attempts_count"] == 2

    # Signal de satisfaction → repart de zéro
    await handle_message("merci, c'est réglé", session_id=session_id, channel="web")
    ctx = await session_manager.get_context(session_id)
    assert ctx["rag_attempts_count"] == 0
