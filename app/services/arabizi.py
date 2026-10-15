# app/services/arabizi.py
"""
Expansion des questions en arabizi tunisien avant la recherche RAG.

La base de connaissances est rédigée en français. Une question en arabizi
(« kifech nraja3 produit ? ») partage peu de mots avec elle : la recherche
par mots-clés (BM25) ne trouve rien, et le modèle d'embeddings comprend mal
l'arabizi. Mesuré sur data/evaluation/recherche.json : 59 % de bonnes
sources en tunisien, contre 94 à 100 % dans les autres langues.

On ajoute à la question la traduction française des mots du SAV reconnus :
« kifech nraja3 produit ? » → « kifech nraja3 produit ? (comment retourner) ».
La question d'origine est gardée telle quelle (le LLM la reçoit sans
changement ; seule la recherche utilise la version complétée).

Lexique volontairement général (vocabulaire courant du service client),
pas construit sur les questions du banc de test. Plusieurs orthographes par
mot : l'arabizi n'a pas d'orthographe fixe.
"""

import re

# mot arabizi → traduction française (mots-clés de la base de connaissances)
LEXICON = {
    # Questions
    "kifech": "comment", "kifeh": "comment", "kifach": "comment",
    "9adech": "combien", "9adeh": "combien", "9addech": "combien", "b9adech": "combien prix",
    "chnouwa": "quoi", "chnowa": "quoi", "chnoua": "quoi", "chnia": "quoi", "chnouma": "quels",
    "wa9tech": "quand", "wa9teh": "quand", "waktech": "quand",
    "win": "où", "wein": "où", "3lech": "pourquoi", "3lach": "pourquoi",
    "chkoun": "qui", "chkon": "qui",
    # Retours, échanges, remboursement
    "nraja3": "retourner retour", "nrajja3": "retourner retour", "raja3": "retourner retour",
    "nrajja3li": "retourner retour", "rja3": "retour", "nbadel": "échanger", "nbaddel": "échanger",
    "tbadel": "échanger", "flousi": "remboursement", "flous": "argent remboursement",
    # Livraison, commande
    "twaslou": "livrez livraison", "twasslou": "livrez livraison", "tousel": "livraison arrive",
    "yousel": "livraison arrive", "wsel": "arrivé reçu", "wslet": "arrivée reçue",
    "tba3thet": "expédiée", "nkoumandi": "commander", "commandit": "commandé",
    "sebt": "samedi week-end", "a7ad": "dimanche week-end", "jem3a": "semaine", "nhar": "jours",
    "nhar3": "jours", "lyoum": "aujourd'hui", "ghodwa": "demain",
    # Paiement, prix
    "nkhallas": "payer paiement", "nkhalles": "payer paiement", "ykhalles": "paie paiement frais",
    "khlass": "paiement", "ta9sit": "plusieurs fois", "taksit": "plusieurs fois",
    "soum": "prix", "s3ar": "prix", "rkhis": "pas cher", "ghali": "cher", "ghalya": "cher",
    "cash": "espèces", "carta": "carte",
    # Produit, état, panne
    "mkasser": "cassé", "mkassra": "cassée", "khayeb": "défectueux mauvais", "ma5demch": "ne fonctionne pas",
    "ye5demch": "ne fonctionne pas", "t5demch": "ne fonctionne pas", "msakker": "fermé",
    "ma ydakhlouch": "pas couvert", "ydakhlou": "couvert",
    # Boutique, contact
    "magasin": "boutique", "7anout": "boutique", "yetsakker": "horaires ouverture fermeture",
    "yet7al": "ouvert horaires", "nkalmekom": "contacter", "telephone": "téléphone contacter",
}

_WORD = re.compile(r"\w+", re.UNICODE)


def expand(text: str) -> str:
    """La question, suivie entre parenthèses de la traduction des mots
    arabizi reconnus ; inchangée si aucun mot n'est reconnu."""
    lowered = text.lower()
    found = []
    for phrase in (k for k in LEXICON if " " in k):  # expressions de plusieurs mots
        if phrase in lowered:
            found.append(LEXICON[phrase])
    for word in _WORD.findall(lowered):
        translation = LEXICON.get(word)
        if translation and translation not in found:
            found.append(translation)
    return f"{text} ({' '.join(found)})" if found else text
