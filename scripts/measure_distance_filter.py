"""
Remarque 43 : filtre MAX_RELEVANT_DISTANCE = 0,75 (recherche hybride).

A2. Pour les 111 questions (banc 68 + tunisiennes 18 + Ragas 25) : candidats
    trouvés par les deux listes, par le dense seul, par BM25 seul ; distance
    cosinus calculée par le code (_CorpusIndex.distance) comparée à un recalcul
    indépendant (embedding stocké relu dans ChromaDB + embedding de la question
    par sentence-transformers, 1 - cos avec normalisation explicite) ; candidats
    écartés par le filtre.
B2. Distances des bonnes sources et des autres candidats du top 20 fusionné.
B3. Sensibilité du seuil (0,5 à 1,0) en modes basic, hybrid et advanced sur
    recherche.json (hit@4, MRR@4 par langue, candidats retirés par question).
B4. Effet du seuil sur la décision d'escalade (confiance 1 - distance min < 0,35)
    sur 143 questions (111 + 14 de calibration + 18 services non proposés).

Le seuil est modifié EN MÉMOIRE (hybrid_retriever.MAX_RELEVANT_DISTANCE et
retriever.MAX_RELEVANT_DISTANCE), jamais sur disque. Pour balayer les seuils
sans refaire la recherche, la boucle de filtrage de hybrid_retriever.search est
rejouée sur les candidats fusionnés (mêmes fonctions : _dense_ranking,
bm25_top, rrf_fuse, distance) ; l'égalité avec les vraies fonctions
hybrid_retriever.search et retriever.search est vérifiée à 0,75 sur toutes les
questions. Production ChromaDB en lecture seule. Ni LLM ni /chat/.

Usage : python scripts/measure_distance_filter.py
"""
import copy
import json
import platform
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import chromadb  # noqa: E402
import numpy as np  # noqa: E402
import sentence_transformers  # noqa: E402
from sentence_transformers import SentenceTransformer  # noqa: E402

from app.config import settings  # noqa: E402
from app.services.rag import hybrid_retriever as hr, reranker, retriever  # noqa: E402
from app.services.rag.embedding_service import embed  # noqa: E402
from scripts.calibrate_threshold import OFFTOPIC_QUESTIONS, PRODUCT_QUESTIONS  # noqa: E402
from scripts.evaluate_retrieval import load_questions  # noqa: E402
from scripts.measure_calibration_services import SERVICES  # noqa: E402

OUT_JSON = ROOT / "docs" / "evaluation" / "filtre_distance.json"
THRESHOLDS = (0.5, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 1.0)
REAL = 0.75


def src(meta):
    return meta.get("source") or meta.get("sku")


def questions():
    qs = []
    for theme, lang, q, acc in load_questions("recherche.json"):
        qs.append({"jeu": "banc68", "id": theme, "langue": lang, "q": q, "acc": acc})
    for theme, lang, q, acc in load_questions("recherche_tunisien_nouvelles.json"):
        qs.append({"jeu": "tn18", "id": theme, "langue": lang, "q": q, "acc": acc})
    for r in json.loads((ROOT / "docs/evaluation/ragas_results.json").read_text(encoding="utf-8"))["results"]:
        qs.append({"jeu": "ragas25", "id": r["id"], "langue": r["lang"], "q": r["question"], "acc": set(r["sources"])})
    for _, q in PRODUCT_QUESTIONS:
        qs.append({"jeu": "calib_legit", "id": q[:30], "langue": "fr", "q": q, "acc": set()})
    for q in OFFTOPIC_QUESTIONS:
        qs.append({"jeu": "calib_horssujet", "id": q[:30], "langue": "fr", "q": q, "acc": set()})
    for q in SERVICES:
        qs.append({"jeu": "services18", "id": q[:30], "langue": "fr", "q": q, "acc": set()})
    return qs


def candidates(index, q):
    """Étapes de hybrid_retriever.search avant le filtre (mêmes fonctions)."""
    emb = embed(q)
    qv = np.asarray(emb, dtype=np.float32)
    dense = hr._dense_ranking(emb, hr.CANDIDATES_PER_LIST, None)
    bm = index.bm25_top(hr.tokenize(q), hr.CANDIDATES_PER_LIST, None)
    dr = {d: r for r, d in enumerate(dense, start=1)}
    br = {d: r for r, d in enumerate(bm, start=1)}
    fused = sorted(hr.rrf_fuse([dense, bm]).items(), key=lambda kv: kv[1], reverse=True)
    rows = []
    for doc_id, score in fused:
        i = index.pos.get(doc_id)
        if i is None:
            continue
        rows.append({"id": doc_id, "i": i, "rrf": score, "dense_rank": dr.get(doc_id), "bm25_rank": br.get(doc_id),
                     "origine": "les deux" if doc_id in dr and doc_id in br else ("dense seul" if doc_id in dr else "BM25 seul"),
                     "distance": index.distance(i, qv), "source": src(index.metadatas[i])})
    return emb, rows


def apply_filter(index, rows, t, top_k):
    """Boucle de hybrid_retriever.search : parcours par RRF, saut si distance > t."""
    hits, skipped = [], 0
    for r in rows:
        if r["distance"] > t:
            skipped += 1
            continue
        i = r["i"]
        hits.append({"document": index.documents[i], "metadata": index.metadatas[i], "distance": r["distance"],
                     "rrf_score": r["rrf"], "dense_rank": r["dense_rank"], "bm25_rank": r["bm25_rank"]})
        if len(hits) >= top_k:
            break
    return hits, skipped


def rank_of(hits, acc):
    return next((k for k, h in enumerate(hits, start=1) if src(h["metadata"]) in acc), None)


def pstats(v):
    if not v:
        return None
    return {"n": len(v), "min": round(min(v), 3), "mediane": round(statistics.median(v), 3),
            "p95": round(float(np.percentile(v, 95)), 3), "max": round(max(v), 3)}


def main():
    settings.RAG_RETRIEVAL_MODE = "advanced"
    index = hr._get_index()
    retriever.search("préchauffage", 4)
    QS = questions()
    st = SentenceTransformer("sentence-transformers/" + settings.EMBEDDING_MODEL, device="cpu")
    col = chromadb.HttpClient(host=settings.CHROMA_HOST, port=settings.CHROMA_PORT).get_collection(
        settings.CHROMA_COLLECTION_NAME)

    data = []
    for k, x in enumerate(QS):
        emb, rows = candidates(index, x["q"])
        x["rows"] = rows
        data.append(x)
    print("candidats calculés", len(data), flush=True)

    # ---------------- A2 : vérification indépendante de la distance
    main111 = [x for x in data if x["jeu"] in ("banc68", "tn18", "ragas25")]
    ids_needed = sorted({r["id"] for x in main111 for r in x["rows"]})
    stored = {}
    for s in range(0, len(ids_needed), 500):
        g = col.get(ids=ids_needed[s:s + 500], include=["embeddings"])
        stored.update({i: np.asarray(e, dtype=np.float64) for i, e in zip(g["ids"], g["embeddings"])})
    Qind = st.encode([x["q"] for x in main111], normalize_embeddings=False)
    ecarts = {"dense seul": [], "BM25 seul": [], "les deux": []}
    norms_docs = []
    for x, qv in zip(main111, Qind):
        qv = np.asarray(qv, dtype=np.float64)
        for r in x["rows"]:
            d = stored[r["id"]]
            norms_docs.append(float(np.linalg.norm(d)))
            ind = 1.0 - float(d @ qv / (np.linalg.norm(d) * np.linalg.norm(qv)))
            r["distance_independante"] = ind
            ecarts[r["origine"]].append(abs(ind - r["distance"]))
    A2 = {"questions": len(main111),
          "candidats_par_question": {o: pstats([sum(1 for r in x["rows"] if r["origine"] == o) for x in main111])
                                     for o in ("les deux", "dense seul", "BM25 seul")},
          "total": {o: sum(1 for x in main111 for r in x["rows"] if r["origine"] == o)
                    for o in ("les deux", "dense seul", "BM25 seul")},
          "ecart_max_vs_recalcul": {o: (max(v) if v else None) for o, v in ecarts.items()},
          "norme_embeddings_stockes": {"min": min(norms_docs), "max": max(norms_docs)},
          "distances_bm25_seul": pstats([r["distance"] for x in main111 for r in x["rows"] if r["origine"] == "BM25 seul"]),
          "bm25_seul_au_dela_075": sum(1 for x in main111 for r in x["rows"] if r["origine"] == "BM25 seul" and r["distance"] > REAL),
          "dense_seul_au_dela_075": sum(1 for x in main111 for r in x["rows"] if r["origine"] == "dense seul" and r["distance"] > REAL),
          "les_deux_au_dela_075": sum(1 for x in main111 for r in x["rows"] if r["origine"] == "les deux" and r["distance"] > REAL)}
    # écartés effectivement pendant search() (la boucle s'arrête dès top_k atteint)
    for top_k, name in ((4, "hybrid"), (settings.RERANK_CANDIDATES, "advanced")):
        sk = [apply_filter(index, x["rows"], REAL, top_k)[1] for x in main111]
        A2[f"ecartes_effectivement_{name}"] = {"total": sum(sk), "questions_touchees": sum(1 for s in sk if s),
                                              "par_question": pstats(sk)}
    print("A2", json.dumps(A2, ensure_ascii=False), flush=True)

    # vérification : la boucle rejouée = vraies fonctions, à 0,75
    mism_h = mism_a = 0
    rr_cache = {}

    def advanced_hits(x, t):
        cands, _ = apply_filter(index, x["rows"], t, max(4, settings.RERANK_CANDIDATES))
        key = (x["q"], tuple(c["metadata"].get("sku") or c["document"][:60] for c in cands))
        if key not in rr_cache:
            rr_cache[key] = reranker.rerank(x["q"], copy.deepcopy(cands), top_n=4)
        return rr_cache[key]

    for x in data:
        settings.RAG_RETRIEVAL_MODE = "hybrid"
        real_h = [h["document"] for h in hr.search(x["q"], top_k=4)]
        mism_h += real_h != [h["document"] for h in apply_filter(index, x["rows"], REAL, 4)[0]]
        settings.RAG_RETRIEVAL_MODE = "advanced"
        real_a = [h["document"] for h in retriever.search(x["q"], 4)]
        mism_a += real_a != [h["document"] for h in advanced_hits(x, REAL)]
    verif = {"questions": len(data), "differences_hybrid": mism_h, "differences_advanced": mism_a}
    print("vérification", verif, flush=True)

    # ---------------- B2 : distributions (top 20 fusionné, sans filtre)
    def dist_sets(sel):
        good_best, good_all, bad, good_beyond = [], [], [], 0
        for x in main111:
            if not x["acc"]:
                continue
            top = x["rows"][:20]
            g = [r for r in top if sel(r) and r["source"] in x["acc"]]
            b = [r for r in top if sel(r) and r["source"] not in x["acc"]]
            if g:
                good_best.append(min(r["distance"] for r in g))
            good_all += [r["distance"] for r in g]
            bad += [r["distance"] for r in b]
            good_beyond += sum(1 for r in g if r["distance"] > REAL)
        return {"meilleure_bonne_source": pstats(good_best), "toutes_bonnes_sources": pstats(good_all),
                "autres_candidats": pstats(bad), "bonnes_sources_au_dela_075": good_beyond}
    B2 = {"tous": dist_sets(lambda r: True), "dense (dense seul + les deux)": dist_sets(lambda r: r["origine"] != "BM25 seul"),
          "BM25 seul": dist_sets(lambda r: r["origine"] == "BM25 seul")}
    # meilleure bonne source dans tout le corpus (recherche exacte)
    exact_best = []
    for x, qv in zip(main111, Qind):
        if not x["acc"]:
            continue
        qn = np.asarray(qv, dtype=np.float32)
        qn = qn / np.linalg.norm(qn)
        d = 1.0 - index.embeddings @ qn
        mask = np.array([src(m) in x["acc"] for m in index.metadatas])
        exact_best.append({"q": x["q"], "jeu": x["jeu"], "distance": round(float(d[mask].min()), 3)})
    B2["meilleure_bonne_source_corpus_exact"] = pstats([e["distance"] for e in exact_best])
    B2["questions_dont_toute_bonne_source_est_au_dela_075"] = [e for e in exact_best if e["distance"] > REAL]
    B2["questions_avec_bonne_source"] = len(exact_best)
    print("B2", json.dumps(B2, ensure_ascii=False)[:1500], flush=True)

    # ---------------- B3 / B4 : balayage
    banc = [x for x in data if x["jeu"] == "banc68"]
    B3, B4 = {}, {}
    base_basic = retriever.MAX_RELEVANT_DISTANCE
    for t in THRESHOLDS:
        B3[t], B4[t] = {}, {}
        for mode in ("basic", "hybrid", "advanced"):
            per = {}
            esc = {}
            removed = []
            for x in data:
                if mode == "basic":
                    retriever.MAX_RELEVANT_DISTANCE = t
                    settings.RAG_RETRIEVAL_MODE = "basic"
                    hits = retriever.search(x["q"], 4)
                    sk = None
                elif mode == "hybrid":
                    hits, sk = apply_filter(index, x["rows"], t, 4)
                else:
                    hits = advanced_hits(x, t)
                    sk = apply_filter(index, x["rows"], t, max(4, settings.RERANK_CANDIDATES))[1]
                conf = retriever.get_best_confidence(hits)
                esc[x["jeu"] + "|" + x["q"]] = {"conf": round(conf, 4), "escalade": conf < settings.RAG_CONFIDENCE_THRESHOLD,
                                                "n_hits": len(hits)}
                if x["jeu"] == "banc68":
                    if sk is not None:
                        removed.append(sk)
                    rk = rank_of(hits, x["acc"])
                    p = per.setdefault(x["langue"], {"n": 0, "hit": 0, "rr": 0.0})
                    p["n"] += 1
                    p["hit"] += rk is not None
                    p["rr"] += 1 / rk if rk else 0
            tot = {k: sum(p[k] for p in per.values()) for k in ("n", "hit", "rr")}
            per["toutes"] = tot
            B3[t][mode] = {"par_langue": {lg: {"hit4": p["hit"], "n": p["n"], "mrr4": round(p["rr"] / p["n"], 3)}
                                          for lg, p in per.items()},
                           "retires_par_question_moyenne": round(statistics.mean(removed), 2) if removed else None}
            B4[t][mode] = esc
            print(t, mode, B3[t][mode]["par_langue"]["toutes"], B3[t][mode]["retires_par_question_moyenne"], flush=True)
    retriever.MAX_RELEVANT_DISTANCE = base_basic
    settings.RAG_RETRIEVAL_MODE = "advanced"

    # B4 : décisions d'escalade qui changent par rapport à 0,75
    B4diff = {}
    for t in THRESHOLDS:
        for mode in ("basic", "hybrid", "advanced"):
            ch = [k for k in B4[t][mode] if B4[t][mode][k]["escalade"] != B4[REAL][mode][k]["escalade"]]
            B4diff[f"{t}|{mode}"] = {"n_changements": len(ch), "exemples": [
                {"q": k, "a_075": B4[REAL][mode][k], "a_t": B4[t][mode][k]} for k in ch[:6]]}
    nb_esc = {f"{t}|{m}": sum(v["escalade"] for v in B4[t][m].values()) for t in THRESHOLDS for m in B4[t]}

    for x in data:
        for r in x["rows"]:
            r.pop("i", None)
        x["acc"] = sorted(x["acc"])
    R = {"versions": {"python": platform.python_version(), "numpy": np.__version__, "chromadb_client": chromadb.__version__,
                      "sentence_transformers": sentence_transformers.__version__, "embedding": settings.EMBEDDING_MODEL,
                      "reranker": settings.RERANKER_MODEL, "rerank_candidates": settings.RERANK_CANDIDATES,
                      "candidates_per_list": hr.CANDIDATES_PER_LIST, "seuil_confiance": settings.RAG_CONFIDENCE_THRESHOLD},
         "A2": A2, "verification": verif, "B2": B2, "B3": {str(k): v for k, v in B3.items()},
         "B4_changements_vs_075": B4diff, "B4_nb_escalades": nb_esc, "n_questions_B4": len(data),
         "questions": [{k: v for k, v in x.items() if k != "rows"} | {"candidats": x["rows"][:40]} for x in data]}
    OUT_JSON.write_text(json.dumps(R, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print("B4 nb escalades", nb_esc)
    print("B4 changements", {k: v["n_changements"] for k, v in B4diff.items()})


if __name__ == "__main__":
    main()
