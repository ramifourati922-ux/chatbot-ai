"""
Remarque 53 :
A) tests des signes (exact, bilatéral) et de Wilcoxon apparié sur les gains Ragas
   Basic → Advanced (docs/evaluation/ragas_results.json, lecture seule) ;
B) ablation de la recherche, SANS LLM, sur les 22 questions notées du jeu Ragas :
   retriever.search(question, 4), comme scripts/evaluate_ragas.py (run_pipeline),
   en modes basic / hybrid / advanced, expansion de l'arabizi désactivée (état de
   la mesure Ragas : run_pipeline n'appelle jamais arabizi.expand) puis activée
   (comme dialogue_manager : seulement si la langue détectée est le tunisien).
   Mesures sur SOURCES ATTENDUES (champ « sources »), pas des scores Ragas.
   Dérive : sources retrouvées maintenant contre retrieved_sources stockées.
C) chiffrage (aucun calcul lancé) à partir de meta.

Réglages modifiés EN MÉMOIRE seulement (settings.RAG_RETRIEVAL_MODE). Production
ChromaDB en lecture seule ; aucun appel Groq ; aucune écriture en base.

Usage : python scripts/measure_ablation_recherche.py
"""
import ast
import hashlib
import json
import random
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from scipy.stats import binomtest, wilcoxon  # noqa: E402

from app.config import settings  # noqa: E402

SRC = ROOT / "docs" / "evaluation" / "ragas_results.json"
OUT = ROOT / "data" / "evaluation" / "ablation_recherche.json"
METRICS = ("context_precision", "context_recall", "faithfulness", "answer_relevancy")
MODES = ("basic", "hybrid", "advanced")
LANGS = ("fr", "en", "ar", "tn")
SEED, B = 42, 10000


def golden_set():
    """GOLDEN_SET de scripts/evaluate_ragas.py, sans importer ragas : seules les
    affectations _ESP32 (liste de SKU) et GOLDEN_SET sont exécutées."""
    tree = ast.parse((ROOT / "scripts" / "evaluate_ragas.py").read_text(encoding="utf-8"))
    keep = [n for n in tree.body if isinstance(n, ast.Assign)
            and any(getattr(t, "id", None) in ("_ESP32", "GOLDEN_SET") for t in n.targets)]
    ns = {}
    exec(compile(ast.Module(body=keep, type_ignores=[]), "evaluate_ragas.py", "exec"), {}, ns)
    if "GOLDEN_SET" not in ns:
        raise RuntimeError("GOLDEN_SET introuvable")
    return ns["GOLDEN_SET"]


def boot(diffs):
    rng = random.Random(SEED)
    m = sorted(statistics.fmean(rng.choices(diffs, k=len(diffs))) for _ in range(B))
    return [round(m[int(0.025 * B)], 3), round(m[int(0.975 * B) - 1], 3)]


def counts(diffs, eps=1e-12):
    return {"progressent": sum(d > eps for d in diffs), "egales": sum(abs(d) <= eps for d in diffs),
            "reculent": sum(d < -eps for d in diffs)}


def part_a(data):
    rows = [r for r in data["results"] if r["category"] != "hors-sujet"]
    out = {}
    for m in METRICS:
        diffs = []
        for r in rows:
            b = r["runs"]["basic"]["ragas"]["scores"].get(m)
            a = r["runs"]["advanced"]["ragas"]["scores"].get(m)
            if b is not None and a is not None:
                diffs.append(a - b)
        c = counts(diffs)
        n_nz = c["progressent"] + c["reculent"]
        p_sign = binomtest(c["progressent"], n_nz, 0.5, alternative="two-sided").pvalue if n_nz else None
        nz = [d for d in diffs if abs(d) > 1e-12]
        w = wilcoxon(nz, alternative="two-sided") if len(nz) >= 1 else None
        out[m] = {"n_apparie": len(diffs), **c, "test_signes_p": round(p_sign, 4) if p_sign is not None else None,
                  "wilcoxon": {"n_sans_egalites": len(nz), "statistique": float(w.statistic) if w else None,
                               "p": round(float(w.pvalue), 4) if w else None,
                               "methode": "scipy.stats.wilcoxon, égalités exclues (zero_method='wilcox')"}}
    return out


def src(hit):
    return hit["metadata"].get("source") or hit["metadata"].get("sku")


def part_b(items, stored):
    from app.services import arabizi
    from app.services.language_detector import detect_language
    from app.services.rag import hybrid_retriever, reranker, retriever
    from app.services.rag.embedding_service import embed
    embed("warmup")
    hybrid_retriever._get_index()
    reranker.warmup()
    res = {}
    for expansion in (False, True):
        for mode in MODES:
            settings.RAG_RETRIEVAL_MODE = mode
            retriever.search("préchauffage", 4)
            per = []
            for it in items:
                q = it["question"]
                query = arabizi.expand(q) if expansion and detect_language(q) == "tn" else q
                hits = retriever.search(query, 4)
                got = [src(h) for h in hits]
                exp = set(it["sources"])
                inter = exp & set(got)
                rank = next((i for i, s in enumerate(got, 1) if s in exp), None)
                per.append({"id": it["id"], "langue": it["lang"], "requete_modifiee": query != q,
                            "sources": got, "hit4": 1.0 if inter else 0.0,
                            "rappel_sources": len(inter) / len(exp), "precision_sources": len(inter) / 4,
                            "borne_precision": min(len(exp), 4) / 4, "rr": 1 / rank if rank else 0.0})
            res[f"{mode}|{'arabizi' if expansion else 'sans_arabizi'}"] = per
            print(mode, "arabizi" if expansion else "sans", round(statistics.fmean(p["hit4"] for p in per), 3), flush=True)
    settings.RAG_RETRIEVAL_MODE = "advanced"
    return res


def summarize(per):
    def agg(rows):
        return {"n": len(rows), **{k: round(statistics.fmean(r[k] for r in rows), 3)
                                   for k in ("hit4", "rappel_sources", "precision_sources", "borne_precision", "rr")}}
    return {"total": agg(per), **{lg: agg([r for r in per if r["langue"] == lg]) for lg in LANGS}}


def paired(res, tag):
    out = {}
    for a, b in (("basic", "hybrid"), ("hybrid", "advanced"), ("basic", "advanced")):
        A, Bv = res[f"{a}|{tag}"], res[f"{b}|{tag}"]
        out[f"{a}->{b}"] = {}
        for k in ("hit4", "rappel_sources", "precision_sources", "rr"):
            d = [y[k] - x[k] for x, y in zip(A, Bv)]
            out[f"{a}->{b}"][k] = {"moyenne": round(statistics.fmean(d), 3), "ic95": boot(d), **counts(d)}
    parts = {}
    for k in ("hit4", "rappel_sources", "precision_sources", "rr"):
        tot = out["basic->advanced"][k]["moyenne"]
        hyb = out["basic->hybrid"][k]["moyenne"]
        parts[k] = {"gain_total": tot, "dont_hybride": hyb, "dont_reclassement": round(tot - hyb, 3),
                    "part_hybride": round(hyb / tot, 2) if tot else None}
    out["decomposition"] = parts
    return out


def drift(res, data):
    stored = {r["id"]: r for r in data["results"]}
    out = {}
    for mode in ("basic", "advanced"):
        now = {p["id"]: p["sources"] for p in res[f"{mode}|sans_arabizi"]}
        same_list = [i for i, s in now.items() if s == stored[i]["runs"][mode]["retrieved_sources"]]
        same_set = [i for i, s in now.items() if set(s) == set(stored[i]["runs"][mode]["retrieved_sources"])]
        out[mode] = {"identiques_ordre_compris": len(same_list), "identiques_en_ensemble": len(same_set), "n": len(now),
                     "differentes": [{"id": i, "stockees": stored[i]["runs"][mode]["retrieved_sources"], "maintenant": s}
                                     for i, s in now.items() if s != stored[i]["runs"][mode]["retrieved_sources"]],
                     "hit4_stocke": round(statistics.fmean(1.0 if stored[i]["runs"][mode]["hit_at_4"] else 0.0 for i in now), 3)}
    return out


def part_c(meta):
    judge_tok, gen_tok = meta["judge_tokens"], meta["gen_tokens"]
    per_mode_judge = judge_tok / 2
    per_mode_gen = gen_tok / 2
    per_mode_min = meta["duration_min"] / 2
    return {"hypotheses": "coût d'un mode = moitié du coût mesuré pour basic + advanced (mêmes 25 questions, "
                          "même juge) ; les tokens comptés sont ceux des réponses 200 (relances 429 sans tokens) ; "
                          "ils incluent les appels de questions abandonnées sur quota puis refaites (non séparables)",
            "un_mode_hybrid": {"tokens_juge": round(per_mode_judge), "tokens_generation": round(per_mode_gen),
                               "requetes_juge": round(meta["judge_requests"] / 2), "requetes_generation": round(meta["gen_requests"] / 2),
                               "jours_quota_juge_200k": round(per_mode_judge / 200000, 2),
                               "jours_quota_generation_200k": round(per_mode_gen / 200000, 2),
                               "duree_calcul_min": round(per_mode_min, 1)},
            "trois_repetitions_basic_advanced": {"tokens_juge": 3 * judge_tok, "tokens_generation": 3 * gen_tok,
                                                 "jours_quota_juge_200k": round(3 * judge_tok / 200000, 2),
                                                 "jours_quota_generation_200k": round(3 * gen_tok / 200000, 2),
                                                 "duree_calcul_min": round(3 * meta["duration_min"], 1)}}


def main():
    h0 = hashlib.sha256(SRC.read_bytes()).hexdigest()
    data = json.loads(SRC.read_text(encoding="utf-8"))
    gs = golden_set()
    by_id = {r["id"]: r for r in data["results"]}
    items = [g for g in gs if g["category"] != "hors-sujet"]
    coherence = {"golden_set": len(gs), "notees": len(items),
                 "identiques_au_json": sum(1 for g in items if by_id[g["id"]]["question"] == g["question"]
                                           and by_id[g["id"]]["sources"] == g["sources"] and by_id[g["id"]]["lang"] == g["lang"])}
    print("cohérence", coherence, flush=True)
    R = {"sha256_avant": h0, "coherence_jeu": coherence, "A_tests": part_a(data)}
    res = part_b(items, data)
    R["B_par_question"] = res
    R["B_resume"] = {k: summarize(v) for k, v in res.items()}
    R["B_apparie"] = {tag: paired(res, tag) for tag in ("sans_arabizi", "arabizi")}
    R["B_derive"] = drift(res, data)
    R["C_chiffrage"] = part_c(data["meta"])
    R["config"] = {"RERANK_CANDIDATES": settings.RERANK_CANDIDATES, "reranker": settings.RERANKER_MODEL,
                   "embedding": settings.EMBEDDING_MODEL, "meta_ragas": data["meta"]}
    R["sha256_apres"] = hashlib.sha256(SRC.read_bytes()).hexdigest()
    OUT.write_text(json.dumps(R, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: R[k] for k in ("A_tests", "B_resume", "B_derive", "C_chiffrage", "sha256_avant", "sha256_apres")},
                     ensure_ascii=False)[:6000])


if __name__ == "__main__":
    main()
