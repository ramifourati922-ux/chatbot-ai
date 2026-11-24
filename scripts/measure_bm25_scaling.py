"""
Remarque 42 (partie B) : coût de l'index BM25 en mémoire et passage à l'échelle.

B1. Index actuel (11 109 chunks lus dans la collection de production, en
    lecture seule) : temps de construction en 5 répétitions, séparé en
    lecture ChromaDB (get paginé, comme hybrid_retriever._build_index),
    tokenisation, BM25Okapi, et conversion des embeddings en tableau numpy.
    Mémoire : RSS / mémoire privée du processus avant-après, tracemalloc,
    taille d'une sérialisation pickle. Temps d'une requête BM25 (tokenize +
    get_scores + top 20, comme _CorpusIndex.bm25_top) sur les 111 questions
    (banc 68 + tunisiennes 18 + Ragas 25).
B2. Corpus SYNTHÉTIQUES de 11 109 / 50 000 / 100 000 / 500 000 documents :
    chunks existants dupliqués, chaque copie suffixée d'un jeton unique
    (« dupN ») pour rester des documents distincts. Mêmes mesures.

Code applicatif importé, jamais modifié. Ni LLM ni /chat/.

Usage : python scripts/measure_bm25_scaling.py
"""
import ctypes
import gc
import json
import pickle
import platform
import statistics
import sys
import time
import tracemalloc
from ctypes import wintypes
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np  # noqa: E402
import rank_bm25  # noqa: E402
from rank_bm25 import BM25Okapi  # noqa: E402

from app.services.rag import hybrid_retriever, vector_store  # noqa: E402
from app.services.rag.hybrid_retriever import DOC_TYPES, PAGE_SIZE, _load_page, tokenize  # noqa: E402
from scripts.measure_hnsw_ef_search import load_queries  # noqa: E402

OUT_MD = ROOT / "docs" / "evaluation" / "bm25_passage_echelle.md"
OUT_JSON = ROOT / "docs" / "evaluation" / "bm25_passage_echelle.json"
REPS = 5
SIZES = (11109, 50000, 100000, 500000)


class PMC(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
                ("PrivateUsage", ctypes.c_size_t)]


def mem_mb():
    """(RSS = working set, mémoire privée) du processus, en Mo (API Windows)."""
    c = PMC()
    c.cb = ctypes.sizeof(PMC)
    k32, psapi = ctypes.WinDLL("kernel32"), ctypes.WinDLL("psapi")
    k32.GetCurrentProcess.restype = wintypes.HANDLE
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
    if not psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(c), c.cb):
        raise OSError(ctypes.get_last_error())
    return round(c.WorkingSetSize / 2**20, 1), round(c.PrivateUsage / 2**20, 1)


def fetch():
    """Lecture paginée, identique à hybrid_retriever._build_index."""
    col = vector_store.get_collection()
    ids, docs, metas, embs = [], [], [], []
    for t in DOC_TYPES:
        off = 0
        while True:
            r = _load_page(col, t, off)
            if not r["ids"]:
                break
            ids += r["ids"]
            docs += r["documents"]
            metas += r["metadatas"]
            embs += r["embeddings"]
            off += PAGE_SIZE
    return ids, docs, metas, embs


def query_times(bm25, queries, passes):
    times = []
    for _ in range(passes):
        for q in queries:
            t0 = time.perf_counter()
            s = bm25.get_scores(tokenize(q))
            top = np.argsort(s)[::-1][:20]
            _ = [i for i in top if s[i] > 0]
            times.append((time.perf_counter() - t0) * 1000)
    return {"n": len(times), "mediane_ms": round(statistics.median(times), 2),
            "p95_ms": round(float(np.percentile(times, 95)), 2), "max_ms": round(max(times), 2)}


def st(v):
    return {"mediane": round(statistics.median(v), 3), "min": round(min(v), 3), "max": round(max(v), 3)}


def main():
    R = {"versions": {"python": platform.python_version(), "numpy": np.__version__,
                      "rank_bm25": getattr(rank_bm25, "__version__", None) or __import__(
                          "importlib.metadata").metadata.version("rank_bm25"),
                      "cpu": platform.processor()}}
    queries = [t for t, _ in load_queries()]

    # ---------------- B1 : 5 répétitions de la construction actuelle
    reps = {"lecture_chromadb_s": [], "tokenisation_s": [], "bm25okapi_s": [], "embeddings_numpy_s": [],
            "total_build_index_s": []}
    for r in range(REPS):
        gc.collect()
        t0 = time.perf_counter()
        ids, docs, metas, embs = fetch()
        t1 = time.perf_counter()
        toks = [tokenize(d) for d in docs]
        t2 = time.perf_counter()
        bm = BM25Okapi(toks)
        t3 = time.perf_counter()
        E = np.asarray(embs, dtype=np.float32)
        t4 = time.perf_counter()
        reps["lecture_chromadb_s"].append(t1 - t0)
        reps["tokenisation_s"].append(t2 - t1)
        reps["bm25okapi_s"].append(t3 - t2)
        reps["embeddings_numpy_s"].append(t4 - t3)
        # chemin réel complet (lecture + _CorpusIndex), chronométré à part
        hybrid_retriever.refresh_index()
        t5 = time.perf_counter()
        hybrid_retriever._get_index()
        reps["total_build_index_s"].append(time.perf_counter() - t5)
        hybrid_retriever.refresh_index()
        print(f"rép. {r + 1}: lecture {t1 - t0:.2f}s, tokenisation {t2 - t1:.2f}s, BM25 {t3 - t2:.2f}s, "
              f"numpy {t4 - t3:.2f}s, _get_index {reps['total_build_index_s'][-1]:.2f}s", flush=True)
        del bm, E, toks
    R["B1_temps"] = {k: st(v) for k, v in reps.items()}
    R["B1_temps"]["n_documents"] = len(ids)

    # mémoire (sur une construction isolée)
    gc.collect()
    m0 = mem_mb()
    tracemalloc.start()
    toks = [tokenize(d) for d in docs]
    bm = BM25Okapi(toks)
    cur, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    m1 = mem_mb()
    E = np.asarray(embs, dtype=np.float32)
    R["B1_memoire"] = {
        "rss_avant_mo": m0[0], "rss_apres_mo": m1[0], "prive_avant_mo": m0[1], "prive_apres_mo": m1[1],
        "tracemalloc_tokens_plus_bm25_mo": round(cur / 2**20, 1), "tracemalloc_pic_mo": round(peak / 2**20, 1),
        "pickle_bm25_mo": round(len(pickle.dumps(bm, protocol=pickle.HIGHEST_PROTOCOL)) / 2**20, 1),
        "pickle_tokens_mo": round(len(pickle.dumps(toks, protocol=pickle.HIGHEST_PROTOCOL)) / 2**20, 1),
        "embeddings_numpy_mo": round(E.nbytes / 2**20, 1),
        "documents_texte_mo": round(sum(len(d.encode("utf-8")) for d in docs) / 2**20, 1),
        "tokens_moyens_par_doc": round(bm.avgdl, 1), "vocabulaire": len(bm.idf)}
    print("mémoire :", R["B1_memoire"], flush=True)
    for q in queries[:5]:
        bm.get_scores(tokenize(q))
    R["B1_requete"] = query_times(bm, queries, 3)
    R["B1_requete"]["questions"] = len(queries)
    print("requête :", R["B1_requete"], flush=True)
    del bm, toks, E

    # ---------------- B2 : corpus synthétiques
    R["B2"] = []
    for n in SIZES:
        gc.collect()
        row = {"n_documents": n}
        try:
            texts = [docs[i % len(docs)] + (f" dup{i // len(docs)}" if i >= len(docs) else "") for i in range(n)]
            m0 = mem_mb()
            t0 = time.perf_counter()
            toks = [tokenize(t) for t in texts]
            t1 = time.perf_counter()
            bm = BM25Okapi(toks)
            t2 = time.perf_counter()
            m1 = mem_mb()
            row.update({"tokenisation_s": round(t1 - t0, 2), "bm25okapi_s": round(t2 - t1, 2),
                        "construction_totale_s": round(t2 - t0, 2),
                        "prive_avant_mo": m0[1], "prive_apres_mo": m1[1],
                        "delta_prive_tokens_bm25_mo": round(m1[1] - m0[1], 1),
                        "vocabulaire": len(bm.idf),
                        "embeddings_float32_calcul_mo": round(n * 384 * 4 / 2**20, 1)})
            try:
                row["pickle_bm25_mo"] = round(len(pickle.dumps(bm, protocol=pickle.HIGHEST_PROTOCOL)) / 2**20, 1)
            except MemoryError:
                row["pickle_bm25_mo"] = "non mesuré (MemoryError)"
            for q in queries[:3]:
                bm.get_scores(tokenize(q))
            row["requete"] = query_times(bm, queries, 3 if n <= 100000 else 1)
            del bm, toks, texts
        except MemoryError as e:
            row["erreur"] = f"non mesuré : MemoryError ({e})"
        R["B2"].append(row)
        print("B2 :", row, flush=True)

    OUT_JSON.write_text(json.dumps(R, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(R, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
