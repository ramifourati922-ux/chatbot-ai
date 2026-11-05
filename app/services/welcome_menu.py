# app/services/welcome_menu.py
"""
Menu d'accueil : des boutons qui envoient au bot une question précise.

Un client qui écrit « bonjour » (ou qui ouvre le chat du site) reçoit en
plus de la réponse un menu des sujets traités. Un clic envoie la question
du bouton, exactement comme si le client l'avait tapée : elle passe par
dialogue_manager.handle_message (transfert, suivi de commande, RAG...),
le moteur ne change pas. Le client n'a plus à formuler sa demande, ce qui
évite les messages vagues (« i need your help », « je veux plus
d'informations ») que la recherche RAG traite mal.

Une seule définition pour les trois canaux :
- site (static/chat.html, via GET /chat/menu et le WebSocket) ;
- WhatsApp : message interactif « liste » (10 lignes au plus, titre de
  24 caractères au plus) ;
- Messenger : réponses rapides (« quick replies », 13 au plus, titre de
  20 caractères au plus).

Identifiant d'un bouton : "menu:<sujet>:<langue>" (ex. "menu:livraison:tn").
WhatsApp et Messenger le renvoient tel quel au clic : on retrouve la
question dans la langue du menu affiché, sans dépendre du titre du bouton.
"""

from typing import Optional

MENU_ID_PREFIX = "menu:"
DEFAULT_LANGUAGE = "fr"

# Ordre d'affichage. Chaque question a été choisie pour être traitée par le
# moteur existant : "commande" → suivi de commande, "conseiller" → demande
# explicite d'humain, les autres → recherche RAG dans les politiques.
TOPICS = ("commande", "livraison", "retours", "garantie", "paiement", "conseiller")

# sujet → langue → (titre du bouton, question envoyée au bot).
# Titres de 20 caractères au plus (limite Messenger, la plus stricte).
# Questions en tunisien : arabizi mêlé de mots français, comme l'écrivent
# les clients. Le modèle d'embeddings comprend mal l'arabizi seul : avec
# « kifech nraja3 produit ? », la recherche trouvait des fiches produits au
# lieu de la politique de retour, et « kifech najjem nkhallas ? » passait
# sous le seuil de confiance (transfert à un conseiller).
_OPTIONS = {
    "commande": {
        "fr": ("Suivre ma commande", "Où est ma commande ?"),
        "en": ("Track my order", "Where is my order?"),
        "ar": ("تتبع طلبيتي", "أين وصلت طلبيتي؟"),
        "tn": ("Win commande mte3i", "win wselt el commande mte3i ?"),
    },
    "livraison": {
        "fr": ("Délais de livraison", "Quels sont les délais de livraison ?"),
        "en": ("Delivery times", "What are the delivery times?"),
        "ar": ("مدة التوصيل", "ما هي مدة التوصيل؟"),
        "tn": ("Livraison", "9adech ta5ou el livraison ?"),
    },
    "retours": {
        "fr": ("Retourner un produit", "Comment retourner un produit ?"),
        "en": ("Return a product", "How do I return a product?"),
        "ar": ("إرجاع منتج", "كيف يمكنني إرجاع منتج؟"),
        "tn": ("Nraja3 produit", "kifech na3mel retour mta3 produit ?"),
    },
    "garantie": {
        "fr": ("Garantie", "Quelle est la durée de garantie ?"),
        "en": ("Warranty", "How long is the warranty?"),
        "ar": ("الضمان", "ما هي مدة الضمان؟"),
        "tn": ("Garantie", "9adech dourat el garantie ?"),
    },
    "paiement": {
        "fr": ("Moyens de paiement", "Quels moyens de paiement acceptez-vous ?"),
        "en": ("Payment methods", "Which payment methods do you accept?"),
        "ar": ("طرق الدفع", "ما هي طرق الدفع المتاحة؟"),
        "tn": ("Kifech nkhallas", "chnouma les moyens de paiement mta3kom ?"),
    },
    "conseiller": {
        "fr": ("Parler à un humain", "Je veux parler à un conseiller"),
        "en": ("Talk to an agent", "I want to talk to an agent"),
        "ar": ("التحدث مع موظف", "أريد التحدث مع موظف"),
        "tn": ("Na7ki m3a wa7ed", "nheb na7ki m3a wa7ed"),
    },
}

# Phrase qui accompagne le menu et texte du bouton qui ouvre la liste
# WhatsApp (20 caractères au plus).
_INTRO = {
    "fr": "Choisissez un sujet, ou écrivez votre question :",
    "en": "Choose a topic, or type your question:",
    "ar": "اختر موضوعًا، أو اكتب سؤالك:",
    "tn": "Ekhtar sujet, walla ekteb sou2alek :",
}
_LIST_BUTTON = {"fr": "Voir les sujets", "en": "See topics", "ar": "عرض المواضيع", "tn": "Chouf les sujets"}


def _language(language: Optional[str]) -> str:
    return language if language in _INTRO else DEFAULT_LANGUAGE


def menu(language: Optional[str] = None) -> list:
    """Les boutons du menu dans cette langue (français par défaut)."""
    lang = _language(language)
    return [
        {"id": f"{MENU_ID_PREFIX}{topic}:{lang}", "label": _OPTIONS[topic][lang][0],
         "question": _OPTIONS[topic][lang][1]}
        for topic in TOPICS
    ]


def intro(language: Optional[str] = None) -> str:
    return _INTRO[_language(language)]


def list_button(language: Optional[str] = None) -> str:
    return _LIST_BUTTON[_language(language)]


def question_for(option_id: Optional[str]) -> Optional[str]:
    """La question d'un bouton à partir de son identifiant, ou None si
    l'identifiant n'est pas celui d'un bouton du menu."""
    if not option_id or not option_id.startswith(MENU_ID_PREFIX):
        return None
    parts = option_id[len(MENU_ID_PREFIX):].split(":")
    if len(parts) != 2:
        return None
    topic, lang = parts
    option = _OPTIONS.get(topic, {}).get(lang)
    return option[1] if option else None


def should_offer(result) -> bool:
    """Proposer le menu avec cette réponse ? Oui après une salutation du
    client (« bonjour », « aslema »...) ou une demande d'aide vague
    (« i need your help », intention apprise "help") : le client n'a pas
    encore dit ce qu'il cherche. Jamais pendant un transfert ni quand un
    conseiller a la main."""
    return (
        getattr(result, "intent", None) in ("greeting", "help")
        and not getattr(result, "escalated", False)
        and not getattr(result, "handled_by_agent", False)
    )
