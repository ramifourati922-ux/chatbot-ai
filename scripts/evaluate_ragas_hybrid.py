"""
RAGas en mode "hybrid" seul (BM25 + dense + RRF, sans reranker), avec le
script existant scripts/evaluate_ragas.py, sans le modifier : mêmes
questions (GOLDEN_SET, 22 notées + 3 hors-sujet), même générateur, même
juge (openai/gpt-oss-20b), mêmes métriques et même traitement des échecs.

Différences, toutes dans ce lanceur :
- PIPELINES = ("hybrid",)
- sorties dans docs/evaluation/mesures/ (ragas_hybrid.json / .md, et
  ragas_hybrid.partial.json en cas d'arrêt : reprise avec --resume)
- réponses HTTP du juge comptées par code (200, 429, autres)
- rapport Markdown propre au mode hybride (celui du script suppose basic/advanced)

    python scripts/evaluate_ragas_hybrid.py            # puis, après un arrêt sur quota :
    python scripts/evaluate_ragas_hybrid.py --resume
"""
import asyncio
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import scripts.evaluate_ragas as er  # noqa: E402

er.PIPELINES = ("hybrid",)
er.OUT_DIR = Path(__file__).parent.parent / "docs" / "evaluation" / "mesures"


class CountingStats(er.CallStats):
    def __init__(self):
        super().__init__()
        self.judge_status = {}

    def load(self, meta):
        super().load(meta)
        self.judge_status = dict(meta.get("judge_status", {}))

    async def on_response(self, response):
        c = Counter(self.judge_status)
        c[str(response.status_code)] += 1
        self.judge_status = dict(c)
        await super().on_response(response)


er.STATS = CountingStats()


def write_markdown(payload, path):
    agg, meta = payload["aggregate"]["hybrid"], payload["meta"]
    lines = ["# RAGas — mode hybrid (BM25 + dense + RRF, sans reranker)", "",
             f"- Date : {meta['date']} ; questions notées : {meta['n_scored']} ; hors-sujet : {meta['n_offtopic']}",
             f"- Générateur `{meta['generator_model']}`, juge `{meta['judge_model']}`",
             f"- Juge : {meta['judge_requests']} requêtes HTTP, codes {meta.get('judge_status')} ; "
             f"génération : {meta['gen_requests']} requêtes dont {meta['gen_429']} × 429 ; durée {meta['duration_min']} min",
             "", "| Métrique | Hybrid |", "|---|---|"]
    for m in er.METRICS:
        lines.append(f"| {m} | {er._fmt(agg[m])} |")
    lines += [f"| hit@4 | {er._fmt(agg['hit_at_4'], True)} |", f"| métriques en échec | {agg['metric_failures']} |",
              f"| hors-sujet escaladés | {agg['offtopic_escalated']}/{agg['offtopic_total']} |", "",
              "| Id | Langue | CP | CR | F | AR | hit@4 | erreurs |", "|---|---|---|---|---|---|---|---|"]
    for r in payload["results"]:
        run = r["runs"]["hybrid"]
        s = run["ragas"]["scores"]
        lines.append(f"| {r['id']} | {r['lang']} | " + " | ".join(er._fmt(s.get(m)) for m in er.METRICS)
                     + f" | {run['hit_at_4']} | {', '.join(run['ragas']['errors']) or '—'} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


er.write_markdown = write_markdown

if __name__ == "__main__":
    sys.argv = [sys.argv[0], "--out", "ragas_hybrid", *sys.argv[1:]]
    asyncio.run(er.main())
