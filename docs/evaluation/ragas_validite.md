# Validité des moyennes Ragas face aux erreurs 429 du juge (remarque 51)

Analyse du 24/11/2026 par `scripts/analyze_ragas_validite.py`. Résultats : `data/evaluation/ragas_validite.json`.
- **Lecture seule.** `docs/evaluation/ragas_results.json` n'est que lu : son empreinte SHA-256 `ead14058…6a2b63` est identique avant et après.
- **Aucun recalcul.** Ragas n'a pas été relancé et Groq n'a pas été appelé. Le code applicatif n'est pas modifié.

## Réponse courte

- **Ce que compte le « 403 sur 802 ».** Ce sont des **réponses HTTP** du juge (`gpt-oss-20b`), **relances comprises**, et non des échecs définitifs. Chaque appel refusé en 429 a été relancé automatiquement, jusqu'à 10 fois, par le client du juge.
- **Aucune métrique n'a échoué sur une 429.** Le JSON enregistre une seule erreur finale : une **erreur 400** (JSON invalide renvoyé par le juge).
- **Les moyennes reposent sur 175 scores sur 176** (22 questions × 4 métriques × 2 modes). Tout est complet, sauf la **Faithfulness du mode Basic : 21 sur 22**, car la question `p-arduino-due` (fr) n'a pas de score.
- **Les valeurs du rapport sont exactes.** Sur les questions appariées, elles ne changent qu'au millième. Le sens et l'ordre de grandeur des gains sont inchangés.
- **Une erreur dans le tableau par langue.** Pour la Faithfulness en français, il compare une moyenne Basic sur 10 questions à une moyenne Advanced sur 11. Appariée, la valeur Advanced est **0,816**, et non 0,802.

## 1. Origine du « 403 sur 802 »

- **Où.** `docs/evaluation/ragas_results.json`, lignes 12-13 : `"judge_requests": 802`, `"judge_429": 403`.
- **Repris dans :** `CHANGELOG_ADVANCED_RAG.md:365` (« 802 requêtes au juge (dont 403 refusées en 429 et réessayées) ») et dans le rapport v5 (`06e-Chapitre6.tex:62`).
- **Comment le chiffre est compté** (`scripts/evaluate_ragas.py:209-215`) :

  ```python
      async def on_response(self, response: httpx.Response):
          self.judge_requests += 1
          if response.status_code == 429:
              self.judge_429 += 1
          elif response.status_code == 200:
              await response.aread()
              self.judge_tokens += response.json().get("usage", {}).get("total_tokens", 0)
  ```

  C'est un crochet httpx (`event_hooks={"response": ...}`, ligne 235) **appelé à chaque réponse HTTP**. Les relances du client OpenAI produisent de nouvelles requêtes, donc **chaque tentative est comptée**. Ainsi, **403 = nombre de réponses 429**, y compris celles qui ont ensuite réussi après relance.
- **Ce que le compteur ne distingue pas.** Il ne sépare pas « 429 puis succès » de « 429 définitif ». On peut cependant le **déduire** des erreurs enregistrées (section 3) : aucune métrique n'a fini en erreur 429.
- **Ce que couvrent les 802 appels.**
  - **Seulement le juge.** La génération a son propre compteur : `gen_requests` 62, `gen_429` 1.
  - **Cumul sur plusieurs reprises.** `STATS.load` (l. 204-207) reprend les compteurs du checkpoint lors d'un `--resume`. Les 802 couvrent donc les 3 jours de calcul.
  - **Appels sans score conservé.** Ils incluent aussi les appels faits pour une question **abandonnée** quand le quota journalier a été atteint : la question était refaite entièrement à la reprise (l. 491-497). Le nombre de ces appels n'est **pas mesurable** à partir des fichiers.

## 2. Relances et comportement en cas d'échec (`scripts/evaluate_ragas.py`)

| Point | Valeur et lignes |
| --- | --- |
| `RunConfig` de Ragas | **Non utilisé.** Les métriques sont appelées directement par `metric.ascore(...)` (l. 296-301) |
| Relances des 429 | Client `AsyncOpenAI` du juge (l. 229-238) : `max_retries=10` (« backoff exponentiel, respecte retry-after sur les 429 »), `timeout=120` |
| `max_workers`, pause entre questions | Aucune : les métriques sont calculées l'une après l'autre (boucle l. 303-321), et les questions aussi (l. 477-499) |
| Relance d'un échec de parsing | 3 essais seulement si l'erreur contient `json_validate_failed` (l. 308-316) ; toute autre erreur est remontée tout de suite |
| Métrique en échec | `out[name] = None`, et l'erreur est gardée dans `errors[name]` (l. 320-321). **Ni 0 ni NaN** ; la question n'est pas exclue des autres métriques |
| Aucun contexte retrouvé | Score fixé à `0.0` pour les 3 métriques qui en ont besoin (l. 304-305). Ce cas n'apparaît dans aucun résultat (voir 3) |
| Quota journalier (« tokens per day ») | `QuotaExhausted` : la question en cours est abandonnée **entière**, dans les deux modes, puis le checkpoint est sauvegardé et le script s'arrête (l. 318-319, 491-497) |
| `--resume` | Recharge `<out>.partial.json`, refuse un autre juge (l. 447-452), et saute les questions déjà notées (`done`, l. 456 et 478). Une question est soit entièrement notée, soit entièrement refaite |
| Moyennes | `_mean` ignore les `None` (l. 325-327) : chaque moyenne porte sur les seuls scores obtenus |

## 3. Scores valides et manquants (22 questions notées ; 3 questions hors sujet sans score)

| Métrique | Basic : valides / manquants | Advanced : valides / manquants |
| --- | --- | --- |
| Context Precision | 22 / 0 | 22 / 0 |
| Context Recall | 22 / 0 | 22 / 0 |
| Faithfulness | **21 / 1** | 22 / 0 |
| Answer Relevancy | 22 / 0 | 22 / 0 |
| **Total** | 87 / 1 | 88 / 0 |

- **Le seul manquant :** `p-arduino-due` (fr), Faithfulness, mode Basic. L'erreur enregistrée est : `BadRequestError: Error code: 400 - … "Failed to validate JSON. Please adjust your prompt. See 'failed_generation' …"`.
- **Ce n'est pas la même question dans les deux modes :** en Advanced, cette question a bien son score.
- **Aucun score n'a été mis à 0 faute de contexte**, dans les deux modes.
- **Le champ `metric_failures`** de l'agrégat vaut 1 en Basic et 0 en Advanced.

**Autre fichier :** `docs/evaluation/ragas_minitest.json` (25/09/2026). C'est un essai sur 2 questions, avec un autre juge (`gpt-oss-120b`) : 49 appels, 17 réponses 429, et tous les scores obtenus (16 sur 16). Il ne sert pas au tableau 6.1.

## 4. Moyennes recalculées (tableau 6.1)

| Métrique | (a) Publié : Basic / Advanced | n Basic / Advanced | (b) Apparié : Basic / Advanced (n) | Rapport | Écart (a) − rapport | Gain (a) → gain (b) |
| --- | --- | --- | --- | --- | --- | --- |
| Context Precision | 0,6452 / 0,9129 | 22 / 22 | 0,6452 / 0,9129 (22) | 0,645 / 0,913 | +0,0002 / −0,0001 | +0,268 → +0,268 |
| Context Recall | 0,5985 / 0,8000 | 22 / 22 | 0,5985 / 0,8000 (22) | 0,599 / 0,800 | −0,0005 / 0 | +0,202 → +0,202 |
| Faithfulness | 0,5325 / 0,6885 | **21** / 22 | 0,5325 / **0,6896** (21) | 0,532 / 0,689 | +0,0005 / −0,0005 | +0,156 → +0,157 |
| Answer Relevancy | 0,4848 / 0,5997 | 22 / 22 | 0,4848 / 0,5997 (22) | 0,485 / 0,600 | −0,0002 / −0,0003 | +0,115 → +0,115 |

- **Calculs.** (a) est la moyenne de chaque mode sur ses scores non nuls (`aggregate`), recalculée ici à l'identique. (b) se limite aux questions notées dans les deux modes.
- **Le seul effet de la valeur manquante** est sur la Faithfulness Advanced : 0,689 sur 22 questions, contre 0,690 sur les 21 appariées. Le tableau du rapport v5 indique déjà 0,690 avec n = 21. **Le sens et l'ordre de grandeur des gains ne changent pas.**
- **Context Recall Basic.** Le rapport v5 affiche 0,598 ; la valeur exacte est 0,5985.

## 5. Par langue (n valides ; moyenne publiée, puis appariée si elle diffère)

| Langue (questions) | Context Precision | Context Recall | Faithfulness | Answer Relevancy |
| --- | --- | --- | --- | --- |
| fr (11) | 0,742 (11) → 1,000 (11) | 0,727 (11) → 0,955 (11) | 0,547 (**10**) → 0,802 (11) ; **apparié (10) : 0,547 → 0,816** | 0,573 (11) → 0,663 (11) |
| en (4) | 0,646 (4) → 1,000 (4) | 0,375 (4) → 0,850 (4) | 0,708 (4) → 0,923 (4) | 0,497 (4) → 0,679 (4) |
| ar (4) | 0,861 (4) → 0,813 (4) | 0,917 (4) → 0,550 (4) | 0,719 (4) → 0,533 (4) | 0,595 (4) → 0,575 (4) |
| tn (3) | 0,000 (3) → 0,611 (3) | 0,000 (3) → 0,500 (3) | 0,000 (3) → 0,167 (3) | 0,000 (3) → 0,296 (3) |

- **Tunisien en mode Basic.** Les zéros sont de **vrais scores** rendus par le juge (contextes présents, aucune erreur), et non des valeurs manquantes.
- **Correction à faire dans le rapport v5** (tableau `tab:ragaslangue`). Pour la Faithfulness en français, il donne « 0,547* → 0,802 », soit 10 questions en Basic contre 11 en Advanced. Sur les mêmes 10 questions, la valeur Advanced est **0,816**.

## 6. Intervalles de confiance bootstrap (questions appariées, graine 42, 10 000 tirages)

| Métrique | n apparié | Gain Advanced − Basic | IC 95 % | Advanced > Basic / = / < |
| --- | --- | --- | --- | --- |
| Context Precision | 22 | +0,268 | [+0,095 ; +0,451] | 10 / 10 / 2 |
| Context Recall | 22 | +0,202 | [−0,003 ; +0,405] | 8 / 12 / 2 |
| Faithfulness | 21 | +0,157 | [−0,009 ; +0,338] | 8 / 7 / 6 |
| Answer Relevancy | 22 | +0,115 | [−0,006 ; +0,252] | 9 / 5 / 8 |

Ces chiffres retrouvent ceux du rapport v5, arrondis : CP [+0,10 ; +0,45] ; CR [0,00 ; +0,41] ; F [−0,01 ; +0,34] ; AR [−0,01 ; +0,25]. Les comptes de signes sont identiques : 10+/2−, 8+/2−, 8+/6−, 9+/8−.

## 7. La question dont le score manque

| Question | Mode | Langue | Catégorie | Contexte (caractères) | Réponse (caractères) | Confiance |
| --- | --- | --- | --- | --- | --- | --- |
| `p-arduino-due` | basic | fr | produit | 1 022 | 248 | 0,599 |
| Les 43 autres couples question × mode (référence) | — | — | — | médiane 799 (206 – 1 108) | médiane 323 (61 – 823) | — |

**Un seul cas : aucun point commun ne peut être établi.** Ni la longueur du contexte, ni celle de la réponse, ni la langue ne sortent des valeurs des autres questions.

## Partie B : proposition (non lancée)

- **Cellules à recalculer : 1.** C'est `p-arduino-due` × Faithfulness × Basic.
- **Méthode à prévoir.** Il faudrait la recalculer **sur la réponse et les contextes déjà enregistrés** dans le JSON, sans régénérer la réponse, et écrire le résultat dans une **copie**. L'option `--ids` du script ne convient pas : elle relance tout le pipeline, génère une nouvelle réponse et note les 8 cellules de la question. Il faudrait donc un petit script dédié.
- **Appels au juge.** La Faithfulness de Ragas fait **2 appels** par échantillon (extraction des affirmations, puis vérification de chacune), plus les relances éventuelles. C'est une estimation à partir du fonctionnement de la métrique, pas une mesure. Cela représente environ 2 à 5 appels, et quelques milliers de tokens.
- **Risque de quota faible.**
  - Pour `gpt-oss-20b`, le CHANGELOG cite 200 000 tokens par jour et par modèle, en fenêtre glissante. La limite par minute de ce modèle n'est pas documentée dans le dépôt.
  - Les 429 observés à N = 5 dans le test de charge concernaient `gpt-oss-120b`, un autre modèle, sous une charge simultanée.
- **Effet attendu.** Il passerait de 21 à 22 questions pour la Faithfulness Basic. Ce nouveau score viendrait d'une autre exécution du juge, non déterministe, à une autre date.

## Limites

- **Les 802 appels ne sont pas décomposables.** On ne peut pas séparer les appels liés aux scores conservés de ceux des questions abandonnées lors d'une interruption pour quota.
- **Les échecs définitifs sont déduits, pas comptés.** L'absence d'échec définitif en 429 vient des erreurs enregistrées par métrique. Le compteur de 429, lui, ne sépare pas les tentatives des échecs.
- **Petits effectifs.** 22 questions : 11 en français, 4 en anglais, 4 en arabe, 3 en tunisien. Les moyennes par langue reposent sur 3 à 11 valeurs.
