"""
Index HNSW de ChromaDB contre recherche exacte, selon ef_search.

Mesure, sur 111 requêtes (banc de 68 questions, 18 questions tunisiennes
nouvelles, 25 questions Ragas — les mêmes que la mesure de l'anomalie 2) :
    - recall@10 de la recherche HNSW non filtrée par rapport à la recherche
      exacte (force brute numpy, distance cosinus sur vecteurs normalisés) ;
    - nombre de requêtes dont le top-10 HNSW est identique au top-10 exact ;
    - documents de politique proches (meilleure politique à distance < 0,3
      en recherche exacte) retrouvés dans le top-8 HNSW ;
    - temps de recherche par requête (médiane, p95), embedding exclu.

Pour ef_search = 100, 200, 500 (M = 16, ef_construction = 100), l'index est
construit dans une collection ChromaDB TEMPORAIRE locale
(chromadb.PersistentClient, dossier temporaire supprimé à la fin), 3 fois
par valeur. La collection de production « liss_strike_kb » n'est que LUE
(configuration, et une ligne de référence par requête query()) ; rien n'y
est écrit.

Usage :
    python scripts/measure_hnsw_ef_search.py [--emb-cache emb_minilm.npy]
Le rapport est écrit dans docs/evaluation/hnsw_ef_search.md.
"""
import argparse
import json
import platform
import random
import shutil
import statistics
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import chromadb  # noqa: E402
from sentence_transformers import SentenceTransformer  # noqa: E402

from app.config import settings  # noqa: E402
from scripts.ingest_knowledge_base import load_policy_chunks, load_product_chunks  # noqa: E402

MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
EF_VALUES = (100, 200, 500)
BUILDS = 3
PASSES = 3
K = 10
CLOSE = 0.3
TOP_POLICY = 8
ARDUINO = "Une carte Arduino est garantie combien de temps ?"
OUT_MD = ROOT / "docs" / "evaluation" / "hnsw_ef_search.md"
OUT_JSON = ROOT / "docs" / "evaluation" / "hnsw_ef_search.json"


def load_queries():
    L4 = ("fr", "en", "ar", "tn")
    ev = ROOT / "data" / "evaluation"
    rech = json.loads((ev / "recherche.json").read_text(encoding="utf-8"))["questions"]
    newtn = json.loads((ev / "recherche_tunisien_nouvelles.json").read_text(encoding="utf-8"))["questions"]
    rag = json.loads((ROOT / "docs" / "evaluation" / "ragas_results.json").read_text(encoding="utf-8"))["results"]
    q = [(it[l], "banc68") for it in rech for l in L4 if l in it]
    q += [(it["tn"], "tn18") for it in newtn if "tn" in it]
    q += [(it["question"], "ragas25") for it in rag]
    return q


def read_production():
    """Lecture seule de la collection de production."""
    try:
        client = chromadb.HttpClient(host=settings.CHROMA_HOST, port=settings.CHROMA_PORT)
        col = client.get_collection(settings.CHROMA_COLLECTION_NAME)
        cfg = col.configuration
        return client, col, {"api_version": client.get_version(), "count": col.count(), "metadata": col.metadata,
                             "hnsw": dict(cfg.get("hnsw") or {}), "spann": cfg.get("spann")}
    except Exception as exc:
        return None, None, {"erreur": f"{type(exc).__name__}: {str(exc)[:200]}"}


def pct(values, p):
    return float(np.percentile(np.asarray(values), p))


def evaluate(search_fn, ids, E, Q, texts, policy_idx):
    """recall@10, top-10 identiques, politiques proches retrouvées, temps."""
    exact_top, recalls, identical, close, arduino = [], [], 0, [], None
    times = []
    for qi, q in enumerate(Q):
        d = 1.0 - E @ q
        ex = [ids[i] for i in np.argsort(d)[:K]]
        hn, _ = search_fn(q)
        r = len(set(ex) & set(hn)) / K
        recalls.append(r)
        identical += hn == ex
        bp = policy_idx[np.argmin(d[policy_idx])]
        if d[bp] < CLOSE:
            close.append({"q": texts[qi], "id": ids[bp], "dist": round(float(d[bp]), 3),
                          "rang_exact": int((d < d[bp]).sum()) + 1,
                          "rang_hnsw": hn.index(ids[bp]) + 1 if ids[bp] in hn else None})
        if texts[qi] == ARDUINO:
            arduino = {"id": ids[bp], "dist": round(float(d[bp]), 3), "rang_exact": int((d < d[bp]).sum()) + 1,
                       "rang_hnsw_top10": hn.index(ids[bp]) + 1 if ids[bp] in hn else None}
    for _ in range(PASSES):
        for q in Q:
            times.append(search_fn(q)[1])
    found = sum(1 for c in close if c["rang_hnsw"] is not None and c["rang_hnsw"] <= TOP_POLICY)
    return {"recall_at_10": round(float(np.mean(recalls)), 3), "recall_min": round(float(np.min(recalls)), 2),
            "top10_identiques": int(identical), "n": len(Q),
            "politiques_proches": {"n": len(close), "retrouvees_top8": found,
                                   "manquees": [c for c in close if not (c["rang_hnsw"] and c["rang_hnsw"] <= TOP_POLICY)]},
            "arduino": arduino,
            "ms_mediane": round(statistics.median(times), 2), "ms_p95": round(pct(times, 95), 2)}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--emb-cache", default=None, help="embeddings .npy des 11 109 documents (sinon calculés)")
    args = parser.parse_args()
    random.seed(42)
    np.random.seed(42)

    ids, docs, metas = [], [], []
    for loader in (load_policy_chunks, load_product_chunks):
        i, d, m = loader()
        ids += i
        docs += d
        metas += m
    types = np.array([m["type"] for m in metas])
    policy_idx = np.where(types == "policy")[0]

    model = SentenceTransformer(MODEL, device="cpu")
    if args.emb_cache and Path(args.emb_cache).exists():
        E = np.load(args.emb_cache).astype(np.float32)
        emb_source = f"cache {Path(args.emb_cache).name}"
    else:
        E = model.encode(docs, batch_size=64, normalize_embeddings=True, show_progress_bar=False).astype(np.float32)
        emb_source = "calculés"
    assert E.shape[0] == len(ids)
    queries = load_queries()
    texts = [t for t, _ in queries]
    Q = model.encode(texts, normalize_embeddings=True, show_progress_bar=False).astype(np.float32)
    for _ in range(5):  # échauffement
        _ = E @ Q[0]

    results = {"versions": {"python": platform.python_version(), "chromadb_client": chromadb.__version__,
                            "numpy": np.__version__, "modele": MODEL, "embeddings_documents": emb_source},
               "requetes": {"n": len(queries), "banc68": sum(s == "banc68" for _, s in queries),
                            "tn18": sum(s == "tn18" for _, s in queries), "ragas25": sum(s == "ragas25" for _, s in queries)}}

    # 1. production (lecture seule)
    _, prod_col, prod = read_production()
    results["production"] = prod
    print("production :", prod, flush=True)

    # 2. recherche exacte
    def exact(q):
        t0 = time.perf_counter()
        d = 1.0 - E @ q
        part = np.argpartition(d, K)[:K]
        top = part[np.argsort(d[part])]
        return [ids[i] for i in top], (time.perf_counter() - t0) * 1000
    results["exact"] = evaluate(exact, ids, E, Q, texts, policy_idx)
    print("exact :", {k: v for k, v in results["exact"].items() if k not in ("politiques_proches", "arduino")}, flush=True)

    # 3. HNSW temporaire, ef_search variable
    root = Path(tempfile.mkdtemp(prefix="hnsw_ef_"))
    results["hnsw"] = {}
    try:
        for ef in EF_VALUES:
            builds = []
            for b in range(BUILDS):
                client = chromadb.PersistentClient(path=str(root / f"ef{ef}-{b}"))
                col = client.create_collection(
                    name=f"tmp_hnsw_ef{ef}_{b}",
                    configuration={"hnsw": {"space": "cosine", "ef_construction": 100, "ef_search": ef,
                                            "max_neighbors": 16}})
                for i in range(0, len(ids), 2000):
                    col.add(ids=ids[i:i + 2000], embeddings=E[i:i + 2000].tolist(),
                            documents=docs[i:i + 2000], metadatas=metas[i:i + 2000])
                applied = dict(col.configuration["hnsw"])

                def hnsw(q, col=col):
                    t0 = time.perf_counter()
                    r = col.query(query_embeddings=[q.tolist()], n_results=K, include=[])
                    return r["ids"][0], (time.perf_counter() - t0) * 1000
                for q in Q[:5]:
                    hnsw(q)  # échauffement
                res = evaluate(hnsw, ids, E, Q, texts, policy_idx)
                res["config_appliquee"] = applied
                builds.append(res)
                print(f"ef_search={ef} construction {b + 1} : recall@10 {res['recall_at_10']} | identiques "
                      f"{res['top10_identiques']}/{res['n']} | politiques {res['politiques_proches']['retrouvees_top8']}"
                      f"/{res['politiques_proches']['n']} | arduino {res['arduino']} | {res['ms_mediane']} ms", flush=True)
                del col, client
            results["hnsw"][ef] = builds
    finally:
        shutil.rmtree(root, ignore_errors=True)

    # 4. référence : index de production (lecture seule, via HTTP)
    if prod_col is not None:
        def prodq(q):
            t0 = time.perf_counter()
            r = prod_col.query(query_embeddings=[q.tolist()], n_results=K, include=[])
            return r["ids"][0], (time.perf_counter() - t0) * 1000
        for q in Q[:5]:
            prodq(q)
        results["production_index"] = evaluate(prodq, ids, E, Q, texts, policy_idx)
        print("production :", {k: v for k, v in results["production_index"].items()
                               if k not in ("politiques_proches", "arduino")}, flush=True)

    OUT_JSON.write_text(json.dumps(results, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    md = render(results)
    OUT_MD.write_text(md, encoding="utf-8")
    print("\n" + md)


def rng(vals, fmt="{}"):
    lo, hi = min(vals), max(vals)
    return fmt.format(lo) if lo == hi else f"{fmt.format(lo)}–{fmt.format(hi)}"


def render(R):
    L = ["# Index HNSW contre recherche exacte, selon ef_search", "",
         "Mesuré par `scripts/measure_hnsw_ef_search.py`. Modèle `paraphrase-multilingual-MiniLM-L12-v2`, "
         f"distance cosinus, {R['requetes']['n']} requêtes ({R['requetes']['banc68']} du banc, "
         f"{R['requetes']['tn18']} tunisiennes nouvelles, {R['requetes']['ragas25']} Ragas), recherche non filtrée, k = 10.", ""]
    p = R["production"]
    L += ["## Configuration de la collection de production `liss_strike_kb`", ""]
    if "erreur" in p:
        L += [f"Non lue : {p['erreur']}", ""]
    else:
        h = p["hnsw"]
        L += ["Valeurs **lues sur la production** (`collection.configuration`, lecture seule, serveur ChromaDB "
              "du conteneur `chatbot_chroma`) :", "",
              "| Paramètre | Valeur | Source |", "| --- | --- | --- |",
              f"| hnsw:space | {h.get('space')} | `configuration` (et `metadata` : {p['metadata']}) |",
              f"| M (max_neighbors) | {h.get('max_neighbors')} | `configuration` |",
              f"| ef_construction | {h.get('ef_construction')} | `configuration` |",
              f"| ef_search | {h.get('ef_search')} | `configuration` |",
              f"| resize_factor | {h.get('resize_factor')} | `configuration` |",
              f"| sync_threshold | {h.get('sync_threshold')} | `configuration` |",
              (f"| batch_size | {h['batch_size']} | `configuration` |" if "batch_size" in h
               else "| batch_size | non exposé | clé absente de `configuration` en chromadb 1.x |"),
              f"| documents | {p['count']} | `count()` |", ""]
    L += ["## Résultats", "",
          "Constructions HNSW dans des collections temporaires locales (M = 16, ef_construction = 100), "
          f"{BUILDS} constructions par valeur (min–max) ; temps : {PASSES} passes après échauffement, "
          "requête seule (embedding exclu).", "",
          "| Recherche | recall@10 | top-10 identiques | politiques proches retrouvées (top-8) | Arduino garantie (rang top-10) | ms médiane | ms p95 |",
          "| --- | --- | --- | --- | --- | --- | --- |"]
    ex = R["exact"]
    L.append(f"| exact (force brute numpy) | 1,000 | {ex['n']}/{ex['n']} | {ex['politiques_proches']['retrouvees_top8']}/"
             f"{ex['politiques_proches']['n']} | {ex['arduino']['rang_hnsw_top10']} | {ex['ms_mediane']} | {ex['ms_p95']} |")
    for ef, builds in R["hnsw"].items():
        ard = [b["arduino"]["rang_hnsw_top10"] for b in builds]
        ard_s = ", ".join("absent" if a is None else str(a) for a in ard)
        L.append(f"| HNSW ef_search = {ef} | {rng([b['recall_at_10'] for b in builds], '{:.3f}')} | "
                 f"{rng([b['top10_identiques'] for b in builds])}/{builds[0]['n']} | "
                 f"{rng([b['politiques_proches']['retrouvees_top8'] for b in builds])}/{builds[0]['politiques_proches']['n']} | "
                 f"{ard_s} | {rng([b['ms_mediane'] for b in builds])} | {rng([b['ms_p95'] for b in builds])} |")
    if "production_index" in R:
        pi = R["production_index"]
        a = pi["arduino"]["rang_hnsw_top10"]
        L.append(f"| production (serveur, HTTP, ef_search = 100) | {pi['recall_at_10']:.3f} | {pi['top10_identiques']}/{pi['n']} | "
                 f"{pi['politiques_proches']['retrouvees_top8']}/{pi['politiques_proches']['n']} | {'absent' if a is None else a} | "
                 f"{pi['ms_mediane']} | {pi['ms_p95']} |")
    ard = R["exact"]["arduino"]
    L += ["", f"Cas Arduino garantie : « {ARDUINO} » ; meilleure politique `{ard['id']}`, distance exacte {ard['dist']}, "
          f"rang exact {ard['rang_exact']}. « absent » = hors du top-10 HNSW. Une valeur par construction.", ""]
    L += ["## Question d'origine à la distance 0,092", "",
          "**Introuvable.** Elle n'apparaît dans aucun fichier du dépôt (`docs/`, `scripts/`, `data/`, `tests/`), "
          "ni dans l'historique git ; seul le rapport v4 cite la distance, sans le texte de la question. "
          "Elle n'a donc pas été rejouée, et n'a pas été remplacée par une autre question.", ""]
    v = R["versions"]
    L += ["## Versions et matériel", "",
          f"- Python {v['python']}, client chromadb {v['chromadb_client']}, numpy {v['numpy']}",
          "- Serveur de production : image `chromadb/chroma:1.4.1` (épinglée par digest), `chroma --version` = 1.4.1 ; "
          f"l'API renvoie la version d'API {R['production'].get('api_version', 'non lue')}",
          "- Collections temporaires : client local chromadb " + v["chromadb_client"] + " (`PersistentClient`), "
          "et non le serveur 1.4.1",
          f"- Embeddings des documents : {v['embeddings_documents']}",
          "- CPU Intel Core i9-11900H, sans GPU", "",
          "## Limites", "",
          "- Les collections temporaires tournent avec le client local chromadb 1.5.9, pas avec le serveur 1.4.1 de "
          "production : l'implémentation HNSW peut différer légèrement. La ligne « production » mesure l'index "
          "réel, mais passe par HTTP : son temps n'est pas comparable aux autres lignes.",
          "- L'index de production a été construit par `upsert` successifs au fil des ingestions ; les collections "
          "temporaires sont construites en une fois. Leur recall peut donc différer de celui de la production.",
          "- Les politiques proches sont comptées comme retrouvées si elles figurent dans le top-8, comme dans la mesure "
          "initiale de l'anomalie 2.",
          "- La question d'origine à 0,092 n'a pas pu être rejouée (introuvable).",
          "- 111 requêtes rédigées pour le projet, pas des messages de clients réels.", ""]
    return "\n".join(L)


if __name__ == "__main__":
    main()
