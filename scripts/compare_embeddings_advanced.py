"""
Comparaison de modèles d'embedding en mode AVANCÉ (comme en production) :
recherche hybride BM25 + dense fusionnée par RRF (hybrid_retriever), puis
reranking cross-encoder (reranker), top 4. Aucun appel au LLM (Groq).

Le pipeline de production est utilisé tel quel. Le script se contente de
brancher, par remplacement d'attributs (monkeypatch) dans ce processus
uniquement :
    - vector_store.get_collection → une collection ChromaDB TEMPORAIRE,
      créée dans un dossier local (chromadb.PersistentClient) ; le serveur
      ChromaDB et la collection « liss_strike_kb » ne sont jamais contactés ;
    - hybrid_retriever.embed → l'embedding de la requête par le modèle testé.
L'index BM25 est reconstruit (refresh_index) à partir de la collection
temporaire : il porte donc sur les mêmes 11 109 documents.

Le hit@4 est calculé par scripts/evaluate_retrieval.evaluate (mêmes
questions, même détection de langue, expansion de l'arabizi seulement si la
langue détectée est « tn »). Le seuil MAX_RELEVANT_DISTANCE (0,75), réglé
pour MiniLM, est appliqué tel quel à tous les modèles.

Étape de contrôle : MiniLM doit retrouver les chiffres du chapitre 6
(hit@4 avancé FR 17/17, EN 17/17, AR 16/17, TN 10/17 sans expansion,
16/17 avec ; tableau tab:retlang et docs/evaluation/recherche_par_langue.md). Sinon le script s'arrête avant les autres modèles.

Usage :
    python scripts/compare_embeddings_advanced.py
    python scripts/compare_embeddings_advanced.py --models minilm labse --out resultats.json
"""
import argparse
import gc
import json
import random
import shutil
import statistics
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np  # noqa: E402
import torch  # noqa: E402
import chromadb  # noqa: E402
from sentence_transformers import SentenceTransformer  # noqa: E402

from app.config import settings  # noqa: E402
from app.services.rag import hybrid_retriever, vector_store  # noqa: E402
from scripts.evaluate_retrieval import evaluate, load_questions  # noqa: E402
from scripts.ingest_knowledge_base import load_policy_chunks, load_product_chunks  # noqa: E402

SEED = 42
REPEATS = 3
BATCH_INSERT = 2000
MODELS = {
    "minilm": ("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", "", ""),
    "labse": ("sentence-transformers/LaBSE", "", ""),
    "e5-base": ("intfloat/multilingual-e5-base", "query: ", "passage: "),
}
# chiffres publiés au chapitre 6 (MiniLM, mode avancé, banc de 68 questions)
EXPECTED_MINILM = {"fr": 17, "en": 17, "ar": 16, "tn_sans": 10, "tn_avec": 16}


def seed_all():
    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)


def load_corpus():
    ids, docs, metas = [], [], []
    for loader in (load_policy_chunks, load_product_chunks):
        i, d, m = loader()
        ids += i
        docs += d
        metas += m
    return ids, docs, metas


def get_embeddings(key, model, docs, d_prefix, cache_dir: Path):
    """Embeddings des documents : relus du cache .npy s'il existe, sinon calculés."""
    path = cache_dir / f"emb_{key}.npy"
    if path.exists():
        emb = np.load(path)
        if emb.shape[0] == len(docs):
            return emb, None
    t0 = time.perf_counter()
    emb = model.encode([d_prefix + d for d in docs], batch_size=64, normalize_embeddings=True,
                       show_progress_bar=False).astype(np.float32)
    seconds = time.perf_counter() - t0
    np.save(path, emb)
    return emb, seconds


def build_collection(path: Path, name: str, ids, docs, metas, emb):
    client = chromadb.PersistentClient(path=str(path))
    coll = client.create_collection(name=name, metadata={"hnsw:space": "cosine"})
    for i in range(0, len(ids), BATCH_INSERT):
        coll.add(ids=ids[i:i + BATCH_INSERT], embeddings=emb[i:i + BATCH_INSERT].tolist(),
                 documents=docs[i:i + BATCH_INSERT], metadatas=metas[i:i + BATCH_INSERT])
    assert coll.count() == len(ids)
    return client, coll


def one_pass(questions):
    """hit@4 par langue ; le tunisien sans puis avec expansion. Latence moyenne."""
    without = evaluate(questions, "advanced", False)["per_lang"]
    with_exp = evaluate(questions, "advanced", True)["per_lang"]
    out = {}
    for lang, s in without.items():
        out["tn_sans" if lang == "tn" else lang] = {"hits": s["hits"], "n": s["n"]}
    if "tn" in with_exp:
        out["tn_avec"] = {"hits": with_exp["tn"]["hits"], "n": with_exp["tn"]["n"]}
    ms = sum(s["ms"] for s in without.values()) + sum(s["ms"] for s in with_exp.values())
    n = sum(s["n"] for s in without.values()) + sum(s["n"] for s in with_exp.values())
    out["latence_ms"] = round(ms / n, 1)
    return out


def run_model(key, root, cache_dir, ids, docs, metas, question_sets):
    hf, q_prefix, d_prefix = MODELS[key]
    seed_all()
    model = SentenceTransformer(hf, device="cpu")
    emb, embed_s = get_embeddings(key, model, docs, d_prefix, cache_dir)

    # requête : même modèle, même préfixe, vecteur normalisé (comme embedding_service.embed)
    hybrid_retriever.embed = lambda text: model.encode(q_prefix + text, normalize_embeddings=True).tolist()
    settings.RERANK_CANDIDATES = 20

    runs = []
    for rep in range(REPEATS):
        seed_all()
        client, coll = build_collection(root / f"{key}-{rep}", f"cmp_adv_{key.replace('-', '_')}",
                                        ids, docs, metas, emb)
        vector_store.get_collection = lambda c=coll: c
        hybrid_retriever.refresh_index()
        t0 = time.perf_counter()
        hybrid_retriever._get_index()  # construction de l'index BM25 hors mesure
        bm25_s = time.perf_counter() - t0
        run = {"index_bm25_s": round(bm25_s, 1)}
        for set_name, questions in question_sets.items():
            run[set_name] = one_pass(questions)
        runs.append(run)
        print(f"   répétition {rep + 1} : " + " ".join(
            f"{k} {v['hits']}/{v['n']}" for k, v in run["banc68"].items() if k != "latence_ms")
            + f" | tn18 sans {run['tn18']['tn_sans']['hits']}/18 avec {run['tn18']['tn_avec']['hits']}/18"
            + f" | {run['banc68']['latence_ms']} ms", flush=True)
        hybrid_retriever.refresh_index()
        del coll, client
        gc.collect()

    summary = {}
    for set_name in question_sets:
        s = {}
        for k in runs[0][set_name]:
            if k == "latence_ms":
                lat = [r[set_name][k] for r in runs]
                s[k] = {"moyenne": round(statistics.mean(lat), 1), "min": min(lat), "max": max(lat)}
                continue
            vals = [r[set_name][k]["hits"] for r in runs]
            s[k] = {"min": min(vals), "max": max(vals), "valeurs": vals, "n": runs[0][set_name][k]["n"]}
        summary[set_name] = s
    del model
    gc.collect()
    return {"modele": hf, "statut": "ok", "dimension": int(emb.shape[1]),
            "embeddings_s": None if embed_s is None else round(embed_s, 1),
            "embeddings_depuis_cache": embed_s is None, "repetitions": runs, "synthese": summary}


def check_minilm(entry) -> list:
    """Écarts entre la mesure MiniLM et les chiffres publiés (vide si conforme)."""
    gaps = []
    for k, expected in EXPECTED_MINILM.items():
        s = entry["synthese"]["banc68"][k]
        if not s["min"] <= expected <= s["max"]:
            gaps.append(f"{k} : mesuré {s['valeurs']}/17, publié {expected}/17")
    return gaps


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--models", nargs="+", default=["minilm", "labse"], choices=list(MODELS))
    parser.add_argument("--out", default=str(Path(__file__).parent.parent / "data" / "evaluation"
                                             / "compare_embeddings_advanced.json"))
    parser.add_argument("--cache-dir", default=None, help="dossier des embeddings .npy (réutilisés)")
    parser.add_argument("--skip-check", action="store_true", help="ne pas exiger les chiffres du chapitre 6")
    args = parser.parse_args()

    seed_all()
    out = Path(args.out)
    cache_dir = Path(args.cache_dir) if args.cache_dir else out.parent
    cache_dir.mkdir(parents=True, exist_ok=True)
    results = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
    results["config"] = {"mode": "advanced", "RERANK_CANDIDATES": 20, "top_k": 4,
                         "MAX_RELEVANT_DISTANCE": hybrid_retriever.MAX_RELEVANT_DISTANCE,
                         "reranker": settings.RERANKER_MODEL, "repetitions": REPEATS,
                         "gpu": torch.cuda.is_available(), "chromadb": chromadb.__version__}
    ids, docs, metas = load_corpus()
    print(f"documents : {len(ids)} | reranker : {settings.RERANKER_MODEL}", flush=True)
    question_sets = {"banc68": load_questions("recherche.json"),
                     "tn18": load_questions("recherche_tunisien_nouvelles.json")}

    root = Path(tempfile.mkdtemp(prefix="cmp_adv_"))
    try:
        for key in args.models:
            print(f"→ {key}", flush=True)
            try:
                results[key] = run_model(key, root, cache_dir, ids, docs, metas, question_sets)
            except Exception as exc:
                results[key] = {"statut": "échec", "erreur": f"{type(exc).__name__}: {str(exc)[:300]}"}
                print(f"   ÉCHEC : {results[key]['erreur']}", flush=True)
            out.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
            if key == "minilm" and results[key].get("statut") == "ok" and not args.skip_check:
                gaps = check_minilm(results[key])
                if gaps:
                    print("ARRÊT : MiniLM ne retrouve pas les chiffres du chapitre 6 : " + " ; ".join(gaps), flush=True)
                    return
                print("   contrôle : MiniLM retrouve les chiffres du chapitre 6", flush=True)
            for p in root.glob(f"{key}-*"):
                shutil.rmtree(p, ignore_errors=True)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    print("FIN", flush=True)


if __name__ == "__main__":
    main()
