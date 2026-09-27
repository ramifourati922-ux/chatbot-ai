# Évaluation RAGas — Basic RAG vs Advanced RAG

- Date : 2026-09-25T15:02:14
- Golden set : 2 questions notées + 0 hors-sujet (comportement seulement)
- Générateur : `openai/gpt-oss-120b` — juge : `openai/gpt-oss-120b` — embeddings : `paraphrase-multilingual-MiniLM-L12-v2`
- Advanced : hybride BM25 + dense + RRF (top-20) puis reranking `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` (top-4)
- Appels Groq : juge 49 (dont 17 × 429), génération 5 (dont 1 × 429) — durée 6.9 min

## Résultats globaux (moyenne sur les questions notées)

| Métrique | Basic RAG | Advanced RAG | Écart |
|---|---|---|---|
| Context Precision | 0.500 | 1.000 | +0.500 |
| Context Recall | 0.500 | 1.000 | +0.500 |
| Faithfulness | 0.400 | 0.717 | +0.317 |
| Answer Relevancy | 0.387 | 0.757 | +0.371 |
| Source attendue dans le top-4 (sans LLM) | 50 % | 100 % | |
| Latence de recherche (médiane) | 3066 ms | 2006 ms | |
| Hors-sujet escaladés (seuil de confiance) | 0/0 | 0/0 | |
| Métriques en échec (parsing/API) | 0 | 0 | |

## Par langue

| Langue | Pipeline | Context Precision | Context Recall | Faithfulness | Answer Relevancy |
|---|---|---|---|---|---|
| fr | basic | 0.500 | 0.500 | 0.400 | 0.387 |
| fr | advanced | 1.000 | 1.000 | 0.717 | 0.757 |

## Détail par question

| Id | Langue | Pipeline | CP | CR | F | AR | hit@4 | Escalade |
|---|---|---|---|---|---|---|---|---|
| p-vl53l0x | fr | basic | 1.000 | 1.000 | 0.800 | 0.773 | oui | non |
| p-vl53l0x | fr | advanced | 1.000 | 1.000 | 0.600 | 0.727 | oui | non |
| p-18650 | fr | basic | 0.000 | 0.000 | 0.000 | 0.000 | non | non |
| p-18650 | fr | advanced | 1.000 | 1.000 | 0.833 | 0.788 | oui | non |
