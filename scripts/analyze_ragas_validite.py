"""
Remarque 51 : validité des moyennes Ragas (lecture seule de
docs/evaluation/ragas_results.json, jamais réécrit ; aucun appel Groq).

Par mode (basic, advanced) et par métrique : scores valides / manquants,
scores mis à 0 faute de contexte ; moyennes publiées (sur les valeurs non
nulles de chaque mode) et appariées (questions valides dans les deux modes) ;
détail par langue ; bootstrap apparié du gain Advanced − Basic (graine 42,
10 000 tirages) ; caractéristiques des questions dont un score manque.

Usage : python scripts/analyze_ragas_validite.py
"""
import json
import random
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
SRC = ROOT / "docs" / "evaluation" / "ragas_results.json"
OUT = ROOT / "data" / "evaluation" / "ragas_validite.json"
METRICS = ("context_precision", "context_recall", "faithfulness", "answer_relevancy")
MODES = ("basic", "advanced")
LANGS = ("fr", "en", "ar", "tn")
SEED, B = 42, 10000
REPORT = {"context_precision": (0.645, 0.913), "context_recall": (0.599, 0.800),
          "faithfulness": (0.532, 0.689), "answer_relevancy": (0.485, 0.600)}


def mean(v):
    return round(sum(v) / len(v), 4) if v else None


def main():
    data = json.loads(SRC.read_text(encoding="utf-8"))
    rows = [r for r in data["results"] if r["category"] != "hors-sujet"]
    R = {"source": str(SRC.relative_to(ROOT)), "meta": data["meta"], "n_questions_notees": len(rows),
         "n_hors_sujet": sum(r["category"] == "hors-sujet" for r in data["results"])}

    # 3. validité par mode et métrique
    val = {}
    for mode in MODES:
        val[mode] = {}
        for m in METRICS:
            miss = [{"id": r["id"], "langue": r["lang"], "erreur": r["runs"][mode]["ragas"]["errors"].get(m, "")[:160]}
                    for r in rows if r["runs"][mode]["ragas"]["scores"].get(m) is None]
            zero_ctx = [r["id"] for r in rows if not r["runs"][mode]["contexts"] and m != "answer_relevancy"]
            val[mode][m] = {"valides": len(rows) - len(miss), "manquants": len(miss), "liste_manquants": miss,
                            "mis_a_0_sans_contexte": zero_ctx}
    R["validite"] = val
    R["erreurs_metriques_agregees"] = {mode: data["aggregate"][mode].get("metric_failures") for mode in MODES}

    # 4. moyennes publiées / appariées
    def sc(r, mode, m):
        return r["runs"][mode]["ragas"]["scores"].get(m)
    R["moyennes"] = {}
    for m in METRICS:
        pub = {mode: data["aggregate"][mode][m] for mode in MODES}
        recomputed = {mode: mean([sc(r, mode, m) for r in rows if sc(r, mode, m) is not None]) for mode in MODES}
        paired = [r for r in rows if sc(r, "basic", m) is not None and sc(r, "advanced", m) is not None]
        pm = {mode: mean([sc(r, mode, m) for r in paired]) for mode in MODES}
        diffs = [sc(r, "advanced", m) - sc(r, "basic", m) for r in paired]
        rng = random.Random(SEED)
        boots = sorted(statistics.fmean(rng.choices(diffs, k=len(diffs))) for _ in range(B))
        R["moyennes"][m] = {
            "a_publiees_json": pub, "a_recalculees": recomputed,
            "n_par_mode": {mode: val[mode][m]["valides"] for mode in MODES},
            "rapport": dict(zip(MODES, REPORT[m])),
            "ecart_json_vs_rapport": {mode: round(pub[mode] - REPORT[m][i], 4) for i, mode in enumerate(MODES)},
            "b_appariees": pm, "n_apparie": len(paired),
            "gain_publie": round(pub["advanced"] - pub["basic"], 4), "gain_apparie": round(pm["advanced"] - pm["basic"], 4),
            "bootstrap_ic95": [round(boots[int(0.025 * B)], 3), round(boots[int(0.975 * B) - 1], 3)],
            "advanced_sup": sum(d > 0 for d in diffs), "egal": sum(d == 0 for d in diffs), "advanced_inf": sum(d < 0 for d in diffs)}

    # 5. par langue
    R["par_langue"] = {}
    for lg in LANGS:
        lr = [r for r in rows if r["lang"] == lg]
        R["par_langue"][lg] = {"n_questions": len(lr)}
        for m in METRICS:
            d = {}
            for mode in MODES:
                v = [sc(r, mode, m) for r in lr if sc(r, mode, m) is not None]
                d[mode] = {"n": len(v), "moyenne": mean(v), "publiee": data["aggregate"][mode][f"lang_{lg}"][m]}
            pr = [r for r in lr if sc(r, "basic", m) is not None and sc(r, "advanced", m) is not None]
            d["apparie"] = {"n": len(pr), "basic": mean([sc(r, "basic", m) for r in pr]),
                            "advanced": mean([sc(r, "advanced", m) for r in pr])}
            R["par_langue"][lg][m] = d

    # 7. caractéristiques des questions avec un score manquant (vs les autres)
    missing_ids = {(x["id"], mode) for mode in MODES for m in METRICS for x in val[mode][m]["liste_manquants"]}

    def feats(r, mode):
        run = r["runs"][mode]
        return {"id": r["id"], "mode": mode, "langue": r["lang"], "categorie": r["category"],
                "contexte_car": sum(len(c) for c in run["contexts"]), "reponse_car": len(run["answer"] or ""),
                "n_contextes": len(run["contexts"]), "confiance": run.get("confidence")}
    allf = [feats(r, mode) for r in rows for mode in MODES]
    R["manquants_caracteristiques"] = [f for f in allf if (f["id"], f["mode"]) in missing_ids]
    others = [f for f in allf if (f["id"], f["mode"]) not in missing_ids]
    R["autres_reference"] = {"n": len(others),
                             "contexte_car_mediane": statistics.median(f["contexte_car"] for f in others),
                             "reponse_car_mediane": statistics.median(f["reponse_car"] for f in others),
                             "reponse_car_min_max": [min(f["reponse_car"] for f in others), max(f["reponse_car"] for f in others)],
                             "contexte_car_min_max": [min(f["contexte_car"] for f in others), max(f["contexte_car"] for f in others)]}
    OUT.write_text(json.dumps(R, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: R[k] for k in ("validite", "moyennes", "manquants_caracteristiques", "autres_reference",
                                         "erreurs_metriques_agregees")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
