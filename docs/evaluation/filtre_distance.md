# Filtre MAX_RELEVANT_DISTANCE = 0,75 (remarque 43, § 5.6.3)

Mesure du 24/11/2026 par `scripts/measure_distance_filter.py`. Données brutes : `filtre_distance.json`.
- **Rien n'est modifié sur disque.** Le seuil est changé **en mémoire** ; le code applicatif n'est pas modifié.
- **Production en lecture seule.** La collection de production est seulement lue.
- **Recherche seule.** Ni LLM ni `/chat/`.

## Réponse courte

- **Calcul de la distance d'un candidat trouvé seulement par BM25.**
  - Elle vaut **1 − produit scalaire** entre l'embedding de la question et l'**embedding du document stocké dans ChromaDB**, que l'index en mémoire (`_CorpusIndex`) a copié au démarrage.
  - C'est la **même formule pour tous les candidats**, y compris ceux du dense : la distance renvoyée par ChromaDB est ignorée.
  - Un recalcul indépendant donne un écart maximal de 5,5 × 10⁻⁷.
- **0,75 n'a jamais été justifié par une mesure.** Le seuil vient du commit `7fb0896` (09/08/2026), avec une justification en mots seulement. Il a ensuite été recopié tel quel pour le mode hybride (`aeec4f3`).
- **0,75 n'est pas sur un plateau.**
  - Le relever fait **gagner** des réponses en tunisien : en hybrid, hit@4 passe de 58/68 à 62/68 sans filtre ; en advanced, de 60/68 à 61/68 à partir de 0,8.
  - Le baisser fait **perdre** des réponses à partir de 0,65.
  - 55 bonnes sources du top 20 fusionné sont au-delà de 0,75, dont 41 trouvées par BM25 seul.
- **Le filtre ne double pas tout à fait le seuil de confiance.**
  - En basic, il ne peut pas changer la décision d'escalade, ce qui se démontre par le code. En hybrid, aucun changement n'est mesuré au-dessus de 0,65.
  - En **advanced**, il change les candidats envoyés au reclassement, donc les 4 passages retenus et la confiance. Résultat mesuré : 5 décisions changent à 0,7, et 2 à 0,8 ou sans filtre.

## A1. Le code : d'où vient la distance et où le filtre s'applique

**Recherche dense : seuls les identifiants sont gardés** (`hybrid_retriever.py:213`) :

```python
def _dense_ranking(query_embedding, n: int, type_filter: Optional[str]) -> list:
    pairs = []
    for doc_type in ((type_filter,) if type_filter else DOC_TYPES):
        res = vector_store.query(query_embedding, top_k=n, where={"type": doc_type})
        pairs += zip(res.get("ids", [[]])[0], res.get("distances", [[]])[0])
    return [doc_id for doc_id, _ in sorted(pairs, key=lambda p: p[1])][:n]
```

**Distance calculée pour chaque candidat fusionné, quelle que soit son origine** (`hybrid_retriever.py:141`) :

```python
    def distance(self, i: int, query_vec: np.ndarray) -> float:
        """Distance cosinus exacte (vecteurs normalisés → 1 - produit scalaire)."""
        if self.missing[i]:
            self.embeddings[i] = embed(self.documents[i])
            self.missing[i] = False
        return float(1.0 - np.dot(self.embeddings[i], query_vec))
```

- `self.embeddings` contient les embeddings **stockés dans ChromaDB**, lus par `_build_index()` au démarrage.
- Si un embedding est illisible (`_load_page`), il est recalculé une seule fois avec le même modèle, puis gardé.
- Il n'y a **pas de valeur par défaut**.
- La formule « 1 − produit scalaire » suppose des vecteurs normalisés. C'est bien le cas : `normalize_embeddings=True` dans `embedding_service.py:59`, et les normes stockées vont de 0,9999999 à 1,0000001 (mesuré).

**Fusion RRF, puis filtre** (`hybrid_retriever.py:239-262`) :

```python
    dense_ids = _dense_ranking(query_embedding, candidates_per_list, type_filter)
    bm25_ids = index.bm25_top(tokenize(query_text), candidates_per_list, type_filter)
    ...
    fused = rrf_fuse([dense_ids, bm25_ids])
    hits = []
    for doc_id, score in sorted(fused.items(), key=lambda kv: kv[1], reverse=True):
        i = index.pos.get(doc_id)
        if i is None:  # index BM25 périmé (ré-ingestion sans refresh_index)
            continue
        distance = index.distance(i, q)
        if distance > MAX_RELEVANT_DISTANCE:
            continue
        hits.append({...})
        if len(hits) >= top_k:
            break
```

**Où le filtre s'applique :**
- **Après la fusion RRF, et sur tous les candidats**, qu'ils viennent du dense, de BM25 ou des deux.
- Les candidats sont parcourus dans l'ordre RRF, et la boucle **s'arrête dès que `top_k` passages sont retenus**. Ceux qui viennent après ne sont jamais examinés.
- **Mode hybrid :** `top_k` = 4.
- **Mode advanced :** `retriever.py:56-59` appelle `hybrid_retriever.search(top_k=RERANK_CANDIDATES=20)`, puis `reranker.rerank(..., top_n=4)`. Le filtre s'applique donc **avant le reclassement**, et choisit les 20 candidats qu'il reçoit.
- **Mode basic :** il a sa propre constante `retriever.MAX_RELEVANT_DISTANCE = 0.75` (`retriever.py:34`), appliquée aux distances renvoyées par ChromaDB, avant la fusion par distance.

## A2. Vérification sur les 111 questions

Les 111 questions sont : le banc de 68, les 18 nouvelles questions tunisiennes et les 25 questions Ragas, sans expansion de l'arabizi.

| Origine du candidat (top 20 de chaque liste, fusion) | Total | Par question : min / médiane / p95 / max | Écart max avec le recalcul indépendant | Au-delà de 0,75 |
| --- | --- | --- | --- | --- |
| Les deux listes | 417 | 0 / 1 / 13 / 18 | 3,0 × 10⁻⁷ | 5 |
| Dense seul | 1 803 | 2 / 19 / 20 / 20 | 5,2 × 10⁻⁷ | 79 |
| **BM25 seul** | **617** | 0 / 3 / 16,5 / 19 | **5,5 × 10⁻⁷** | **293** |

Le recalcul indépendant relit l'embedding stocké dans ChromaDB, encode la question avec `SentenceTransformer` sans normalisation, puis calcule `1 − cos` avec une normalisation explicite.

- **Distances des candidats BM25 seul :** min 0,434, médiane 0,743, p95 0,951, max 1,057. Près de la moitié des candidats que seul BM25 apporte sont donc au-delà de 0,75.
- **Candidats réellement écartés pendant `search()`.** La boucle s'arrête à `top_k`, donc tous les candidats lointains ne sont pas examinés.

  | Mode | Candidats écartés | Questions touchées | Moyenne par question | Maximum |
  | --- | --- | --- | --- | --- |
  | Hybrid (`top_k` = 4) | 46 | 20 sur 111 | 0,41 | 6 |
  | Advanced (`top_k` = 20) | 331 | 56 sur 111 | 2,98 | 29 |

- **Fidélité de la reproduction.** La boucle rejouée pour le balayage a été comparée aux vraies fonctions `hybrid_retriever.search` et `retriever.search`, à 0,75, sur les 143 questions : **0 différence** en hybrid comme en advanced.

## B1. Origine de 0,75

- **Commit `7fb0896` (09/08/2026)**, « feat: pipeline RAG complet… », dans `app/services/rag/retriever.py` : « Distance cosinus max acceptée pour qu'un résultat soit considéré pertinent (0 = identique, 2 = opposé). Au-delà, on préfère ne rien donner au LLM plutôt que du bruit non pertinent — c'est ce qui évite les réponses hors-sujet "collées" à un chunk qui n'a rien à voir. » **Aucune mesure n'est citée**, et le message de commit ne parle pas de ce seuil.
- **Commit `aeec4f3` (25/09/2026)**, recherche hybride, dans `hybrid_retriever.py` : « Même seuil que le Basic RAG (retriever.MAX_RELEVANT_DISTANCE) : un candidat trop éloigné sémantiquement est écarté même si BM25 l'a remonté, pour ne pas injecter de bruit lexical dans le prompt. » Le seuil a été **recopié**, et non recalibré, alors que BM25 apporte des candidats bien plus lointains.
- **Documentation.** `CHANGELOG_ADVANCED_RAG.md:42` dit seulement que les distances gardent la même échelle qu'en basic. `app/config.py` et `docs/` ne contiennent **aucune justification chiffrée**.

## B2. Distribution des distances

Elle porte sur les 108 questions qui ont une bonne source (3 questions Ragas hors sujet n'en ont pas), dans le top 20 fusionné, sans filtre.

| Ensemble | n | Min | Médiane | p95 | Max | Bonnes sources > 0,75 |
| --- | --- | --- | --- | --- | --- | --- |
| Meilleure bonne source par question, tous candidats (1) | 103 | 0,092 | 0,454 | 0,774 | 0,924 | — |
| Toutes les bonnes sources, tous candidats | 520 | 0,092 | 0,558 | 0,831 | 1,028 | **55** |
| Autres candidats, tous | 1 640 | 0,308 | 0,606 | 0,817 | 1,051 | — |
| Meilleure bonne source, dense (dense seul et les deux) | 90 | 0,092 | 0,428 | 0,637 | 0,752 | — |
| Toutes les bonnes sources, dense | 432 | 0,092 | 0,531 | 0,727 | 0,809 | 14 |
| Autres candidats, dense | 1 348 | 0,308 | 0,582 | 0,738 | 0,832 | — |
| Meilleure bonne source, BM25 seul | 33 | 0,434 | 0,716 | 0,917 | 0,974 | — |
| Toutes les bonnes sources, BM25 seul | 88 | 0,434 | 0,737 | 0,930 | 1,028 | **41** |
| Autres candidats, BM25 seul | 292 | 0,452 | 0,746 | 0,952 | 1,051 | — |

(1) Pour 5 questions, aucune bonne source n'apparaît dans le top 20 fusionné.

- **Plus grande distance d'une bonne source :** 1,028 parmi les candidats, et 0,924 pour la meilleure bonne source d'une question.
- **Recherche exacte sur tout le corpus** (meilleure bonne source parmi les 11 109 documents) : min 0,092, médiane 0,469, p95 0,787, max 0,898. Pour **9 questions sur 108, toutes en tunisien**, *toute* bonne source est au-delà de 0,75 ; aucune ne peut donc passer le filtre. Ce sont :
  - « chkoun ykhalles el transport ki nraja3 produit ? » (0,786) ;
  - « chnouwa eli ma ydakhlouch fel garantie ? » (0,752) ;
  - « el colis wsel w fih composant mkasser… » (0,876) ;
  - « b chnouwa najjem nkhallas 3andkom ? » (0,833) ;
  - « najjem nkhallas b ta9sit ? » (0,874) ;
  - « el colis wsel w na9es fih article… » (0,787) ;
  - « jani produit ghalet mouch eli commandit » (0,898) ;
  - « el khlass bel carta 3al site mdhamoun ? » (0,751) ;
  - « ki njib sa7bi yechri, nerba7 chay ? » (0,846).
- **Les deux distributions se recouvrent largement.** Les autres candidats ont une médiane de 0,606 et un p95 de 0,817 ; les bonnes sources, une médiane de 0,558 et un p95 de 0,831. Aucun seuil de distance ne sépare les bonnes sources des autres.

## B3. Sensibilité du seuil (`recherche.json`, 68 questions, sans expansion de l'arabizi)

hit@4 sur 68, avec le MRR@4 entre parenthèses ; « retirés » = candidats écartés en moyenne par question pendant `search()`.

| Seuil | Basic | Hybrid | Hybrid : retirés | Advanced | Advanced : retirés |
| --- | --- | --- | --- | --- | --- |
| 0,50 | 38 (0,515) | 39 (0,544) | 15,1 | 39 (0,555) | 20,7 |
| 0,60 | 49 (0,634) | 53 (0,710) | 6,1 | 54 (0,768) | 12,9 |
| 0,65 | 53 (0,692) | 57 (0,761) | 4,0 | 59 (0,842) | 8,8 |
| 0,70 | 54 (0,700) | 58 (0,768) | 2,0 | 60 (0,849) | 6,2 |
| **0,75** | **54 (0,700)** | **58 (0,768)** | **0,44** | **60 (0,857)** | **3,3** |
| 0,80 | 54 (0,700) | 59 (0,783) | 0,31 | 61 (0,871) | 1,7 |
| 0,85 | 54 (0,700) | 60 (0,787) | 0,19 | 61 (0,871) | 0,9 |
| 0,90 | 54 (0,700) | 60 (0,790) | 0,10 | 61 (0,871) | 0,65 |
| 1,00 (pas de filtre) | 54 (0,700) | **62 (0,801)** | 0 | 61 (0,871) | 0,04 |

**Par langue.** fr, en et ar sont stables de 0,70 à 1,00 dans les deux modes, à une exception près : en advanced, l'arabe vaut 17/17 à 0,70 contre 16/17 de 0,75 à 1,00. Le tunisien, lui, varie :

| Seuil | tn, hybrid | tn, advanced |
| --- | --- | --- |
| 0,70 | 9/17 | 9/17 |
| 0,75 | 9/17 | 10/17 |
| 0,80 | 10/17 | 11/17 |
| 0,85 | 11/17 | 11/17 |
| 0,90 | 11/17 | 11/17 |
| 1,00 | 13/17 | 11/17 |

**Lecture :**
- **Basic.** Plateau dès 0,70 : le filtre n'a plus d'effet sur les 4 premiers résultats.
- **Hybrid.** 0,75 est **au bord**. Le hit@4 baisse à 0,65 (57), et **augmente dès 0,80**, jusqu'à 62 sans filtre. Les gains sont tous en tunisien, dont les bonnes sources trouvées par BM25 sont lointaines en dense.
- **Advanced.** 0,75 est **au bord**. Le hit@4 baisse à 0,65 (59) et gagne +1 à 0,80, puis forme un plateau. À 0,70, le hit@4 est le même (60) mais le MRR baisse un peu.

## B4. Filtre 0,75 et seuil de confiance 0,35

La confiance vaut `1 − min(distance des 4 passages retenus)`, et l'escalade a lieu si elle est inférieure à 0,35, c'est-à-dire si la distance minimale dépasse 0,65 (`retriever.get_best_confidence`, `dialogue_manager.py:736-739`). Sans aucun passage, la confiance vaut 0 et la conversation est escaladée.

- **Basic : le filtre ne peut pas changer la décision**, ce qui se démontre par le code.
  - Les résultats sont triés par distance, donc le filtre ne fait que couper la fin de la liste.
  - Si le meilleur passage est à 0,65 ou moins, il reste, et la décision est identique.
  - Si tous les passages sont au-delà, l'escalade a lieu dans les deux cas.
  - Mesuré sur 143 questions : 0 changement pour tout seuil ≥ 0,65.
- **Hybrid : aucun changement mesuré pour tout seuil ≥ 0,65 (0 sur 143).**
  - Un changement reste possible en théorie. Les passages sont triés par RRF : si le filtre retire un lointain, sa place dans le top 4 revient au suivant, qui peut être plus proche.
- **Advanced : le filtre change la décision.**
  - Il choisit les 20 candidats donnés au reclassement, et la confiance se calcule sur les 4 passages que le reclassement garde.
  - Écarter un candidat lointain peut donc faire remonter un passage plus proche, ou l'inverse.

| Seuil | Escalades en advanced (143 questions) | Décisions différentes de 0,75 |
| --- | --- | --- |
| 0,65 | 5 | 8 |
| 0,70 | 8 | 5 |
| **0,75** | **13** | — |
| 0,80 | 13 | 2 |
| 0,85 | 12 | 1 |
| 0,90 et 1,00 | 13 | 2 |

Les 143 questions sont : les 111, les 14 de calibration et les 18 sur des services non proposés.

- **Exemples entre 0,75 et 0,70.** « What does the warranty not cover? » est escaladée à 0,75 (confiance 0,342), mais pas à 0,70 (0,400). Il en va de même pour « najjem nkhallas b ta9sit ? » (0,296 contre 0,395) et « kifech nkalmekom ? » (0,286 contre 0,406).
- **À 0,75 en advanced, 13 escalades :**
  - 3 questions de services non proposés, et la blague ;
  - 9 questions légitimes, dont 7 en tunisien. Pour 3 d'entre elles, la bonne source est pourtant dans les 4 passages : « What does the warranty not cover? », « najjem nbadel el produit b produit ekher ? » et « kifech nkalmekom ? ».
- **En basic, avec les mêmes questions, 5 escalades seulement.**

**Conclusion B4.** En basic et en hybrid, le filtre est en pratique redondant avec le seuil de confiance pour la décision d'escalade : il agit seulement sur le **contenu** envoyé au LLM. En advanced, il ne l'est pas. Un filtre plus strict fait remonter des passages plus proches dans les 4 retenus, et réduit les escalades de questions légitimes (13 à 0,75, 5 à 0,65). En contrepartie, le hit@4 baisse : 59 au lieu de 60.

## Limites

- **Expansion de l'arabizi non appliquée.** Le tunisien est mesuré **sans** l'expansion de l'arabizi active en production (`RAG_ARABIZI_EXPANSION`). C'est ce qui touche le plus le tunisien ; en production, les chiffres tunisiens sont meilleurs (voir `recherche_par_langue.md`).
- **Petits jeux.** 68 questions pour le balayage (17 par langue), et 111 ou 143 pour les distributions et l'escalade. Une question vaut 1,5 point de hit@4.
- **« Bonne source ».** C'est le fichier de règles ou la référence produit attendue (même définition que `evaluate_retrieval.py`) : un autre passage peut être utile sans être compté.
- **Effet sur les réponses du LLM non mesuré.** Faute d'appel au LLM, on ne mesure ni la qualité des réponses ni les hallucinations quand on relâche le filtre, alors que c'est le rôle déclaré du seuil (« éviter le bruit »). Il faudrait une évaluation Ragas, avec un quota Groq.
- **Balayage rejoué.** Il rejoue la boucle de filtrage sur les candidats calculés une seule fois. Son égalité avec les vraies fonctions n'a été vérifiée qu'à 0,75 (0 différence sur 143). Le reclassement est mis en cache par ensemble de candidats, ce qui est sans effet puisqu'il est déterministe.

## Versions et matériel

- Python 3.13.5, numpy 2.5.1, sentence-transformers 5.7.0, rank_bm25 0.2.2, client chromadb 1.5.9, serveur ChromaDB 1.4.1 (Docker)
- Embedding `paraphrase-multilingual-MiniLM-L12-v2` ; reclassement `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`
- `RERANK_CANDIDATES` = 20, `CANDIDATES_PER_LIST` = 20, RRF k = 60, seuil de confiance 0,35 (cosinus)
- Intel Core i9-11900H, 15,7 Go de RAM, sans GPU, Windows 11
