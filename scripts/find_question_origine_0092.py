"""Anomalie 2 (distance 0,092) : reconstitution de la question d'origine par les données.

Candidates : data/evaluation/*.json, docs/evaluation/ragas_results.json, data/intents/test.json
et les chaînes des tests/*.py et scripts/*.py. Pour chacune : meilleure distance policy (exacte,
numpy sur les 11 109 embeddings de production) et top-10 HNSW de production non filtré.
Lecture seule de la collection de production (get + query, aucun add/upsert/delete).

Usage : python scripts/find_question_origine_0092.py
"""
import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np  # noqa: E402
import chromadb  # noqa: E402
from sentence_transformers import SentenceTransformer  # noqa: E402
from app.config import settings  # noqa: E402
from scripts.measure_hnsw_ef_search import MODEL, read_production  # noqa: E402

OUT = ROOT / "docs" / "evaluation" / "question_origine_0092.json"
BAD = ("{", "}", "=", "\\", "http", ".py", ".txt", ".json", ".npy", "__", "%", "->", "::", "<", ">")


def gather():
    c = {}

    def add(t, src):
        t = (t or "").strip()
        if t and t not in c:
            c[t] = src
    ev = ROOT / "data" / "evaluation"
    for it in json.loads((ev / "recherche.json").read_text(encoding="utf-8"))["questions"]:
        for l in ("fr", "en", "ar", "tn"):
            add(it.get(l), f"data/evaluation/recherche.json ({l})")
    for it in json.loads((ev / "recherche_tunisien_nouvelles.json").read_text(encoding="utf-8"))["questions"]:
        add(it.get("tn"), "data/evaluation/recherche_tunisien_nouvelles.json")
    for it in json.loads((ROOT / "docs/evaluation/ragas_results.json").read_text(encoding="utf-8"))["results"]:
        add(it["question"], "docs/evaluation/ragas_results.json")
    for it in json.loads((ROOT / "data/intents/test.json").read_text(encoding="utf-8"))["messages"]:
        add(it["text"], "data/intents/test.json")
    n_files = {}
    for folder in ("tests", "scripts"):
        files = sorted(f for f in (ROOT / folder).glob("*.py") if f.name != Path(__file__).name)
        n_files[folder] = len(files)
        for f in files:
            for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    s = node.value.strip()
                    if 5 <= len(s) <= 200 and "\n" not in s and " " in s and not any(b in s for b in BAD):
                        add(s, f"{folder}/{f.name}")
    return c, n_files


def main():
    cands, n_files = gather()
    texts = list(cands)
    print(len(texts), "candidates", n_files, flush=True)
    client, col, prod = read_production()
    assert col is not None, prod
    ids, E, types = [], [], []
    off = 0
    while True:  # lecture paginée des 11 109 embeddings de production
        r = col.get(limit=1000, offset=off, include=["embeddings", "metadatas"])
        if not r["ids"]:
            break
        ids += r["ids"]
        E.append(np.asarray(r["embeddings"], dtype=np.float32))
        types += [m.get("type") for m in r["metadatas"]]
        off += 1000
    E = np.vstack(E)
    types = np.array(types)
    pol = np.where(types == "policy")[0]
    print("production :", len(ids), "embeddings,", len(pol), "policy", flush=True)
    model = SentenceTransformer(MODEL, device="cpu")
    Q = model.encode(texts, batch_size=64, normalize_embeddings=True, show_progress_bar=False).astype(np.float32)
    rows = []
    for t, q in zip(texts, Q):
        d = 1.0 - E @ q
        bp = pol[np.argmin(d[pol])]
        r = col.query(query_embeddings=[q.tolist()], n_results=10, include=["distances", "metadatas"])
        top = [{"id": i, "type": m.get("type"), "dist": round(float(x), 3)}
               for i, m, x in zip(r["ids"][0], r["metadatas"][0], r["distances"][0])]
        rows.append({"question": t, "source": cands[t], "policy_dist_exacte": round(float(d[bp]), 4),
                     "policy_id": ids[bp], "rang_policy_exact": int((d < d[bp]).sum()) + 1,
                     "top10_prod_hnsw": top,
                     "top8_tous_produits": all(x["type"] == "product" for x in top[:8]),
                     "policy_dans_top10_hnsw": (([x["id"] for x in top].index(ids[bp]) + 1)
                                                if ids[bp] in [x["id"] for x in top] else None)})
    OUT.write_text(json.dumps({"n": len(rows), "fichiers": n_files, "production": prod, "rows": rows},
                              ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    both = [x for x in rows if 0.085 <= x["policy_dist_exacte"] <= 0.100 and x["top8_tous_produits"]]
    c1 = [x for x in rows if 0.085 <= x["policy_dist_exacte"] <= 0.100]
    c2 = [x for x in rows if x["top8_tous_produits"]]
    missed = [x for x in rows if x["policy_dist_exacte"] < 0.3 and x["policy_dans_top10_hnsw"] is None]
    print("cond1 (0,085-0,100):", len(c1), "| cond2 (top8 produits):", len(c2), "| les deux:", len(both),
          "| policy <0,3 absente du top10 prod:", len(missed))
    for name, L in (("LES DEUX", both), ("COND1", c1), ("POLICY<0.3 MANQUEE", missed)):
        print("\n==", name)
        for x in L:
            print(f"{x['policy_dist_exacte']:.4f} {x['policy_id']} | top8 produits={x['top8_tous_produits']} | "
                  f"rang policy HNSW={x['policy_dans_top10_hnsw']} | {x['question']} [{x['source']}] | top3="
                  + ", ".join(f"{t['type']}:{t['dist']}" for t in x["top10_prod_hnsw"][:3]))


if __name__ == "__main__":
    main()
