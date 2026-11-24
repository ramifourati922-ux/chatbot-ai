# Question d'origine de l'anomalie 2 (distance 0,092)

Recherche du 24/11/2026, par `scripts/find_question_origine_0092.py` (étape 2), avec les fouilles textuelles décrites ci-dessous (étape 1). La collection de production `liss_strike_kb` a seulement été lue (`get` et `query`), jamais modifiée. Aucun code applicatif n'a été modifié.

Phrase du rapport visée : « Une question de politique, dont le document idéal était à la distance 0,092, ne le retrouvait pas : les huit premiers résultats étaient des produits, à environ 0,78. »

## Conclusion

**Introuvable de façon établie.**
- **Aucune trace textuelle.** Aucun fichier ne donne le texte de la question.
- **Aucune candidate ne remplit les deux conditions.** Il fallait une meilleure politique entre 0,085 et 0,100 **et** 8 premiers résultats non filtrés tous des produits.

Une seule question remplit la première condition : « Quel est le délai pour retourner un produit ? », à 0,0918 de `policy-sav-retours-0000`.
- **Ce qui la rapproche du cas d'origine :**
  - arrondie, sa distance vaut 0,092 ;
  - c'est une question de SAV, et le premier rapport parle de « a customer service policy question » ;
  - elle figure dans `tests/test_retriever.py:20`, dans une recherche **filtrée** sur les politiques. Ce test date du commit `7fb0896` (09/08/2026), le même que le correctif de la recherche duale.
- **Ce qui empêche de conclure :** l'index de production actuel ne reproduit pas l'anomalie pour elle.
  - Sans filtre, le document idéal sort au **rang 1** et les 10 premiers résultats sont tous des politiques.
  - Ses 8 produits les plus proches sont à 0,669–0,715, et non à environ 0,78.

C'est donc **une candidate plausible, non établie**. Elle ne doit pas être présentée comme la question d'origine. Le rejeu de l'étape 3 n'a pas été fait, puisque la question n'est pas retrouvée.

## Étape 1 : traces textuelles

### Ce qui a été fouillé

| Emplacement | Contenu fouillé | Motifs |
| --- | --- | --- |
| Transcripts Claude Code (`C:\Users\ramif\.claude\projects\`) | 1 dossier (`c--Users-ramif-chatbot-ai`), 1 fichier `.jsonl` : la session en cours, environ 24 800 lignes | `0.092`, `0,092`, `0{,}092`, `092` isolé, `0.78`, « régions denses », « zones denses », `HNSW`, « dual search », « deux requêtes », « policy et product », `where=None` |
| Historique git | 76 commits, toutes branches (`--all`) | `git log -S"0.092"`, `git log -S"0,092"`, `git log -S"HNSW"` (diffs) ; messages de commit filtrés par `092`, `dual`, `filtre`, `policy`, `hnsw`, `where` |
| Dépôt `chatbot-ai` | 319 fichiers, fichiers non suivis compris, hors `venv/`, `.git/` et `data/chroma/` | mêmes motifs ; aucun dossier `logs/`, aucun `*.log`, aucun notebook |
| `C:\Users\ramif\Downloads` (récursif) | 515 fichiers `.tex`, `.md`, `.txt` ou `.html` ; 107 PDF (via `pdftotext`) ; 51 DOCX (via `word/document.xml`) | mêmes motifs |
| `C:\Users\ramif\Documents` | vide | — |
| `C:\Users\ramif\OneDrive` et `Desktop` | 213 fichiers texte, 13 PDF, 0 DOCX | mêmes motifs : aucune occurrence |

### Ce qui a été trouvé

- **Transcript.**
  - La plus ancienne occurrence de « 0,092 » (ligne 9109) est une réécriture du rapport en Claude Docs, à partir d'une version antérieure.
  - Toutes les occurrences suivantes reprennent la phrase du rapport, la remarque de l'encadrant ou cette recherche.
  - Aucune ne contient le texte de la question.
  - 13 résultats d'outils de la session sont des images ou des documents, impossibles à fouiller par texte.
- **Git.**
  - `-S"0.092"` et `-S"0,092"` ne renvoient rien.
  - `-S"HNSW"` renvoie 2 commits : `7fb0896` (09/08/2026) et `aeec4f3` (25/09/2026).
  - Le premier contient le commentaire de `retriever.search_basic` (`app/services/rag/retriever.py:67-76`). Il décrit le mécanisme (« rater un chunk de politique bien plus pertinent »), sans question ni distance.
  - Aucun message de commit ne parle de recherche duale ni de filtre.
- **Dépôt.**
  - Les seules occurrences sont dans `docs/evaluation/hnsw_ef_search.md:34,51` et `scripts/measure_hnsw_ef_search.py:271,292`. Elles ont été écrites le 23/11/2026, et disent justement que la question est introuvable.
  - Le test de non-régression `tests/test_hybrid_retriever.py:71` utilise « Combien de temps dure la garantie ? ». Il ne cite aucune distance.
- **Rapports antérieurs.** La phrase figure dans toutes les versions, du premier rapport anglais au v5, sans jamais le texte de la question. La plus ancienne est `Downloads\report.pdf` (03/09/2026), ligne 1283 de `pdftotext -layout` :

  ```
  document. After the fix above, an unfiltered search for a customer service policy question still
  failed to find a document that was independently confirmed to be an excellent match (distance
  of 0.092), even though the filtered search, restricted to the policy category, found it easily.
  Looking directly at the vector database's unfiltered results showed that the eight top results all
  belonged to the product category, at much higher distances (around 0.78). The root cause was
  ```

- **Autres versions du même passage.** On le retrouve, à la ligne près, dans :
  - `Rapport.pdf:1357` et `Rapport (1).pdf:1357` (anglais) ;
  - `Rapport_PFE_LissStrike_v1_FR.docx:571` ;
  - les v2, v3, v4 et v5 en PDF ;
  - `Rapport_PFE_LissStrike_v4_Latex\chapitre\06d-Chapitre5.tex` et `Rapport_PFE_LissStrike_v5_Latex\chapitre\06d-Chapitre5.tex` ;
  - `1. Comprendre le projet.pdf:730`.
- **Fausse alerte.** L'occurrence de `0.092` dans `Downloads\chromadb_liss_strike.html` est une coordonnée d'embedding de la visionneuse, sans rapport.

## Étape 2 : reconstitution par les données

### Méthode

Il y a **1 431 candidates distinctes** :
- 68 de `data/evaluation/recherche.json` (17 thèmes × 4 langues) ;
- 18 de `recherche_tunisien_nouvelles.json` ;
- 25 de `docs/evaluation/ragas_results.json` ;
- 58 de `data/intents/test.json` ;
- 420 chaînes de 35 fichiers `tests/*.py` ;
- 842 chaînes de 14 fichiers `scripts/*.py`.

Sont gardées toutes les chaînes Python de 5 à 200 caractères, sur une seule ligne, avec une espace et sans caractère de code. Elles comprennent donc aussi des réponses de référence, et pas seulement des questions.

Pour chaque candidate :
- l'embedding est calculé avec `paraphrase-multilingual-MiniLM-L12-v2`, normalisé ;
- la meilleure distance « policy » est **exacte** : produit scalaire numpy sur les 11 109 embeddings lus dans la production, dont 59 politiques ;
- les 10 premiers résultats viennent du **HNSW de production non filtré** : `query`, `n_results=10`, client HTTP.

### Résultat

| Condition | Candidates |
| --- | --- |
| Meilleure politique entre 0,085 et 0,100 | **2** |
| 8 premiers résultats non filtrés tous des produits | 1 057 |
| **Les deux** | **0** |

Les 2 candidates de la fenêtre 0,085–0,100 :

| Question | Source (première rencontrée) | Distance policy (exacte) | Document policy | Rang exact | 8 premiers HNSW tous des produits ? | Top-3 HNSW non filtré |
| --- | --- | --- | --- | --- | --- | --- |
| Quel est le délai pour retourner un produit ? | `docs/evaluation/ragas_results.json` (aussi `tests/test_retriever.py:20`, depuis `7fb0896`) | 0,0918 | `policy-sav-retours-0000` | 1 | **non** : 10 politiques | `policy-sav-retours-0000` 0,092 ; `policy-sav-retours-0006` 0,250 ; `policy-sav-retours-0001` 0,350 |
| « Q: Quels sont les moyens de paiement acceptés ? R: Carte bancaire, espèces à la livraison. » | `tests/test_reranker.py` (un faux passage de test, pas une question) | 0,0970 | `policy-ecommerce-paiement-0000` | 1 | **non** : 10 politiques | `policy-ecommerce-paiement-0000` 0,097 ; `…-0001` 0,340 ; `…-0004` 0,354 |

Pour la première, les 8 produits les plus proches, avec filtre `type = product`, sont à 0,669–0,715. Le premier est `product-LS-MO-000071`.

### Observation annexe : cas actuels où une politique proche est ratée sans filtre

Dans l'index de production actuel, 5 candidates ont une politique à moins de 0,3, alors que leurs 8 premiers résultats non filtrés sont tous des produits. Aucune n'est dans la fenêtre 0,085–0,100. Elles ne sont donc **pas** la question d'origine, mais elles montrent que le phénomène existe encore sans la recherche duale.

| Candidate | Source | Politique (exacte, rang 1) | Distance | Top-3 HNSW non filtré |
| --- | --- | --- | --- | --- |
| Livrez-vous en dehors de Tunis ? | `tests/test_rag_loop.py` | `policy-general-faq-0004` | 0,167 | produits à 0,947 ; 0,949 ; 0,949 |
| La livraison est gratuite à partir de 150 DT d'achat… *(réponse de référence)* | `scripts/evaluate_ragas.py` | `policy-sav-livraison-0003` | 0,153 | produits à 0,629 ; 0,634 ; 0,635 |
| Les instruments de mesure comme les multimètres sont garantis 12 mois… *(réponse de référence)* | `scripts/evaluate_ragas.py` | `policy-sav-garantie-0002` | 0,271 | produits à 0,637 ; 0,638 ; 0,639 |
| Oui, sous 7 jours calendaires après réception… *(réponse de référence)* | `scripts/evaluate_ragas.py` | `policy-sav-retours-0000` | 0,284 | produits à 0,887 ; 0,889 ; 0,893 |
| Une carte Arduino est garantie combien de temps ? | `data/evaluation/recherche.json` (fr) | `policy-sav-garantie-0000` | 0,285 | produits à 0,450 ; 0,459 ; 0,463 |

La ligne Arduino est le cas déjà rapporté dans `hnsw_ef_search.md`.

## Étape 3 : rejeu

**Non fait**, car la question n'est pas retrouvée de façon établie. Pour la candidate plausible, l'index de production actuel donne déjà :
- en recherche exacte, le document idéal au rang 1, à 0,092 ;
- en HNSW non filtré, le même document au rang 1, à 0,092.

## Versions

- Python 3.13.5, numpy 2.5.1, sentence-transformers 5.7.0
- Client chromadb 1.5.9 ; serveur ChromaDB 1.4.1 (image `chromadb/chroma:1.4.1`, l'API répond « 1.0.0 »)
- Collection de production : 11 109 documents, dont 59 politiques ; `space` cosine, `max_neighbors` 16, `ef_construction` 100, `ef_search` 100

## Limites

- **L'index d'origine n'existe plus.**
  - L'anomalie a été observée vers août 2026, sur un index HNSW construit à l'époque. Sa version de ChromaDB n'est pas notée, et ses paramètres et son ordre d'insertion peuvent différer.
  - Le HNSW est approximatif et dépend de la construction. Un cas raté sur l'ancien index peut être trouvé sur l'index actuel, et l'inverse aussi : c'est le cas de la candidate plausible.
  - La seconde condition se teste donc sur un autre index que celui de l'époque.
- **La question n'est peut-être pas dans le dépôt.**
  - Elle a pu être tapée à la main, dans un terminal ou dans l'interface web, sans être enregistrée.
  - La base de conversations PostgreSQL n'a pas été fouillée : elle ne faisait pas partie des sources demandées.
- **Une partie des sources est illisible par texte.**
  - Les 13 images ou documents joints dans la session.
  - Les captures d'écran insérées dans les rapports PDF et DOCX, dont seul le texte a été extrait.
- **Transcripts.** Un seul existe : celui de la session en cours. Il n'y a pas de transcript de la période où l'anomalie a été corrigée (août 2026).
- **Distances.** Elles sont recalculées avec le modèle actuel ; le modèle n'a pas changé depuis. L'écart de 0,0002 entre 0,0918 et 0,092 vient de l'arrondi.
