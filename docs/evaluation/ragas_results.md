# Évaluation RAGas — Basic RAG vs Advanced RAG

- Date : 2026-09-27T19:26:16
- Golden set : 22 questions notées + 3 hors-sujet (comportement seulement)
- Générateur : `openai/gpt-oss-120b` — juge : `openai/gpt-oss-20b` — embeddings : `paraphrase-multilingual-MiniLM-L12-v2`
- Advanced : hybride BM25 + dense + RRF (top-20) puis reranking `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` (top-4)
- Appels Groq : juge 802 (dont 403 × 429, 678697 tokens), génération 62 (dont 1 × 429, 58797 tokens) — durée 71.6 min

## Résultats globaux (moyenne sur les questions notées)

| Métrique | Basic RAG | Advanced RAG | Écart |
|---|---|---|---|
| Context Precision | 0.645 | 0.913 | +0.268 |
| Context Recall | 0.599 | 0.800 | +0.202 |
| Faithfulness | 0.532 | 0.689 | +0.156 |
| Answer Relevancy | 0.485 | 0.600 | +0.115 |
| Source attendue dans le top-4 (sans LLM) | 77 % | 95 % | |
| Latence de recherche (médiane) | 177 ms | 1214 ms | |
| Hors-sujet escaladés (seuil de confiance) | 1/3 | 1/3 | |
| Métriques en échec (parsing/API) | 1 | 0 | |

## Par langue

| Langue | Pipeline | Context Precision | Context Recall | Faithfulness | Answer Relevancy |
|---|---|---|---|---|---|
| fr | basic | 0.742 | 0.727 | 0.547 | 0.573 |
| fr | advanced | 1.000 | 0.955 | 0.802 | 0.663 |
| en | basic | 0.646 | 0.375 | 0.708 | 0.497 |
| en | advanced | 1.000 | 0.850 | 0.923 | 0.679 |
| ar | basic | 0.861 | 0.917 | 0.719 | 0.595 |
| ar | advanced | 0.812 | 0.550 | 0.533 | 0.575 |
| tn | basic | 0.000 | 0.000 | 0.000 | 0.000 |
| tn | advanced | 0.611 | 0.500 | 0.167 | 0.296 |

## Détail par question

| Id | Langue | Pipeline | CP | CR | F | AR | hit@4 | Escalade |
|---|---|---|---|---|---|---|---|---|
| p-vl53l0x | fr | basic | 1.000 | 1.000 | 0.800 | 0.650 | oui | non |
| p-vl53l0x | fr | advanced | 1.000 | 1.000 | 0.714 | 0.604 | oui | non |
| p-18650 | fr | basic | 0.500 | 0.000 | 0.000 | 0.830 | non | non |
| p-18650 | fr | advanced | 1.000 | 1.000 | 0.833 | 0.801 | oui | non |
| p-nema17 | fr | basic | 0.000 | 0.000 | 0.000 | 0.000 | non | non |
| p-nema17 | fr | advanced | 1.000 | 0.500 | 0.714 | 0.734 | oui | non |
| p-analyseur | fr | basic | 1.000 | 1.000 | 0.800 | 0.635 | oui | non |
| p-analyseur | fr | advanced | 1.000 | 1.000 | 0.667 | 0.172 | oui | non |
| p-arduino-due | fr | basic | 0.833 | 1.000 | — | 0.792 | oui | non |
| p-arduino-due | fr | advanced | 1.000 | 1.000 | 0.667 | 0.722 | oui | non |
| p-esp32 | fr | basic | 0.000 | 0.000 | 0.000 | 0.000 | non | oui |
| p-esp32 | fr | advanced | 1.000 | 1.000 | 0.857 | 0.829 | oui | non |
| p-12v5a | fr | basic | 1.000 | 1.000 | 0.571 | 0.531 | oui | non |
| p-12v5a | fr | advanced | 1.000 | 1.000 | 0.571 | 0.437 | oui | non |
| p-rpi4 | fr | basic | 1.000 | 1.000 | 0.500 | 0.811 | oui | non |
| p-rpi4 | fr | advanced | 1.000 | 1.000 | 1.000 | 0.869 | oui | non |
| s-retour | fr | basic | 1.000 | 1.000 | 1.000 | 0.814 | oui | non |
| s-retour | fr | advanced | 1.000 | 1.000 | 1.000 | 0.891 | oui | non |
| s-frais | fr | basic | 1.000 | 1.000 | 0.800 | 0.626 | oui | non |
| s-frais | fr | advanced | 1.000 | 1.000 | 0.800 | 0.626 | oui | non |
| s-cash | fr | basic | 0.833 | 1.000 | 1.000 | 0.608 | oui | non |
| s-cash | fr | advanced | 1.000 | 1.000 | 1.000 | 0.605 | oui | non |
| en-warranty | en | basic | 0.000 | 0.000 | 0.000 | 0.000 | non | non |
| en-warranty | en | advanced | 1.000 | 1.000 | 1.000 | 0.744 | oui | non |
| en-shipping | en | basic | 1.000 | 1.000 | 1.000 | 0.609 | oui | non |
| en-shipping | en | advanced | 1.000 | 1.000 | 1.000 | 0.620 | oui | non |
| en-return | en | basic | 0.583 | 0.500 | 1.000 | 0.821 | oui | non |
| en-return | en | advanced | 1.000 | 1.000 | 0.833 | 0.821 | oui | non |
| en-esp32 | en | basic | 1.000 | 0.000 | 0.833 | 0.560 | oui | non |
| en-esp32 | en | advanced | 1.000 | 0.400 | 0.857 | 0.531 | oui | non |
| ar-frais | ar | basic | 1.000 | 1.000 | 0.571 | 0.518 | oui | non |
| ar-frais | ar | advanced | 1.000 | 1.000 | 0.800 | 0.535 | oui | non |
| ar-retour | ar | basic | 1.000 | 1.000 | 0.889 | 0.667 | oui | non |
| ar-retour | ar | advanced | 0.500 | 0.000 | 0.375 | 0.667 | oui | non |
| ar-garantie | ar | basic | 0.639 | 0.667 | 0.667 | 0.548 | oui | non |
| ar-garantie | ar | advanced | 1.000 | 0.200 | 0.333 | 0.452 | oui | non |
| ar-paiement | ar | basic | 0.806 | 1.000 | 0.750 | 0.645 | oui | non |
| ar-paiement | ar | advanced | 0.750 | 1.000 | 0.625 | 0.645 | oui | non |
| tn-garantie | tn | basic | 0.000 | 0.000 | 0.000 | 0.000 | non | non |
| tn-garantie | tn | advanced | 1.000 | 1.000 | 0.500 | 0.398 | oui | non |
| tn-sfax | tn | basic | 0.000 | 0.000 | 0.000 | 0.000 | oui | non |
| tn-sfax | tn | advanced | 0.833 | 0.500 | 0.000 | 0.000 | oui | non |
| off-couscous | fr | basic | — | — | — | — | — | non |
| off-couscous | fr | advanced | — | — | — | — | — | non |
| off-jupiter | fr | basic | — | — | — | — | — | oui |
| off-jupiter | fr | advanced | — | — | — | — | — | oui |
| off-capitale | fr | basic | — | — | — | — | — | non |
| off-capitale | fr | advanced | — | — | — | — | — | non |
| tn-probleme | tn | basic | 0.000 | 0.000 | 0.000 | 0.000 | oui | non |
| tn-probleme | tn | advanced | 0.000 | 0.000 | 0.000 | 0.490 | non | non |
