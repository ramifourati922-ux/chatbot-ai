# Passage Basic RAG → Advanced RAG

Référence : Module 3 GenAI School, partie « Advanced RAG ».
Périmètre volontairement minimal : deux techniques de l'étape
*retrieval* (recherche hybride, reranking), recalibrage du seuil de
confiance, puis évaluation RAGas avant/après.

| Étape | Technique | Module | Statut |
|---|---|---|---|
| 1 | Recherche hybride BM25 + dense + RRF | `app/services/rag/hybrid_retriever.py` | ✅ |
| 2 | Reranking cross-encoder multilingue | `app/services/rag/reranker.py` | à faire |
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
| « Raspberry Pi 4 8GB prix » | produit 8Go #1 | kit Raspberry #1, produit 8Go #2 (léger recul) |

Latence de recherche : médiane ~300 ms dans les deux cas (machine
chargée, mesure bruitée) — surcoût BM25 négligeable. Construction de
l'index au premier appel : 6 à 20 s (préchargement au démarrage de
l'API prévu à l'étape 2).

Tests : 109 → 119 (10 nouveaux dans `tests/test_hybrid_retriever.py`),
0 régression.

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
