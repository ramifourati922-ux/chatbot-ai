# Tests des signes, ablation de la recherche et chiffrage (remarque 53)

Mesure du 24/11/2026 par `scripts/measure_ablation_recherche.py`. Données par question : `data/evaluation/ablation_recherche.json`.
- **Lecture seule.** `docs/evaluation/ragas_results.json` n'est que lu, avec un SHA-256 identique avant et après (`ead14058…6a2b63`). La production ChromaDB n'est que lue.
- **Aucun appel.** Ni Groq ni écriture en base.
- **Réglages en mémoire seulement.** Le mode de recherche et l'expansion de l'arabizi ne sont modifiés que dans le script.

## A. Tests des signes et de Wilcoxon (gains Ragas Basic → Advanced)

Les tests portent sur les questions notées dans les deux modes. Le test des signes est exact et bilatéral (loi binomiale, p = 0,5), sans les égalités. Le test de Wilcoxon apparié vient de `scipy.stats.wilcoxon` (scipy 1.18.0 était déjà installé), lui aussi sans les égalités.

| Métrique | n apparié | Advanced > / = / < Basic | p (test des signes) | Wilcoxon : n sans égalités, statistique W, p |
| --- | --- | --- | --- | --- |
| Context Precision | 22 | **10 / 10 / 2** | **0,039** | 12, W = 7,5, **p = 0,011** |
| Context Recall | 22 | **8 / 12 / 2** | 0,109 | 10, W = 10, p = 0,078 |
| Faithfulness | 21 | **8 / 7 / 6** | 0,791 | 14, W = 31, p = 0,177 |
| Answer Relevancy | 22 | **9 / 5 / 8** | 1,000 | 17, W = 58, p = 0,404 |

- **Comptes de signes.** Ils retrouvent ceux attendus : 10+/2−, 8+/2−, 8+/6− et 9+/8−.
- **Seule la Context Precision** a un gain significatif au seuil de 5 %, avec les deux tests.

## B. Ablation de la recherche, sans LLM

### Méthode

- **Jeu.** Les 22 questions notées du jeu Ragas sont lues dans `GOLDEN_SET` de `scripts/evaluate_ragas.py`, en n'exécutant que les affectations `_ESP32` et `GOLDEN_SET`, sans importer ragas. Elles sont identiques aux 22 questions de `ragas_results.json` : mêmes textes, mêmes sources attendues, mêmes langues (fr 11, en 4, ar 4, tn 3).
- **Recherche.** `retriever.search(question, 4)`, comme dans `run_pipeline`, après les mêmes préchargements : embedding, index BM25 et reclassement.
- **Expansion de l'arabizi.**
  - **« Sans arabizi »** reproduit l'état de la mesure Ragas : `run_pipeline` n'appelle **jamais** `arabizi.expand`, quel que soit le réglage.
  - **« Avec arabizi »** applique l'expansion comme `dialogue_manager`, seulement si la langue détectée est le tunisien. Elle ne modifie la requête que de 2 questions (`tn-garantie`, `tn-sfax`), et **ne change aucune mesure** : les deux tableaux sont identiques. Un seul tableau est donc donné ci-dessous.
- **Mesures sur SOURCES ATTENDUES (champ `sources`), et non des scores Ragas.**
  - **hit@4** : au moins une source attendue figure dans les 4 passages.
  - **Rappel des sources** : part des sources attendues retrouvées.
  - **Précision des sources** : sources attendues retrouvées, divisées par 4. Sa borne maximale est min(sources attendues ; 4) / 4 : quand moins de 4 sources sont attendues, la précision ne peut pas atteindre 1.
  - **MRR@4** : inverse du rang de la première source attendue.

### Résultats (identiques sans et avec arabizi)

| Mode | Langue (n) | hit@4 | Rappel des sources | Précision des sources (borne max) | MRR@4 |
| --- | --- | --- | --- | --- | --- |
| **basic** | **total (22)** | **0,864** | **0,784** | **0,295 (0,420)** | **0,750** |
| | fr (11) | 0,818 | 0,750 | 0,295 (0,500) | 0,773 |
| | en (4) | 1,000 | 0,875 | 0,438 (0,438) | 0,750 |
| | ar (4) | 1,000 | 1,000 | 0,250 (0,250) | 0,875 |
| | tn (3) | 0,667 | 0,500 | 0,167 (0,333) | 0,500 |
| **hybrid** | **total (22)** | **0,909** | **0,795** | **0,318 (0,420)** | **0,788** |
| | fr (11) | 0,909 | 0,795 | 0,386 (0,500) | 0,803 |
| | en (4) | 1,000 | 0,812 | 0,312 (0,438) | 0,750 |
| | ar (4) | 1,000 | 1,000 | 0,250 (0,250) | 0,875 |
| | tn (3) | 0,667 | 0,500 | 0,167 (0,333) | 0,667 |
| **advanced** | **total (22)** | **0,955** | **0,875** | **0,375 (0,420)** | **0,902** |
| | fr (11) | 1,000 | 0,909 | 0,500 (0,500) | 1,000 |
| | en (4) | 1,000 | 0,812 | 0,312 (0,438) | 0,833 |
| | ar (4) | 1,000 | 1,000 | 0,250 (0,250) | 0,875 |
| | tn (3) | 0,667 | 0,667 | 0,167 (0,333) | 0,667 |

### Différences appariées par question

Moyenne, IC 95 % bootstrap (graine 42, 10 000 tirages), et nombre de questions qui progressent / sont égales / reculent :

| Étape | hit@4 | Rappel des sources | Précision des sources | MRR@4 |
| --- | --- | --- | --- | --- |
| basic → hybrid | +0,045 [0,000 ; +0,136] (1 / 21 / 0) | +0,011 [−0,023 ; +0,045] (2 / 19 / 1) | +0,023 [−0,045 ; +0,091] (2 / 19 / 1) | +0,038 [−0,045 ; +0,121] (3 / 18 / 1) |
| hybrid → advanced | +0,045 [−0,091 ; +0,182] (2 / 19 / 1) | +0,080 [−0,034 ; +0,216] (3 / 18 / 1) | +0,057 [−0,011 ; +0,148] (3 / 18 / 1) | +0,114 [−0,083 ; +0,311] (7 / 12 / 3) |
| basic → advanced | +0,091 [−0,091 ; +0,273] (3 / 18 / 1) | +0,091 [−0,034 ; +0,239] (4 / 16 / 2) | +0,080 [−0,034 ; +0,216] (4 / 16 / 2) | +0,152 [−0,030 ; +0,341] (7 / 12 / 3) |

**Part du gain basic → advanced due à chaque étape :**

| Mesure | Gain total | dont fusion hybride (BM25 + RRF) | dont reclassement (cross-encoder) |
| --- | --- | --- | --- |
| hit@4 | +0,091 | +0,045 (49 %) | +0,046 (51 %) |
| Rappel des sources | +0,091 | +0,011 (12 %) | +0,080 (88 %) |
| Précision des sources | +0,080 | +0,023 (29 %) | +0,057 (71 %) |
| MRR@4 | +0,152 | +0,038 (25 %) | +0,114 (75 %) |

**Lecture :**
- **Le reclassement apporte l'essentiel du gain** sur le rappel, la précision et l'ordre (MRR).
- **Pour le hit@4, la part est égale** entre les deux étapes : une question gagnée par chacune.
- **Aucun intervalle n'exclut nettement 0.** Seul basic → hybrid sur le hit@4 a une borne basse à 0. Sur 22 questions, ces écarts restent incertains.

### Dérive depuis la mesure Ragas de septembre (sans arabizi)

| Mode | Questions aux 4 sources identiques (ordre compris) | Identiques en ensemble | hit@4 stocké → actuel |
| --- | --- | --- | --- |
| basic | 19 / 22 | 19 / 22 | 0,773 → 0,864 |
| advanced | 20 / 22 | 20 / 22 | 0,955 → 0,955 |

**Questions qui diffèrent :**
- **basic, `p-esp32`.** Le JSON ne stocke qu'une source, `ecommerce/paiement.txt`. Aujourd'hui, 4 sources sont trouvées, dont 2 ESP32 attendus (`LS-CP-000020`, `LS-CP-000028`) : la question devient un succès.
- **basic, `en-warranty`.** Auparavant 4 multimètres. Aujourd'hui `sav/garantie.txt` en 2e position : la question devient un succès.
- **basic, `tn-garantie`.** 2 sources sur 4 changent ; le résultat reste un échec dans les deux cas.
- **advanced, `en-warranty`** et **advanced, `tn-garantie`.** La politique de garantie reste en tête ; seuls les produits qui suivent changent.

**L'index a changé depuis la mesure.** La mesure Ragas date du 25 au 27/09/2026. Le commit `1993dbb` du 29/09/2026 a modifié `data/knowledge_base/general/faq.txt`, et l'index actuel contient le nouveau texte (vérifié pour la remarque 33 : le score du couscous est passé de 0,500 à 0,531). La base a donc été réingérée depuis, ce qui reconstruit l'index HNSW, qui est approximatif.

**Les chiffres actuels du mode basic ne sont donc pas ceux de la mesure Ragas** : 17 succès sur 22 à l'époque, 19 aujourd'hui. Le gain de hit@4 basic → advanced vaut +0,182 dans le JSON de septembre et **+0,091 aujourd'hui**.

## C. Chiffrage (rien n'a été lancé)

Le coût d'un mode est estimé à la **moitié** du coût mesuré pour basic et advanced (`meta` de `ragas_results.json`) : mêmes 25 questions, même juge.
- **Ce que comptent les tokens.** Seulement les réponses 200 : les relances 429 n'en consomment pas.
- **Ce qu'ils incluent aussi.** Les appels des questions abandonnées sur quota puis refaites, impossibles à séparer.
- **Durée.** Elle suppose le même débit qu'en septembre.

| Scénario | Tokens du juge (gpt-oss-20b) | Tokens de génération (gpt-oss-120b) | Jours de quota du juge (200 000/j) | Jours de quota de génération (200 000/j) | Durée de calcul |
| --- | --- | --- | --- | --- | --- |
| Un mode supplémentaire (hybrid) | ≈ 339 000 (≈ 401 requêtes, 429 compris) | ≈ 29 400 (≈ 31 requêtes) | ≈ 1,7, soit **2 jours** | ≈ 0,15 | ≈ 36 min |
| 3 répétitions complètes de basic + advanced | ≈ 2 036 000 | ≈ 176 000 | ≈ 10,2, soit **11 jours** | ≈ 0,9 | ≈ 215 min |

La fenêtre de 200 000 tokens par jour est glissante sur 24 h, d'après `CHANGELOG_ADVANCED_RAG.md`. Elle est contrôlée par modèle.

### Ajouter le mode hybrid dans `scripts/evaluate_ragas.py`

- **Ligne 79.** `PIPELINES = ("basic", "advanced")` devient `("basic", "hybrid", "advanced")`, ou `("hybrid",)` pour ne calculer que ce mode. `run_pipeline` accepte déjà n'importe quel mode, puisqu'il fixe `settings.RAG_RETRIEVAL_MODE = mode`.
- **`write_markdown`, ligne 359.** `b, a = agg["basic"], agg["advanced"]` est codé en dur pour deux modes. Avec `("hybrid",)` seul, le rapport Markdown échouerait sur une clé absente. Avec trois modes, il ignorerait hybrid. Il faut donc généraliser cette fonction. `aggregate` boucle déjà sur `PIPELINES` (l. 332).
- **`--resume` ne permet pas d'ajouter seulement hybrid** aux questions déjà notées.
  - Il saute toute question dont l'identifiant est dans le checkpoint (`done`, l. 456 et 478), sans regarder les modes.
  - Le checkpoint `<out>.partial.json` est supprimé à la fin d'une exécution complète (l. 512). Il n'en reste donc pas pour les résultats de septembre.
  - Pour ne calculer que hybrid sans toucher aux résultats existants, il faut une exécution séparée : `PIPELINES = ("hybrid",)` et `--out ragas_hybrid`, qui écrit un autre fichier, avec `write_markdown` corrigé. `--resume` reprend alors cette seule exécution si le quota l'interrompt.
- **Mélange de juges.** Le contrôle `--resume` (l. 447-452) refuse de reprendre un checkpoint noté par un autre juge, mais **seulement à l'intérieur d'une même exécution**. Pour comparer, il faut garder `--judge-model` à sa valeur par défaut, `openai/gpt-oss-20b`.
- **Comparabilité limitée.** Une nouvelle exécution générerait de nouvelles réponses (température 0,3), à une autre date et sur l'index actuel (voir la dérive). Le mode hybrid ne serait donc pas exactement comparable aux chiffres basic et advanced de septembre. Pour une comparaison propre, il faudrait refaire les trois modes dans la même exécution, soit environ 1 018 000 tokens du juge, environ 5,1 jours de quota et environ 107 min.

## Limites

- **Petit jeu.** 22 questions, dont 3 en tunisien et 4 en anglais et en arabe : une question vaut 4,5 points de hit@4 au total, et 25 à 33 points dans une langue.
- **Index actuel.** Les mesures de B portent sur l'index d'aujourd'hui, différent de celui de la mesure Ragas (voir la dérive).
- **Pas des scores Ragas.** Les mesures sur sources attendues n'évaluent pas la qualité des réponses.
- **Chiffrage à volume constant.** Il suppose le même volume d'appels qu'en septembre, alors que les 429, les abandons sur quota et la longueur des réponses varient.
