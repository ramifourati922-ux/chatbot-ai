"""
Remarque 54 : les 3 questions tunisiennes à 0,000 en mode Basic (lecture seule).

Lit docs/evaluation/ragas_results.json (jamais réécrit, SHA-256 contrôlé), sans
appel Groq ni LLM, et écrit docs/evaluation/analyse_tunisien_basic.md.
Repérage des refus : détecteur de l'application (dialogue_manager._is_no_info_answer)
complété par une relecture manuelle (REFUS_MANUELS : refus que le détecteur rate,
texte cité dans le rapport).

Usage : python scripts/analyse_tunisien_basic.py
"""
import hashlib
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.services.dialogue_manager import _is_no_info_answer  # noqa: E402

SRC = ROOT / "docs" / "evaluation" / "ragas_results.json"
OUT = ROOT / "docs" / "evaluation" / "analyse_tunisien_basic.md"
METRICS = ("context_precision", "context_recall", "faithfulness", "answer_relevancy")
NAMES = {"context_precision": "CP", "context_recall": "CR", "faithfulness": "F", "answer_relevancy": "AR"}
# Refus repérés à la relecture et manqués par le détecteur (texte justificatif)
REFUS_MANUELS = {
    ("tn-garantie", "basic"): "« ma nجمش نعطيك معلومات دقيقة على الضمان متاع الـmultimetre » (je ne peux pas te donner d'information précise sur la garantie du multimètre)",
    ("p-18650", "basic"): "« Je ne vois aucune référence de piles 18650 dans les informations dont je dispose […] Je ne peux donc pas confirmer leur disponibilité »",
}
# Classement manuel des 6 réponses tunisiennes : (classe, justification)
CLASSEMENT = {
    ("tn-garantie", "basic"): ("(a) refus", "« ma nجمش نعطيك معلومات دقيقة على الضمان […] نحولك لمستشار الخدمة » : pas d'information, proposition de conseiller ; aucun fait affirmé."),
    ("tn-sfax", "basic"): ("(a) refus", "« ma 3andich ma3loumet d9i9a 3la thaman el livraison le Sfax. Najem n3ayetlek l'équipe » : pas d'information sur le prix, proposition de rappel."),
    ("tn-probleme", "basic"): ("(a) au sens large : demande de précisions et renvoi (pas un refus d'information)", "« يلزمنا شوية تفاصيل إضافية: رقم الطلبية […] نقترح عليك الاتصال بخدمة الحرفاء على الرقم الموجود في موقعنا » : demande le numéro et la nature du problème, renvoie au service client ; ne donne pas la procédure de la référence (photo, 48 h, contact@lissstrike.tn)."),
    ("tn-garantie", "advanced"): ("(d) correcte", "« الضمان على الملتيمتر هو 12 شهر ضد أي عيب تصنيعي » : 12 mois contre tout défaut de fabrication, comme la référence et le passage 1."),
    ("tn-sfax", "advanced"): ("(a) refus", "« ما عنديش معلومات دقيقة على ثمن التوصيل لسفكس » : pas d'information sur le prix, alors que les passages donnent la couverture de Sfax et le délai de 3 à 6 jours (pas les frais)."),
    ("tn-probleme", "advanced"): ("(a) au sens large, avec un fait inventé", "Demande les mêmes précisions, puis « تتصل بخدمة الحرفاء على الرقم 71 555 555 » : ce numéro ne figure ni dans les passages ni dans la base (le numéro de la FAQ est +216 29943697)."),
}


def mean(v):
    v = [x for x in v if x is not None]
    return (round(statistics.fmean(v), 3), len(v)) if v else (None, 0)


def fmt(v):
    return "—" if v is None else f"{v:.3f}".replace(".", ",")


def main():
    h0 = hashlib.sha256(SRC.read_bytes()).hexdigest()
    d = json.loads(SRC.read_text(encoding="utf-8"))
    rows = [r for r in d["results"] if r["category"] != "hors-sujet"]
    refus = {}
    for r in rows:
        for m in ("basic", "advanced"):
            k = (r["id"], m)
            auto = _is_no_info_answer(r["runs"][m]["answer"])
            refus[k] = {"refus": auto or k in REFUS_MANUELS, "source": "détecteur" if auto else ("relecture" if k in REFUS_MANUELS else "")}

    L = ["# Les 3 questions tunisiennes à 0,000 en mode Basic (remarque 54)", "",
         "Analyse du 24/11/2026 par `scripts/analyse_tunisien_basic.py`, en lecture seule de `docs/evaluation/ragas_results.json` "
         f"(SHA-256 identique avant et après : `{h0}`). Aucun appel à Groq ni à un LLM, aucune écriture en base, code "
         "applicatif inchangé.", ""]

    # 1. données complètes
    L += ["## 1. Les 3 questions, en Basic et en Advanced", ""]
    for r in [x for x in rows if x["lang"] == "tn"]:
        L += [f"### `{r['id']}` (catégorie {r['category']})", "", f"- **Question :** {r['question']}",
              f"- **Référence :** {r['reference']}", f"- **Sources attendues :** {', '.join(r['sources'])}", ""]
        for m in ("basic", "advanced"):
            run = r["runs"][m]
            s = run["ragas"]["scores"]
            L += [f"#### {m.capitalize()}", "",
                  f"- **retrieved_sources :** {', '.join(run['retrieved_sources'])} ; **hit_at_4 :** {run['hit_at_4']} ; "
                  f"**confiance :** {run['confidence']} (= 1 − distance minimale : {round(1 - run['confidence'], 3)}) ; "
                  f"**would_escalate :** {run['would_escalate']}",
                  "- **Scores :** " + ", ".join(f"{NAMES[k]} {fmt(s.get(k))}" for k in METRICS)
                  + f" ; **erreurs :** {run['ragas']['errors'] or 'aucune'}",
                  f"- **Classement :** {CLASSEMENT[(r['id'], m)][0]}. {CLASSEMENT[(r['id'], m)][1]}", "",
                  "**Réponse générée (en entier) :**", ""]
            L += [f"> {line}" if line else ">" for line in run["answer"].splitlines()] + [""]
            L += [f"**Contextes transmis au juge : {len(run['contexts'])}** (200 premiers caractères)", ""]
            L += [f"{i}. {c[:200].replace(chr(10), ' ⏎ ')}" for i, c in enumerate(run["contexts"], 1)] + [""]

    # 3. origine des refus
    L += ["## 3. D'où viennent les refus", "",
          "- **Pas du code.** Les 3 réponses Basic ont une confiance de 0,438, 0,482 et 0,498, au-dessus du seuil de 0,35 : "
          "`would_escalate` vaut `false` partout. D'ailleurs, l'évaluation Ragas n'utilise pas `dialogue_manager` : "
          "`scripts/evaluate_ragas.py` (`run_pipeline`, `_generate`) appelle directement le LLM avec `build_messages`. "
          "L'escalade du code (`low_rag_confidence`) ne pouvait donc pas s'appliquer ; elle n'est qu'enregistrée, dans `would_escalate`.",
          "- **Du LLM, qui suit la consigne du prompt système** (`app/services/rag/llm_factory.py`) : « SI LE CONTEXTE NE RÉPOND "
          "PAS À LA QUESTION précise posée […] dis-le clairement au client (ex: \"je n'ai pas cette information précise\") et "
          "propose de vérifier ou de le mettre en relation avec un conseiller — NE COMBLE JAMAIS le vide […] ».",
          "- **C'est le comportement voulu** quand les passages ne contiennent pas la réponse. En Basic, `tn-garantie` ne reçoit "
          "que des LED et des rubans LED. `tn-sfax` reçoit les livraisons express et du week-end, sans les frais pour Sfax. "
          "Dans les deux cas, la base contient pourtant la réponse : 12 mois pour les multimètres dans `sav/garantie.txt`, "
          "12 DT hors Grand Tunis dans `sav/livraison.txt`. **L'échec vient de la recherche, pas de la génération.**",
          "- **Distances.** Le JSON ne stocke que la confiance, c'est-à-dire 1 − la plus petite distance : 0,562, 0,518 et 0,502 "
          "pour la distance minimale en Basic. **La distance de chacun des 4 passages n'est pas stockée.** En mode basic, "
          "le filtre `MAX_RELEVANT_DISTANCE = 0,75` (`retriever._query_one`) ne garde que des passages à 0,75 ou moins : "
          "les 4 passages de chaque question l'ont donc passé.", ""]

    # 4. pourquoi 0
    L += ["## 4. Pourquoi 0,000 : ce que fait chaque métrique (ragas 0.4.3, `ragas/metrics/collections/`)", "",
          "| Métrique | Calcul (code) | Dépend de la réponse ? | Origine du 0 pour les 3 réponses Basic |",
          "| --- | --- | --- | --- |",
          "| Context Precision (`ContextPrecision` = `ContextPrecisionWithReference`, `context_precision/metric.py:81-128`) | Un verdict « utile / pas utile » par passage, **au regard de la référence**, puis une précision moyenne. Si tous les verdicts valent 0, le numérateur est nul, donc le score est 0 | **Non** : seuls la question, la référence et les passages | **(ii) passages non pertinents** : le juge a jugé les 4 passages inutiles pour la référence |",
          "| Context Recall (`context_recall/metric.py:82-129`) | Chaque affirmation de la référence est-elle attribuable aux passages ? Score = part des affirmations attribuées | **Non** | **(ii)** : aucune affirmation de la référence n'est trouvée dans les passages (pas de garantie de 12 mois, pas de frais de 12 DT, pas de procédure de réclamation) |",
          "| Faithfulness (`faithfulness/metric.py:88-161`) | La réponse est découpée en affirmations, puis chacune est vérifiée contre les passages. Score = affirmations soutenues / affirmations. **NaN s'il n'y a aucune affirmation** (l. 119-121) | **Oui** | **(iii)** : ce n'est pas un 0 automatique. Le score vaut 0,0 et non NaN, donc des affirmations ont été extraites, et aucune n'a été jugée soutenue par les passages. Le détail des affirmations et des verdicts **n'est pas stocké** dans le JSON |",
          "| Answer Relevancy (`answer_relevancy/metric.py:93-156`, `strictness=1` dans `evaluate_ragas.py:437`) | Le juge régénère une question à partir de la réponse, avec un indicateur `noncommittal` (réponse évasive). Score = cosinus moyen × (1 si au moins une réponse n'est pas évasive, sinon 0) (l. 153-154) | **Oui** | **(i) 0 par construction quand le juge marque la réponse comme évasive** : un 0,0 exact correspond à `noncommittal = 1`, car un cosinus nul n'arrive pratiquement jamais. L'indicateur lui-même n'est pas stocké |",
          "",
          "**Les 0 de Context Precision et de Context Recall ne viennent donc pas du refus.** Ils mesurent la recherche. "
          "Preuve dans le JSON : `tn-sfax` en Advanced est **aussi un refus**, mais obtient CP 0,833 et CR 0,500, car ses "
          "passages contiennent la couverture de Sfax et le délai de livraison.", ""]

    # 5. tous les refus
    L += ["## 5. Toutes les réponses de refus (22 questions × 2 modes)", "",
          "Repérage : le détecteur de l'application (`dialogue_manager._is_no_info_answer`), complété par la relecture des 44 "
          "réponses. Deux refus manqués par le détecteur ont été ajoutés : `tn-garantie` Basic, en texte mêlant arabizi et "
          "lettres arabes, et `p-18650` Basic.", "",
          "| Question | Mode | Langue | Refus | Repérage | CP | CR | F | AR |", "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    ref_rows = []
    for r in rows:
        for m in ("basic", "advanced"):
            if refus[(r["id"], m)]["refus"]:
                s = r["runs"][m]["ragas"]["scores"]
                ref_rows.append((r, m))
                L.append(f"| `{r['id']}` | {m} | {r['lang']} | oui | {refus[(r['id'], m)]['source']} | "
                         + " | ".join(fmt(s.get(k)) for k in METRICS) + " |")
    fz = sum(1 for r, m in ref_rows if r["runs"][m]["ragas"]["scores"].get("faithfulness") == 0)
    az = sum(1 for r, m in ref_rows if r["runs"][m]["ragas"]["scores"].get("answer_relevancy") == 0)
    L += ["", f"**{len(ref_rows)} refus** sur 44 réponses : {sum(m == 'basic' for _, m in ref_rows)} en Basic et "
          f"{sum(m == 'advanced' for _, m in ref_rows)} en Advanced.",
          f"- **Faithfulness = 0 pour {fz} refus sur {len(ref_rows)}.** Ragas pénalise systématiquement les refus sur cette "
          "métrique.",
          f"- **Answer Relevancy = 0 pour {az} refus sur {len(ref_rows)}.** L'exception est `p-18650` Basic (0,830) : sa "
          "réponse explique ce qu'elle voit (« seules les fiches de chargeurs et de supports sont mentionnées »), et le juge "
          "ne l'a pas jugée évasive.",
          "- **CP et CR varient avec les passages**, et non avec le refus : de 0 à 0,833.",
          "- **Hors refus.** Les réponses `tn-probleme`, qui demandent des précisions, obtiennent aussi F = 0. AR vaut 0 en "
          "Basic et 0,490 en Advanced.", ""]

    # 6. recalcul sans refus
    def block(sel_rows, title):
        out = [f"**{title}**", "", "| Mode | " + " | ".join(f"{NAMES[k]} (n)" for k in METRICS) + " |",
               "| --- | " + " | ".join("---" for _ in METRICS) + " |"]
        for m in ("basic", "advanced"):
            for excl in (False, True):
                cells = []
                for k in METRICS:
                    v, n = mean([r["runs"][m]["ragas"]["scores"].get(k) for r in sel_rows
                                 if not (excl and refus[(r["id"], m)]["refus"])])
                    cells.append(f"{fmt(v)} ({n})")
                out.append(f"| {m}{' sans refus' if excl else ' (publié)'} | " + " | ".join(cells) + " |")
        both = [r for r in sel_rows if not refus[(r["id"], "basic")]["refus"] and not refus[(r["id"], "advanced")]["refus"]]
        for m in ("basic", "advanced"):
            cells = []
            for k in METRICS:
                pairs = [r for r in both if r["runs"]["basic"]["ragas"]["scores"].get(k) is not None
                         and r["runs"]["advanced"]["ragas"]["scores"].get(k) is not None]
                v, n = mean([r["runs"][m]["ragas"]["scores"].get(k) for r in pairs])
                cells.append(f"{fmt(v)} ({n})")
            out.append(f"| {m} apparié, sans refus dans aucun des deux modes | " + " | ".join(cells) + " |")
        return out + [""]
    L += ["## 6. Moyennes recalculées sans les refus (aucun recalcul côté juge)", "",
          "Les scores sont repris tels quels du JSON. Une réponse de refus est retirée de toutes les métriques de son mode. "
          "Les `None` restent exclus, comme pour la Faithfulness Basic de `p-arduino-due`.", ""]
    L += block([r for r in rows if r["lang"] == "tn"], "Tunisien (3 questions)")
    L += block(rows, "Global (22 questions)")
    L += ["**Lecture.**",
          "- **En tunisien**, il ne reste en Basic que `tn-probleme`, à 0 partout. Comme ce n'est pas un refus, la moyenne "
          "Basic reste à 0 avec n = 1. Une moyenne tunisienne sans refus ne repose donc que sur 1 ou 2 réponses.",
          "- **Sur les 16 questions sans refus dans aucun des deux modes**, l'écart Advanced − Basic devient : CP +0,035, "
          "CR −0,036, F −0,040 (n = 15), AR −0,009. **Le gain publié vient donc surtout des 6 refus du mode Basic** : 5 "
          "questions où la recherche Basic ne trouvait pas les bons passages, et que le mode Advanced résout. Sur les questions "
          "déjà bien servies par Basic, Advanced n'apporte pas de gain mesurable.",
          "- **Retirer les refus revient à retirer les cas où la recherche a échoué.** Cela embellit surtout le mode Basic. "
          "C'est une **analyse de sensibilité**, pas une correction : un refus honnête reste le bon comportement quand les "
          "passages manquent.", "",
          "## Limites", "",
          "- **Classement manuel par une seule personne (Claude)**, à partir du texte des réponses. La traduction des passages "
          "en tunisien et en arabe est donnée à titre indicatif.",
          "- **Détails intermédiaires du juge non stockés.** Les affirmations extraites, les verdicts, l'indicateur "
          "`noncommittal` et la distance de chaque passage ne sont pas dans le JSON. Les explications du point 4 reposent sur "
          "le code de ragas 0.4.3 et sur les scores enregistrés.",
          "- **Petit effectif.** 3 questions tunisiennes : aucune conclusion statistique n'est possible.", ""]
    OUT.write_text("\n".join(L), encoding="utf-8")
    h1 = hashlib.sha256(SRC.read_bytes()).hexdigest()
    print("refus :", [(r["id"], m) for r, m in ref_rows])
    print("SHA-256 avant", h0, "après", h1, "identiques", h0 == h1)


if __name__ == "__main__":
    main()
