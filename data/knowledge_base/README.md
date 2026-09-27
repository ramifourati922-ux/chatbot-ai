# Knowledge Base — Liss Strike

Ce dossier contient la base de connaissances que le chatbot utilise
pour répondre (RAG : recherche dans cette base, puis génération de la
réponse par le LLM à partir des passages trouvés).

**⚠️ Contenu de démonstration.** Les politiques SAV/e-commerce et le
catalogue produits sont **fictifs**, rédigés ou générés pour le projet
(les `.txt` portent la mention `⚠️ CONTENU EXEMPLE` ; le `.csv` est
généré par script, voir plus bas). Ils ne décrivent
pas la vraie boutique Liss Strike : à valider/remplacer avant toute mise
en production réelle.

## Contenu actuel

```text
data/knowledge_base/
├── sav/
│   ├── retours.txt        →  7 Q/R : politique de retour           (+ retours.pdf)
│   ├── livraison.txt      → 12 Q/R : délais, zones, frais          (+ livraison.pdf)
│   ├── garantie.txt       → 10 Q/R : durées et conditions          (+ garantie.pdf)
│   └── reclamations.txt   →  6 Q/R : procédure de réclamation
├── ecommerce/
│   ├── paiement.txt       →  9 Q/R : moyens de paiement            (+ paiement.pdf)
│   ├── promotions.txt     →  6 Q/R : codes promo, soldes, fidélité (+ promotions.pdf)
│   └── produits.csv       → 11 050 produits (catalogue synthétique)
└── general/
    └── faq.txt            →  9 Q/R : questions générales           (+ faq.pdf)
```

Soit **59 chunks de politiques + 11 050 chunks produits = 11 109 chunks**
indexés dans ChromaDB (collection `liss_strike_kb`, métadonnée `type` =
`policy` ou `product`).

## Comment la base est utilisée

1. **Indexation** (`scripts/ingest_knowledge_base.py`) : chaque bloc
   Q/R et chaque ligne produit devient un **chunk**, transformé en
   vecteur (embedding local `paraphrase-multilingual-MiniLM-L12-v2`) et
   stocké dans ChromaDB.
2. **Recherche** (`app/services/rag/`, mode `advanced` par défaut) :
   recherche hybride (sens via les embeddings + mots exacts via BM25,
   fusionnés par RRF) sur 20 candidats, puis reranking par un
   cross-encoder multilingue qui garde les 4 meilleurs. Le client n'a
   pas besoin de taper la question mot pour mot.
3. **Génération** : les chunks retenus sont donnés en contexte au LLM
   (Groq), qui répond dans la langue du client (fr/en/ar/tunisien) sans
   inventer ce qui n'est pas dans le contexte.

Détails, mesures et évaluation RAGas : `CHANGELOG_ADVANCED_RAG.md`.

## Format Q/R — règle importante

```text
Q: Quel est le délai pour retourner un produit ?
R: Vous disposez de 7 jours calendaires à partir de la date de réception...
```

Chaque bloc Q/R (séparé par une ligne vide) est un chunk indépendant :
il doit être **autonome et compréhensible sans le reste du fichier**
(pas de « comme dit plus haut »), car il peut être retrouvé seul. Les
lignes commençant par `#` sont des commentaires, ignorés à l'indexation.

## ⚠️ Trois formats, trois usages — ne pas les confondre

- **`.txt` (Q/R)** : la **source de vérité** des politiques, indexée par
  le RAG. Pour modifier une politique, modifier le `.txt`.
- **`.pdf`** : **artefact de présentation** généré à partir du `.txt`
  (`scripts/generate_policy_pdfs.py`), pour un affichage côté site ou la
  soutenance. **Non indexé** par le RAG (un PDF reconverti en texte
  casserait la découpe « un bloc Q/R = un chunk »). Après modification
  d'un `.txt`, relancer le script, sinon les deux se désynchronisent.
- **`produits.csv`** : catalogue **synthétique**, généré par
  combinatoire (`scripts/generate_products_catalog.py`, graine fixe =
  reproductible) : valeur × puissance × boîtier pour les résistances,
  longueur × couleur × densité pour les rubans LED, etc., comme chez un
  vrai distributeur de composants. Pour l'ajuster, modifier le script
  puis le relancer.

## Après une modification de la base

```bash
./venv/Scripts/python.exe scripts/ingest_knowledge_base.py --reset
```

`--reset` vide la collection avant de ré-indexer (sinon les anciens
chunks restent). Puis **redémarrer l'API** : l'index BM25 de la
recherche hybride est construit en mémoire au démarrage.

## Ajouter un nouveau fichier Q/R

1. Créer le `.txt` dans le sous-dossier approprié, au format Q/R.
2. **L'ajouter à la liste `QR_FILES`** de
   `scripts/ingest_knowledge_base.py` : le script n'indexe que les
   fichiers de cette liste (il ne parcourt pas le dossier
   automatiquement).
3. Ré-indexer avec `--reset` et redémarrer l'API (voir ci-dessus).
