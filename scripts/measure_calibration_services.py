"""
Seuil de confiance RAG (0,35) face à 18 questions sur des services plausibles
mais non proposés, avec l'issue réelle dans le pipeline (POST /chat/).

1. Recherche seule, en mode advanced comme /chat/ (retriever.search, top 4),
   collection de production en LECTURE seule : plus petite distance, score de
   confiance (1 - distance min), passages retenus (filtre 0,75), meilleur
   document, arrêt par le seuil.
2. Issue réelle : POST /chat/ (API locale, session neuve) pour chaque question
   dont le score est >= 0,35 (le LLM est appelé), et pour UNE seule question
   sous le seuil (vérification du message d'escalade). Appels espacés de 3,2 s.
3. Comparaison : mêmes mesures pour les 10 questions produit et les 4 questions
   hors sujet de la calibration (scripts/calibrate_threshold.py).
4. Nettoyage : lignes PostgreSQL et sessions Redis créées, par identifiant.

Les 18 questions viennent du script de mesure utilisé pour le tableau
tab:calib18 du rapport (calib18.py, 19/11/2026), reprises à l'identique.

Usage (API démarrée sur http://127.0.0.1:8000) :
    python scripts/measure_calibration_services.py
"""
import asyncio
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from app.config import settings  # noqa: E402
from app.services.language_detector import detect_language  # noqa: E402
from app.services.rag import hybrid_retriever, retriever  # noqa: E402
from scripts.calibrate_threshold import OFFTOPIC_QUESTIONS, PRODUCT_QUESTIONS  # noqa: E402
from scripts.measure_escalation_latency import Bench, cleanup, db_check  # noqa: E402

SERVICES = [
    "Faites-vous la réparation d'ordinateurs portables ?", "Proposez-vous la location de matériel électronique ?",
    "Avez-vous une boutique à Paris ?", "Livrez-vous en Algérie ?", "Proposez-vous des formations en robotique ?",
    "Concevez-vous des circuits imprimés sur mesure pour les entreprises ?",
    "Vendez-vous des téléphones portables reconditionnés ?", "Acceptez-vous le paiement en cryptomonnaie ?",
    "Installez-vous des panneaux solaires à domicile ?", "Développez-vous des applications mobiles sur commande ?",
    "Proposez-vous un abonnement mensuel de composants ?", "Vendez-vous des pièces détachées automobiles ?",
    "Recrutez-vous des stagiaires cet été ?", "Livrez-vous par drone ?",
    "Organisez-vous des ateliers d'électronique pour enfants ?", "Puis-je payer en plusieurs fois sans frais ?",
    "Acceptez-vous les chèques-cadeaux d'autres magasins ?", "Faites-vous de la maintenance de serveurs ?",
]
OUT = ROOT / "docs" / "evaluation" / "calibration_18_services.json"


def retrieval(question):
    hits = retriever.search(question, 4)
    candidates = hybrid_retriever.search(question, top_k=settings.RERANK_CANDIDATES)  # avant reranking
    conf = retriever.get_best_confidence(hits)
    best = min(hits, key=lambda h: h["distance"]) if hits else None
    return {
        "langue": detect_language(question),
        "distance_min": round(best["distance"], 3) if best else None,
        "score": round(conf, 3),
        "passages_retenus": len(hits),
        "candidats_sous_075": len(candidates),
        "meilleur_doc": None if best is None else {
            "type": best["metadata"].get("type"),
            "id": best["metadata"].get("sku") or best["metadata"].get("source"),
            "texte": best["document"].split("\nR:")[0].split(" | ")[0][:90]},
        "arretee_par_seuil": conf < retriever.get_confidence_threshold(hits),
    }


def main():
    settings.RAG_RETRIEVAL_MODE = "advanced"
    retriever.search("préchauffage", 4)
    rows = [{"question": q, **retrieval(q)} for q in SERVICES]
    legit = [{"question": q, **retrieval(q)} for _, q in PRODUCT_QUESTIONS]
    off = [{"question": q, **retrieval(q)} for q in OFFTOPIC_QUESTIONS]
    for r in rows:
        print(f"{r['score']:.3f} {'ARRÊT' if r['arretee_par_seuil'] else 'LLM  '} {r['passages_retenus']} | {r['question']}",
              flush=True)

    b = Bench()
    b.post("bonjour")  # échauffement, non compté
    checked_one_below = False
    for r in rows:
        if r["arretee_par_seuil"] and checked_one_below:
            r["chat"] = None  # LLM non appelé : pas d'appel /chat/ inutile
            continue
        _, d = b.post(r["question"])
        r["chat"] = {k: d[k] for k in ("response", "intent", "confidence", "escalated", "escalation_reason", "sources")}
        checked_one_below |= r["arretee_par_seuil"]
        print("   ->", d["escalated"], d["escalation_reason"], "|", d["response"][:120].replace("\n", " "), flush=True)

    OUT.with_name("calibration_18_services_sessions.json").write_text(json.dumps(b.sessions), encoding="utf-8")
    import time
    time.sleep(3)

    async def post():
        return await db_check(b.sessions), await cleanup(b.sessions)
    before, clean = asyncio.run(post())

    def s(v):
        return {"min": min(v), "mediane": round(statistics.median(v), 3), "max": max(v)}
    R = {"services": rows, "legitimes": legit, "hors_sujet": off,
         "scores": {"services": s([r["score"] for r in rows]), "legitimes": s([r["score"] for r in legit]),
                    "hors_sujet": s([r["score"] for r in off])},
         "base_avant_nettoyage": {"users": len(before["users"]), "conversations": len(before["conversations"]),
                                  "messages": before["messages"]},
         "nettoyage": clean, "config": {"mode": settings.RAG_RETRIEVAL_MODE, "signal": settings.RAG_CONFIDENCE_SIGNAL,
                                        "seuil": settings.RAG_CONFIDENCE_THRESHOLD,
                                        "RERANK_CANDIDATES": settings.RERANK_CANDIDATES,
                                        "MAX_RELEVANT_DISTANCE": retriever.MAX_RELEVANT_DISTANCE,
                                        "reranker": settings.RERANKER_MODEL}}
    OUT.write_text(json.dumps(R, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: R[k] for k in ("scores", "base_avant_nettoyage", "nettoyage")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
