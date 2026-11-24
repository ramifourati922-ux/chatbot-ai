"""
Remarque 52, étape 2 : notes du juge Ragas (gpt-oss-20b) contre annotation humaine.

Entrées (lecture seule, jamais modifiées) :
    data/evaluation/annotation_juge/feuille_annotation_remplie.csv  (séparateur « ; »)
    data/evaluation/annotation_juge/feuille_annotation_2.csv        (facultatif : 2e annotateur)
    data/evaluation/annotation_juge/cle_secrete.json
Sorties :
    docs/evaluation/validation_juge.md, data/evaluation/validation_juge.json

Correspondance : fidelite ↔ faithfulness, pertinence ↔ answer_relevancy,
rappel ↔ context_recall. Notes humaines dans {0 ; 0,5 ; 1} (virgule acceptée) ;
cellule vide ou « ? » : item exclu de la métrique concernée.

Aucun appel Groq, aucune écriture en base. Le script s'arrête sans rien écrire
si la feuille remplie est absente ou si une valeur est hors de {0 ; 0,5 ; 1}.

Usage :
    python scripts/compare_juge_humain.py
    python scripts/compare_juge_humain.py --feuille <csv> --out-md <md> --out-json <json>   (essai)
"""
import argparse
import csv
import json
import math
import random
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
DIR = ROOT / "data" / "evaluation" / "annotation_juge"
METRICS = {"fidelite": "faithfulness", "pertinence": "answer_relevancy", "rappel": "context_recall"}
ALLOWED = {0.0, 0.5, 1.0}
SEED, B = 42, 10000
THRESHOLDS = {"1/3-2/3": (1 / 3, 2 / 3), "0,25-0,75": (0.25, 0.75)}


# ---------------------------------------------------------------- statistiques
def ranks(v):
    order = sorted(range(len(v)), key=lambda i: v[i])
    r = [0.0] * len(v)
    i = 0
    while i < len(v):
        j = i
        while j + 1 < len(v) and v[order[j + 1]] == v[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def pearson(x, y):
    if len(x) < 2:
        return None
    mx, my = statistics.fmean(x), statistics.fmean(y)
    sx = math.sqrt(sum((a - mx) ** 2 for a in x))
    sy = math.sqrt(sum((b - my) ** 2 for b in y))
    if sx == 0 or sy == 0:
        return None  # une des séries est constante : corrélation indéfinie
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / (sx * sy)


def spearman(x, y):
    return pearson(ranks(x), ranks(y)) if len(x) >= 2 else None


def boot_ci(x, y, fn):
    rng = random.Random(SEED)
    idx = list(range(len(x)))
    vals = []
    for _ in range(B):
        s = [rng.choice(idx) for _ in idx]
        v = fn([x[i] for i in s], [y[i] for i in s])
        if v is not None:
            vals.append(v)
    if len(vals) < B * 0.5:
        return None, len(vals)
    vals.sort()
    return [round(vals[int(0.025 * len(vals))], 3), round(vals[int(0.975 * len(vals)) - 1], 3)], len(vals)


def to3(v, lo, hi):
    return 0.0 if v < lo else (0.5 if v < hi else 1.0)


def kappa_quadratic(a, b):
    cats = [0.0, 0.5, 1.0]
    n = len(a)
    if n == 0:
        return None
    O = [[sum(1 for x, y in zip(a, b) if x == ci and y == cj) for cj in cats] for ci in cats]
    pa = [sum(O[i]) / n for i in range(3)]
    pb = [sum(O[i][j] for i in range(3)) / n for j in range(3)]
    w = [[((i - j) ** 2) / 4 for j in range(3)] for i in range(3)]
    obs = sum(w[i][j] * O[i][j] / n for i in range(3) for j in range(3))
    exp = sum(w[i][j] * pa[i] * pb[j] for i in range(3) for j in range(3))
    return None if exp == 0 else 1 - obs / exp


def confusion(human, judge3):
    cats = [0.0, 0.5, 1.0]
    return {f"humain={h}": {f"juge={j}": sum(1 for x, y in zip(human, judge3) if x == h and y == j) for j in cats}
            for h in cats}


def r3(v):
    return None if v is None else round(v, 3)


# ---------------------------------------------------------------- lecture
def parse(cell):
    c = (cell or "").strip().replace(",", ".")
    if c in ("", "?"):
        return None
    return float(c)


def read_sheet(path):
    rows = list(csv.DictReader(open(path, encoding="utf-8-sig", newline=""), delimiter=";"))
    out, problems, excluded = {}, [], {m: [] for m in METRICS}
    for r in rows:
        item = (r.get("item") or "").strip()
        out[item] = {"commentaire": (r.get("commentaire") or "").strip()}
        for m in METRICS:
            raw = r.get(m)
            try:
                v = parse(raw)
            except ValueError:
                problems.append(f"{item} {m} : valeur illisible {raw!r}")
                continue
            if v is None:
                excluded[m].append(item)
            elif v not in ALLOWED:
                problems.append(f"{item} {m} : {raw!r} hors de {{0 ; 0,5 ; 1}}")
            out[item][m] = v
    return rows, out, problems, excluded


def analyse(pairs):
    """pairs : liste de (note_humaine, note_juge, item)."""
    h = [p[0] for p in pairs]
    j = [p[1] for p in pairs]
    res = {"n": len(pairs)}
    if len(pairs) < 2:
        return res
    sp = spearman(h, j)
    ci, nb = boot_ci(h, j, spearman)
    res.update({"spearman": r3(sp), "spearman_ic95": ci, "bootstrap_tirages_definis": nb,
                "pearson": r3(pearson(h, j)), "ecart_absolu_moyen": r3(statistics.fmean(abs(a - b) for a, b in zip(h, j))),
                "biais_moyen_juge_moins_humain": r3(statistics.fmean(b - a for a, b in zip(h, j)))})
    for name, (lo, hi) in THRESHOLDS.items():
        j3 = [to3(v, lo, hi) for v in j]
        res[f"seuils_{name}"] = {"accord_exact": r3(sum(a == b for a, b in zip(h, j3)) / len(h)),
                                 "kappa_pondere_quadratique": r3(kappa_quadratic(h, j3)), "confusion": confusion(h, j3)}
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--feuille", default=str(DIR / "feuille_annotation_remplie.csv"))
    ap.add_argument("--feuille2", default=str(DIR / "feuille_annotation_2.csv"))
    ap.add_argument("--cle", default=str(DIR / "cle_secrete.json"))
    ap.add_argument("--out-md", default=str(ROOT / "docs" / "evaluation" / "validation_juge.md"))
    ap.add_argument("--out-json", default=str(ROOT / "data" / "evaluation" / "validation_juge.json"))
    args = ap.parse_args()
    if not Path(args.feuille).exists():
        sys.exit(f"Feuille remplie introuvable : {args.feuille}. Rien n'est calculé ni écrit.")
    key = json.loads(Path(args.cle).read_text(encoding="utf-8"))["items"]
    rows, human, problems, excluded = read_sheet(args.feuille)
    check = {"lignes": len(rows), "items_attendus": len(key), "items_inconnus": sorted(set(human) - set(key)),
             "items_absents": sorted(set(key) - set(human)), "valeurs_invalides": problems, "exclus_vide_ou_?": excluded}
    print("contrôle :", json.dumps(check, ensure_ascii=False), flush=True)
    if problems or check["items_inconnus"] or len(rows) != 30:
        sys.exit("Feuille non conforme (voir contrôle) : rien n'est écrit.")

    R = {"controle": check, "metriques": {}, "par_langue": {}, "par_mode": {}, "paires": {}, "desaccords": {}}
    for hm, jm in METRICS.items():
        pairs = [(human[a][hm], key[a]["juge"][jm], a) for a in key
                 if human.get(a, {}).get(hm) is not None and key[a]["juge"][jm] is not None]
        R["metriques"][hm] = {"juge": jm, **analyse(pairs)}
        for grp, field in (("par_langue", "langue"), ("par_mode", "mode")):
            R[grp].setdefault(hm, {})
            for val in sorted({key[a][field] for a in key}):
                sub = [p for p in pairs if key[p[2]][field] == val]
                hh, jj = [p[0] for p in sub], [p[1] for p in sub]
                R[grp][hm][val] = {"n": len(sub), "spearman": r3(spearman(hh, jj)) if len(sub) >= 2 else None,
                                   "biais_moyen_juge_moins_humain": r3(statistics.fmean(b - a for a, b in zip(hh, jj))) if sub else None}
        # 5. paires de questions présentes dans les deux modes
        byq = {}
        for p in pairs:
            byq.setdefault(key[p[2]]["question_id"], {})[key[p[2]]["mode"]] = p
        rows5 = []
        for q, d in sorted(byq.items()):
            if "basic" in d and "advanced" in d:
                gh = d["advanced"][0] - d["basic"][0]
                gj = d["advanced"][1] - d["basic"][1]
                sh = (gh > 0) - (gh < 0)
                sj = (gj > 1e-9) - (gj < -1e-9)
                rows5.append({"paire": f"{d['basic'][2]}/{d['advanced'][2]}", "langue": key[d['basic'][2]]["langue"],
                              "gain_humain": r3(gh), "gain_juge": r3(gj), "meme_sens": sh == sj})
        R["paires"][hm] = {"n_paires": len(rows5), "meme_sens": sum(r["meme_sens"] for r in rows5),
                           "gain_moyen_humain": r3(statistics.fmean(r["gain_humain"] for r in rows5)) if rows5 else None,
                           "gain_moyen_juge": r3(statistics.fmean(r["gain_juge"] for r in rows5)) if rows5 else None,
                           "detail": rows5}
        # 6. 5 plus grands désaccords
        worst = sorted(pairs, key=lambda p: -abs(p[1] - p[0]))[:5]
        R["desaccords"][hm] = [{"item": a, "langue": key[a]["langue"], "humain": h_, "juge": j_,
                                "commentaire": human[a]["commentaire"][:200]} for h_, j_, a in worst]

    # 7. second annotateur
    if Path(args.feuille2).exists():
        _, human2, problems2, _ = read_sheet(args.feuille2)
        R["second_annotateur"] = {"valeurs_invalides": problems2}
        for hm, jm in METRICS.items():
            common = [a for a in key if human.get(a, {}).get(hm) is not None and human2.get(a, {}).get(hm) is not None]
            x = [human[a][hm] for a in common]
            y = [human2[a][hm] for a in common]
            avg = [((human[a][hm] + human2[a][hm]) / 2, key[a]["juge"][jm], a) for a in common if key[a]["juge"][jm] is not None]
            R["second_annotateur"][hm] = {"n": len(common), "spearman": r3(spearman(x, y)),
                                          "kappa_pondere_quadratique": r3(kappa_quadratic(x, y)),
                                          "accord_exact": r3(sum(a == b for a, b in zip(x, y)) / len(x)) if x else None,
                                          "moyenne_humains_vs_juge": analyse(avg)}
    else:
        R["second_annotateur"] = "absent (feuille_annotation_2.csv introuvable)"

    Path(args.out_json).write_text(json.dumps(R, ensure_ascii=False, indent=1), encoding="utf-8")
    Path(args.out_md).write_text(render(R), encoding="utf-8")
    print("écrit :", args.out_md, args.out_json)


def fmt(v):
    return "—" if v is None else (f"{v:.3f}".replace(".", ",") if isinstance(v, float) else str(v))


def render(R):
    L = ["# Validation du juge Ragas par annotation humaine (remarque 52)", "",
         "Calculé par `scripts/compare_juge_humain.py` (aucun appel Groq). Correspondance : fidélité ↔ "
         "Faithfulness, pertinence ↔ Answer Relevancy, rappel ↔ Context Recall. L'Answer Relevancy de Ragas "
         "est une similarité entre la question et des questions régénérées à partir de la réponse (elle ne "
         "dépasse pas 0,891 sur cet échantillon) : seuls les rangs (Spearman) et les tendances sont comparés "
         "pour elle, pas les valeurs absolues.", "",
         f"Contrôle de la feuille : {R['controle']['lignes']} lignes ; items exclus (vide ou « ? ») : "
         + "; ".join(f"{m} {len(v)}" for m, v in R["controle"]["exclus_vide_ou_?"].items()), "",
         "## Accord par métrique", "",
         "| Métrique | n | Spearman [IC 95 %] | Pearson | Écart absolu moyen | Biais (juge − humain) | Accord exact (seuils 1/3-2/3) | κ pondéré | Accord exact (0,25-0,75) | κ pondéré |",
         "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for hm, d in R["metriques"].items():
        s1, s2 = d.get("seuils_1/3-2/3", {}), d.get("seuils_0,25-0,75", {})
        L.append(f"| {hm} ({d['juge']}) | {d['n']} | {fmt(d.get('spearman'))} {d.get('spearman_ic95')} | {fmt(d.get('pearson'))} | "
                 f"{fmt(d.get('ecart_absolu_moyen'))} | {fmt(d.get('biais_moyen_juge_moins_humain'))} | "
                 f"{fmt(s1.get('accord_exact'))} | {fmt(s1.get('kappa_pondere_quadratique'))} | {fmt(s2.get('accord_exact'))} | "
                 f"{fmt(s2.get('kappa_pondere_quadratique'))} |")
    L += ["", "Matrices de confusion (lignes : humain ; colonnes : juge converti, seuils 1/3-2/3) :", ""]
    for hm, d in R["metriques"].items():
        c = d.get("seuils_1/3-2/3", {}).get("confusion")
        if c:
            L += [f"**{hm}**", "", "| humain \\ juge | 0 | 0,5 | 1 |", "| --- | --- | --- | --- |"]
            for h, row in c.items():
                L.append(f"| {h.split('=')[1]} | " + " | ".join(str(v) for v in row.values()) + " |")
            L.append("")
    for grp, title in (("par_langue", "Par langue"), ("par_mode", "Par mode")):
        L += [f"## {title}", "", "| Métrique | Groupe | n | Spearman | Biais (juge − humain) |", "| --- | --- | --- | --- | --- |"]
        for hm, d in R[grp].items():
            for g, v in d.items():
                L.append(f"| {hm} | {g} | {v['n']} | {fmt(v['spearman'])} | {fmt(v['biais_moyen_juge_moins_humain'])} |")
        L.append("")
    L += ["## Paires Basic / Advanced (même question)", "",
          "| Métrique | Paires | Même sens du gain | Gain moyen humain | Gain moyen juge |", "| --- | --- | --- | --- | --- |"]
    for hm, d in R["paires"].items():
        L.append(f"| {hm} | {d['n_paires']} | {d['meme_sens']} | {fmt(d['gain_moyen_humain'])} | {fmt(d['gain_moyen_juge'])} |")
    L += ["", "## Plus grands désaccords", ""]
    for hm, lst in R["desaccords"].items():
        L += [f"**{hm}**", "", "| Item | Langue | Humain | Juge | Commentaire |", "| --- | --- | --- | --- | --- |"]
        L += [f"| {x['item']} | {x['langue']} | {fmt(x['humain'])} | {fmt(x['juge'])} | {x['commentaire']} |" for x in lst]
        L.append("")
    L += ["## Second annotateur", "", json.dumps(R["second_annotateur"], ensure_ascii=False)[:2000]
          if isinstance(R["second_annotateur"], dict) else str(R["second_annotateur"]), "",
          "## Limites", "",
          "- 30 items seulement (12 fr, 6 en, 6 ar, 6 tn) ; effectifs très faibles par langue et par mode.",
          "- Un seul annotateur si `feuille_annotation_2.csv` est absent ; s'il s'agit de l'auteur du système, "
          "l'annotation n'est pas indépendante.",
          "- Context Precision n'est pas validée (pas de colonne d'annotation correspondante).",
          "- Échelle humaine à 3 niveaux contre une note continue du juge : la conversion en 3 classes dépend "
          "des seuils (deux jeux de seuils donnés).", ""]
    return "\n".join(L)


if __name__ == "__main__":
    main()
