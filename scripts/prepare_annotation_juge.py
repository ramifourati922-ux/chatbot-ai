"""
Remarque 52, étape 1 : feuille d'annotation humaine pour valider le juge Ragas.

Lecture seule de docs/evaluation/ragas_results.json (aucun appel Groq, aucune
écriture en base). Échantillon de 30 réponses (question × mode) parmi les 44
réponses notées, stratifié par langue et par mode :
    fr 12 (6 basic + 6 advanced), en 6 (3+3), ar 6 (3+3), tn 6 (3+3).
Tirage : random.Random(42). On tire jusqu'à obtenir un échantillon qui couvre
l'étendue des notes du juge : au moins 3 réponses dans chacune des tranches
[0 ; 1/3[, [1/3 ; 2/3[ et [2/3 ; 1] pour la Faithfulness ET pour l'Answer
Relevancy. Le numéro du tirage retenu est enregistré dans la clé.
La réponse dont la Faithfulness n'a pas été notée par le juge est exclue du
tirage (pas de note à comparer).

Sorties :
    data/evaluation/annotation_juge/feuille_annotation.csv et .md (A01…A30, ordre
        aléatoire ; ni mode, ni identifiant d'origine, ni note du juge)
    data/evaluation/annotation_juge/cle_secrete.json (correspondance et notes)
    docs/evaluation/annotation_juge/consignes.md

Usage : python scripts/prepare_annotation_juge.py
"""
import csv
import hashlib
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
SRC = ROOT / "docs" / "evaluation" / "ragas_results.json"
OUT = ROOT / "data" / "evaluation" / "annotation_juge"
DOC = ROOT / "docs" / "evaluation" / "annotation_juge"
SEED = 42
QUOTA = {("fr", "basic"): 6, ("fr", "advanced"): 6, ("en", "basic"): 3, ("en", "advanced"): 3,
         ("ar", "basic"): 3, ("ar", "advanced"): 3, ("tn", "basic"): 3, ("tn", "advanced"): 3}
MIN_PER_BIN = 3
MAX_DRAWS = 10000

CONSIGNES = """# Consignes d'annotation : validation du juge Ragas (remarque 52)

Fichiers à remplir : `data/evaluation/annotation_juge/feuille_annotation.csv` (colonnes vides)
ou, pour lire plus facilement, `feuille_annotation.md` (même contenu, mêmes identifiants A01 à A30).

**Annoter sans consulter les notes du juge ni le mode** (Basic ou Advanced). Ne pas ouvrir
`cle_secrete.json` avant d'avoir terminé les 30 items.

Pour chaque item sont affichés : la question, la réponse de référence, les passages récupérés
(séparés et numérotés) et la réponse générée par le chatbot. Juger avec les seuls éléments affichés.

Valeurs possibles : **0**, **0,5** ou **1**.

| Colonne | Question à se poser | 1 | 0,5 | 0 |
| --- | --- | --- | --- | --- |
| `fidelite` | Toutes les affirmations de la réponse sont-elles soutenues par les passages affichés ? | toutes | certaines ne sont pas soutenues | la plupart ne sont pas soutenues ou sont inventées |
| `pertinence` | La réponse répond-elle à la question posée ? | oui | partiellement | non |
| `rappel` | Les passages affichés contiennent-ils l'information de la réponse de référence ? | toute | une partie | aucune |
| `commentaire` | Libre, facultatif | | | |

Cas particulier : une réponse « je n'ai pas l'information » est notée **1 en fidélité** si elle
est honnête (rien d'inventé). Sa pertinence se juge à part : elle ne répond pas à la question.

Remplir toutes les lignes, sans modifier les autres colonnes ni l'ordre des items.
"""


def bins(v):
    return 0 if v < 1 / 3 else (1 if v < 2 / 3 else 2)


def main():
    h_before = hashlib.sha256(SRC.read_bytes()).hexdigest()
    data = json.loads(SRC.read_text(encoding="utf-8"))
    rows = [r for r in data["results"] if r["category"] != "hors-sujet"]
    pool = {k: [] for k in QUOTA}
    excluded = []
    for r in rows:
        for mode in ("basic", "advanced"):
            s = r["runs"][mode]["ragas"]["scores"]
            if s.get("faithfulness") is None or s.get("answer_relevancy") is None:
                excluded.append({"id": r["id"], "mode": mode, "raison": "note du juge absente"})
                continue
            pool[(r["lang"], mode)].append((r, mode))

    rng = random.Random(SEED)
    for draw in range(1, MAX_DRAWS + 1):
        sample = []
        for k, n in QUOTA.items():
            sample += rng.sample(pool[k], n)
        ok = True
        for metric in ("faithfulness", "answer_relevancy"):
            counts = [0, 0, 0]
            for r, mode in sample:
                counts[bins(r["runs"][mode]["ragas"]["scores"][metric])] += 1
            ok &= min(counts) >= MIN_PER_BIN
        if ok:
            break
    else:
        sys.exit("aucun tirage ne couvre l'étendue des notes")

    order = list(range(len(sample)))
    random.Random(SEED).shuffle(order)
    items, key = [], {}
    for pos, idx in enumerate(order, 1):
        r, mode = sample[idx]
        run = r["runs"][mode]
        aid = f"A{pos:02d}"
        items.append({"id": aid, "question": r["question"], "reference": r["reference"],
                      "contextes": run["contexts"], "reponse": run["answer"]})
        s = run["ragas"]["scores"]
        key[aid] = {"question_id": r["id"], "mode": mode, "langue": r["lang"],
                    "juge": {"faithfulness": s.get("faithfulness"), "answer_relevancy": s.get("answer_relevancy"),
                             "context_recall": s.get("context_recall")}}

    OUT.mkdir(parents=True, exist_ok=True)
    DOC.mkdir(parents=True, exist_ok=True)
    with open(OUT / "feuille_annotation.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["item", "question", "reponse_de_reference", "passages_recuperes", "reponse_generee",
                    "fidelite", "pertinence", "rappel", "commentaire"])
        for it in items:
            passages = "\n\n".join(f"[Passage {i}]\n{c}" for i, c in enumerate(it["contextes"], 1))
            w.writerow([it["id"], it["question"], it["reference"], passages, it["reponse"], "", "", "", ""])
    md = ["# Feuille d'annotation : validation du juge Ragas", "",
          "Consignes : `docs/evaluation/annotation_juge/consignes.md`. Valeurs : 0, 0,5 ou 1. "
          "Reporter les notes dans `feuille_annotation.csv` (même identifiant).", ""]
    for it in items:
        md += [f"## {it['id']}", "", f"**Question.** {it['question']}", "",
               f"**Réponse de référence.** {it['reference']}", "", "**Passages récupérés.**", ""]
        for i, c in enumerate(it["contextes"], 1):
            md += [f"> **Passage {i}**", ">"] + [f"> {line}" if line else ">" for line in c.splitlines()] + [""]
        md += ["**Réponse générée.**", ""] + [f"> {line}" if line else ">" for line in it["reponse"].splitlines()] + [""]
        md += ["| fidelite | pertinence | rappel | commentaire |", "| --- | --- | --- | --- |", "|  |  |  |  |", "", "---", ""]
    (OUT / "feuille_annotation.md").write_text("\n".join(md), encoding="utf-8")
    (DOC / "consignes.md").write_text(CONSIGNES, encoding="utf-8")
    secret = {"_avertissement": "Ne pas ouvrir avant la fin de l'annotation.", "graine": SEED,
              "tirage_retenu": draw, "critere": f">= {MIN_PER_BIN} réponses par tranche [0;1/3[, [1/3;2/3[, [2/3;1] "
              "pour faithfulness et answer_relevancy", "quotas": {f"{k[0]}-{k[1]}": v for k, v in QUOTA.items()},
              "exclus_du_tirage": excluded, "source_sha256": h_before, "items": key}
    (OUT / "cle_secrete.json").write_text(json.dumps(secret, ensure_ascii=False, indent=1), encoding="utf-8")

    # description agrégée (sans scores par item)
    def rng_of(metric, sel):
        v = [key[a]["juge"][metric] for a in sel if key[a]["juge"][metric] is not None]
        b = [0, 0, 0]
        for x in v:
            b[bins(x)] += 1
        return {"min": min(v), "max": max(v), "tranches_bas_moyen_haut": b, "n": len(v)}
    from collections import Counter
    desc = {"n": len(items), "tirage_retenu": draw,
            "langue": dict(Counter(v["langue"] for v in key.values())), "mode": dict(Counter(v["mode"] for v in key.values())),
            "questions_distinctes": len({v["question_id"] for v in key.values()}),
            "questions_dans_les_deux_modes": sum(1 for q, c in Counter(v["question_id"] for v in key.values()).items() if c == 2),
            "faithfulness": rng_of("faithfulness", key), "answer_relevancy": rng_of("answer_relevancy", key),
            "context_recall": rng_of("context_recall", key), "exclus": excluded,
            "sha256_avant": h_before, "sha256_apres": hashlib.sha256(SRC.read_bytes()).hexdigest()}
    print(json.dumps(desc, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
