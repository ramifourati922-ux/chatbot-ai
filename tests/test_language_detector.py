# tests/test_language_detector.py
"""
Tests de app/services/language_detector.py
Couvre les 4 langues cibles + cas limites (messages courts/vides/emoji).
"""

import pytest

from app.services.language_detector import detect_language


@pytest.mark.parametrize("text,expected", [
    # Français
    ("Bonjour, où est ma commande #CMD12345 ?", "fr"),
    ("Merci beaucoup pour votre aide", "fr"),
    ("Je voudrais un remboursement s'il vous plaît", "fr"),
    # Anglais
    ("Hello, where is my order?", "en"),
    ("Can you help me with a refund please?", "en"),
    ("Thanks for your help", "en"),
    # Arabe littéraire (MSA) — pas de marqueur tunisien
    ("مرحبا، أين طلبيتي؟", "ar"),
    ("أريد استرداد أموالي من فضلكم", "ar"),
    ("عندي مشكلة في الطلبية", "ar"),
    # Tunisien — écriture arabe (avec marqueur dialectal)
    ("وين commande متاعي؟", "tn"),
    ("علاش الطلبية ما وصلتش؟", "tn"),
    # Tunisien — arabizi (latin + chiffres)
    ("3andi mochkla fel commande", "tn"),
    ("wain commande mte3i", "tn"),
    ("chna7wel", "tn"),
    ("kifech na3mel bch nrod colis", "tn"),
])
def test_detect_language(text, expected):
    assert detect_language(text) == expected


@pytest.mark.parametrize("text", [
    # Notations techniques (unité collée à un chiffre de {2,3,5,7,9}) à
    # ne PAS confondre avec de l'arabizi — régression du bug où "5V"
    # etc. déclenchaient ARABIZI_DIGIT_PATTERN (voir _is_technical_unit_notation).
    "Avez-vous des modules relais 5V disponibles ?",
    "J'aimerais un capteur de température 3.3V pour mon projet",
    "Je cherche un câble USB-C 2.0",
    "Quelle est la fréquence WiFi, 2.4GHz ou 5GHz ?",
    "Cette batterie fait combien d'Ah, 9Ah ?",
    "Le module fait 3mm d'épaisseur",
    "Avez-vous la carte ESP32 en stock ?",
    "Une résistance de 9V fonctionne avec ce montage ?",
])
def test_technical_unit_notation_is_not_mistaken_for_arabizi(text):
    assert detect_language(text) == "fr"


@pytest.mark.parametrize("text", ["ok", "cc", "👍", "", "  ", "hi"])
def test_short_or_ambiguous_defaults_to_default_language(text):
    from app.services.language_detector import DEFAULT_LANGUAGE
    assert detect_language(text) == DEFAULT_LANGUAGE


# ── Anglais court et informel (langdetect → langue non supportée) ───────
# Régression : "I need ur help" était classé néerlandais par langdetect,
# le repli sur DEFAULT_LANGUAGE faisait répondre en français.

@pytest.mark.parametrize("text,langdetect_guess", [
    ("I need ur help", "nl"),
    ("can u help me", "cy"),
    ("can you help me", "cy"),
    ("r u open today", "cy"),
    ("plz answer me", "nl"),
    ("u have arduino?", "pt"),
    ("help me pls", "nl"),
])
def test_informal_english_misdetected_by_langdetect_is_english(text, langdetect_guess):
    from langdetect import detect
    from app.services.language_detector import detect_language_detailed
    assert detect(text) == langdetect_guess  # le cas corrigé est bien celui du repli
    result = detect_language_detailed(text)
    assert result.language == "en"
    assert result.method == "english_hint"


@pytest.mark.parametrize("text", ["need ur assistance", "thx for ur help", "where r u located"])
def test_informal_english_already_detected_stays_english(text):
    assert detect_language(text) == "en"


@pytest.mark.parametrize("text", [
    # Messages français courts que langdetect classe dans une langue non
    # supportée : sans indice anglais, ils restent en français
    "ok merci",        # slovaque
    "dispo ?",         # italien
    "ça marche",       # turc
    "je cherche un kit",  # allemand
    "combien le port",    # espagnol
    "svp aidez moi",      # hongrois
    # Indice anglais mais aussi indice français : reste en français
    "help svp",
])
def test_short_french_misdetected_by_langdetect_stays_french(text):
    assert detect_language(text) == "fr"
