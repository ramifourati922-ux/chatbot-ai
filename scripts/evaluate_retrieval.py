# scripts/evaluate_retrieval.py
"""
Banc de test de la recherche RAG, langue par langue, sans LLM (aucun
quota Groq consommé).

data/evaluation/recherche.json : 17 thèmes (12 règles, 5 produits), chacun
posé en français, anglais, arabe et tunisien, soit 68 questions. Pour
chaque mode de recherche (basic, hybrid, advanced) et chaque langue :

- hit@4 : part des questions dont une bonne source figure dans les 4
  passages envoyés au LLM ;
- MRR@4 : moyenne de 1/rang de la première bonne source (1 = en tête,
  0 = absente des 4) : mesure aussi l'ordre, que le reranker modifie ;
- temps moyen de la recherche.

Complète l'évaluation RAGas (docs/evaluation/ragas_results.md), qui ne
comptait que 3 à 4 questions en arabe et en tunisien.

Usage :
    python scripts/evaluate_retrieval.py
    python scripts/evaluate_retrieval.py --out docs/evaluation/recherche_par_langue.md
"""

import argparse
import csv
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.services import arabizi
from app.services.language_detector import detect_language
from app.services.rag import retriever

ROOT = Path(__file__).parent.parent
LANGUAGES = ("fr", "en", "ar", "tn")
# nom affiché → (mode de recherche, expansion de l'arabizi comme en production)
MODES = {
    "basic": ("basic", False),
    "hybrid": ("hybrid", False),
    "advanced": ("advanced", False),
    "advanced + arabizi": ("advanced", True),
}


def load_questions(name: str) -> list:
    """[(thème, langue, question, sources acceptées), ...] pour les langues
    présentes dans chaque thème."""
    data = json.loads((ROOT / "data" / "evaluation" / name).read_text(encoding="utf-8"))
    with open(ROOT / "data" / "knowledge_base" / "ecommerce" / "produits.csv", encoding="utf-8") as f:
        catalog = list(csv.DictReader(f))
    questions = []
    for item in data["questions"]:
        if "produit" in item:
            accepted = {p["sku"] for p in catalog if item["produit"].lower() in p["nom"].lower()}
        else:
            accepted = set(item["sources"])
        for lang in LANGUAGES:
            if lang in item:
                questions.append((item["theme"], lang, item[lang], accepted))
    return questions


def evaluate(questions: list, mode: str, expand_arabizi: bool) -> dict:
    settings.RAG_RETRIEVAL_MODE = mode
    retriever.search("préchauffage", 4)  # chargement des modèles hors mesure
    per_lang = defaultdict(lambda: {"hits": 0, "rr": 0.0, "n": 0, "ms": 0.0})
    misses = []
    for theme, lang, question, accepted in questions:
        # Comme dialogue_manager : expansion seulement si la langue DÉTECTÉE est le tunisien
        query = arabizi.expand(question) if expand_arabizi and detect_language(question) == "tn" else question
        t0 = time.perf_counter()
        hits = retriever.search(query, 4)
        elapsed = (time.perf_counter() - t0) * 1000
        found = [h["metadata"].get("source") or h["metadata"].get("sku") for h in hits]
        rank = next((i for i, source in enumerate(found, start=1) if source in accepted), None)
        stats = per_lang[lang]
        stats["n"] += 1
        stats["ms"] += elapsed
        if rank:
            stats["hits"] += 1
            stats["rr"] += 1 / rank
        else:
            misses.append((lang, theme, question))
    return {"per_lang": per_lang, "misses": misses}


def report(results: dict, set_name: str, n_questions: int, out: Path | None) -> None:
    lines = [
        "# Recherche RAG par langue (sans LLM)",
        "",
        f"Banc de test : `data/evaluation/{set_name}`, {n_questions} questions. "
        "Mesuré par `scripts/evaluate_retrieval.py`.",
        "",
        "- **hit@4** : une bonne source figure dans les 4 passages envoyés au LLM.",
        "- **MRR@4** : moyenne de 1/rang de la première bonne source (1 = toujours en tête).",
        "- **advanced + arabizi** : question tunisienne complétée par la traduction des mots reconnus "
        "(`app/services/arabizi.py`), comme en production avec `RAG_ARABIZI_EXPANSION`.",
        "",
        "| Mode | Langue | hit@4 | MRR@4 | Temps moyen de recherche |",
        "| --- | --- | --- | --- | --- |",
    ]
    for mode in MODES:
        per_lang = results[mode]["per_lang"]
        langs = [lang for lang in LANGUAGES if per_lang[lang]["n"]]
        for lang in langs:
            s = per_lang[lang]
            lines.append(f"| {mode} | {lang} | {s['hits']}/{s['n']} ({s['hits'] / s['n']:.0%}) | "
                         f"{s['rr'] / s['n']:.2f} | {s['ms'] / s['n']:.0f} ms |")
        if len(langs) > 1:
            total = {k: sum(per_lang[lang][k] for lang in langs) for k in ("hits", "rr", "n", "ms")}
            lines.append(f"| **{mode}** | **toutes** | **{total['hits']}/{total['n']} "
                         f"({total['hits'] / total['n']:.0%})** | **{total['rr'] / total['n']:.2f}** | "
                         f"**{total['ms'] / total['n']:.0f} ms** |")
    for mode in MODES:
        misses = results[mode]["misses"]
        lines += ["", f"Questions sans bonne source dans les 4 passages, mode {mode} ({len(misses)}) :", ""]
        lines += [f"- [{lang}] {theme} : « {question} »" for lang, theme, question in misses] or ["- aucune"]
    lines += [
        "", "## Limites", "",
        "- Peu de thèmes, questions écrites pour le projet : des tendances, pas des mesures définitives.",
        "- Les questions arabes sur un produit gardent son nom en lettres latines (« ESP32 »), "
        "comme les clients l'écrivent.",
        "- Mesure la recherche seule, pas la réponse rédigée par le LLM (voir l'évaluation RAGas).",
        "- Lexique arabizi écrit après avoir vu les échecs en tunisien de `recherche.json` : sa "
        "généralisation est vérifiée sur des questions tunisiennes nouvelles "
        "(`recherche_tunisien_nouvelles.json`).",
        "- Temps mesurés sur un ordinateur portable, sans GPU.",
    ]
    text = "\n".join(lines) + "\n"
    print(text)
    if out:
        out.write_text(text, encoding="utf-8")
        print(f"Écrit dans {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--set", default="recherche.json", help="jeu de questions dans data/evaluation/")
    parser.add_argument("--out", type=Path, help="écrire le rapport Markdown")
    args = parser.parse_args()
    questions = load_questions(args.set)
    results = {name: evaluate(questions, *MODES[name]) for name in MODES}
    report(results, args.set, len(questions), args.out)
