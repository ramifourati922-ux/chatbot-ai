# Index BM25 en mémoire : coût, passage à l'échelle et mise à jour (remarque 42, partie B)

Mesure du 24/11/2026 par `scripts/measure_bm25_scaling.py`. Données brutes de la 2e exécution : `bm25_passage_echelle.json`.
- **Deux exécutions complètes.** Les temps de tokenisation et de requête varient du simple au double entre les deux : la machine n'était pas isolée. Les deux sont donnés, sous forme de fourchette.
- **Code importé, jamais modifié.** La production ChromaDB est seulement lue, et ni le LLM ni `/chat/` ne sont appelés.

## B1. Index actuel (11 109 chunks)

### Ce que dit le code

- **Construction.** L'index est construit **à la demande**, au premier appel de `hybrid_retriever._get_index()`, protégé par un verrou à double vérification. Au démarrage, `app/main.py:_preload_rag` le déclenche en mode `hybrid` ou `advanced`.
  1. Lecture de **toute** la collection ChromaDB, par pages de 500 et type par type : documents, métadonnées et embeddings.
  2. Tokenisation de tout le corpus.
  3. `BM25Okapi(tokens)`.
  4. Conversion des embeddings en tableau numpy.
- **Mise à jour.**
  - `refresh_index()` ne fait que `_index = None`, et rien ne l'appelle automatiquement.
  - La **requête suivante** reconstruit tout l'index, en tenant le verrou : les requêtes simultanées du même processus attendent la fin de la reconstruction.
  - `rank_bm25.BM25Okapi` ne permet **ni ajout ni suppression** de document : toute modification du catalogue impose une reconstruction complète.
  - Chaque processus Uvicorn ou Gunicorn garde sa propre copie de l'index. Un `refresh_index()` dans un processus n'invalide pas les autres.
- **Index périmé.** Sans `refresh_index()`, un document supprimé ou modifié dans ChromaDB reste dans BM25. `search()` ignore seulement les identifiants absents de `index.pos`. Un **nouveau** document reste invisible pour BM25, mais pas pour la recherche dense.

### Temps de construction (5 répétitions par exécution)

| Étape | Médiane | Min | Max |
| --- | --- | --- | --- |
| Lecture ChromaDB (`get` paginé, 23 pages) | 3,06 s | 2,84 s | 3,96 s |
| Tokenisation (11 109 documents) | 0,70 s | 0,57 s | 0,86 s |
| Construction `BM25Okapi` | 0,11 s | 0,10 s | 0,17 s |
| Conversion des embeddings en numpy | 0,01 s | 0,01 s | 0,02 s |
| **`_get_index()` complet (chemin réel)** | **3,98 s** | **3,78 s** | **4,29 s** |

Les valeurs regroupent les 10 répétitions des deux exécutions. La **lecture depuis ChromaDB représente environ 75 % du temps** ; BM25 lui-même ne prend qu'environ 0,1 s.

Les « 6 à 20 s » du rapport et du commentaire de `main.py` ne sont **pas retrouvés** pour l'index seul : 3,8 à 4,3 s, avec ChromaDB local et déjà démarré. Ce chiffre correspond à l'ensemble de `_preload_rag`, qui charge aussi le modèle d'embedding et le reclassement, sur un démarrage à froid. Cet ensemble n'a **pas été mesuré** ici.

### Mémoire

| Mesure | Valeur |
| --- | --- |
| Tokens et BM25 (tracemalloc, allocation nette ; pic) | 21,6 Mo ; 21,7 Mo |
| Variation de la mémoire du processus pendant la construction | environ 0 Mo : l'allocateur réutilise la mémoire libérée par les répétitions précédentes, donc la mesure **n'est pas exploitable** à cette taille |
| Pickle de l'objet `BM25Okapi` | 2,2 Mo |
| Embeddings en numpy (11 109 × 384 float32), gardés dans `_CorpusIndex` | 16,3 Mo |
| Textes des documents (UTF-8) | 2,4 Mo |
| Taille moyenne d'un document / vocabulaire | 30,5 tokens / 1 847 termes distincts |

### Temps d'une requête BM25 (tokenize, `get_scores` et top 20, comme `bm25_top`)

111 questions (banc 68, tunisiennes 18, Ragas 25), 3 passages, soit 333 mesures : **médiane de 7,6 à 14,3 ms, p95 de 14,4 à 26,1 ms**, selon l'exécution.

## B2. Passage à l'échelle (corpus SYNTHÉTIQUES)

Les corpus sont construits en dupliquant les 11 109 chunks réels ; chaque copie reçoit un jeton unique « dupN ». Le vocabulaire reste donc presque constant, de 1 847 à 1 892 termes, alors qu'un vrai catalogue plus grand aurait plus de termes distincts.

| Documents | Tokenisation | `BM25Okapi` | Construction hors lecture | Mémoire privée ajoutée (tokens + BM25) | Pickle BM25 | Requête : médiane | Requête : p95 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 11 109 | 0,34–0,77 s | 0,06–0,11 s | 0,4–0,9 s | non exploitable (voir B1), 21,6 Mo par tracemalloc | 2,2 Mo | 6,8–14,2 ms | 13,6–24,5 ms |
| 50 000 | 1,7–3,6 s | 0,33–0,53 s | 2,0–4,1 s | 79 Mo | 10,0 Mo | 54–61 ms | 105–113 ms |
| 100 000 | 4,6–9,1 s | 0,64–0,97 s | 5,6–9,7 s | 206 Mo | 20,1 Mo | 110–147 ms | 247–277 ms |
| 500 000 | 32,7–37,3 s | 5,9–7,8 s | **40,5–43,3 s** | **1 087 Mo** | 67–101 Mo (1) | **775–807 ms** | **1,29–1,55 s** |

(1) La taille dépend du partage des chaînes en mémoire : pickle n'écrit qu'une fois un objet partagé. Elle vaut 101,1 Mo quand chaque document est tokenisé séparément, et 66,6 Mo quand les tokens sont partagés.

**Non mesuré :**
- **Lecture ChromaDB à grande échelle.** Les corpus synthétiques ne sont pas insérés dans ChromaDB, puisque la production est en lecture seule. Par simple calcul linéaire, à partir de 3 s pour 11 109 documents, elle prendrait environ 2 min 15 s pour 500 000 : c'est une **extrapolation**, pas une mesure.
- **Embeddings à grande échelle.** Leur taille n'est pas mesurée mais calculée (N × 384 × 4 octets) : 73 Mo pour 50 000 documents, 146 Mo pour 100 000, 732 Mo pour 500 000. `_CorpusIndex` les garde en plus de BM25.

**Rechargement d'un index sérialisé** (`pickle.loads`, 3 essais) : 0,04 à 0,05 s pour 11 109 documents, et 1,1 à 1,3 s pour 500 000 (pickle de 66,6 Mo). C'est à comparer à environ 4 s et plus de 40 s pour une reconstruction.

### Lecture des résultats

- **Requête.** C'est le vrai problème d'échelle : son temps est **linéaire** en nombre de documents. `rank_bm25.get_scores` parcourt en Python le dictionnaire de **chaque** document, pour chaque terme de la question. À 500 000 documents, une requête BM25 seule prend environ 0,8 s en médiane et 1,3 à 1,6 s au p95, soit davantage que tout le reste de la recherche aujourd'hui (environ 0,2 s en basic).
- **Construction et mémoire.** Elles croissent à peu près linéairement : environ 2,2 Mo par tranche de 1 000 documents pour les tokens et BM25, plus 1,5 Mo pour les embeddings. À 500 000 documents, chaque processus garderait environ 1,1 Go (tokens et BM25) plus 0,7 Go (embeddings).
- **Catalogue actuel.** À 11 109 documents, le coût reste faible : environ 4 s au démarrage, environ 40 Mo et environ 10 ms par requête.

## Pistes (discussion, non implémentées)

1. **Mise à jour.**
   - Appeler `refresh_index()` à la fin de `ingest_knowledge_base.py`, ou exposer une route d'administration qui le fait.
   - Construire le nouvel index **à côté**, puis remplacer la référence en une seule affectation, pour ne bloquer aucune requête pendant la reconstruction.
   - Avec plusieurs processus, publier un numéro de version, par exemple dans Redis, que chaque processus compare avant de chercher.
2. **Démarrage.** Sauvegarder l'index (pickle ou fichier) à l'ingestion et le recharger au démarrage : 0,05 s mesuré au lieu d'environ 4 s, mais le fichier doit rester synchronisé avec ChromaDB.
3. **Grande échelle (au-delà d'environ 100 000 documents).** Remplacer `rank_bm25` par un **index inversé**, qui ne parcourt que les documents contenant les termes de la question. On peut le trouver dans PostgreSQL (`tsvector` et GIN, déjà présent dans l'architecture), SQLite FTS5, Tantivy ou OpenSearch. Ces outils permettent aussi l'ajout et la suppression incrémentaux. Ces options n'ont **pas été mesurées**.

## Versions

Python 3.13.5, numpy 2.5.1, rank_bm25 0.2.2, client chromadb 1.5.9, serveur ChromaDB 1.4.1 (Docker, même machine), Intel Core i9-11900H, 15,7 Go de RAM, Windows 11.

## Limites

- **Corpus synthétiques.** Leur vocabulaire est figé et les documents sont des copies : un vrai catalogue de 500 000 produits aurait plus de termes distincts, d'où plus de mémoire et un IDF différent.
- **Machine non isolée.** Facteur de 1,5 à 2 entre les deux exécutions sur la tokenisation et les requêtes : il faut lire les fourchettes, pas une valeur unique.
- **Lecture ChromaDB à grande échelle et démarrage complet** (les « 6 à 20 s ») : **non mesurés**.
- **Mesure mémoire à 11 109 documents.** La variation de la mémoire du processus n'est pas exploitable, à cause de la réutilisation de la mémoire déjà allouée : seul tracemalloc compte. À grande échelle, cette variation inclut les listes de tokens, qui sont gardées pendant la mesure alors que l'application les libère après la construction.
- **Requêtes.** Les temps portent sur BM25 seul, en un seul processus et sans charge concurrente.
