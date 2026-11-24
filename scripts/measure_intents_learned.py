"""
Remarque 48 : intentions apprises par exemples (app/services/semantic_intent.py).

A2. Exemples : répartition, doublons, chevauchement (identiques ou
    similarité > 0,95) avec data/intents/dev.json, test.json,
    test_appris.json et les bancs de recherche (recherche.json,
    recherche_tunisien_nouvelles.json, ragas_results.json).
B2. Règles seules vs règles + classifieur (seuils actuels 0,62 / 0,82), sur
    test.json et test_appris.json : précision, rappel, F1 par intention et
    par langue, matrice de confusion, messages corrigés / dégradés, faux
    transferts et transferts manqués.
B3. Balayage des seuils (bas 0,50-0,75, haut 0,70-0,95, pas 0,05) ; si une
    valeur est proposée : choisie sur la moitié A de test_appris.json,
    validée sur la moitié B (découpage fixé dans le fichier avant la mesure).
B4. Ablation : 50 % des exemples tirés au hasard, 5 tirages (graines 0-4).
B5. Coût : warmup, temps par classification, mémoire de l'index.

Le classifieur est activé EN MÉMOIRE seulement (INTENT_MODEL_ENABLED reste
false sur disque). Aucun appel LLM ni /chat/ ; ChromaDB n'est pas utilisé.

Usage : python scripts/measure_intents_learned.py
"""
import json
import platform
import random
import statistics
import sys
import time
import tracemalloc
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np  # noqa: E402

from app.config import settings  # noqa: E402
from app.services import semantic_intent as si  # noqa: E402
from app.services.intent_classifier import IntentClassifier  # noqa: E402
from app.services.language_detector import detect_language  # noqa: E402
from app.services.rag.embedding_service import embed, embed_batch  # noqa: E402
from scripts.evaluate_intents import rules_intent  # noqa: E402

DATA = ROOT / "data" / "intents"
OUT = ROOT / "docs" / "evaluation" / "intentions_apprises.json"
INTENTS = ("human_agent", "frustration", "order_tracking", "help", "general")
ESC = si.ESCALATION_INTENTS
LOW, HIGH = settings.INTENT_SIMILARITY_THRESHOLD, settings.INTENT_ESCALATION_THRESHOLD


def norm(v):
    m = np.asarray(v, dtype=np.float32)
    return m / np.linalg.norm(m, axis=-1, keepdims=True)


def load_sets():
    test = [{"jeu": "test.json", "langue": detect_language(m["text"]), "langue_source": "détectée", **m}
            for m in json.loads((DATA / "test.json").read_text(encoding="utf-8"))["messages"]]
    appris = [{"jeu": "test_appris.json", "langue_source": "annotée", **m}
              for m in json.loads((DATA / "test_appris.json").read_text(encoding="utf-8"))["messages"]]
    return test, appris


def decide(rule, best_label, best_score, low, high):
    """Même décision que evaluate_intents.with_model / dialogue_manager."""
    if rule != "general":
        return rule
    if best_label == si.NEGATIVE:
        return "general"
    return best_label if best_score >= (high if best_label in ESC else low) else "general"


def prf(gold, pred, labels):
    out = {}
    for lab in labels:
        tp = sum(1 for g, p in zip(gold, pred) if g == lab and p == lab)
        fp = sum(1 for g, p in zip(gold, pred) if g != lab and p == lab)
        fn = sum(1 for g, p in zip(gold, pred) if g == lab and p != lab)
        P = tp / (tp + fp) if tp + fp else None
        R = tp / (tp + fn) if tp + fn else None
        F = 2 * P * R / (P + R) if P and R else (0.0 if P is not None and R is not None else None)
        out[lab] = {"n": tp + fn, "precision": P, "rappel": R, "f1": F}
    return out


def binary(gold, pred, positive):
    """Décision binaire : positive = ensemble de labels (transfert, ou RAG = general)."""
    g = [x in positive for x in gold]
    p = [x in positive for x in pred]
    tp = sum(a and b for a, b in zip(g, p))
    fp = sum((not a) and b for a, b in zip(g, p))
    fn = sum(a and (not b) for a, b in zip(g, p))
    return {"precision": tp / (tp + fp) if tp + fp else None, "rappel": tp / (tp + fn) if tp + fn else None,
            "vp": tp, "fp": fp, "fn": fn}


def evaluate(msgs, preds_key):
    gold = [m["intent"] for m in msgs]
    pred = [m[preds_key] for m in msgs]
    labels = list(INTENTS) + sorted({p for p in pred if p not in INTENTS})
    conf = {g: dict(Counter(p for gg, p in zip(gold, pred) if gg == g)) for g in INTENTS}
    return {"n": len(msgs), "exactitude": sum(g == p for g, p in zip(gold, pred)) / len(msgs),
            "par_intention": prf(gold, pred, INTENTS), "confusion": conf, "labels_predits": labels,
            "transfert": binary(gold, pred, ESC), "rag": binary(gold, pred, {"general"}),
            "faux_transferts": [m["text"] for m in msgs if m[preds_key] in ESC and m["intent"] not in ESC],
            "transferts_manques": [m["text"] for m in msgs if m["intent"] in ESC and m[preds_key] not in ESC],
            "par_langue": {lg: {"n": len(v), "exactitude": sum(m["intent"] == m[preds_key] for m in v) / len(v),
                                "transfert": binary([m["intent"] for m in v], [m[preds_key] for m in v], ESC)}
                           for lg, v in group(msgs, "langue").items()}}


def group(msgs, key):
    d = defaultdict(list)
    for m in msgs:
        d[m[key]].append(m)
    return dict(sorted(d.items()))


def main():
    R = {"versions": {"python": platform.python_version(), "numpy": np.__version__, "modele": settings.EMBEDDING_MODEL,
                      "seuils": {"INTENT_SIMILARITY_THRESHOLD": LOW, "INTENT_ESCALATION_THRESHOLD": HIGH},
                      "INTENT_MODEL_ENABLED_sur_disque": settings.INTENT_MODEL_ENABLED}}
    clf = IntentClassifier()

    # ---------------- B5 : warmup et mémoire de l'index
    embed("préchauffage du modèle")
    si.reset()
    tracemalloc.start()
    t0 = time.perf_counter()
    si.warmup()
    warm = time.perf_counter() - t0
    cur, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    idx = si._get_index()
    R["B5_warmup"] = {"s": round(warm, 3), "exemples": len(idx.texts), "matrice_ko": round(idx.matrix.nbytes / 1024, 1),
                      "tracemalloc_net_ko": round(cur / 1024, 1), "tracemalloc_pic_ko": round(peak / 1024, 1)}
    print("B5 warmup", R["B5_warmup"], flush=True)

    # ---------------- A2 : exemples et chevauchement
    pairs = si.load_examples()
    data = json.loads(si.EXAMPLES_PATH.read_text(encoding="utf-8"))
    R["A2_repartition"] = {i: {lg: len(v) for lg, v in data[i].items()} for i in (*si.LEARNED_INTENTS, si.NEGATIVE)}
    texts = [t for _, t in pairs]
    R["A2_longueur_mots"] = {"min": min(len(t.split()) for t in texts), "mediane": statistics.median(len(t.split()) for t in texts),
                             "max": max(len(t.split()) for t in texts)}
    R["A2_doublons_exacts"] = sum(c - 1 for c in Counter(t.strip().lower() for t in texts).values() if c > 1)
    E = idx.matrix
    others = {}
    for name in ("dev.json", "test.json", "test_appris.json"):
        others[name] = [m["text"] for m in json.loads((DATA / name).read_text(encoding="utf-8"))["messages"]]
    ev = ROOT / "data" / "evaluation"
    others["recherche.json"] = [it[l] for it in json.loads((ev / "recherche.json").read_text(encoding="utf-8"))["questions"]
                                for l in ("fr", "en", "ar", "tn") if l in it]
    others["recherche_tunisien_nouvelles.json"] = [it["tn"] for it in json.loads(
        (ev / "recherche_tunisien_nouvelles.json").read_text(encoding="utf-8"))["questions"]]
    others["ragas_results.json"] = [r["question"] for r in json.loads(
        (ROOT / "docs/evaluation/ragas_results.json").read_text(encoding="utf-8"))["results"]]
    R["A2_chevauchement"] = {}
    for name, lst in others.items():
        V = norm(embed_batch(lst))
        S = V @ E.T
        best = S.max(axis=1)
        arg = S.argmax(axis=1)
        exact = sum(1 for t in lst if t.strip().lower() in {x.strip().lower() for x in texts})
        close = [{"phrase": lst[i], "exemple": idx.texts[arg[i]], "intention_exemple": idx.labels[arg[i]],
                  "similarite": round(float(best[i]), 3)} for i in np.where(best > 0.95)[0]]
        R["A2_chevauchement"][name] = {"n": len(lst), "identiques": exact, "similarite_sup_095": len(close),
                                       "max": round(float(best.max()), 3), "mediane_meilleure": round(float(np.median(best)), 3),
                                       "cas": close}
        print("A2", name, {k: v for k, v in R["A2_chevauchement"][name].items() if k != "cas"}, flush=True)

    # ---------------- classification de tous les messages (scores gardés pour B3/B4)
    test, appris = load_sets()
    allm = test + appris
    times = []
    for m in allm:
        m["regle"] = rules_intent(clf, m["text"])
        t0 = time.perf_counter()
        v = norm(embed(m["text"]))
        m["_vec"] = v
        s = E @ v
        b = int(np.argmax(s))
        times.append((time.perf_counter() - t0) * 1000)
        m["plus_proche"] = {"intention": idx.labels[b], "score": round(float(s[b]), 4), "exemple": idx.texts[b]}
        m["avec_modele"] = decide(m["regle"], idx.labels[b], float(s[b]), LOW, HIGH)
        # contrôle : même décision que le vrai code (semantic_intent.classify), seuils actuels
        real = si.classify(m["text"]) if m["regle"] == "general" else None
        real_dec = m["regle"] if m["regle"] != "general" else (real.intent if real else "general")
        assert real_dec == m["avec_modele"], (m["text"], real_dec, m["avec_modele"])
    R["B5_classification_ms"] = {"n": len(times), "mediane": round(statistics.median(times), 2),
                                 "p95": round(float(np.percentile(times, 95)), 2), "max": round(max(times), 2)}
    print("B5 classification", R["B5_classification_ms"], flush=True)

    # ---------------- B2
    R["B2"] = {}
    for name, msgs in (("test.json", test), ("test_appris.json", appris), ("les deux", allm)):
        R["B2"][name] = {"regles_seules": evaluate(msgs, "regle"), "regles_plus_modele": evaluate(msgs, "avec_modele"),
                         "changements": [{"texte": m["text"], "langue": m["langue"], "attendu": m["intent"],
                                          "regles": m["regle"], "avec_modele": m["avec_modele"],
                                          "effet": ("corrigé" if m["avec_modele"] == m["intent"] else
                                                    "dégradé" if m["regle"] == m["intent"] else "erreur changée"),
                                          "score": m["plus_proche"]["score"], "exemple": m["plus_proche"]["exemple"]}
                                         for m in msgs if m["regle"] != m["avec_modele"]]}
        b = R["B2"][name]
        print("B2", name, "exactitude", round(b["regles_seules"]["exactitude"], 3), "->",
              round(b["regles_plus_modele"]["exactitude"], 3), "| changements", Counter(c["effet"] for c in b["changements"]),
              "| faux transferts", len(b["regles_plus_modele"]["faux_transferts"]),
              "| transferts manqués", len(b["regles_seules"]["transferts_manques"]), "->",
              len(b["regles_plus_modele"]["transferts_manques"]), flush=True)

    # ---------------- B3 : balayage (sur test_appris, test.json, et les deux)
    lows = [round(x, 2) for x in np.arange(0.50, 0.751, 0.05)]
    highs = [round(x, 2) for x in np.arange(0.70, 0.951, 0.05)]

    def sweep(msgs, low, high):
        gold = [m["intent"] for m in msgs]
        pred = [decide(m["regle"], m["plus_proche"]["intention"], m["plus_proche"]["score"], low, high) for m in msgs]
        return {"exactitude": sum(g == p for g, p in zip(gold, pred)) / len(msgs),
                "transfert": binary(gold, pred, ESC), "rag": binary(gold, pred, {"general"})}
    R["B3"] = {}
    for name, msgs in (("test_appris.json", appris), ("test.json", test), ("les deux", allm),
                       ("moitie_A", [m for m in appris if m["moitie"] == "A"]),
                       ("moitie_B", [m for m in appris if m["moitie"] == "B"])):
        R["B3"][name] = {"bas_varie_haut_082": {str(lo): sweep(msgs, lo, HIGH) for lo in lows},
                         "haut_varie_bas_062": {str(hi): sweep(msgs, LOW, hi) for hi in highs},
                         "actuel": sweep(msgs, LOW, HIGH)}
    # proposition éventuelle : meilleure exactitude sur A, à faux transferts nuls, puis validée sur B
    A = [m for m in appris if m["moitie"] == "A"]
    Bm = [m for m in appris if m["moitie"] == "B"]
    grid = [(lo, hi) for lo in lows for hi in highs]
    scored = []
    for lo, hi in grid:
        s = sweep(A, lo, hi)
        if s["transfert"]["fp"] == 0:
            scored.append((s["exactitude"], -abs(lo - LOW) - abs(hi - HIGH), lo, hi))
    best = max(scored)
    lo_b, hi_b = best[2], best[3]
    R["B3_proposition"] = {"choisi_sur_A": {"bas": lo_b, "haut": hi_b, "A": sweep(A, lo_b, hi_b), "A_actuel": sweep(A, LOW, HIGH)},
                           "valide_sur_B": {"propose": sweep(Bm, lo_b, hi_b), "actuel": sweep(Bm, LOW, HIGH)},
                           "regle_de_choix": "exactitude maximale sur A sans faux transfert ; à égalité, le plus proche des seuils actuels"}
    print("B3 proposition", json.dumps(R["B3_proposition"], ensure_ascii=False)[:600], flush=True)

    # ---------------- B4 : ablation 50 %
    R["B4"] = []
    full_labels = np.array(idx.labels)
    for seed in range(5):
        rng = random.Random(seed)
        keep = sorted(rng.sample(range(len(full_labels)), len(full_labels) // 2))
        Ek, Lk = E[keep], full_labels[keep]
        for m in allm:
            s = Ek @ m["_vec"]
            b = int(np.argmax(s))
            m["abl"] = decide(m["regle"], Lk[b], float(s[b]), LOW, HIGH)
        ev_ = evaluate(allm, "abl")
        row = {"graine": seed, "exemples_gardes": len(keep), "par_intention_gardes": dict(Counter(Lk.tolist())),
               "exactitude": ev_["exactitude"], "transfert": ev_["transfert"],
               "rappel": {k: v["rappel"] for k, v in ev_["par_intention"].items()},
               "exactitude_par_langue": {lg: v["exactitude"] for lg, v in ev_["par_langue"].items()}}
        R["B4"].append(row)
        print("B4", seed, round(row["exactitude"], 3), row["transfert"], {k: round(v, 2) for k, v in row["exactitude_par_langue"].items()}, flush=True)
    full = evaluate(allm, "avec_modele")
    R["B4_reference_100"] = {"exactitude": full["exactitude"], "transfert": full["transfert"],
                             "exactitude_par_langue": {lg: v["exactitude"] for lg, v in full["par_langue"].items()},
                             "rappel": {k: v["rappel"] for k, v in full["par_intention"].items()}}

    for m in allm:
        m.pop("_vec", None)
        m.pop("abl", None)
    R["messages"] = allm
    OUT.write_text(json.dumps(R, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print("écrit", OUT)


if __name__ == "__main__":
    main()
