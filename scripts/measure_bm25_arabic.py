"""
Remarque 42 (partie A) : normalisation de l'arabe pour BM25.

A2. Ce que fait AUJOURD'HUI hybrid_retriever.tokenize sur des variantes
    orthographiques arabes (entrée -> tokens), et ce que NFKD + suppression
    des marques combinantes change réellement, caractère par caractère.
A3. Impact d'une normalisation arabe (normalize_ar, SANS racinisation),
    appliquée avant tokenize aux documents ET aux questions :
    BM25 seul, hybrid et advanced, sur le banc data/evaluation/recherche.json
    (68 questions, dont 17 en arabe) et sur un jeu SYNTHÉTIQUE de variantes
    orthographiques construit mécaniquement à partir des 17 questions arabes.
    hit@4 et rang de la première bonne source (même définition que
    scripts/evaluate_retrieval.py).

Rien n'est modifié sur disque : tokenize et l'index BM25 sont remplacés EN
MÉMOIRE (monkeypatch) le temps de la mesure. Collection de production lue
seulement (get / query). Ni LLM ni /chat/.

Usage : python scripts/measure_bm25_arabic.py
"""
import copy
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np  # noqa: E402
from rank_bm25 import BM25Okapi  # noqa: E402

from app.config import settings  # noqa: E402
from app.services.rag import hybrid_retriever, retriever  # noqa: E402
from scripts.evaluate_retrieval import load_questions  # noqa: E402

OUT_MD = ROOT / "docs" / "evaluation" / "bm25_arabe.md"
OUT_JSON = ROOT / "docs" / "evaluation" / "bm25_arabe.json"
ORIG_TOKENIZE = hybrid_retriever.tokenize

_DIACRITICS = re.compile(r"[ً-ْٰ]")
_ALIFS = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ة": "ه"})
AR_LETTER = re.compile(r"[ء-ي]")


def normalize_ar(text: str) -> str:
    """Diacritiques (U+064B-U+0652, U+0670) et tatweel (U+0640) supprimés,
    أ إ آ ٱ -> ا, ى -> ي, ة -> ه. Pas de racinisation."""
    text = _DIACRITICS.sub("", text).replace("ـ", "")
    return text.translate(_ALIFS)


def tokenize_norm(text: str) -> list:
    return ORIG_TOKENIZE(normalize_ar(text))


# ---------------------------------------------------------------- A2
PAIRS = [
    ("alif avec hamza", "أريد", "اريد"), ("alif avec hamza", "إرجاع", "ارجاع"), ("alif madda", "آلة", "اله"),
    ("alif wasla", "ٱلضمان", "الضمان"),
    ("ta marbuta", "الضمانة", "الضمانه"), ("ta marbuta", "الفاتورة", "الفاتوره"),
    ("alif maqsura", "على", "علي"),
    ("diacritiques", "مُدَّةُ الضَّمَانِ", "مدة الضمان"),
    ("tatweel", "الضمــــان", "الضمان"),
    ("article ال", "الضمان", "ضمان"), ("préposition collée ب", "بالضمان", "الضمان"),
    ("préposition collée ل", "للشحن", "الشحن"),
]
CHARS = ["أ", "إ", "آ", "ٱ", "ؤ", "ئ", "ة", "ى", "ـ", "َ", "ُ", "ِ", "ّ", "ْ",
         "ً", "ٰ", "ﻠ"]


def nfkd_effect(c):
    d = unicodedata.normalize("NFKD", c.lower())
    kept = "".join(x for x in d if not unicodedata.combining(x))
    return {"car": c, "code": f"U+{ord(c):04X}", "nom": unicodedata.name(c, "?"),
            "nfkd": " ".join(f"U+{ord(x):04X}" for x in d),
            "apres_suppression_combinantes": " ".join(f"U+{ord(x):04X}" for x in kept) or "(supprimé)",
            "token_regex_w": bool(re.fullmatch(r"\w+", kept)) if kept else None}


# ---------------------------------------------------------------- A3
def variants(q):
    """Variantes SYNTHÉTIQUES construites mécaniquement."""
    words = q.split(" ")
    return {
        "hamza retirée (أ إ آ -> ا)": q.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا"),
        "ة -> ه": q.replace("ة", "ه"),
        "diacritiques ajoutés (fatha après chaque lettre)": "".join(
            c + "َ" if AR_LETTER.match(c) else c for c in q),
        "tatweel inséré (après la 1re lettre des mots de 3 lettres ou plus)": " ".join(
            (w[0] + "ــ" + w[1:]) if len(AR_LETTER.findall(w)) >= 3 and AR_LETTER.match(w[0]) else w
            for w in words),
    }


def source_of(meta):
    return meta.get("source") or meta.get("sku")


def bm25_eval(index, bm25, tok, question, accepted):
    scores = bm25.get_scores(tok(question)) if tok(question) else np.zeros(len(index.ids))
    order = np.argsort(scores)[::-1]
    rank = None
    for r, i in enumerate(order, start=1):
        if scores[i] <= 0:
            break
        if source_of(index.metadatas[i]) in accepted:
            rank = r
            break
    top20 = [index.ids[i] for i in order[:20] if scores[i] > 0]
    return {"hit4": rank is not None and rank <= 4, "rang": rank, "top20": top20,
            "tokens": tok(question), "n_scores_pos": int((scores > 0).sum())}


def pipeline_eval(mode, question, accepted):
    settings.RAG_RETRIEVAL_MODE = mode
    hits = retriever.search(question, 4)
    found = [source_of(h["metadata"]) for h in hits]
    rank = next((i for i, s in enumerate(found, start=1) if s in accepted), None)
    return {"hit4": rank is not None, "rang": rank}


def use(index, tok):
    """Monkeypatch EN MÉMOIRE : tokenize et index BM25 utilisés par search()."""
    hybrid_retriever.tokenize = tok
    hybrid_retriever._index = index


def main():
    R = {"tokenize_source": None, "paires": [], "caracteres": [], "stopwords_ar": None}
    import inspect
    R["tokenize_source"] = inspect.getsource(ORIG_TOKENIZE)
    R["stopwords_ar"] = sorted(w for w in hybrid_retriever._STOPWORDS if AR_LETTER.search(w))
    for phen, a, b in PAIRS:
        ta, tb = ORIG_TOKENIZE(a), ORIG_TOKENIZE(b)
        na, nb = tokenize_norm(a), tokenize_norm(b)
        R["paires"].append({"phenomene": phen, "a": a, "b": b, "tokens_a": ta, "tokens_b": tb, "identiques": ta == tb,
                            "norm_tokens_a": na, "norm_tokens_b": nb, "norm_identiques": na == nb})
        print(f"{phen:22s} {a!r} -> {ta} | {b!r} -> {tb} | identiques={ta == tb} | normalisé={na == nb}", flush=True)
    R["caracteres"] = [nfkd_effect(c) for c in CHARS]
    for c in R["caracteres"]:
        print(c, flush=True)

    # index de production (lecture seule), puis variante normalisée en mémoire
    settings.RAG_RETRIEVAL_MODE = "hybrid"
    idx = hybrid_retriever._get_index()
    ar_docs = sum(1 for d in idx.documents if AR_LETTER.search(d))
    R["corpus"] = {"n": len(idx.ids), "documents_avec_lettres_arabes": ar_docs}
    print("corpus :", R["corpus"], flush=True)
    idx_norm = copy.copy(idx)
    idx_norm.bm25 = BM25Okapi([tokenize_norm(d) for d in idx.documents])
    vocab_ar = {t for d in idx.documents for t in ORIG_TOKENIZE(d) if AR_LETTER.search(t)}
    R["corpus"]["tokens_arabes_dans_l_index"] = len(vocab_ar)
    R["corpus"]["documents_modifies_par_normalize_ar"] = sum(1 for d in idx.documents if normalize_ar(d) != d)

    questions = load_questions("recherche.json")
    R["banc"] = []
    for theme, lang, q, accepted in questions:
        row = {"theme": theme, "langue": lang, "question": q,
               "tokens_identiques": ORIG_TOKENIZE(q) == tokenize_norm(q)}
        row["bm25"] = bm25_eval(idx, idx.bm25, ORIG_TOKENIZE, q, accepted)
        row["bm25_norm"] = bm25_eval(idx_norm, idx_norm.bm25, tokenize_norm, q, accepted)
        R["banc"].append(row)

    # variantes synthétiques des 17 questions arabes
    R["variantes"] = []
    for theme, lang, q, accepted in questions:
        if lang != "ar":
            continue
        for vname, v in variants(q).items():
            R["variantes"].append({"theme": theme, "variante": vname, "original": q, "question": v,
                                   "modifiee": v != q, "accepted": sorted(accepted),
                                   "bm25": bm25_eval(idx, idx.bm25, ORIG_TOKENIZE, v, accepted),
                                   "bm25_norm": bm25_eval(idx_norm, idx_norm.bm25, tokenize_norm, v, accepted)})

    # pipelines : basic (référence dense), hybrid, advanced ; actuel vs normalisé
    retriever.search("préchauffage", 4)
    for mode in ("basic", "hybrid", "advanced"):
        for label, index, tok in (("actuel", idx, ORIG_TOKENIZE), ("norm", idx_norm, tokenize_norm)):
            if mode == "basic" and label == "norm":
                continue  # basic n'utilise pas BM25
            use(index, tok)
            settings.RAG_RETRIEVAL_MODE = mode
            retriever.search("préchauffage", 4)
            for row, (theme, lang, q, accepted) in zip(R["banc"], questions):
                row[f"{mode}_{label}"] = pipeline_eval(mode, q, accepted)
            for v in R["variantes"]:
                v[f"{mode}_{label}"] = pipeline_eval(mode, v["question"], set(v["accepted"]))
            print(mode, label, "fait", flush=True)
    use(idx, ORIG_TOKENIZE)

    # A3 bis (complément) : normaliser la QUESTION avant toute la recherche
    # (embedding dense compris), index inchangé. Deux versions : complète
    # (normalize_ar) et légère (diacritiques + tatweel seulement).
    pre = {"pre_complet": normalize_ar,
           "pre_leger": lambda t: _DIACRITICS.sub("", t).replace("ـ", "")}
    for mode in ("basic", "hybrid", "advanced"):
        settings.RAG_RETRIEVAL_MODE = mode
        retriever.search("préchauffage", 4)
        for pname, f in pre.items():
            for row, (theme, lang, q, accepted) in zip(R["banc"], questions):
                row[f"{mode}_{pname}"] = pipeline_eval(mode, f(q), accepted)
            for v in R["variantes"]:
                v[f"{mode}_{pname}"] = pipeline_eval(mode, f(v["question"]), set(v["accepted"]))
            print(mode, pname, "fait", flush=True)
    hybrid_retriever.refresh_index()

    for row in R["banc"]:
        row["bm25"].pop("top20_ids", None)
        row["bm25_liste_identique"] = row["bm25"]["top20"] == row["bm25_norm"]["top20"]
    for v in R["variantes"]:
        v["bm25_liste_identique"] = v["bm25"]["top20"] == v["bm25_norm"]["top20"]
    OUT_JSON.write_text(json.dumps(R, ensure_ascii=False, indent=1), encoding="utf-8")
    summary(R)


def summary(R):
    def cnt(rows, key):
        return sum(1 for r in rows if r[key]["hit4"]), len(rows)
    cols = ["bm25", "bm25_norm", "basic_actuel", "hybrid_actuel", "hybrid_norm", "advanced_actuel", "advanced_norm"]
    cols += [f"{m}_{p}" for m in ("basic", "hybrid", "advanced") for p in ("pre_leger", "pre_complet")]
    print("\n=== banc (hit@4) ===")
    for lang in ("fr", "en", "ar", "tn"):
        rows = [r for r in R["banc"] if r["langue"] == lang]
        print(lang, {c: "%d/%d" % cnt(rows, c) for c in cols},
              "| tokens identiques", sum(r["tokens_identiques"] for r in rows),
              "| listes BM25 identiques", sum(r["bm25_liste_identique"] for r in rows), flush=True)
    print("\n=== variantes synthétiques (hit@4) ===")
    for vname in dict.fromkeys(v["variante"] for v in R["variantes"]):
        rows = [v for v in R["variantes"] if v["variante"] == vname]
        print(vname, "modifiées", sum(v["modifiee"] for v in rows), {c: "%d/%d" % cnt(rows, c) for c in cols},
              "| listes BM25 identiques", sum(v["bm25_liste_identique"] for v in rows), flush=True)


if __name__ == "__main__":
    main()
