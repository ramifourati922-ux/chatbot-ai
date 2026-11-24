"""
Comparaison empirique de modèles d'embedding sur le banc de recherche.

Mesure le hit@4 de la recherche dense seule (sans LLM, sans BM25 ni
reranking), avec exactement la recherche du mode « basic » du pipeline
(app/services/rag/retriever.search_basic) :
    - collection ChromaDB, espace « cosine », vecteurs normalisés ;
    - deux requêtes filtrées par type (policy, product), k = 4 chacune ;
    - filtre distance <= MAX_RELEVANT_DISTANCE (0,75) ;
    - fusion par distance croissante, 4 passages gardés ;
    - hit@4 : une source acceptée figure dans ces 4 passages.

Pour chaque modèle, les 11 109 documents produits par
scripts/ingest_knowledge_base.py (mêmes textes, mêmes métadonnées, mêmes
identifiants) sont indexés dans une collection ChromaDB TEMPORAIRE, créée
dans un dossier local à part (chromadb.PersistentClient). Le serveur
ChromaDB de production et la collection « liss_strike_kb » ne sont jamais
contactés.

Le tunisien est mesuré sans puis avec l'expansion de l'arabizi
(app/services/arabizi.py), appliquée comme en production : seulement si la
langue détectée est « tn ». Le hit@4 global est donné avec l'expansion
(configuration de production, RAG_ARABIZI_EXPANSION=True) et sans.

L'insertion dans l'index HNSW et les requêtes sont répétées REPEATS fois
pour vérifier la variabilité ; le calcul des embeddings, déterministe, est
fait une fois par modèle.

Usage :
    python scripts/compare_embeddings.py
    python scripts/compare_embeddings.py --models minilm e5-base --out resultats.json
"""
import argparse
import gc
import json
import os
import platform
import random
import shutil
import statistics
import sys
import tempfile
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np  # noqa: E402
import torch  # noqa: E402
import chromadb  # noqa: E402
from sentence_transformers import SentenceTransformer  # noqa: E402

from app.services import arabizi  # noqa: E402
from app.services.language_detector import detect_language  # noqa: E402
from app.services.rag.retriever import MAX_RELEVANT_DISTANCE  # noqa: E402
from scripts.evaluate_retrieval import load_questions  # noqa: E402
from scripts.ingest_knowledge_base import load_policy_chunks, load_product_chunks  # noqa: E402

SEED = 42
TOP_K = 4
REPEATS = 3
BATCH_INSERT = 2000

# clé → (identifiants Hugging Face essayés dans l'ordre, préfixe requête, préfixe document)
MODELS = {
    "minilm": (["sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"], "", ""),
    "e5-base": (["intfloat/multilingual-e5-base"], "query: ", "passage: "),
    "bge-m3": (["BAAI/bge-m3"], "", ""),
    "labse": (["sentence-transformers/LaBSE"], "", ""),
    # modèle arabe : premier disponible de la liste
    "arabe": ([
        "Omartificial-Intelligence-Space/Arabic-Triplet-Matryoshka-V2",
        "Omartificial-Intelligence-Space/GATE-AraBert-v1",
        "akhooli/Arabic-SBERT-100K",
    ], "", ""),
}


def seed_all():
    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)


def dir_size(path: Path) -> int:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def load_corpus():
    ids, docs, metas = [], [], []
    for loader in (load_policy_chunks, load_product_chunks):
        i, d, m = loader()
        ids += i
        docs += d
        metas += m
    return ids, docs, metas


def load_model(candidates):
    errors = []
    for hf in candidates:
        try:
            return hf, SentenceTransformer(hf, device="cpu"), errors
        except Exception as exc:  # téléchargement ou chargement impossible
            errors.append(f"{hf} : {type(exc).__name__}: {str(exc)[:200]}")
    return None, None, errors


def truncation(model, texts):
    tok = model.tokenizer
    limit = model.max_seq_length
    lengths = [len(tok(t, add_special_tokens=True)["input_ids"]) for t in texts]
    n_trunc = sum(1 for n in lengths if n > limit)
    return {"max_seq_length": limit, "tokens_max": max(lengths),
            "tokens_moyen": round(statistics.mean(lengths), 1),
            "tronques": n_trunc, "tronques_pct": round(100 * n_trunc / len(texts), 2)}


def search(collection, qv):
    hits = []
    for doc_type in ("policy", "product"):
        r = collection.query(query_embeddings=[qv], n_results=TOP_K, where={"type": doc_type},
                             include=["metadatas", "distances"])
        for meta, dist in zip(r["metadatas"][0], r["distances"][0]):
            if dist <= MAX_RELEVANT_DISTANCE:
                hits.append((dist, meta.get("source") or meta.get("sku")))
    return sorted(hits, key=lambda h: h[0])[:TOP_K]


def evaluate(model, collection, questions, q_prefix):
    """Une passe : hit@4 par langue (tn sans et avec expansion) + latence."""
    per = defaultdict(lambda: {"n": 0, "hits": 0})
    latencies = []
    for _, lang, question, accepted in questions:
        variants = [("tn_sans", question), ("tn_avec", arabizi.expand(question)
                    if detect_language(question) == "tn" else question)] if lang == "tn" else [(lang, question)]
        for key, text in variants:
            t0 = time.perf_counter()
            qv = model.encode(q_prefix + text, normalize_embeddings=True).tolist()
            found = search(collection, qv)
            latencies.append((time.perf_counter() - t0) * 1000)
            per[key]["n"] += 1
            per[key]["hits"] += any(src in accepted for _, src in found)
    return per, latencies


def run_model(key, root, ids, docs, metas, question_sets):
    candidates, q_prefix, d_prefix = MODELS[key]
    seed_all()
    t0 = time.perf_counter()
    hf, model, errors = load_model(candidates)
    if model is None:
        return {"cle": key, "statut": "échec", "erreurs": errors}
    load_s = time.perf_counter() - t0
    texts = [d_prefix + d for d in docs]
    entry = {"cle": key, "statut": "ok", "modele": hf, "essais_echoues": errors,
             "prefixes": {"requete": q_prefix, "document": d_prefix},
             "chargement_s": round(load_s, 1),
             "parametres_M": round(sum(p.numel() for p in model.parameters()) / 1e6),
             "troncature": truncation(model, texts)}

    t0 = time.perf_counter()
    emb = model.encode(texts, batch_size=64, normalize_embeddings=True, show_progress_bar=False)
    embed_s = time.perf_counter() - t0
    entry["dimension"] = int(emb.shape[1])
    entry["embeddings_s"] = round(embed_s, 1)
    emb = emb.tolist()

    runs = []
    for rep in range(REPEATS):
        seed_all()
        path = root / f"{key}-{rep}"
        client = chromadb.PersistentClient(path=str(path))
        coll = client.create_collection(name=f"cmp_{key.replace('-', '_')}", metadata={"hnsw:space": "cosine"})
        t0 = time.perf_counter()
        for i in range(0, len(ids), BATCH_INSERT):
            coll.add(ids=ids[i:i + BATCH_INSERT], embeddings=emb[i:i + BATCH_INSERT],
                     documents=docs[i:i + BATCH_INSERT], metadatas=metas[i:i + BATCH_INSERT])
        insert_s = time.perf_counter() - t0
        assert coll.count() == len(ids)
        size = dir_size(path)
        run = {"insertion_s": round(insert_s, 1), "taille_index_Mo": round(size / 2**20, 1)}
        for set_name, questions in question_sets.items():
            evaluate(model, coll, questions[:4], q_prefix)  # préchauffage hors mesure
            per, lat = evaluate(model, coll, questions, q_prefix)
            run[set_name] = {k: {"hits": v["hits"], "n": v["n"]} for k, v in per.items()}
            run[set_name]["latence_ms"] = round(statistics.mean(lat), 1)
        runs.append(run)
        del coll, client
        gc.collect()
    entry["repetitions"] = runs

    # synthèse : hit@4 identique d'une répétition à l'autre ? sinon min / max
    summary = {}
    for set_name in question_sets:
        keys = [k for k in runs[0][set_name] if k != "latence_ms"]
        s = {}
        for k in keys:
            vals = [r[set_name][k]["hits"] for r in runs]
            s[k] = {"hits": vals[0] if len(set(vals)) == 1 else vals, "n": runs[0][set_name][k]["n"],
                    "stable": len(set(vals)) == 1}
        lat = [r[set_name]["latence_ms"] for r in runs]
        s["latence_ms"] = {"moyenne": round(statistics.mean(lat), 1), "min": min(lat), "max": max(lat)}
        summary[set_name] = s
    entry["synthese"] = summary
    ins = [r["insertion_s"] for r in runs]
    entry["indexation_s"] = {"embeddings": entry["embeddings_s"], "insertion_moyenne": round(statistics.mean(ins), 1),
                             "total": round(entry["embeddings_s"] + statistics.mean(ins), 1),
                             "insertion_min_max": [min(ins), max(ins)]}
    entry["taille_index_Mo"] = runs[-1]["taille_index_Mo"]
    entry["vecteurs_bruts_Mo"] = round(len(ids) * entry["dimension"] * 4 / 2**20, 1)
    del model, emb
    gc.collect()
    return entry


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--models", nargs="+", default=list(MODELS), choices=list(MODELS))
    parser.add_argument("--out", default=str(Path(__file__).parent.parent / "data" / "evaluation" / "compare_embeddings.json"))
    parser.add_argument("--workdir", default=None, help="dossier des collections temporaires (supprimé à la fin)")
    args = parser.parse_args()

    seed_all()
    torch.set_num_threads(os.cpu_count() or 1)
    out = Path(args.out)
    results = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
    results["materiel"] = {"cpu": platform.processor(), "threads_torch": torch.get_num_threads(),
                           "gpu": torch.cuda.is_available(), "torch": torch.__version__,
                           "chromadb": chromadb.__version__, "python": platform.python_version()}
    ids, docs, metas = load_corpus()
    print(f"documents : {len(ids)}", flush=True)
    question_sets = {"banc68": load_questions("recherche.json"),
                     "tn18": load_questions("recherche_tunisien_nouvelles.json")}
    root = Path(args.workdir or tempfile.mkdtemp(prefix="cmp_emb_"))
    root.mkdir(parents=True, exist_ok=True)
    try:
        for key in args.models:
            if results.get(key, {}).get("statut") == "ok":
                print(f"déjà mesuré : {key}", flush=True)
                continue
            print(f"→ {key}", flush=True)
            try:
                results[key] = run_model(key, root, ids, docs, metas, question_sets)
            except Exception as exc:
                results[key] = {"cle": key, "statut": "échec", "erreurs": [f"{type(exc).__name__}: {str(exc)[:300]}"]}
            out.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
            r = results[key]
            if r["statut"] == "ok":
                b = r["synthese"]["banc68"]
                print(f"   {r['modele']} | dim {r['dimension']} | "
                      + " ".join(f"{k} {v['hits']}/{v['n']}" for k, v in b.items() if k != "latence_ms")
                      + f" | indexation {r['indexation_s']['total']} s", flush=True)
            else:
                print(f"   ÉCHEC : {r['erreurs']}", flush=True)
            for p in root.glob(f"{key}-*"):
                shutil.rmtree(p, ignore_errors=True)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    print("FIN", flush=True)


if __name__ == "__main__":
    main()
