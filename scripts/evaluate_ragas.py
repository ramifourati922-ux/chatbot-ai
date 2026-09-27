# scripts/evaluate_ragas.py
"""
Évaluation RAGas avant/après (Advanced RAG, étape 4) : Basic RAG vs
Advanced RAG (hybride BM25 + dense + RRF, puis reranking) sur le même
golden set et le même corpus.

Métriques RAGas (juge = Groq openai/gpt-oss-20b, différent du générateur
gpt-oss-120b ; embeddings = modèle local) :
    - Context Precision : les chunks pertinents sont-ils bien classés en tête ?
    - Context Recall    : le contexte contient-il tout ce qu'il faut pour
                          produire la réponse de référence ?
    - Faithfulness      : la réponse est-elle entièrement appuyée par le contexte ?
    - Answer Relevancy  : la réponse répond-elle à la question posée ?
Plus une métrique sans LLM : source attendue retrouvée dans le top-4 (hit@4).

Golden set : 25 questions reprises des étapes 1-3 (calibrate_threshold.py
et benchmarks du CHANGELOG), 4 langues. Les 3 questions hors-sujet ne
sont pas notées par RAGas (aucun contexte ni réponse de référence) :
on vérifie seulement le comportement (escalade ou refus).

Génération : même prompt que le chatbot (llm_factory.build_messages),
toujours avec le modèle principal (settings.GROQ_MODEL). On n'utilise
PAS llm_factory.ask(), qui bascule silencieusement sur le modèle de
secours en cas de limite de débit : une partie des réponses viendrait
alors d'un autre modèle, ce qui fausserait la comparaison avant/après.

Limites Groq (offre gratuite, gpt-oss-120b) : 1 000 requêtes/jour et
8 000 tokens/minute. Les erreurs 429 sont réessayées avec backoff par
le client (max_retries), en respectant l'en-tête retry-after ; le
script compte les appels et les 429 pour le rapport.

Usage :
    ./venv/Scripts/python.exe scripts/evaluate_ragas.py --limit 2    # mini-test
    ./venv/Scripts/python.exe scripts/evaluate_ragas.py              # golden set complet
Sortie : docs/evaluation/ragas_results.json et ragas_results.md
"""

import argparse
import asyncio
import json
import sys
import time
import types
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# ⚠️ ragas 0.4.3 importe sans condition ChatVertexAI depuis
# langchain_community.chat_models.vertexai, module retiré de
# langchain-community 0.4 (la 0.3, qui l'a encore, exige
# langchain-core < 1.0, incompatible avec le reste du projet). On
# n'utilise pas Vertex AI : un module factice suffit, et il n'existe
# que dans ce script (l'application n'importe jamais ragas).
_vertex = types.ModuleType("langchain_community.chat_models.vertexai")
_vertex.ChatVertexAI = type("ChatVertexAI", (), {})
sys.modules.setdefault("langchain_community.chat_models.vertexai", _vertex)

import httpx  # noqa: E402
from groq import RateLimitError  # noqa: E402
from langchain_groq import ChatGroq  # noqa: E402
from openai import AsyncOpenAI  # noqa: E402
from ragas.embeddings import embedding_factory  # noqa: E402
from ragas.llms import llm_factory  # noqa: E402
from ragas.metrics.collections import (  # noqa: E402
    AnswerRelevancy,
    ContextPrecision,
    ContextRecall,
    Faithfulness,
)

from app.config import settings  # noqa: E402
from app.services.language_detector import detect_language  # noqa: E402
from app.services.rag import hybrid_retriever, reranker, retriever  # noqa: E402
from app.services.rag.embedding_service import embed  # noqa: E402
from app.services.rag.llm_factory import build_messages  # noqa: E402

OUT_DIR = Path(__file__).parent.parent / "docs" / "evaluation"
PIPELINES = ("basic", "advanced")
METRICS = ("context_precision", "context_recall", "faithfulness", "answer_relevancy")
TOP_K = 4  # comme dialogue_manager

# ── Golden set ────────────────────────────────────────────────────────
# reference : réponse attendue, rédigée à partir de la knowledge base
# (en français, langue du corpus : Context Precision/Recall comparent la
# référence aux chunks). sources : fichiers de politique ou SKU produits
# attendus ; une seule suffit pour hit@4.
_ESP32 = [f"LS-CP-0000{n}" for n in (17, 18, 19, 20, 21, 22, 27, 28)]

GOLDEN_SET = [
    # Produits (fr) — calibrate_threshold.py + benchmarks étapes 1-2
    {"id": "p-vl53l0x", "lang": "fr", "category": "produit",
     "question": "Avez-vous un capteur de distance VL53L0X ?",
     "reference": "Oui, le capteur VL53L0X est en stock en trois versions : capteur seul (nu) à 32,98 DT, breakout board à 50,93 DT et module complet à 54,04 DT.",
     "sources": ["LS-CA-000034", "LS-CA-000035", "LS-CA-000036"]},
    {"id": "p-18650", "lang": "fr", "category": "produit",
     "question": "Vous avez des piles 18650 en stock ?",
     "reference": "Oui, les piles/batteries 18650 sont en stock en packs de 4 (9,44 DT), de 10 (23,43 DT) et de 20 (6,32 DT).",
     "sources": ["LS-AL-000031", "LS-AL-000032", "LS-AL-000033"]},
    {"id": "p-nema17", "lang": "fr", "category": "produit",
     "question": "Combien coute un moteur pas-a-pas NEMA17 ?",
     "reference": "Les moteurs pas-à-pas NEMA17 coûtent entre 21,59 DT et 58,09 DT selon la variante (pas de 0,9° ou 1,8°, courant de 1 A à 2,5 A) ; certaines variantes sont en stock, d'autres sur commande.",
     "sources": [f"LS-MR-0000{n}" for n in range(11, 19)]},
    {"id": "p-analyseur", "lang": "fr", "category": "produit",
     "question": "Vous vendez des analyseurs logiques 8 canaux ?",
     "reference": "Oui, l'analyseur logique 8 canaux est en stock à 39,76 DT.",
     "sources": ["LS-IM-000031"]},
    {"id": "p-arduino-due", "lang": "fr", "category": "produit",
     "question": "Est-ce que la carte Arduino Due est disponible ?",
     "reference": "Oui : la version compatible (clone) est en stock à 54,75 DT ; la version originale est disponible sur commande à 88,73 DT.",
     "sources": ["LS-CP-000013", "LS-CP-000014"]},
    {"id": "p-esp32", "lang": "fr", "category": "produit",
     "question": "ESP32 wifi bluetooth",
     "reference": "Plusieurs modules ESP32 (Wi-Fi + Bluetooth) sont proposés, par exemple le Module ESP32 DevKitC en 4MB Flash (41,91 DT) et en 8MB Flash (40,57 DT), tous deux en stock.",
     "sources": _ESP32},
    {"id": "p-12v5a", "lang": "fr", "category": "produit",
     "question": "alimentation 12V 5A",
     "reference": "Le bloc secteur 12V 5A est disponible en stock à 24,73 DT.",
     "sources": ["LS-AL-000060"]},
    {"id": "p-rpi4", "lang": "fr", "category": "produit",
     "question": "Raspberry Pi 4 8GB prix",
     "reference": "Le Raspberry Pi 4 Model B (8Go) coûte 246,64 DT, mais il est actuellement en rupture de stock.",
     "sources": ["LS-CP-000039"]},
    # SAV / e-commerce (fr)
    {"id": "s-retour", "lang": "fr", "category": "sav",
     "question": "Quel est le délai pour retourner un produit ?",
     "reference": "Vous disposez de 7 jours calendaires à partir de la date de réception pour retourner un produit non ouvert et non utilisé.",
     "sources": ["sav/retours.txt"]},
    {"id": "s-frais", "lang": "fr", "category": "sav",
     "question": "Quels sont les frais de livraison ?",
     "reference": "La livraison est gratuite à partir de 150 DT d'achat. En dessous, les frais sont de 8 DT pour le Grand Tunis et de 12 DT pour le reste du pays.",
     "sources": ["sav/livraison.txt"]},
    {"id": "s-cash", "lang": "fr", "category": "sav",
     "question": "Le paiement à la livraison est-il possible ?",
     "reference": "Oui, le paiement à la livraison en espèces est disponible dans toute la Tunisie, sans frais supplémentaire, avec un plafond de 500 DT par commande.",
     "sources": ["ecommerce/paiement.txt"]},
    # Anglais
    {"id": "en-warranty", "lang": "en", "category": "sav",
     "question": "What is the warranty on a multimeter?",
     "reference": "Les instruments de mesure (multimètres, oscilloscopes) sont garantis 12 mois contre tout défaut de fabrication.",
     "sources": ["sav/garantie.txt"]},
    {"id": "en-shipping", "lang": "en", "category": "sav",
     "question": "How much is shipping?",
     "reference": "La livraison est gratuite à partir de 150 DT d'achat. En dessous, les frais sont de 8 DT pour le Grand Tunis et de 12 DT pour le reste du pays.",
     "sources": ["sav/livraison.txt"]},
    {"id": "en-return", "lang": "en", "category": "sav",
     "question": "Can I return a product?",
     "reference": "Oui, sous 7 jours calendaires après réception, si le produit n'est ni ouvert ni utilisé. Les composants électroniques déballés ne sont pas repris sauf défaut de fabrication.",
     "sources": ["sav/retours.txt"]},
    {"id": "en-esp32", "lang": "en", "category": "produit",
     "question": "Do you sell ESP32 boards?",
     "reference": "Oui, plusieurs modules ESP32 sont vendus : DevKitC (4MB à 41,91 DT, 8MB à 40,57 DT), ESP32-S3, ESP32-C3 et ESP32-CAM.",
     "sources": _ESP32},
    # Arabe
    {"id": "ar-frais", "lang": "ar", "category": "sav",
     "question": "كم تكلفة التوصيل",
     "reference": "La livraison est gratuite à partir de 150 DT d'achat. En dessous, les frais sont de 8 DT pour le Grand Tunis et de 12 DT pour le reste du pays.",
     "sources": ["sav/livraison.txt"]},
    {"id": "ar-retour", "lang": "ar", "category": "sav",
     "question": "هل يمكنني إرجاع المنتج",
     "reference": "Oui, sous 7 jours calendaires après réception, si le produit n'est ni ouvert ni utilisé.",
     "sources": ["sav/retours.txt"]},
    {"id": "ar-garantie", "lang": "ar", "category": "sav",
     "question": "ما هي مدة الضمان",
     "reference": "La garantie dépend du produit : 6 mois pour les cartes programmables et l'outillage, 3 mois pour les modules et capteurs, 12 mois pour les instruments de mesure, contre tout défaut de fabrication.",
     "sources": ["sav/garantie.txt"]},
    {"id": "ar-paiement", "lang": "ar", "category": "sav",
     "question": "ما هي طرق الدفع المتاحة",
     "reference": "Les moyens de paiement acceptés sont la carte bancaire (Visa/Mastercard) en ligne, le paiement à la livraison en espèces, D17 et Flouci.",
     "sources": ["ecommerce/paiement.txt"]},
    # Tunisien (arabizi)
    {"id": "tn-garantie", "lang": "tn", "category": "sav",
     "question": "chnowa el garantie mta3 el multimetre",
     "reference": "Les instruments de mesure comme les multimètres sont garantis 12 mois contre tout défaut de fabrication.",
     "sources": ["sav/garantie.txt"]},
    {"id": "tn-sfax", "lang": "tn", "category": "sav",
     "question": "9adeh el livraison l sfax",
     "reference": "Oui, Liss Strike livre à Sfax. Hors Grand Tunis, les frais sont de 12 DT (gratuit à partir de 150 DT d'achat) et le délai est de 3 à 6 jours ouvrés.",
     "sources": ["sav/livraison.txt"]},
    {"id": "tn-probleme", "lang": "tn", "category": "sav",
     "question": "3andi mochkla fil livraison",
     "reference": "Si le produit est arrivé cassé ou défectueux, prenez une photo du produit et de l'emballage et contactez Liss Strike sous 48h via le chat ou à contact@lissstrike.tn avec le numéro de commande ; un remplacement ou un remboursement sera proposé.",
     "sources": ["sav/reclamations.txt", "sav/livraison.txt"]},
    # Hors-sujet : pas de note RAGas, comportement seulement
    {"id": "off-couscous", "lang": "fr", "category": "hors-sujet",
     "question": "Quelle est la recette du couscous tunisien ?", "reference": None, "sources": []},
    {"id": "off-jupiter", "lang": "fr", "category": "hors-sujet",
     "question": "Combien de lunes a la planete Jupiter ?", "reference": None, "sources": []},
    {"id": "off-capitale", "lang": "fr", "category": "hors-sujet",
     "question": "Quelle est la capitale de la France ?", "reference": None, "sources": []},
]


# ── Suivi des appels Groq (juge) ─────────────────────────────────────
class CallStats:
    def __init__(self):
        self.judge_requests = 0
        self.judge_429 = 0
        self.judge_tokens = 0
        self.gen_requests = 0
        self.gen_429 = 0
        self.gen_tokens = 0

    def load(self, meta: dict):
        """Reprise : repart des compteurs cumulés du checkpoint."""
        for k in vars(self):
            setattr(self, k, meta.get(k, 0))

    async def on_response(self, response: httpx.Response):
        self.judge_requests += 1
        if response.status_code == 429:
            self.judge_429 += 1
        elif response.status_code == 200:
            await response.aread()
            self.judge_tokens += response.json().get("usage", {}).get("total_tokens", 0)


class QuotaExhausted(Exception):
    """Quota journalier de tokens Groq (TPD) atteint : inutile d'insister."""


def _is_daily_quota(error: Exception) -> bool:
    return "tokens per day" in str(error)


STATS = CallStats()


def _judge(model: str):
    client = AsyncOpenAI(
        api_key=settings.GROQ_API_KEY,
        base_url="https://api.groq.com/openai/v1",
        max_retries=10,  # backoff exponentiel, respecte retry-after sur les 429
        timeout=120,
        http_client=httpx.AsyncClient(event_hooks={"response": [STATS.on_response]}, timeout=120),
    )
    # max_tokens relevé : gpt-oss raisonne avant de répondre, 1 024 tokens
    # (défaut ragas) tronquent la sortie structurée.
    return llm_factory(model, provider="openai", client=client, temperature=0.0, max_tokens=4096)


_generator = None


def _generate(question: str, language: str, context: str) -> str:
    """Même prompt que le chatbot, modèle principal uniquement, 429 réessayés."""
    global _generator
    if _generator is None:
        _generator = ChatGroq(api_key=settings.GROQ_API_KEY, model=settings.GROQ_MODEL,
                              temperature=0.3, max_tokens=1024, max_retries=0)
    delay = 5
    for _ in range(10):
        STATS.gen_requests += 1
        try:
            msg = _generator.invoke(build_messages(question, language, context))
            STATS.gen_tokens += (msg.usage_metadata or {}).get("total_tokens", 0)
            return msg.content
        except RateLimitError as e:
            STATS.gen_429 += 1
            if _is_daily_quota(e):
                raise QuotaExhausted(str(e)) from e
            time.sleep(delay)
            delay = min(delay * 2, 60)
    raise RuntimeError("génération : trop d'erreurs 429")


def _source_of(hit: dict) -> str:
    return hit["metadata"].get("source") or hit["metadata"].get("sku")


def run_pipeline(item: dict, mode: str) -> dict:
    settings.RAG_RETRIEVAL_MODE = mode
    t0 = time.perf_counter()
    hits = retriever.search(item["question"], TOP_K)
    retrieval_ms = (time.perf_counter() - t0) * 1000
    language = detect_language(item["question"])
    contexts = [h["document"] for h in hits]
    answer = _generate(item["question"], language, retriever.format_context(hits))
    sources = [_source_of(h) for h in hits]
    confidence = retriever.get_best_confidence(hits)
    return {
        "language_detected": language,
        "retrieval_ms": round(retrieval_ms),
        "contexts": contexts,
        "retrieved_sources": sources,
        "hit_at_4": bool(set(sources) & set(item["sources"])) if item["sources"] else None,
        "confidence": round(confidence, 3),
        # Ce que ferait réellement le chatbot (escalade low_rag_confidence)
        "would_escalate": confidence < retriever.get_confidence_threshold(hits),
        "answer": answer,
    }


async def score(metrics: dict, item: dict, run: dict) -> dict:
    q, ref, ctx, ans = item["question"], item["reference"], run["contexts"], run["answer"]
    calls = {
        "context_precision": lambda: metrics["context_precision"].ascore(user_input=q, reference=ref, retrieved_contexts=ctx),
        "context_recall": lambda: metrics["context_recall"].ascore(user_input=q, retrieved_contexts=ctx, reference=ref),
        "faithfulness": lambda: metrics["faithfulness"].ascore(user_input=q, response=ans, retrieved_contexts=ctx),
        "answer_relevancy": lambda: metrics["answer_relevancy"].ascore(user_input=q, response=ans),
    }
    out, errors = {}, {}
    for name, call in calls.items():
        if not ctx and name != "answer_relevancy":
            out[name] = 0.0  # aucun contexte retrouvé
            continue
        try:
            for attempt in range(3):
                try:
                    out[name] = round(float((await call()).value), 4)
                    break
                except Exception as e:
                    # gpt-oss-20b renvoie parfois une sortie vide refusée par
                    # Groq (json_validate_failed) : erreur ponctuelle, on réessaie.
                    if "json_validate_failed" not in str(e) or attempt == 2:
                        raise
        except Exception as e:  # un échec de parsing ne doit pas arrêter toute l'évaluation
            if _is_daily_quota(e):
                raise QuotaExhausted(str(e)) from e
            out[name] = None
            errors[name] = f"{type(e).__name__}: {str(e)[:300]}"
    return {"scores": out, "errors": errors}


def _mean(values):
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), 4) if values else None


def aggregate(results: list) -> dict:
    agg = {}
    for mode in PIPELINES:
        rows = [r for r in results if r["category"] != "hors-sujet"]
        by = lambda f: [f(r["runs"][mode]) for r in rows]  # noqa: E731
        agg[mode] = {m: _mean(by(lambda run, m=m: run["ragas"]["scores"].get(m))) for m in METRICS}
        agg[mode]["hit_at_4"] = _mean(by(lambda run: 1.0 if run["hit_at_4"] else 0.0))
        agg[mode]["retrieval_ms_median"] = sorted(by(lambda run: run["retrieval_ms"]))[len(rows) // 2] if rows else None
        agg[mode]["metric_failures"] = sum(len(run["ragas"]["errors"]) for run in by(lambda run: run))
        for lang in ("fr", "en", "ar", "tn"):
            lrows = [r for r in rows if r["lang"] == lang]
            if lrows:
                agg[mode][f"lang_{lang}"] = {
                    m: _mean([r["runs"][mode]["ragas"]["scores"].get(m) for r in lrows]) for m in METRICS
                }
        off = [r for r in results if r["category"] == "hors-sujet"]
        agg[mode]["offtopic_escalated"] = sum(r["runs"][mode]["would_escalate"] for r in off)
        agg[mode]["offtopic_total"] = len(off)
    return agg


def _fmt(v, pct=False):
    if v is None:
        return "—"
    return f"{v * 100:.0f} %" if pct else f"{v:.3f}"


def write_markdown(payload: dict, path: Path):
    agg, meta = payload["aggregate"], payload["meta"]
    b, a = agg["basic"], agg["advanced"]
    names = {"context_precision": "Context Precision", "context_recall": "Context Recall",
             "faithfulness": "Faithfulness", "answer_relevancy": "Answer Relevancy"}
    lines = [
        "# Évaluation RAGas — Basic RAG vs Advanced RAG", "",
        f"- Date : {meta['date']}",
        f"- Golden set : {meta['n_scored']} questions notées + {meta['n_offtopic']} hors-sujet (comportement seulement)",
        f"- Générateur : `{meta['generator_model']}` — juge : `{meta['judge_model']}` — embeddings : `{meta['embedding_model']}`",
        f"- Advanced : hybride BM25 + dense + RRF (top-{meta['rerank_candidates']}) puis reranking `{meta['reranker_model']}` (top-{TOP_K})",
        f"- Appels Groq : juge {meta['judge_requests']} (dont {meta['judge_429']} × 429, {meta['judge_tokens']} tokens), "
        f"génération {meta['gen_requests']} (dont {meta['gen_429']} × 429, {meta['gen_tokens']} tokens) — durée {meta['duration_min']} min",
        "",
        "## Résultats globaux (moyenne sur les questions notées)", "",
        "| Métrique | Basic RAG | Advanced RAG | Écart |",
        "|---|---|---|---|",
    ]
    for m in METRICS:
        delta = None if b[m] is None or a[m] is None else a[m] - b[m]
        lines.append(f"| {names[m]} | {_fmt(b[m])} | {_fmt(a[m])} | {'—' if delta is None else f'{delta:+.3f}'} |")
    lines += [
        f"| Source attendue dans le top-4 (sans LLM) | {_fmt(b['hit_at_4'], True)} | {_fmt(a['hit_at_4'], True)} | |",
        f"| Latence de recherche (médiane) | {b['retrieval_ms_median']} ms | {a['retrieval_ms_median']} ms | |",
        f"| Hors-sujet escaladés (seuil de confiance) | {b['offtopic_escalated']}/{b['offtopic_total']} | {a['offtopic_escalated']}/{a['offtopic_total']} | |",
        f"| Métriques en échec (parsing/API) | {b['metric_failures']} | {a['metric_failures']} | |",
        "", "## Par langue", "",
        "| Langue | Pipeline | " + " | ".join(names[m] for m in METRICS) + " |",
        "|---|---|" + "---|" * len(METRICS),
    ]
    for lang in ("fr", "en", "ar", "tn"):
        for mode in PIPELINES:
            row = agg[mode].get(f"lang_{lang}")
            if row:
                lines.append(f"| {lang} | {mode} | " + " | ".join(_fmt(row[m]) for m in METRICS) + " |")
    lines += ["", "## Détail par question", "",
              "| Id | Langue | Pipeline | CP | CR | F | AR | hit@4 | Escalade |",
              "|---|---|---|---|---|---|---|---|---|"]
    for r in payload["results"]:
        for mode in PIPELINES:
            run = r["runs"][mode]
            s = run["ragas"]["scores"]
            hit = "—" if run["hit_at_4"] is None else ("oui" if run["hit_at_4"] else "non")
            lines.append(f"| {r['id']} | {r['lang']} | {mode} | " + " | ".join(_fmt(s.get(m)) for m in METRICS)
                         + f" | {hit} | {'oui' if run['would_escalate'] else 'non'} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, help="ne traiter que les N premières questions notées (mini-test)")
    # Juge ≠ générateur : quota Groq séparé (200k tokens/jour par modèle)
    # et pas de biais d'auto-évaluation du modèle qui a produit la réponse.
    parser.add_argument("--judge-model", default="openai/gpt-oss-20b")
    parser.add_argument("--out", default="ragas_results", help="nom de base des fichiers de sortie")
    parser.add_argument("--resume", action="store_true",
                        help="reprendre depuis le checkpoint <out>.partial.json (questions déjà notées sautées)")
    parser.add_argument("--ids", nargs="+",
                        help="ne traiter que ces questions (ex: les hors-sujet, qui n'utilisent pas le juge, "
                             "pendant que le quota du juge est épuisé)")
    args = parser.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    checkpoint = OUT_DIR / f"{args.out}.partial.json"

    items = GOLDEN_SET
    if args.limit:
        items = [i for i in GOLDEN_SET if i["category"] != "hors-sujet"][:args.limit]
    if args.ids:
        unknown = set(args.ids) - {i["id"] for i in GOLDEN_SET}
        if unknown:
            sys.exit(f"Ids inconnus : {sorted(unknown)}")
        items = [i for i in GOLDEN_SET if i["id"] in args.ids]

    judge = _judge(args.judge_model)
    embeddings = embedding_factory("huggingface", f"sentence-transformers/{settings.EMBEDDING_MODEL}")
    metrics = {
        "context_precision": ContextPrecision(llm=judge),
        "context_recall": ContextRecall(llm=judge),
        "faithfulness": Faithfulness(llm=judge),
        # strictness=1 : 1 question générée au lieu de 3 (économise le quota Groq)
        "answer_relevancy": AnswerRelevancy(llm=judge, embeddings=embeddings, strictness=1),
    }

    # Préchargement (comme le lifespan de l'API) : sinon la 1re recherche
    # mesurée paie le chargement des modèles.
    embed("warmup")
    hybrid_retriever._get_index()
    reranker.warmup()
    t_start = time.time()
    results, elapsed_before = [], 0.0
    if args.resume and checkpoint.exists():
        saved = json.loads(checkpoint.read_text(encoding="utf-8"))
        if saved["meta"]["judge_model"] != args.judge_model:
            sys.exit(f"Checkpoint noté avec le juge {saved['meta']['judge_model']}, pas {args.judge_model} : "
                     "mélanger deux juges fausserait la comparaison.")
        results = saved["results"]
        STATS.load(saved["meta"])
        elapsed_before = saved["meta"]["duration_min"]
        print(f"↻ Reprise : {len(results)} questions déjà notées")
    done = {r["id"] for r in results}

    def meta():
        return {
            "date": datetime.now().isoformat(timespec="seconds"),
            "n_scored": sum(r["category"] != "hors-sujet" for r in results),
            "n_offtopic": sum(r["category"] == "hors-sujet" for r in results),
            "generator_model": settings.GROQ_MODEL,
            "judge_model": args.judge_model,
            "embedding_model": settings.EMBEDDING_MODEL,
            "reranker_model": settings.RERANKER_MODEL,
            "rerank_candidates": settings.RERANK_CANDIDATES,
            "confidence_signal": settings.RAG_CONFIDENCE_SIGNAL,
            **vars(STATS),
            "duration_min": round(elapsed_before + (time.time() - t_start) / 60, 1),
        }

    def save_checkpoint():
        checkpoint.write_text(json.dumps({"meta": meta(), "results": results}, ensure_ascii=False, indent=2),
                              encoding="utf-8")

    for n, item in enumerate(items, 1):
        if item["id"] in done:
            continue
        row = {k: item[k] for k in ("id", "lang", "category", "question", "reference", "sources")}
        row["runs"] = {}
        try:
            for mode in PIPELINES:
                run = run_pipeline(item, mode)
                if item["category"] == "hors-sujet":
                    run["ragas"] = {"scores": {}, "errors": {}}
                else:
                    run["ragas"] = await score(metrics, item, run)
                row["runs"][mode] = run
                _print_progress(n, len(items), item, mode, run, t_start)
        except QuotaExhausted as e:
            # Question en cours abandonnée entière : pas de basic et
            # d'advanced notés sur des fenêtres de quota différentes.
            save_checkpoint()
            sys.exit(f"\n⛔ Quota journalier Groq atteint pendant '{item['id']}' ({str(e)[:200]})\n"
                     f"   {len(results)}/{len(items)} questions sauvegardées dans {checkpoint}\n"
                     f"   Relancer plus tard avec --resume.")
        results.append(row)
        save_checkpoint()

    if args.ids and {i["id"] for i in GOLDEN_SET} - {r["id"] for r in results}:
        # Sous-ensemble traité mais golden set incomplet : on garde le
        # checkpoint pour la suite, pas de rapport final partiel.
        missing = [i["id"] for i in GOLDEN_SET if i["id"] not in {r["id"] for r in results}]
        print(f"\n↳ Checkpoint mis à jour ({len(results)}/{len(GOLDEN_SET)}). Reste : {missing}")
        return

    payload = {"meta": meta(), "results": results}
    payload["aggregate"] = aggregate(results)
    (OUT_DIR / f"{args.out}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(payload, OUT_DIR / f"{args.out}.md")
    checkpoint.unlink(missing_ok=True)
    print(f"\n✅ {OUT_DIR / (args.out + '.json')}\n✅ {OUT_DIR / (args.out + '.md')}")
    print(json.dumps(payload["aggregate"], ensure_ascii=False, indent=2))


def _print_progress(n, total, item, mode, run, t_start):
    s = run["ragas"]["scores"]
    print(f"[{n}/{total}] {item['id']:14s} {mode:8s} "
          + " ".join(f"{m[:4]}={_fmt(s.get(m))}" for m in METRICS)
          + f" hit={run['hit_at_4']} esc={run['would_escalate']} "
          + (f"ERREURS={run['ragas']['errors']}" if run["ragas"]["errors"] else "")
          + f" | juge {STATS.judge_requests} req ({STATS.judge_429}x429) {STATS.judge_tokens} tok"
          + f" | génération {STATS.gen_tokens} tok ({(time.time() - t_start) / 60:.1f} min)",
          flush=True)

if __name__ == "__main__":
    asyncio.run(main())
