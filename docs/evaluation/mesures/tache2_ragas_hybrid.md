# Tâche 2 : RAGas en mode hybrid (BM25 + dense + RRF, sans reranker)

## État : PARTIEL, 17 questions sur 22
- **Lancement :** `scripts/evaluate_ragas_hybrid.py`, un lanceur de `scripts/evaluate_ragas.py` qui ne modifie pas ce script. Il reprend les mêmes questions, le même générateur `openai/gpt-oss-120b`, le même juge `openai/gpt-oss-20b`, les mêmes métriques et le même traitement des échecs. Seul le mode change : `hybrid`.
- **Date :** 24/11/2026, de 23:20 à 23:45 (durée mesurée : 24,1 min).
- **Arrêt :** pendant la question `ar-garantie`, Groq a renvoyé « Rate limit reached for model `openai/gpt-oss-20b` … on tokens per day (TPD) ». C'est le quota journalier de tokens du juge.
- **Questions notées :** 17. Elles sont sauvegardées dans `ragas_hybrid.partial.json`.
- **Non traitées :**
  - ar-garantie, ar-paiement ;
  - tn-garantie, tn-sfax, tn-probleme ;
  - les 3 hors-sujet (off-couscous, off-jupiter, off-capitale).
- **Pour compléter, après la remise à zéro du quota :** `venv/Scripts/python.exe scripts/evaluate_ragas_hybrid.py --resume`.
- **Le chiffre sur 22 questions n'existe donc pas encore.** Ce fichier n'en donne aucun.

## Appels Groq
| | Requêtes HTTP | 200 | 429 | Autres |
| --- | --- | --- | --- | --- |
| Juge (gpt-oss-20b) | 291 | 143 | 145 | 3 × 400 |
| Génération (gpt-oss-120b) | 18 | 18 | 0 | 0 |

- **Tokens :** 257 698 pour le juge, 17 563 pour la génération.
- **Scores obtenus :** 68 sur 68 (17 questions × 4 métriques), aucun en échec.

**Traitement des échecs,** tel que le code le fait (`scripts/evaluate_ragas.py`) :
- **429 du juge :** le client réessaie jusqu'à 10 fois, avec un délai croissant et en respectant l'en-tête `retry-after` (`max_retries=10`, ligne 233).
- **400 `json_validate_failed`** (sortie vide de gpt-oss-20b) : l'appel est relancé jusqu'à 3 fois (lignes 308-316).
- **Échec persistant :** la métrique est notée `None`, exclue de la moyenne et comptée dans `metric_failures`. Aujourd'hui, il y en a eu 0.
- **Quota journalier :** le script s'arrête net et sauvegarde un point de reprise. La question en cours est abandonnée entière (lignes 491-497).
- **429 de la génération :** relance après une attente de 5 s, puis 10, 20… jusqu'à 60 s, 10 fois au plus (lignes 245-264). Il n'y en a eu aucun.

## Comparaison sur les MÊMES 17 questions
Basic et Advanced viennent de `docs/evaluation/ragas_results.json` (27/09/2026), restreints à ces 17 questions. Hybrid a été mesuré aujourd'hui. Fichier : `ragas_comparaison_17.json`.

| Métrique | Basic | Hybrid | Advanced |
| --- | --- | --- | --- |
| Context Precision | 0,750 | 0,861 | 0,971 |
| Context Recall | 0,676 | 0,794 | 0,877 |
| Faithfulness | 0,610 (16 notes) | 0,848 | 0,805 |
| Answer Relevancy | 0,557 | 0,685 | 0,659 |
| Source attendue dans le top-4 (hit@4) | 76,5 % | 94,1 % | 100 % |
| Latence de recherche (médiane) | 171 ms | 149 ms | 1104 ms |
| Métriques en échec | 1 | 0 | 0 |

Pour mémoire, Basic et Advanced sur les 22 questions (27/09) :

| Métrique | Basic | Advanced |
| --- | --- | --- |
| Context Precision | 0,645 | 0,913 |
| Context Recall | 0,599 | 0,800 |
| Faithfulness | 0,533 | 0,689 |
| Answer Relevancy | 0,485 | 0,600 |

## Limites
1. **17 questions sur 22, et la sélection est biaisée.** Il manque les 3 questions en tunisien et 2 des 4 questions en arabe, qui sont les plus difficiles : le tunisien valait 0 en Basic sur les 22. Les moyennes sur 17 sont donc **plus hautes** que sur 22, pour tous les modes.
2. **Dates différentes.** Hybrid a été mesuré le 24/11 avec le code actuel ; Basic et Advanced le 27/09. Entre les deux, la génération et le code ont pu changer : l'expansion de l'arabizi, par exemple, ne touche pas ces 17 questions. L'écart Hybrid vs Advanced en Faithfulness et en Answer Relevancy (+0,04 et +0,03) est de l'ordre de la variabilité de la génération : il **ne permet pas** de dire que Hybrid est meilleur sur ces deux métriques.
3. **Une seule exécution**, avec un seul juge LLM, non validé contre des annotations humaines (tâche 1 non faite).
