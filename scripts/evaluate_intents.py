# scripts/evaluate_intents.py
"""
Mesure avant/après des intentions apprises (app/services/semantic_intent.py).

- « avant » : règles seules (intent_classifier), le comportement d'origine ;
- « après » : règles, puis intentions apprises quand aucune règle ne
  tranche (INTENT_MODEL_ENABLED=True).

Métriques par intention : précision (parmi les messages classés X, part
vraiment X), rappel (parmi les vrais X, part reconnue), F1 ; exactitude
globale ; faux transferts (message envoyé à un conseiller à tort) ; temps
ajouté par message.

Deux jeux distincts, et distincts des exemples d'entraînement :
- data/intents/dev.json : calibration des seuils (--calibrate) ;
- data/intents/test.json : mesure finale, jamais utilisé pour régler.

Usage :
    python scripts/evaluate_intents.py --calibrate           # choisit les seuils sur dev.json
    python scripts/evaluate_intents.py                        # mesure sur test.json
    python scripts/evaluate_intents.py --out docs/evaluation/intentions_avant_apres.md
"""

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.services import semantic_intent
from app.services.intent_classifier import IntentClassifier

DATA = Path(__file__).parent.parent / "data" / "intents"
INTENTS = ("human_agent", "frustration", "order_tracking", "help", "general")
ESCALATIONS = semantic_intent.ESCALATION_INTENTS


def load(name: str) -> list:
    return json.loads((DATA / name).read_text(encoding="utf-8"))["messages"]


def rules_intent(classifier: IntentClassifier, text: str) -> str:
    intent = classifier.classify(text).intent
    return intent if intent in INTENTS else ("small_talk" if intent in ("greeting", "thanks", "goodbye") else "general")


def with_model(rule: str, match, similarity: float, escalation: float) -> str:
    """Décision « après » : la règle si elle a tranché, sinon l'intention apprise."""
    if rule != "general":
        return rule
    if match.intent == semantic_intent.NEGATIVE:
        return "general"
    threshold = escalation if match.intent in ESCALATIONS else similarity
    return match.intent if match.score >= threshold else "general"


def metrics(gold: list, pred: list) -> dict:
    per_intent = {}
    for intent in INTENTS:
        tp = sum(g == p == intent for g, p in zip(gold, pred))
        predicted, actual = pred.count(intent), gold.count(intent)
        precision = tp / predicted if predicted else 0.0
        recall = tp / actual if actual else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_intent[intent] = (precision, recall, f1, actual)
    return {
        "accuracy": sum(g == p for g, p in zip(gold, pred)) / len(gold),
        "per_intent": per_intent,
        "false_escalations": [i for i, (g, p) in enumerate(zip(gold, pred)) if p in ESCALATIONS and g != p],
        "missed_escalations": [i for i, (g, p) in enumerate(zip(gold, pred)) if g in ESCALATIONS and p not in ESCALATIONS],
    }


def prepare(messages: list):
    classifier = IntentClassifier()
    semantic_intent.warmup()
    rules, matches, durations = [], [], []
    for m in messages:
        rule = rules_intent(classifier, m["text"])
        rules.append(rule)
        t0 = time.perf_counter()
        matches.append(semantic_intent.nearest(m["text"]))
        if rule == "general":  # le modèle n'est consulté que dans ce cas
            durations.append((time.perf_counter() - t0) * 1000)
    return rules, matches, durations


def calibrate(messages: list) -> None:
    gold = [m["intent"] for m in messages]
    rules, matches, _ = prepare(messages)
    grid = [round(0.40 + 0.02 * i, 2) for i in range(26)]  # 0.40 → 0.90
    results = []
    for similarity in grid:
        for escalation in grid:
            if escalation < similarity:
                continue
            pred = [with_model(r, m, similarity, escalation) for r, m in zip(rules, matches)]
            res = metrics(gold, pred)
            results.append((len(res["false_escalations"]), -res["accuracy"], similarity, escalation, res))
    # Priorité : aucun faux transfert, puis la meilleure exactitude, puis
    # les seuils les plus hauts (les plus prudents) à égalité
    results.sort(key=lambda r: (r[0], r[1], -r[3], -r[2]))
    print("Meilleures combinaisons sur dev.json (faux transferts, exactitude, seuil, seuil transfert) :")
    for false_esc, neg_acc, similarity, escalation, _ in results[:8]:
        print(f"  {false_esc} faux transfert(s) | exactitude {-neg_acc:.3f} | seuil {similarity} | transfert {escalation}")
    print("\nScores bruts (message → exemple le plus proche) :")
    for m, r, match in zip(messages, rules, matches):
        if r == "general":
            print(f"  {m['intent']:14} ← {match.intent:14} {match.score:.3f}  {m['text']}")


def report(messages: list, out: Path | None) -> None:
    gold = [m["intent"] for m in messages]
    rules, matches, durations = prepare(messages)
    similarity, escalation = settings.INTENT_SIMILARITY_THRESHOLD, settings.INTENT_ESCALATION_THRESHOLD
    after = [with_model(r, m, similarity, escalation) for r, m in zip(rules, matches)]
    before_m, after_m = metrics(gold, rules), metrics(gold, after)

    lines = [
        "# Intentions apprises : mesure avant / après",
        "",
        f"Jeu de test : `data/intents/test.json`, {len(messages)} messages "
        f"({', '.join(f'{k} {v}' for k, v in sorted(Counter(gold).items()))}), "
        "jamais utilisé pour régler les seuils ni écrire les exemples.",
        f"Seuils (calibrés sur `data/intents/dev.json`) : similarité {similarity}, transfert {escalation}.",
        "",
        "- **Avant** : règles seules (`intent_classifier.py`).",
        "- **Après** : règles, puis intentions apprises si aucune règle ne tranche (`INTENT_MODEL_ENABLED=True`).",
        "",
        "| Mesure | Avant | Après |",
        "| --- | --- | --- |",
        f"| Exactitude globale | {before_m['accuracy']:.1%} | {after_m['accuracy']:.1%} |",
        f"| Faux transferts vers un conseiller | {len(before_m['false_escalations'])} | {len(after_m['false_escalations'])} |",
        f"| Transferts manqués | {len(before_m['missed_escalations'])} | {len(after_m['missed_escalations'])} |",
    ]
    if durations:
        durations.sort()
        lines.append(f"| Temps ajouté par message sans règle (médiane, CPU) | 0 ms | {durations[len(durations) // 2]:.0f} ms |")
    lines += ["", "| Intention | Messages | Précision avant | Rappel avant | Précision après | Rappel après |",
              "| --- | --- | --- | --- | --- | --- |"]
    for intent in INTENTS:
        pb, rb, _, n = before_m["per_intent"][intent]
        pa, ra, _, _ = after_m["per_intent"][intent]
        lines.append(f"| {intent} | {n} | {pb:.0%} | {rb:.0%} | {pa:.0%} | {ra:.0%} |")
    errors = [(m, b, a) for m, b, a in zip(messages, rules, after) if a != m["intent"]]
    lines += ["", f"Erreurs restantes après ({len(errors)}) :", ""]
    lines += [f"- « {m['text']} » : attendu `{m['intent']}`, obtenu `{a}`" for m, b, a in errors] or ["- aucune"]
    changed = [(m, b, a) for m, b, a in zip(messages, rules, after) if a != b]
    lines += ["", f"Décisions changées par le modèle ({len(changed)}) :", ""]
    lines += [f"- « {m['text']} » : `{b}` → `{a}` (attendu `{m['intent']}`)" for m, b, a in changed] or ["- aucune"]

    lines += [
        "", "## Limites de cette mesure", "",
        "- Petit échantillon (une soixantaine de messages, 10 à 17 par intention) : des tendances, pas des "
        "mesures statistiquement solides.",
        "- Messages écrits pour le projet, pas recueillis auprès de vrais clients ; les exemples, les seuils et "
        "le jeu de test viennent du même auteur.",
        "- La frustration reste mal reconnue (seuil de transfert strict, choisi pour n'envoyer aucune simple "
        "question à un conseiller) ; en arabizi, le modèle d'embeddings confond une panne de produit et une "
        "plainte contre le service.",
        "- Seule l'intention est mesurée ici, pas la qualité de la réponse qui suit.",
    ]
    text = "\n".join(lines) + "\n"
    print(text)
    if out:
        out.write_text(text, encoding="utf-8")
        print(f"Écrit dans {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--calibrate", action="store_true", help="choisir les seuils sur dev.json")
    parser.add_argument("--out", type=Path, help="écrire le rapport Markdown")
    args = parser.parse_args()
    if args.calibrate:
        calibrate(load("dev.json"))
    else:
        report(load("test.json"), args.out)
