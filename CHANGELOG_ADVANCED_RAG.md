# Passage Basic RAG → Advanced RAG

Référence : Module 3 GenAI School, partie « Advanced RAG ».
Périmètre volontairement minimal : deux techniques de l'étape
*retrieval* (recherche hybride, reranking), recalibrage du seuil de
confiance, puis évaluation RAGas avant/après.

| Étape | Technique | Module | Statut |
|---|---|---|---|
| 1 | Recherche hybride BM25 + dense + RRF | `app/services/rag/hybrid_retriever.py` | ✅ |
| 2 | Reranking cross-encoder multilingue (mmarco-mMiniLMv2) | `app/services/rag/reranker.py` | ✅ |
| 3 | Recalibrage `RAG_CONFIDENCE_THRESHOLD` | `app/config.py`, `scripts/calibrate_threshold.py` | ✅ |
| 4 | Évaluation RAGas avant/après | `scripts/evaluate_ragas.py`, `docs/evaluation/` | ✅ |

Voir aussi la section « Correctifs après la revue du projet » (mémoire,
persistance, politesse, ordre des messages, confiance, boucle RAG) et
les anomalies n°6 à 11.

Le Basic RAG reste disponible (`RAG_RETRIEVAL_MODE=basic`) pour que
l'évaluation compare les deux pipelines sur le même corpus et le même
golden set.

---

## Étape 1 — Recherche hybride (BM25 + dense + RRF)

### Quoi

- **Sparse** : index BM25Okapi (`rank_bm25`) construit en mémoire sur
  les 11 109 chunks déjà indexés dans ChromaDB (même corpus que le
  dense, aucune source de vérité supplémentaire).
- **Dense** : recherche existante, inchangée — dual search
  policy/product fusionnée par distance (correctif HNSW de l'anomalie
  n°2 conservé).
- **Fusion** : Reciprocal Rank Fusion, `score(d) = Σ 1/(k + rang_i(d))`,
  k = 60 — remplace le tri par distance du Basic RAG.
- Tokenisation BM25 : minuscules, suppression des accents/diacritiques
  (NFKD), mots unicode (latin et alphabet arabe), mots-outils fr/en/ar
  retirés, **chiffres conservés** (`3andi`, `12v`, `5a` restent des
  tokens — cohérent avec le correctif Arabizi/unités techniques).
- Chaque hit garde sa distance cosinus exacte (calculée depuis les
  embeddings stockés), donc le filtre `MAX_RELEVANT_DISTANCE = 0.75` et
  la confiance `1 - distance` gardent la même échelle qu'en Basic.

### Pourquoi (réf. cours : hybrid search)

L'embedding dense capte le sens mais rate les correspondances
lexicales exactes (références, unités, noms de modules, arabizi) ;
BM25 fait l'inverse. RRF combine les deux par **rang** plutôt que par
score, car une distance cosinus et un score BM25 non borné ne sont pas
comparables.

### Choix de conception : 2 listes, pas 4

Première version : 4 listes RRF (dense et BM25, chacune séparée
policy/product). Rejetée après test : RRF donne le même score au 1er
produit et à la 1re politique quelle que soit leur pertinence réelle
— sur « ما هي مدة الضمان » (durée de garantie), un produit sans rapport
(« Circuit intégré 555 ») entrait dans le top-3. Version retenue :
1 liste dense (dual search déjà fusionnée par distance) + 1 liste BM25
sur tout le corpus (BM25 est exact, sans index approximatif, et ses
scores sont comparables entre types).

### Impact observé (qualitatif, avant RAGas)

| Requête | Basic | Hybride |
|---|---|---|
| « ESP32 wifi bluetooth » | 1 seul hit (politique paiement), confiance 0.252 → **escalade à tort** | modules ESP32 en #2/#3 (rang BM25 1 et 2), confiance 0.561 |
| « alimentation 12V 5A » | correct | correct (Bloc secteur 12V 5A en #1) |
| « ما هي مدة الضمان » | politiques garantie | identique |
| Hors-sujet (Jupiter, capitale de la France) | confiance 0.391 / 0.444 | identique |
| « Raspberry Pi 4 8GB prix » | produit 8Go #1 | kit Raspberry #1, produit 8Go #2 (léger recul, corrigé par l'étape 2) |

Latence de recherche : médiane ~300 ms dans les deux cas (machine
chargée, mesure bruitée) — surcoût BM25 négligeable. Construction de
l'index au premier appel : 6 à 20 s → préchargée au démarrage de l'API
depuis l'étape 2.

Tests : 109 → 119 (10 nouveaux dans `tests/test_hybrid_retriever.py`),
0 régression.

---

## Étape 2 — Reranking cross-encoder

### Quoi

- `retriever.search()` en mode `advanced` (nouveau défaut) : recherche
  hybride sur **20 candidats** (`RERANK_CANDIDATES`), puis le
  cross-encoder note chaque paire (question, chunk) et on garde le
  **top-4** (valeur déjà demandée par `dialogue_manager`, dans la
  fourchette 3-5 recommandée).
- Modèle : **`cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`** (118M
  paramètres), score passé explicitement par une sigmoïde → 0-1 (le
  modèle renvoie sinon des logits bruts entre ~-8 et +10).
- Préchargement au démarrage de l'API (`lifespan` dans `app/main.py`) :
  modèle d'embeddings + index BM25 + reranker. La première requête
  client ne paie plus les 6-20 s de construction de l'index. En cas
  d'échec (ChromaDB éteint), l'API démarre quand même et charge au
  premier appel.
- La confiance RAG reste `1 - distance cosinus` (min sur les hits
  retenus) → `RAG_CONFIDENCE_THRESHOLD` inchangé à ce stade (étape 3).
- Les modes `basic` et `hybrid` restent sélectionnables
  (`RAG_RETRIEVAL_MODE`) pour l'ablation RAGas.

### Pourquoi (réf. cours : reranking / "retrieve then rerank")

Un bi-encoder (MiniLM, retrieval) encode question et document
séparément ; un cross-encoder les lit ensemble dans la même passe
d'attention → jugement de pertinence bien plus fin, mais trop coûteux
pour 11 000 chunks. D'où le schéma en deux temps : rappel large et
bon marché (hybride, top-20), puis précision (cross-encoder, top-4).

### Choix du modèle : compromis latence / précision

| Modèle | Paramètres | Langues | Verdict |
|---|---|---|---|
| `cross-encoder/ms-marco-MiniLM-L-6-v2` | 22M | anglais uniquement | ❌ inadapté (corpus fr, questions fr/en/ar/tn) |
| `BAAI/bge-reranker-v2-m3` | 568M | multilingue | ❌ plus précis, mais ~1-4 s ajoutées par requête sur CPU sans GPU → incompatible avec une démo en direct |
| **`cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`** | **118M** | multilingue (mMARCO : MS MARCO traduit en 14 langues, dont fr et ar) | ✅ retenu |

(Au passage : le téléchargement depuis Hugging Face restait bloqué à
0 octet avec le backend Xet de `huggingface_hub` sur cette connexion ;
`HF_HUB_DISABLE_XET=1` a débloqué la situation.)

### Latence mesurée (CPU, 8 threads, pas de GPU)

9 questions de l'étape 1, top-20 candidats :

| Pipeline | Médiane | Max |
|---|---|---|
| Basic (dense) | 220 ms | 257 ms |
| Hybride (BM25 + dense + RRF) | 208 ms | 279 ms |
| Reranking seul (20 paires) | 883 ms | 985 ms |
| **Advanced (hybride top-20 + reranking)** | **1 084 ms** | **1 505 ms** |

Surcoût du reranking : ~0,9 s par question, sous la limite de 1,5-2 s
fixée. Levier si besoin : `RERANK_CANDIDATES=12` → reranking ~0,4 s
médiane (0,8 s max) sur les questions ar/tn/fr de contrôle.
Chargement du reranker au démarrage : ~3 s.

### Impact qualitatif — mêmes questions que l'étape 1

Top-1 retenu (score reranker entre parenthèses) :

| Requête | Basic | Hybride | Advanced |
|---|---|---|---|
| « Quel est le délai pour retourner un produit ? » | ✅ délai de retour | ✅ délai de retour | ✅ délai de retour (0,99) |
| « ESP32 wifi bluetooth » | ❌ politique paiement (1 seul hit, escalade à tort) | ≈ politique paiement #1, ESP32 en #2/#3 | ✅ 3 modules ESP32 en top-3 |
| « Raspberry Pi 4 8GB prix » | ✅ RPi 4 8Go | ≈ kit Raspberry #1, 8Go #2 | ✅ RPi 4 8Go, puis 4Go, 2Go |
| « alimentation 12V 5A » | ✅ bloc 12V 5A | ✅ bloc 12V 5A | ✅ bloc 12V 5A, puis alim. LED 12V 5A |
| « What is the warranty on a multimeter? » | ❌ 3 multimètres (produits, pas la garantie) | ❌ idem | ✅ **politique garantie instruments de mesure** (remontée du rang 8) |
| « ما هي مدة الضمان » (durée de garantie) | ≈ réclamations #1, garanties #2/#3 | ≈ idem | ≈ garantie outillage #1, puis livraison / remboursement |
| « 3andi mochkla fil livraison » | ≈ produit #1, livraison #2/#3 | ✅ 3 politiques livraison | ❌ 3 produits sans rapport (scores < 0,04) |
| Hors-sujet (Jupiter, capitale de la France) | produits / politiques proches | idem | idem, **scores très bas** (logits ≈ -7 à -8) |

Questions de contrôle supplémentaires en arabe / tunisien (hybride →
advanced) :

| Requête | Effet du reranking |
|---|---|
| « chnowa el garantie mta3 el multimetre » | ✅ politique garantie instruments remontée du rang 19 (l'hybride ne remontait que des LED et multimètres) |
| « 9adeh el livraison l sfax » | ✅ « Livrez-vous en dehors de Tunis ? » en #1 |
| « كم تكلفة التوصيل » (coût de livraison) | = frais de livraison #1 dans les deux cas |
| « هل يمكنني إرجاع المنتج » (puis-je retourner) | ≈ politiques voisines (garantie, non-retournables, échange) au lieu des 3 politiques de retour |
| « nheb nraja3 produit » | = échec dans les deux cas (résistances), score reranker 0,002 |

**Bilan** : gains nets en français et en anglais (termes techniques,
questions « garantie » posées sur un produit) ; effet mitigé en
arabe / arabizi, limite attendue d'un cross-encoder de 118M
(bge-reranker-v2-m3 serait meilleur ici, au prix de la latence).
Observation utile pour l'étape 3 : quand le reranker se trompe, son
score reste très bas (< 0,05), alors que les bons top-1 sont à
0,15-0,99. L'évaluation RAGas (étape 4, golden set sur 4 langues)
tranchera chiffres à l'appui.

Tests : 119 → 123 (4 nouveaux dans `tests/test_reranker.py`, dont un
sur le vrai modèle avec une question arabe et des documents
français), 0 régression en mode `advanced`.

---

## Étape 3 — Recalibrage de `RAG_CONFIDENCE_THRESHOLD`

### Protocole

`scripts/calibrate_threshold.py` : même protocole que la calibration
d'origine (10 questions produit, une par catégorie du catalogue, + 4
hors-sujet), rejoué sur les 3 pipelines. En mode advanced, deux
signaux candidats : **cosinus** (`1 - distance`, signal d'origine) et
**score reranker** (cross-encoder, 0-1). Contrôle complémentaire sur
26 questions fr/en/ar/tn (19 légitimes, 7 hors-sujet).

### Résultats — protocole d'origine (14 questions)

| Pipeline / signal | Produits légitimes (min – max) | Hors-sujet (min – max) | Séparables ? |
|---|---|---|---|
| Basic / cosinus | 0.368 – 0.745 | 0.267 – **0.500** | ❌ marge -0.133 |
| Hybride / cosinus | 0.368 – 0.745 | 0.267 – **0.500** | ❌ marge -0.133 |
| Advanced / cosinus | 0.368 – 0.745 | 0.263 – 0.429 | ❌ marge -0.062 |
| **Advanced / reranker** | **0.839 – 1.000** | **0.001 – 0.039** | ✅ **marge +0.800** |

Rappel (déjà observé lors de la calibration d'origine, cf. captures
Figures 23-24) : en cosinus, les hors-sujet ne sont pas tous sous le
seuil. « Recette du couscous tunisien » → 0.500 (chunk « livraison à
l'international », mot « Tunisie »), « capitale de la France » → 0.363.
Avec 0.35, seuls 2 hors-sujet sur 4 escaladent (Jupiter, blague) ; les
autres sont refusés par le garde-fou hors-sujet du prompt système
(défense en profondeur). Le score reranker est le premier signal qui
sépare les 4.

Le reranker améliore aussi le top-1 sur 3 catégories : NEMA17 exact
(au lieu de NEMA14 / driver A4988), « Contrôleur LED RGB (télécommande
IR) » (au lieu d'un ruban LED), « Pile 18650 » (au lieu d'un chargeur).

### Résultats — contrôle multilingue (score reranker)

| Groupe | Scores |
|---|---|
| Hors-sujet, 4 langues (11 questions en tout) | 0.000 – 0.039 |
| Légitimes, bon chunk en top-1 — fr/en | 0.189 – 1.000 |
| Légitimes, bon chunk en top-1 — ar/tn | 0.051 – 0.580 |
| Légitimes ar/tn, **mauvais** chunk en top-1 (5 cas) | 0.002 – 0.047 |
| « ce produit est nul » (critique produit, ne doit pas escalader) | **0.041** |

Un seuil à 0.045 sur le score reranker ferait escalader tous les
hors-sujet et les 5 questions ar/tn mal servies (par exemple « nheb
nraja3 produit » → résistances). Ce sont exactement les cas « dans le
domaine mais mal couvert » que le cosinus n'a jamais su isoler (voir la
LIMITE CONNUE dans `config.py`).

### Décision : cosinus conservé par défaut, seuil 0.35 inchangé

- **Défaut** : `RAG_CONFIDENCE_SIGNAL="cosine"`, `RAG_CONFIDENCE_THRESHOLD=0.35`,
  sur la même échelle qu'avant dans les 3 modes. 0.35 reste sous toutes
  les questions produit légitimes (minimum 0.368, marge réduite de 0.04
  à 0.018). 0 régression : 124 tests passent.
- **Option** : `RAG_CONFIDENCE_SIGNAL="reranker"`, seuil
  `RAG_RERANK_CONFIDENCE_THRESHOLD=0.045` (mode advanced uniquement).
  Pas activé par défaut pour deux raisons :
  1. **Régression** sur `test_normal_product_criticism_does_not_escalate` :
     « ce produit est nul » = 0.041 < 0.045 → escalade.
  2. **Aucun seuil ne sépare** cette critique (0.041) de « recette du
     couscous » (0.039). Les marges font ~0.006 de chaque côté, sur un
     petit échantillon.

  À trancher avec RAGas (étape 4, golden set multilingue).

| | Ancien | Nouveau |
|---|---|---|
| Signal | 1 - distance cosinus du hit n°1 (hits triés par distance) | 1 - **plus petite** distance cosinus des hits retenus (hits triés par RRF / reranker) |
| Seuil | 0.35 | 0.35 (revérifié) |
| Option | — | score reranker, seuil 0.045 (`RAG_CONFIDENCE_SIGNAL=reranker`) |

---

## Étape 4 — Évaluation RAGas : Basic RAG vs Advanced RAG

Résultats complets : `docs/evaluation/ragas_results.md` (tableaux) et
`ragas_results.json` (réponses, contextes et scores bruts, question par
question). Script : `scripts/evaluate_ragas.py`.

### Protocole d'évaluation

- **Pipelines comparés** : Basic (dense seul, `RAG_RETRIEVAL_MODE=basic`)
  et Advanced (hybride top-20 puis reranking top-4). Même corpus, même
  golden set, même prompt de génération (`llm_factory.build_messages`),
  même modèle générateur.
- **Golden set** : 25 questions reprises des étapes 1-3 (continuité avec
  ce qui est déjà documenté) — 11 fr (8 produits, 3 SAV), 4 en, 4 ar,
  3 tn, 3 hors-sujet. Référence et sources attendues rédigées à partir
  de la knowledge base (en français, langue du corpus).
- **Métriques RAGas 0.4.3** (API `ragas.metrics.collections`) : Context
  Precision, Context Recall, Faithfulness, Answer Relevancy
  (`strictness=1`). Plus une métrique sans LLM : source attendue dans le
  top-4 (hit@4). Les 3 hors-sujet ne sont pas notés par RAGas (pas de
  référence) : on vérifie seulement le comportement (refus ou escalade).
- **Modèles** : générateur `openai/gpt-oss-120b` (celui du chatbot) ;
  juge `openai/gpt-oss-20b` (Groq) ; embeddings pour Answer Relevancy :
  le modèle local du projet.
  - **Juge ≠ générateur** : évite le biais d'auto-évaluation, et chaque
    modèle a son propre quota Groq.
  - La génération n'utilise pas `llm_factory.ask()` : en cas de 429,
    elle basculerait silencieusement sur le modèle de secours, et une
    partie des réponses viendrait d'un autre modèle.

### Résultats globaux (22 questions notées)

| Métrique | Basic RAG | Advanced RAG | Écart |
|---|---|---|---|
| Context Precision | 0.645 | **0.913** | **+0.268** |
| Context Recall | 0.599 | **0.800** | **+0.202** |
| Faithfulness | 0.532 | **0.689** | **+0.156** |
| Answer Relevancy | 0.485 | **0.600** | **+0.115** |
| Source attendue dans le top-4 | 77 % | **95 %** | +18 pts |
| Latence de recherche (médiane) | 177 ms | 1 214 ms | +1,0 s |
| Hors-sujet refusés (escalade ou garde-fou du prompt) | 3/3 | 3/3 | = |
| Métriques en échec (parsing) | 1 / 88 | 0 / 88 | |

### Par langue

| Langue (n) | Basic — CP / CR / F / AR | Advanced — CP / CR / F / AR | Lecture |
|---|---|---|---|
| fr (11) | 0.74 / 0.73 / 0.55 / 0.57 | **1.00 / 0.95 / 0.80 / 0.66** | ✅ gain net sur les 4 métriques |
| en (4) | 0.65 / 0.38 / 0.71 / 0.50 | **1.00 / 0.85 / 0.92 / 0.68** | ✅ gain net |
| ar (4) | **0.86 / 0.92 / 0.72 / 0.59** | 0.81 / 0.55 / 0.53 / 0.58 | ❌ **régression** (recall, faithfulness) |
| tn (3) | 0.00 / 0.00 / 0.00 / 0.00 | 0.61 / 0.50 / 0.17 / 0.30 | ✅ gain en recherche, génération faible |

### Analyse

- **D'où vient le gain.** 4 questions où Basic ne retrouve pas la bonne
  source et Advanced si :
  - « piles 18650 » : Basic remonte des chargeurs ;
  - « NEMA17 » : Basic remonte des NEMA14 et d'autres moteurs ;
  - « ESP32 wifi bluetooth » : Basic remonte la politique de paiement ;
  - « warranty on a multimeter » : Basic remonte des fiches produits
    au lieu de la politique de garantie.

  Le LLM répond alors honnêtement « je ne trouve pas l'information »
  et RAGas note 0 partout. Sur les autres questions fr/en, les deux
  pipelines font jeu égal (CP/CR déjà à 1.0 en Basic).
- **Régression en arabe**, cohérente avec l'étape 2 (constat
  qualitatif, désormais chiffré). Sur « هل يمكنني إرجاع المنتج »
  (retour) et « ما هي مدة الضمان » (garantie), le reranker mmarco écarte
  les bons chunks : Context Recall 1.00 → 0.00 et 0.67 → 0.20. Limite
  d'un cross-encoder de 118M paramètres en cross-lingue ar → fr ; c'est
  le prix du choix « latence » de l'étape 2 (bge-reranker-v2-m3 écarté).
- **Tunisien** : la recherche progresse (Basic ne trouve rien sur 3/3),
  mais la génération reste faible. Sur « 9adeh el livraison l sfax »,
  le contexte est bon (CP 0.83) mais le LLM répond qu'il n'a pas
  d'information pour Sfax (le chunk dit « 12 DT hors Grand Tunis » sans
  nommer Sfax) → Faithfulness et Answer Relevancy à 0.
- **Seul échec de recherche d'Advanced** : « 3andi mochkla fil
  livraison » (question vague, en arabizi) → produits sans rapport. Les
  deux pipelines demandent des précisions au client, ce qui est
  raisonnable ; la référence (« produit arrivé cassé ») était elle-même
  une interprétation.
- **Hors-sujet** : défense en profondeur confirmée dans les deux
  pipelines. « Jupiter » escalade au seuil de confiance ; « couscous » et
  « capitale de la France » sont refusés par le garde-fou du prompt
  système.
- **Coût** : +1 s de recherche par question (reranking sur CPU, cf.
  étape 2).

### Limites de l'évaluation (à citer dans le rapport)

- **Petit échantillon** : 22 questions notées, dont seulement 3-4 en ar
  et en tn. Les écarts par langue sont des tendances, pas des mesures
  statistiquement solides.
- **Golden set construit par l'auteur**, à partir de questions déjà
  testées aux étapes 1-3 : risque de biais, même si ces questions ont
  été choisies avant l'évaluation.
- **Answer Relevancy bruitée** avec `strictness=1` (1 question générée
  au lieu de 3, pour économiser le quota). Exemple : « analyseur logique »,
  réponses quasi identiques notées 0.63 (Basic) et 0.17 (Advanced).
- **Biais de RAGas** : une réponse honnête « je n'ai pas l'information »
  obtient 0 en Answer Relevancy et en Faithfulness, alors que c'est le
  bon comportement pour un chatbot SAV quand le contexte manque.
- **Juge plus petit que le générateur** (20b vs 120b) : choix contraint
  par les quotas. Un seul échec de parsing sur 176 notations (sortie
  vide du juge), réessayé ensuite automatiquement.

### Coût et déroulé

- **Volume** : 802 requêtes au juge (dont 403 refusées en 429 et
  réessayées), 679 k tokens ; génération : 62 requêtes, 59 k tokens.
  71,6 min de calcul effectif.
- **Quota** : offre gratuite Groq limitée à **200 000 tokens par jour et
  par modèle** (fenêtre glissante de 24 h) → le calcul a été étalé sur
  3 jours (25 au 27 septembre). Le script sauvegarde après chaque
  question (`docs/evaluation/ragas_results.partial.json`), s'arrête
  proprement sur le quota journalier et reprend avec `--resume` ; il
  refuse de reprendre avec un autre juge.
- **Dépendances** : `ragas==0.4.3` rétrograde `tenacity` (9.1 → 8.5),
  `rich` et `fsspec`, sans impact sur les 124 tests. Il importe aussi
  sans condition un module Vertex AI retiré de `langchain-community`
  0.4 → module factice injecté dans le script d'évaluation uniquement.

### Perspectives

- **Reranking conditionné à la langue** : le reranker seulement pour
  fr/en (déjà détectée par `language_detector`), hybride seul pour
  ar/tn. D'après ces chiffres, ça garderait le gain fr/en sans la
  régression en arabe.
- Reranker plus fort en arabe (bge-reranker-v2-m3) si un GPU est
  disponible.
- Normalisation ou traduction de l'arabizi avant la recherche.
- Élargir le golden set (≥ 10 questions par langue) et repasser
  Answer Relevancy avec `strictness=3`.

---

## Correctifs après la revue du projet

Après la migration Advanced RAG, une revue complète du projet puis un
test manuel de bout en bout contre l'API réelle (pas seulement les
tests automatisés) ont mis au jour des manques et des bugs. Chaque
correctif a suivi le même protocole : un test qui reproduit le problème
(et échoue sur l'ancien code), le correctif, la suite complète, une
vérification sur l'API réelle, puis un commit.

| # | Commit | Problème | Correctif | Tests |
|---|---|---|---|---|
| 1 | `f9a2c35` | Le LLM n'avait **aucune mémoire** : « et la garantie ? » après une question sur l'Arduino Uno n'avait aucun sens pour lui | Historique transmis au LLM + questions de suivi rattachées à la précédente pour la recherche | 124 → 144 |
| 2 | `0bd1d01` | PostgreSQL **n'était pas utilisé** : les conversations disparaissaient avec la session Redis (1 h) | Chaque échange est enregistré (tâche de fond, statut `escalated`) | 144 → 148 |
| 3 | `478a99c` | Documentation incohérente, ChromaDB en `:latest` | README de la base, `.env.example`, `ChatResponse`, ChromaDB épinglé | 148 |
| 4 | `acd4eae` | *(test manuel)* **« bonjour », « merci » escaladaient** vers un humain | Catégorie « politesse » traitée avant le RAG | 148 → 185 |
| 5 | `440ca05` | *(test manuel)* **Messages en base dans le désordre** (régression du correctif 2, anomalie n°9) | Horodatage de chaque message côté Python | 185 → 186 |
| 6 | `7ef15db` | *(test manuel)* `confidence` **toujours à 0.0** sur les réponses RAG | Expose la vraie confiance RAG | 186 → 187 |
| 7 | `d05b4ff` | *(préparation de la démo)* **3 bonnes questions d'affilée → transfert** « je n'arrive pas à répondre » | Le compteur de boucle ne compte que les vrais échecs | 187 → 204 |

### 1. Mémoire conversationnelle (`f9a2c35`)

- **Constat** : `llm_factory.build_messages()` n'envoyait que le prompt
  système et le message courant ; l'historique, pourtant stocké dans
  Redis, n'était jamais transmis au LLM.
- **Correctif** : les 6 derniers messages de la session (3 échanges,
  500 caractères max chacun) sont insérés entre le prompt système et la
  question. Pour la **recherche**, une question de suivi est précédée de
  la dernière question *autonome* du client.
- **Choix mesurés** (sur « et la garantie ? » après « Avez-vous
  l'Arduino Uno ? ») :
  - question précédente **du client** plutôt que dernière réponse du
    bot : la réponse du bot (prix, variantes) noie le sujet et fait
    perdre la politique de garantie des résultats ;
  - détection par règles **étroites** (connecteur en tête : et / and /
    w / و, ou pronom dans une question de 6 mots max) : rattacher une
    question autonome comme « frais de livraison ? » fait disparaître la
    politique de livraison des résultats ;
  - pas de reformulation par LLM : un appel Groq de plus par message.
- **Résultat** : « et la garantie ? » retrouve l'Arduino Uno et la
  garantie des cartes programmables (6 mois).

### 2. Persistance des conversations (`0bd1d01`)

- **Constat** : tables `users` / `conversations` / `messages` et
  `ConversationRepository` en place, mais rien n'y écrivait.
- **Correctif** : `handle_message()` calcule la réponse puis programme
  l'enregistrement dans une **tâche de fond**, quelle que soit l'issue
  (réponse RAG ou escalade, qui passe la conversation au statut
  `escalated`). La conversation en cours est retrouvée en base (activité
  depuis moins d'une heure), pas stockée dans la session Redis : la
  session est réécrite en entier à chaque message, une écriture
  concurrente aurait pu écraser un message.
- **Latence** (escalade, médiane sur 10) : 7,2 ms sans persistance,
  16,9 ms avec ; l'écriture (~30 ms) n'est pas attendue par le client.
  Une panne de PostgreSQL est seulement journalisée.

### 3. Cohérence documentaire (`478a99c`)

- README de la base de connaissances réécrit (il disait encore « aucun
  contenu n'est écrit » ; il affirmait aussi, à tort, que l'ingestion
  parcourt automatiquement le dossier).
- `.env.example` complété avec les 7 réglages RAG.
- ChromaDB épinglé par digest sur l'image qui a indexé la base (serveur
  1.4.1 ; le tag `1.4.1` publié aujourd'hui est une autre build) : évite
  une régression de l'anomalie n°6.

### 4. Salutations et remerciements (`acd4eae`)

- **Constat** (test manuel) : « hello », « bonsoir », « bonjour »,
  « salut », « merci », « aslema », « مرحبا » → escalade
  `low_rag_confidence`. La base ne contient aucune salutation : la
  confiance tombait entre 0,27 et 0,35, sous le seuil.
- **Correctif** : catégorie `SMALL_TALK` dans le classifieur (règles
  fr/en/ar/tn, uniquement si **tous** les mots du message sont des mots
  de politesse), réponse toute prête dans la langue du client, sans RAG
  ni LLM (~10 ms). « bonjour, quelle est la garantie ? » reste une
  question normale.

### 5. Ordre des messages en base (`440ca05`)

Régression introduite par le correctif 2, détectée par le test manuel :
voir anomalie n°9.

### 6. Champ `confidence` (`7ef15db`)

- **Constat** : `confidence` valait 0.0 sur toutes les réponses RAG : il
  contenait la confiance du classifieur d'intentions, qui vaut 0.0 quand
  aucune de ses règles ne s'applique.
- **Correctif** : sur une réponse RAG, la confiance du RAG (celle déjà
  comparée au seuil d'escalade). Vérifié avant : aucun code ne décidait
  à partir de cette valeur (routes, interface et persistance ne font que
  la recopier). Exemples réels : garantie fr 0,847, arabe 0,793.

### 7. Compteur de boucle RAG (`d05b4ff`)

- **Constat** (préparation de la démo) : le compteur augmentait à
  chaque question RAG, même bien répondue ; la 3e question d'affilée
  déclenchait un transfert « je n'arrive pas à répondre ». Le scénario
  de démo devait insérer un « merci » pour l'éviter.
- **Correctif** : le compteur n'augmente plus qu'après une réponse du
  LLM qui dit **ne pas avoir l'information** (motifs relevés sur de
  vraies réponses, en 4 langues) ; une réponse informative le remet à
  zéro. Il faut donc 3 échecs **consécutifs**, et le transfert remplace
  alors la 3e réponse « je ne sais pas ». La confiance trop faible
  escaladait déjà immédiatement (inchangé).
- **Limite** : détection par mots-clés, une formulation inédite n'est
  pas comptée (le client peut toujours demander un humain).
- **Vérification** : 4 questions RAG d'affilée sur l'API réelle →
  aucun transfert.

### Hygiène des données de test

Les nouveaux tests suppriment ce qu'ils écrivent en base. Les tests
`dialogue_manager` existants, eux, laissent encore des utilisateurs de
test à chaque lancement de la suite : la base a été vidée avant la
préparation de la démo (voir `docs/demo/CHECKLIST_JOUR_J.txt`).

### Limites restantes (documentées, non corrigées)

- **Anglais cross-lingue** : « What is the warranty on programmable
  boards? » ne retrouve pas la politique de garantie.
- **Tunisien en arabizi** : réponse en arabe littéraire au lieu de
  l'arabizi du client.
- **« 3D » pris pour de l'arabizi** : anomalie n°10.
- **Sessions WebSocket usurpables** : l'identifiant de session est
  choisi par le client ; une session WhatsApp ayant pour identifiant le
  numéro de téléphone, un client web qui connaît ce numéro peut
  rejoindre la même session. Plus sensible depuis la mémoire
  conversationnelle (l'historique est transmis au LLM). Piste :
  préfixer les sessions par canal et générer l'identifiant côté
  serveur.
- **Escalade sans humain derrière** : le statut `escalated` est en
  base, mais aucun agent n'est notifié.
- **Pas d'authentification ni de limite de débit** ; pas de
  `Dockerfile` ni de CI ; pas de suivi de commande.

---

## Anomalies découvertes (migration et correctifs)

### Anomalie n°6 — Données ChromaDB hors du volume Docker

- **Symptôme** : aucun en fonctionnement normal — l'API répondait,
  11 109 chunks indexés. Risque latent : toute recréation du conteneur
  (`docker compose up --force-recreate`, `docker compose down` puis
  `up`, mise à jour de l'image `latest`) aurait effacé la knowledge
  base, **même sans `-v`**. La consigne du README (« `down` sans `-v`
  est sans risque ») était donc fausse pour ChromaDB.
- **Diagnostic** : `docker inspect chatbot_chroma` → volume
  `chroma_data` monté sur `/chroma/chroma` ; `du -sh` dans le
  conteneur → `/chroma/chroma` = 4 Ko (vide), `/data` = 43 Mo
  (`chroma.sqlite3` + segment HNSW).
- **Cause** : les versions récentes de l'image `chromadb/chroma`
  persistent dans `/data` ; l'ancien chemin `/chroma/chroma` du
  `docker-compose.yml` n'est plus utilisé. Les données vivaient dans la
  couche en écriture du conteneur, pas dans le volume nommé.
- **Correction** :
  1. `docker stop chatbot_chroma` puis
     `docker cp chatbot_chroma:/data ./chroma_data_backup` (copie
     cohérente, SQLite à l'arrêt) ;
  2. `docker-compose.yml` : `chroma_data:/chroma/chroma` →
     `chroma_data:/data` ;
  3. `docker compose up -d chromadb` (recrée le conteneur, volume vide) ;
  4. `docker stop` → `docker cp ./chroma_data_backup/. chatbot_chroma:/data`
     → `docker start` ;
  5. vérification puis suppression du backup local.
- **Vérification** : `vector_store.count() == 11109`, puis
  **`docker compose up -d --force-recreate chromadb`** →
  toujours 11 109 chunks et recherche fonctionnelle : les données
  survivent maintenant à la recréation du conteneur.

### Anomalie n°7 — Embeddings illisibles pour ~100 produits (contournement)

- **Symptôme** : à la construction de l'index hybride,
  `collection.get(include=["embeddings"])` lève
  `InternalError: Error executing plan: Internal error: Error getting embedding`.
- **Diagnostic** : pagination puis recherche par offset — l'erreur ne
  touche que les enregistrements produits à partir de l'offset 10 941
  (≈ 109 derniers insérés). Leurs documents et métadonnées se lisent
  normalement et ils restent trouvables par `query()` (recherche
  dense). Le problème persiste après la recréation du conteneur
  (anomalie n°6).
- **Cause** : côté serveur ChromaDB (lecture des vecteurs de ces
  enregistrements via `get`, alors que `query` fonctionne) ; cause
  racine non investiguée.
- **Contournement** (`hybrid_retriever._load_page` /
  `_CorpusIndex.distance`) : une page dont les embeddings sont
  illisibles est rechargée sans eux ; les vecteurs manquants sont
  recalculés localement **à la demande** (seulement si BM25 remonte un
  de ces chunks), avec le même modèle et `normalize_embeddings=True`
  qu'à l'ingestion → mêmes vecteurs, puis mis en cache. Recalculer
  toute la page d'avance aurait coûté ~30 s au démarrage (~55 ms par
  chunk sur CPU).
- **Pas de fix racine pour l'instant** : une ré-ingestion complète
  (`ingest_knowledge_base.py --reset`) le corrigerait probablement,
  mais n'est pas nécessaire tant que le contournement tient.

### Anomalie n°8 — Un PostgreSQL natif Windows masque celui de Docker

- **Symptôme** : toutes les connexions à la base échouent
  (`ConnectionDoesNotExistError: connection was closed in the middle of
  operation`, `WinError 64`), alors que le conteneur `chatbot_postgres`
  tourne et répond à `psql` depuis l'intérieur.
- **Diagnostic** : `Get-NetTCPConnection -LocalPort 5432` → le port est
  tenu par un processus `postgres` Windows (service
  `postgresql-x64-18`, démarrage automatique), pas par Docker. Les
  connexions à `localhost:5432` atterrissaient sur ce serveur, qui ne
  connaît pas l'utilisateur `chatbot_user`.
- **Cause** : un PostgreSQL 18 installé nativement, relancé au
  redémarrage de Windows ; avant, le port menait bien au conteneur.
- **Correction** (hors code, en administrateur) :
  `Stop-Service postgresql-x64-18` puis
  `Set-Service postgresql-x64-18 -StartupType Manual`.
- **Vérification** : port 5432 tenu par `com.docker.backend`, tests de
  persistance au vert. Contrôle ajouté à la checklist du jour J.

### Anomalie n°9 — Messages enregistrés dans le désordre

- **Symptôme** (test manuel) : dans 5 conversations sur 7, les messages
  sortaient dans l'ordre « assistant → user ».
- **Diagnostic** : le message du client et la réponse avaient
  exactement le même `created_at`, à la microseconde.
- **Cause** : les deux messages sont écrits dans la même transaction, et
  le `now()` de PostgreSQL renvoie l'heure de **début** de la
  transaction ; le tri par date ne pouvait pas les départager. Le test
  du correctif 2 passait par chance.
- **Correction** (`440ca05`) : `handle_message()` date l'échange côté
  Python (message du client = heure de réception, réponse = heure où
  elle est prête, au moins 1 µs après) ;
  `ConversationRepository.add_message()` accepte `created_at`.
- **Vérification** : test dédié (4 horodatages distincts et strictement
  croissants, échoue sur l'ancien code) ; sur l'API réelle, la réponse
  est datée ~3,6 s après la question, soit le temps de traitement réel.

### Anomalie n°10 — « 3D » pris pour de l'arabizi (non corrigée)

- **Symptôme** : « Quel est le prix d'une imprimante 3D Prusa ? », posée
  en français, reçoit une réponse en tunisien arabizi (« Prix ta3
  l'imprimante 3D… »).
- **Cause probable** : `language_detector` considère un chiffre collé à
  des lettres comme un marqueur d'arabizi (« 3andi », « n7eb ») ; « 3D »
  n'est pas couvert par l'exception des unités techniques (« 12V »,
  « 5A »).
- **Statut** : non corrigée (hors périmètre) ; à éviter en démonstration.

### Anomalie n°11 — Suite de tests bloquée (environnement de test)

- **Symptôme** : la suite complète, qui tournait en ~1 min, ne se
  terminait plus (> 10 min) après l'ajout de la persistance ; chaque
  fichier de test, lancé seul, passait.
- **Diagnostic** : `faulthandler` → un test attend indéfiniment dans
  `wait_for_pending_persistence()`, sur une tâche d'écriture créée par
  un test précédent.
- **Cause** : pytest-asyncio crée une boucle asyncio par test ; une
  tâche de fond restée en attente dans la boucle (fermée) d'un test
  précédent ne se termine jamais. Les connexions asyncpg du pool sont
  elles aussi liées à leur boucle d'origine. N'arrive pas en production
  (une seule boucle).
- **Correction** : on n'attend plus que les tâches de la boucle courante
  (`_alive_in_this_loop`) ; les fixtures de test abandonnent le pool
  (`engine.dispose(close=False)`) au lieu de fermer des connexions liées
  à une boucle morte.
