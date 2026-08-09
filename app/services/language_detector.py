# app/services/language_detector.py
"""
Détection automatique de la langue d'un message client.

Langues supportées :
    "fr" → Français
    "en" → Anglais
    "ar" → Arabe littéraire (فصحى)
    "tn" → Tunisien (dialecte, écrit en lettres arabes OU en arabizi)

Stratégie (par ordre de priorité) :
    1. Message trop court / vide → langue par défaut (DEFAULT_LANGUAGE).
    2. Le texte contient des caractères arabes (unicode ٠٦٠٠-٠٦FF) :
       - si des mots typiquement tunisiens sont détectés → "tn"
       - sinon → "ar" (arabe littéraire par défaut)
    3. Le texte est en écriture latine et contient des marqueurs
       "arabizi" tunisiens (mots-clés type "3andi", "chna7wel", "win",
       ou un chiffre utilisé comme lettre à l'intérieur d'un mot,
       ex: "n7eb", "5ouya") → "tn"
    4. Sinon on utilise `langdetect` (basé sur des n-grammes statistiques)
       pour trancher entre "fr" et "en" (et "ar" en secours).

Pourquoi cette approche hybride et pas juste `langdetect` seul ?
    - `langdetect` est entraîné sur de l'arabe littéraire et des langues
      "standard" : il ne connaît PAS le tunisien (ni en lettres arabes,
      ni en arabizi). Un message tunisien serait mal classé (souvent en
      "ar", "fr" ou même une langue aléatoire sur les messages courts).
    - Le tunisien en arabizi (alphabet latin + chiffres) est confondu
      par `langdetect` avec du français/anglais/malaisien selon le cas.
    - Un simple dictionnaire de mots-clés tunisiens, combiné à la
      détection d'écriture arabe (regex unicode, fiable à 100%), suffit
      à couvrir l'essentiel des cas réels d'un service client tunisien,
      sans dépendre d'un modèle ML supplémentaire à télécharger/héberger.
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Optional

from langdetect import detect, DetectorFactory, LangDetectException

# langdetect utilise un générateur pseudo-aléatoire en interne pour les
# textes ambigus → sans seed fixe, le résultat peut varier d'un appel à
# l'autre pour le même texte. On fixe la seed pour un résultat déterministe.
DetectorFactory.seed = 0

logger = logging.getLogger(__name__)

# Langue utilisée quand on ne peut rien déterminer (message vide, trop
# court, "ok", emoji seul, etc.). Le français est la langue principale
# de Liss Strike en Tunisie, d'où ce choix.
DEFAULT_LANGUAGE = "fr"

# En dessous de ce nombre de caractères utiles, on ne tente même pas
# `langdetect` (trop peu de signal statistique, résultat non fiable).
MIN_CHARS_FOR_STATISTICAL_DETECTION = 4

# Plage unicode des caractères arabes (arabe standard + tunisien
# s'écrivent avec le même alphabet).
ARABIC_SCRIPT_PATTERN = re.compile(r"[؀-ۿ]")

# ── Marqueurs du dialecte tunisien écrit en lettres ARABES ──
# Mots/tournures qui n'existent (quasi) jamais en arabe littéraire
# standard, ou dont le sens/usage y diffère nettement.
TUNISIAN_ARABIC_MARKERS = {
    "برشا",      # barsha = beaucoup
    "ياسر",      # yasser = beaucoup
    "توا",       # tawa = maintenant
    "باهي",      # bahi = bien/ok
    "شنوة",      # chnoua = quoi
    "شنو",       # chnou = quoi
    "علاش",      # 3lech = pourquoi
    "وين",       # win = où
    "قداش",      # 9addesh = combien
    "كيفاش",     # kifech = comment
    "مالا",       # mela = alors/donc
    "نجم",       # najam = pouvoir (vs أستطيع en MSA)
    "نحب",       # nheb = je veux (vs أريد en MSA)
    "فمة",       # famma = il y a
    "برشة",
    "زعما",      # zaama = genre / soi-disant
    "عادي",      # utilisé très fréquemment en tunisien familier
    "خويا",      # khouya = mon frère
    "بزاف",      # bezzef = beaucoup (aussi marocain, mais rare en MSA écrit)
}

# ── Marqueurs du dialecte tunisien écrit en ARABIZI (latin + chiffres) ──
# Mots-clés fréquents dans les messages clients tunisiens.
TUNISIAN_ARABIZI_KEYWORDS = {
    "3andi", "3andek", "3neya", "chna7wel", "chnowa", "chnia", "chna",
    "kifech", "kifeh", "win", "wain", "winou", "3lech", "3laesh",
    "barcha", "yezzi", "yezi", "mte3i", "mte3", "labes", "mouch",
    "mush", "famma", "fama", "n7eb", "nheb", "t7eb", "5ouya", "khouya",
    "chwiya", "chouiya", "9adechna", "9adesh", "9addesh", "asba7",
    "twal", "mochkla", "moshkla", "3ndi", "eli", "hkeya", "bereau",
    "sahbi", "sa7bi", "hedhi", "hedha", "haja", "7aja", "yerham",
    "inchallah", "insha2allah", "mte3", "dima", "barka",
}

# Un chiffre "collé" à des lettres à l'intérieur d'un mot est un signal
# fort d'arabizi (3, 7, 9, 5, 2 remplacent des lettres arabes sans
# équivalent latin direct : ع ح ق/ء خ ء).
ARABIZI_DIGIT_PATTERN = re.compile(r"[a-zA-Z]+[23579][a-zA-Z]+|[a-zA-Z]+[23579]$|^[23579][a-zA-Z]+")

# Faux positifs fréquents dans un contexte e-commerce électronique :
# une unité technique collée à un chiffre ("5V", "3.3V", "9Ah", "2mm",
# "7Hz"...) matche ARABIZI_DIGIT_PATTERN (chiffre de l'ensemble
# {2,3,5,7,9} suivi de lettres) alors que ce n'est PAS de l'arabizi.
# Un vrai mot arabizi tunisien est un mot complet ("3andi", "9adesh",
# "chna7wel"), pas une unité de mesure — donc si la partie "lettres"
# du token correspond exactement à une unité connue, on l'exclut.
TECHNICAL_UNIT_SUFFIXES = {
    "v", "a", "w", "hz", "khz", "mhz", "ghz", "mm", "cm", "km", "kg",
    "g", "mg", "ml", "l", "ah", "mah", "ms", "db", "va", "ohm", "f",
    "uf", "nf", "pf", "dt", "tnd", "usd", "eur", "px",
}


def _is_technical_unit_notation(token: str) -> bool:
    """True si `token` est une notation technique (chiffre + unité,
    ex: "5v", "9ah", "3mm") plutôt qu'un vrai mot arabizi."""
    letters_only = re.sub(r"\d", "", token)
    return letters_only in TECHNICAL_UNIT_SUFFIXES


@dataclass
class LanguageResult:
    """Résultat détaillé (utile pour debug/tests, pas juste le code langue)."""
    language: str
    method: str  # "default" | "arabic_script" | "arabizi_keyword" | "arabizi_digit" | "statistical"
    matched: Optional[str] = None
    raw_scores: dict = field(default_factory=dict)


def _looks_tunisian_arabic(text: str) -> Optional[str]:
    """Cherche un marqueur tunisien dans un texte en écriture arabe."""
    for marker in TUNISIAN_ARABIC_MARKERS:
        if marker in text:
            return marker
    return None


def _looks_tunisian_arabizi(text_lower: str) -> Optional[str]:
    """Cherche un marqueur arabizi tunisien dans un texte en écriture latine."""
    tokens = re.findall(r"[a-z0-9]+", text_lower)
    for token in tokens:
        if token in TUNISIAN_ARABIZI_KEYWORDS:
            return token
    for token in tokens:
        if ARABIZI_DIGIT_PATTERN.search(token) and not _is_technical_unit_notation(token):
            return token
    return None


def detect_language_detailed(text: str) -> LanguageResult:
    """
    Version détaillée de detect_language : renvoie aussi la méthode
    utilisée pour trancher (pratique pour les tests / logs / soutenance).
    """
    if not text or not text.strip():
        return LanguageResult(DEFAULT_LANGUAGE, "default")

    cleaned = text.strip()

    # Messages très courts ("ok", "cc", "👍", "merci") : pas assez de
    # signal pour trancher fiablement → langue par défaut, SAUF si un
    # marqueur fort (arabe/tunisien) est quand même présent.
    is_short = len(re.sub(r"[^\w]", "", cleaned, flags=re.UNICODE)) < MIN_CHARS_FOR_STATISTICAL_DETECTION

    # 1. Écriture arabe → "ar" ou "tn"
    if ARABIC_SCRIPT_PATTERN.search(cleaned):
        marker = _looks_tunisian_arabic(cleaned)
        if marker:
            return LanguageResult("tn", "arabic_script", matched=marker)
        return LanguageResult("ar", "arabic_script")

    # 2. Écriture latine avec marqueurs tunisiens (arabizi)
    lower = cleaned.lower()
    marker = _looks_tunisian_arabizi(lower)
    if marker:
        method = "arabizi_digit" if ARABIZI_DIGIT_PATTERN.search(marker) else "arabizi_keyword"
        return LanguageResult("tn", method, matched=marker)

    # 3. Message trop court pour la détection statistique → défaut
    if is_short:
        return LanguageResult(DEFAULT_LANGUAGE, "default")

    # 4. Détection statistique (fr / en / ar en secours)
    try:
        detected = detect(cleaned)
    except LangDetectException:
        return LanguageResult(DEFAULT_LANGUAGE, "default")

    if detected in ("fr", "en", "ar"):
        return LanguageResult(detected, "statistical")

    # langdetect peut renvoyer d'autres codes ISO (ex: "ca", "so"...)
    # sur des textes ambigus/courts → on retombe sur le défaut plutôt
    # que d'exposer une langue non supportée par le bot.
    logger.info(f"🌐 langdetect a renvoyé '{detected}' (non supporté), fallback {DEFAULT_LANGUAGE}")
    return LanguageResult(DEFAULT_LANGUAGE, "default")


def detect_language(text: str) -> str:
    """
    Détecte la langue d'un message et retourne un code parmi :
    "fr", "en", "ar", "tn".

    Usage :
        lang = detect_language("wain commande mte3i")  # → "tn"
        lang = detect_language("Bonjour, où est ma commande ?")  # → "fr"
    """
    return detect_language_detailed(text).language
