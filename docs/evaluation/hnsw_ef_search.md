# Index HNSW contre recherche exacte, selon ef_search

Mesuré par `scripts/measure_hnsw_ef_search.py`. Modèle `paraphrase-multilingual-MiniLM-L12-v2`, distance cosinus, 111 requêtes (68 du banc, 18 tunisiennes nouvelles, 25 Ragas), recherche non filtrée, k = 10.

## Configuration de la collection de production `liss_strike_kb`

Valeurs **lues sur la production** (`collection.configuration`, lecture seule, serveur ChromaDB du conteneur `chatbot_chroma`) :

| Paramètre | Valeur | Source |
| --- | --- | --- |
| hnsw:space | cosine | `configuration` (et `metadata` : {'hnsw:space': 'cosine'}) |
| M (max_neighbors) | 16 | `configuration` |
| ef_construction | 100 | `configuration` |
| ef_search | 100 | `configuration` |
| resize_factor | 1.2 | `configuration` |
| sync_threshold | 1000 | `configuration` |
| batch_size | non exposé | clé absente de `configuration` en chromadb 1.x |
| documents | 11109 | `count()` |

## Résultats

Constructions HNSW dans des collections temporaires locales (M = 16, ef_construction = 100), 3 constructions par valeur (min–max) ; temps : 3 passes après échauffement, requête seule (embedding exclu).

| Recherche | recall@10 | top-10 identiques | politiques proches retrouvées (top-8) | Arduino garantie (rang top-10) | ms médiane | ms p95 |
| --- | --- | --- | --- | --- | --- | --- |
| exact (force brute numpy) | 1,000 | 111/111 | 13/13 | 1 | 0.37 | 0.46 |
| HNSW ef_search = 100 | 0.733–0.881 | 65–79/111 | 6–11/13 | 1, 1, 1 | 1.02–4.06 | 1.34–4.81 |
| HNSW ef_search = 200 | 0.858–0.900 | 82–92/111 | 10–13/13 | 1, 1, 1 | 3.86–4.33 | 4.83–5.4 |
| HNSW ef_search = 500 | 0.956–0.968 | 100–101/111 | 13/13 | 1, 1, 1 | 4.58–5.08 | 5.66–6.01 |
| production (serveur, HTTP, ef_search = 100) | 0.883 | 87/111 | 12/13 | absent | 52.17 | 55.54 |

Cas Arduino garantie : « Une carte Arduino est garantie combien de temps ? » ; meilleure politique `policy-sav-garantie-0000`, distance exacte 0.285, rang exact 1. « absent » = hors du top-10 HNSW. Une valeur par construction.

## Question d'origine à la distance 0,092

**Introuvable.** Elle n'apparaît dans aucun fichier du dépôt (`docs/`, `scripts/`, `data/`, `tests/`), ni dans l'historique git ; seul le rapport v4 cite la distance, sans le texte de la question. Elle n'a donc pas été rejouée, et n'a pas été remplacée par une autre question.

## Versions et matériel

- Python 3.13.5, client chromadb 1.5.9, numpy 2.5.1
- Serveur de production : image `chromadb/chroma:1.4.1` (épinglée par digest), `chroma --version` = 1.4.1 ; l'API renvoie la version d'API 1.0.0
- Collections temporaires : client local chromadb 1.5.9 (`PersistentClient`), et non le serveur 1.4.1
- Embeddings des documents : calculés
- CPU Intel Core i9-11900H, sans GPU

## Limites

- Les collections temporaires tournent avec le client local chromadb 1.5.9, pas avec le serveur 1.4.1 de production : l'implémentation HNSW peut différer légèrement. La ligne « production » mesure l'index réel, mais passe par HTTP : son temps n'est pas comparable aux autres lignes.
- L'index de production a été construit par `upsert` successifs au fil des ingestions ; les collections temporaires sont construites en une fois. Leur recall peut donc différer de celui de la production.
- Les politiques proches sont comptées comme retrouvées si elles figurent dans le top-8, comme dans la mesure initiale de l'anomalie 2.
- La question d'origine à 0,092 n'a pas pu être rejouée (introuvable).
- 111 requêtes rédigées pour le projet, pas des messages de clients réels.
