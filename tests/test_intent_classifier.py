# tests/test_intent_classifier.py
"""
Tests de app/services/intent_classifier.py
Couvre les 2 catégories d'escalade (explicite / frustration) dans les
4 langues cibles, les non-régressions (pas de faux positif), et
l'extraction d'entités.
"""

import pytest

from app.services.intent_classifier import IntentClassifier

clf = IntentClassifier()


@pytest.mark.parametrize("text", [
    # Français
    "Je veux parler à un agent humain",
    "Je voudrais parler à un conseiller",
    # Anglais
    "I want to talk to a human agent",
    "Can I speak to a representative?",
    # Arabe littéraire
    "أريد التحدث مع موظف بشري",
    "حولني لموظف",
    # Tunisien
    "3andi mochkla, nheb na7ki m3a agent",
    "bcha na7ki m3a wa7ed",
])
def test_explicit_escalation_detected(text):
    result = clf.classify(text)
    assert result.requires_escalation is True
    assert result.escalation_reason == "explicit"
    assert result.intent == "human_agent"


@pytest.mark.parametrize("text", [
    # Français (2+ cas)
    "Votre service client est horrible",
    "j'en ai marre, ça ne marche jamais avec vous",
    # Anglais (2+ cas)
    "Your customer service is terrible, I'm fed up",
    "I'm filing a complaint about this",
    # Arabe littéraire (2+ cas)
    "خدمتكم سيئة جدا وسأتقدم بشكوى",
    "سئمت من هذا التعامل",
    # Tunisien (2+ cas)
    "khedma khayba barcha, za3fen barcha",
    "3andi mochkla kbira m3akom, ma nesta7amelch aktar",
])
def test_frustration_escalation_detected(text):
    result = clf.classify(text)
    assert result.requires_escalation is True
    assert result.escalation_reason == "frustration"
    assert result.intent == "frustration"


@pytest.mark.parametrize("text", [
    # Salutations et questions normales — aucune escalade
    "Bonjour",
    "Hello where is my order CMD123?",
    "Quel est le prix de ce produit ?",
    # Faux positifs à éviter explicitement
    "je veux un agent électronique",  # "agent" hors contexte de contact
    "Human resources department is on floor 2",  # "human" hors contexte
    "Insaan est un mot arabe pour humain",  # mot proche isolé
    # Critiques produit normales — NE DOIVENT PAS être confondues avec
    # une frustration envers le SERVICE
    "ce produit est nul",
    "la qualité est mauvaise",
    "this product is terrible",
    "le produit ne fonctionne pas bien",
])
def test_no_escalation_on_normal_messages(text):
    result = clf.classify(text)
    assert result.requires_escalation is False
    assert result.escalation_reason is None


def test_entity_extraction():
    result = clf.classify(
        "Ma commande CMD4521 n'est pas arrivée, contactez-moi au "
        "test@mail.com, montant 45.5 dt"
    )
    assert result.entities["order_number"] == "CMD4521"
    assert result.entities["email"] == "TEST@MAIL.COM"
    assert result.entities["amount"] == "45.5 DT"


@pytest.mark.parametrize("text,expected", [
    ("merci, c'est réglé", True),
    ("thanks, that's fixed", True),
    ("merci", False),  # trop ambigu seul, ne doit pas clore la boucle
    ("merci pour l'info", False),
])
def test_satisfaction_signal(text, expected):
    assert clf.is_satisfaction_signal(text) is expected
