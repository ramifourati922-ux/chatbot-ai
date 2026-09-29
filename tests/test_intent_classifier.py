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
    # Français : tournures ajoutées (responsable, passez-moi, transférez-moi,
    # j'exige, il me faut, svp...), apostrophe droite ou typographique
    "je veux un responsable",
    "Je veux parler au responsable",
    "je demande à parler au responsable",
    "passez-moi quelqu'un d'autre",
    "je veux quelqu'un d'autre",
    "Passez-moi un conseiller s'il vous plaît",
    "je ne suis pas satisfait, transférez-moi",
    "je ne suis pas satisfaite, transférez-moi à un conseiller",
    "transférez-moi vers un agent",
    "j'exige de parler à un humain",
    "J'exige de parler à quelqu'un",
    "vous ne comprenez rien à ma demande, il me faut un conseiller",
    "raccrochez pas, passez-moi un agent",
    "restez en ligne, passez-moi un agent",
    "mettez-moi en relation avec un conseiller",
    "j'ai besoin d'un conseiller",
    "j’ai besoin d’un conseiller",
    "il me faut un conseiller",
    "je voudrais parler à une personne",
    "je veux une vraie personne",
    "je veux un agent svp",
    "un conseiller svp",
    "un agent s'il vous plaît",
    "un humain stp",
    "conseiller",
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
    # Français : tournures ajoutées (reproche au service, pas au produit)
    "vous ne comprenez rien à ma demande",
    "tu ne comprends rien",
    "vous ne comprenez pas ma question",
    "je ne suis pas satisfait de votre service",
    "pas du tout satisfaite de vos réponses",
    "c'est inadmissible",
    "c'est scandaleux !",
    "ça fait trois fois que je demande la même chose",
    "ça fait 5 fois que je vous écris",
    "je vous l'ai déjà dit trois fois",
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
    # Proches des tournures d'escalade ajoutées, sans demande d'humain
    "je ne suis pas satisfait de ce capteur",
    "je ne suis pas satisfaite de la qualité du produit",
    "qui est responsable de la garantie ?",
    "le responsable du magasin est-il disponible samedi ?",
    "je n'ai pu parler à personne",
    "une personne peut-elle récupérer ma commande ?",
    "je veux offrir un kit à une personne",
    "je veux un agent de nettoyage",
    "je veux un capteur de présence humaine",
    "le détecteur humain svp",
    "passez-moi le lien du produit",
    "mettez-moi de côté un arduino",
    "il me faut une carte arduino",
    "j'ai besoin d'un conseil pour choisir",
    "vous comprenez l'arabe ?",
    "le prix est scandaleusement bas",
    "ça fait deux fois que je commande chez vous, super service",
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


# ── Demande explicite d'humain en anglais ───────────────────────────────
# Trous des règles anglaises : article "an" ("speak to an agent"), pas
# d'équivalent de "je veux / j'ai besoin d'un conseiller" ("I need a
# human"), rôles "live agent", "operator", "customer support"...

@pytest.mark.parametrize("text", [
    "can I speak to an agent",
    "connect me to an agent",
    "let me talk to an agent",
    "I need a human",
    "I want a human",
    "I need an agent to call me back",
    "I'd like a representative please",
    "get me a human",
    "speak to a live agent",
    "I want to talk to customer support",
    "put me through to an operator",
    "is there a human I can talk to",
    "I need human help",
    "human please",
    "agent pls",
])
def test_english_explicit_escalation_detected(text):
    result = clf.classify(text)
    assert result.requires_escalation is True
    assert result.escalation_reason == "explicit"


@pytest.mark.parametrize("text", [
    # Demande d'aide sans rôle humain : comme "j'ai besoin d'aide" en
    # français, ce n'est pas une demande de transfert
    "I need ur help",
    "I need help",
    "help",
    "can you help me find a product",
    "how can I get help with my order",
    "who can help me choose an arduino",
    "can someone tell me the price",
    # Rôle humain suivi d'un nom : question produit
    "I want a human presence sensor",
    "I need a human detection module for my robot",
    "do you have a human body sensor",
    "I need an operator amplifier",
    "I want an agent based kit",
    "is the agent software included",
    "is the live chat free",
])
def test_english_help_or_product_question_is_not_escalated(text):
    result = clf.classify(text)
    assert result.requires_escalation is False
