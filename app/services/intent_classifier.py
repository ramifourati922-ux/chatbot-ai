# app/services/intent_classifier.py
"""
Détecteur d'escalade vers un agent humain.

C'est la SEULE classification qui reste à base de règles. Pourquoi :
un client qui demande explicitement un humain — ou qui exprime une
frustration claire envers le service — ne doit jamais être raté par
une classification approximative ; la fiabilité déterministe prime
ici sur la flexibilité. Tout le reste (salutation, question commande,
question produit, question générale...) est délégué au pipeline RAG +
LLM, qui comprend nativement l'intention et répond dans la bonne
langue (français, anglais, arabe littéraire, tunisien — voir
language_detector.py) sans qu'il faille dupliquer des règles par
langue pour chaque type de demande.

Deux catégories d'escalade, deux jeux de patterns :
- "explicit"   : le client demande directement un humain.
- "frustration": le client n'a rien demandé explicitement, mais son
                 mécontentement envers le SERVICE (pas le produit)
                 est net — on préfère transférer plutôt que de le
                 laisser insister devant un bot.

Dans les deux cas, les patterns sont volontairement contextuels
(verbe/intention + rôle, ou mécontentement + contexte service), pas
des mots-clés isolés : un mot comme "agent"/"humain" pris seul est
ambigu (ex. "je veux un agent électronique" ne doit PAS déclencher),
et un adjectif négatif seul confondrait "le produit est nul" (critique
produit normale, doit passer par le RAG) avec "votre service est
nul" (frustration réelle, doit escalader).
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Category(str, Enum):
    GENERAL = "general"
    ESCALATE = "escalate"


@dataclass
class IntentResult:
    """Résultat de la classification. requires_escalation est le signal
    qui compte ; escalation_reason distingue le type d'escalade (utile
    pour adapter le message de transfert et les logs/analytics).
    intent/category/confidence restent surtout pour les logs."""
    intent: str
    category: Category
    confidence: float
    entities: dict = field(default_factory=dict)
    requires_escalation: bool = False
    escalation_reason: Optional[str] = None  # "explicit" | "frustration" | None


class IntentClassifier:

    def __init__(self):
        self._explicit_patterns = self._load_explicit_escalation_patterns()
        self._frustration_patterns = self._load_frustration_patterns()
        self._satisfaction_patterns = self._load_satisfaction_patterns()
        self._entity_patterns = self._load_entity_patterns()

    def _load_explicit_escalation_patterns(self) -> list:
        """Regex de détection d'une demande explicite d'agent humain, dans
        les 4 langues supportées. Chaque pattern combine une intention de
        contact ("parler à", "talk to", "تحدث مع", "n7ki m3a"...) avec
        un rôle humain (agent/conseiller/human/موظف/insen...)."""
        return [
            # ─── Français ───
            r"parler\s+(à|avec)\s+(un\s+)?(humain|agent|conseiller|quelqu'?un)",
            r"agent\s+humain",
            r"un\s+vrai\s+(humain|agent|conseiller)",
            r"(veux|voudrais|besoin\s+d[e']|j'aimerais)\s+.{0,20}(parler\s+(à|avec)\s+)?(un\s+)?(conseiller|humain)",
            r"(transf[ée]rer|passer)\s+.{0,15}(un\s+)?(agent|conseiller|humain)",
            r"(service\s+client|support)\s+(humain|réel)",

            # ─── Anglais ───
            r"(talk|speak)\s+(to|with)\s+(a\s+)?(human|agent|representative|someone|person)",
            r"human\s+agent",
            r"real\s+(person|human|agent)",
            r"(connect|transfer)\s+me\s+(to|with)\s+(a\s+)?(human|agent|representative)",
            r"customer\s+service\s+(rep|representative|agent)",

            # ─── Arabe littéraire ───
            r"(أريد|اريد|أحتاج|أرغب)\s+.{0,20}(التحدث|التواصل|أتحدث)\s+.{0,10}(مع\s+)?(موظف|إنسان|بشري|وكيل)",
            r"(تحويل(ي)?|حوّلني|حولني)\s+.{0,15}(موظف|وكيل|إنسان)",
            r"موظف\s+بشري",
            r"وكيل\s+بشري",

            # ─── Tunisien (arabizi + dialecte) ───
            r"n[h7]?[ae]+b\s+n[ae]7ki\s+m3a\s+(wa7ed|agent)",
            r"bcha\s+n[ae]7ki\s+m3a",
            r"7[h]?[ae]+b\s+n[ae]7ki\s+m3a\s+(wa7ed|agent)",
            r"7awelni\s+l\s*agent",
            r"insen\s+(3adi|7a[ck]i[ck]i|7ay)",
        ]

    def _load_frustration_patterns(self) -> list:
        """Regex de détection de frustration/colère envers le SERVICE.
        Combine systématiquement un mécontentement avec un contexte de
        service (mot "service"/"khedma"/"خدمة", ou une expression figée
        de ras-le-bol) — jamais un adjectif négatif seul, pour ne pas
        confondre avec une critique produit normale ("ce produit est
        nul" ne doit PAS matcher ici)."""
        return [
            # ─── Français ───
            r"service\s+(client\s+)?(est\s+)?(horrible|nul|inadmissible|catastrophique|lamentable)",
            r"j'en\s+ai\s+marre",
            r"(je\s+vais\s+)?porter\s+plainte",
            r"(ça|ca)\s+ne\s+marche\s+jamais\s+avec\s+vous",

            # ─── Anglais ───
            r"terrible\s+(customer\s+)?service",
            r"service\s+is\s+(terrible|horrible|awful|a\s+joke)",
            r"fed\s+up",
            r"filing\s+a\s+complaint",
            r"never\s+works\s+with\s+you",

            # ─── Arabe littéraire ───
            r"(خدمة|خدمتكم)\s+(سيئة|فظيعة|كارثية|مقرفة|رديئة)",
            r"سأتقدم\s+بشكوى",
            r"سئمت\s+من\s+(هذا\s+)?(التعامل|الخدمة)",
            r"لا\s+يعمل\s+معكم\s+أبدا",

            # ─── Tunisien (arabizi + dialecte) ───
            r"khedma\s+khayba",
            r"za3fen\s+barcha",
            r"mochkla\s+kbira\s+m3akom",
            r"ma\s+nesta7amelch\s+aktar",
        ]

    def _load_satisfaction_patterns(self) -> list:
        """Regex de détection d'un signal de satisfaction/résolution —
        sert à réinitialiser le compteur de boucle RAG (voir
        dialogue_manager.handle_message), pas à l'escalade. Comme pour
        le reste : "merci" seul est trop ambigu (peut clore n'importe
        quel échange sans indiquer que le problème est résolu), donc on
        exige un remerciement combiné à un mot de résolution/clôture."""
        return [
            # ─── Français ───
            r"merci.{0,15}(c'est\s+(réglé|bon|résolu)|parfait)",
            r"(c'est\s+réglé|c'est\s+résolu|c'est\s+bon).{0,15}merci",
            r"(super|nickel|parfait)\s*,?\s*merci",

            # ─── Anglais ───
            r"thanks?.{0,15}(that('s| is)\s+(fixed|solved|all\s+good)|perfect)",
            r"(that\s+(solved|fixed)\s+it|all\s+good)\s*,?\s*thanks?",

            # ─── Arabe littéraire ───
            r"شكرا.{0,15}(تم\s+الحل|تم\s+حل)",
            r"(تم\s+الحل|تم\s+حل\s+المشكلة).{0,10}شكرا",

            # ─── Tunisien (arabizi + dialecte) ───
            r"(chokran|merci)\s*,?\s*(5alas|khlas|7allit)",
            r"(5alas|khlas)\s*,?\s*(chokran|merci)",
        ]

    def is_satisfaction_signal(self, text: str) -> bool:
        """True si le message exprime une satisfaction/clôture claire
        (utilisé par dialogue_manager pour réinitialiser le compteur de
        boucle RAG, indépendamment de l'escalade)."""
        text_lower = text.lower().strip()
        return any(re.search(p, text_lower, re.IGNORECASE) for p in self._satisfaction_patterns)

    def _load_entity_patterns(self) -> dict:
        return {
            "order_number": r"(?:commande|order|cmd|ref|#)\s*[:#]?\s*([A-Z0-9]{4,15})",
            "phone_number": r"(?:0|\+?216)[\s\-]?\d{2}[\s\-]?\d{3}[\s\-]?\d{3}",
            "email": r"[\w\.\-]+@[\w\.\-]+\.\w{2,6}",
            "amount": r"\d+(?:[.,]\d{1,2})?\s*(?:dt|dinar|tnd|€|\$)",
        }

    def classify(self, text: str) -> IntentResult:
        """Détecte une demande d'escalade humaine (explicite ou par
        frustration). Tout le reste part vers le RAG (voir
        dialogue_manager.handle_message). La demande explicite est
        vérifiée en premier : si un client frustré demande aussi
        directement un agent, "explicit" est le signal le plus fort."""
        text_lower = text.lower().strip()
        entities = self._extract_entities(text)

        for pattern in self._explicit_patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return IntentResult(
                    intent="human_agent",
                    category=Category.ESCALATE,
                    confidence=0.97,
                    entities=entities,
                    requires_escalation=True,
                    escalation_reason="explicit",
                )

        for pattern in self._frustration_patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return IntentResult(
                    intent="frustration",
                    category=Category.ESCALATE,
                    confidence=0.90,
                    entities=entities,
                    requires_escalation=True,
                    escalation_reason="frustration",
                )

        return IntentResult(
            intent="general",
            category=Category.GENERAL,
            confidence=0.0,
            entities=entities,
            requires_escalation=False,
            escalation_reason=None,
        )

    def _extract_entities(self, text: str) -> dict:
        """Extraction d'entités (numéro de commande, téléphone, email,
        montant) — utile pour le RAG et les logs, indépendant de la
        classification d'intent."""
        entities = {}
        for name, pattern in self._entity_patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = match.group(1) if match.lastindex else match.group(0)
                entities[name] = value.strip().upper()
        return entities
