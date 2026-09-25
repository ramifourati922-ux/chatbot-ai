# scripts/calibrate_threshold.py
"""
Recalibrage empirique de RAG_CONFIDENCE_THRESHOLD (Advanced RAG, étape 3).

Même protocole que la calibration d'origine (test_calibration.py) :
10 questions produit (une par catégorie du catalogue) + 4 questions
hors-sujet. Mesuré pour les 3 pipelines (basic / hybrid / advanced), et
en mode advanced pour les 2 signaux de confiance candidats :
    - cosinus  : 1 - plus petite distance cosinus parmi les hits retenus
                 (signal par défaut, retriever.get_best_confidence)
    - reranker : score cross-encoder (sigmoïde, 0-1) du meilleur hit

Usage :
    ./venv/Scripts/python.exe scripts/calibrate_threshold.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.services.rag import retriever

PRODUCT_QUESTIONS = [
    ("Capteurs", "Avez-vous un capteur de distance VL53L0X ?"),
    ("Connectique", "Je cherche des cables Dupont male-femelle"),
    ("Alimentation", "Vous avez des piles 18650 en stock ?"),
    ("Moteurs & Roues", "Combien coute un moteur pas-a-pas NEMA17 ?"),
    ("Afficheurs", "Avez-vous un afficheur 7 segments 4 chiffres ?"),
    ("Eclairage LED", "Je voudrais un controleur LED RGB avec telecommande"),
    ("Instruments de Mesure", "Vous vendez des analyseurs logiques 8 canaux ?"),
    ("Outillage", "Avez-vous de l'etain a souder sans plomb ?"),
    ("Cartes Programmables", "Est-ce que la carte Arduino Due est disponible ?"),
    ("Modules", "Je cherche un module relais 16 canaux"),
]

OFFTOPIC_QUESTIONS = [
    "Quelle est la recette du couscous tunisien ?",
    "Combien de lunes a la planete Jupiter ?",
    "Quelle est la capitale de la France ?",
    "Raconte-moi une blague",
]


def _signals(question: str, mode: str) -> dict:
    settings.RAG_RETRIEVAL_MODE = mode
    hits = retriever.search(question, top_k=4)
    return {
        "cosinus": retriever.get_best_confidence(hits),
        "reranker": max((h["rerank_score"] for h in hits), default=0.0) if mode == "advanced" else None,
        "top1": hits[0]["document"].split("|")[0].split("\n")[0][:45] if hits else "(aucun hit)",
    }


def _summary(label: str, product: list, offtopic: list):
    lo, hi = min(product), max(offtopic)
    sep = "séparables" if lo > hi else "NON séparables"
    print(f"{label:22s} produits min={lo:.3f} (max={max(product):.3f})  |  "
          f"hors-sujet max={hi:.3f} (min={min(offtopic):.3f})  →  {sep}, marge={lo - hi:+.3f}")


def main():
    results = {}
    for mode in ("basic", "hybrid", "advanced"):
        results[mode] = {
            "product": [(cat, q, _signals(q, mode)) for cat, q in PRODUCT_QUESTIONS],
            "offtopic": [(None, q, _signals(q, mode)) for q in OFFTOPIC_QUESTIONS],
        }

    for mode, res in results.items():
        print(f"\n=== {mode} ===")
        for group in ("product", "offtopic"):
            for cat, q, s in res[group]:
                rr = f"  reranker={s['reranker']:.3f}" if s["reranker"] is not None else ""
                print(f"  [{(cat or 'hors-sujet'):22s}] cos={s['cosinus']:.3f}{rr}  top1={s['top1']!r}  <- {q}")

    print("\n=== Résumé ===")
    for mode, res in results.items():
        _summary(f"{mode} / cosinus",
                 [s["cosinus"] for _, _, s in res["product"]],
                 [s["cosinus"] for _, _, s in res["offtopic"]])
    adv = results["advanced"]
    _summary("advanced / reranker",
             [s["reranker"] for _, _, s in adv["product"]],
             [s["reranker"] for _, _, s in adv["offtopic"]])
    print(f"\nSeuils : cosinus = {settings.RAG_CONFIDENCE_THRESHOLD} (défaut), "
          f"reranker = {settings.RAG_RERANK_CONFIDENCE_THRESHOLD} (RAG_CONFIDENCE_SIGNAL=reranker)")


if __name__ == "__main__":
    main()
