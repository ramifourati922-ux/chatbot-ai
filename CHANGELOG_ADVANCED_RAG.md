# Passage Basic RAG → Advanced RAG

Référence : Module 3 GenAI School, partie « Advanced RAG ».
Périmètre volontairement minimal : deux techniques de l'étape
*retrieval* (recherche hybride, reranking), recalibrage du seuil de
confiance, puis évaluation RAGas avant/après.

| Étape | Technique | Module | Statut |
|---|---|---|---|
| 1 | Recherche hybride BM25 + dense + RRF | `app/services/rag/hybrid_retriever.py` | ✅ |
| 2 | Reranking cross-encoder multilingue (mmarco-mMiniLMv2) | `app/services/rag/reranker.py` | ✅ |
| 3 | Recalibrage `RAG_CONFIDENCE_THRESHOLD` | `app/config.py` | à faire |
| 4 | Évaluation RAGas avant/après | `scripts/evaluate_ragas.py` | à faire |

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

## Anomalies découvertes pendant la migration

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
