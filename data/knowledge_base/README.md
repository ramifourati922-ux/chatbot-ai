# Knowledge Base — Liss Strike

Ce dossier contient les informations réelles sur "Liss Strike" que le
chatbot utilise pour répondre (via RAG : recherche sémantique +
génération par le LLM). **Aucun contenu réel n'est encore écrit ici**
— seulement des templates avec des placeholders `[À REMPLIR : ...]`.

## Comment remplir un fichier

Remplace chaque `[À REMPLIR : ...]` par la vraie information sur Liss
Strike. Supprime les lignes d'exemple qui ne s'appliquent pas, ajoute
autant de blocs Q/R que nécessaire. Le format des commentaires (`#`)
en haut de chaque fichier peut rester tel quel — il sert de rappel
pour toi, il n'est pas utilisé par le bot.

## Pourquoi le format "Q: ... / R: ..." ?

Chaque bloc Q/R devient un **chunk** indépendant lors de l'indexation
dans ChromaDB (Tâche 4 — pas encore fait). Concrètement :

1. Le message d'un client est transformé en vecteur (embedding).
2. On cherche les blocs Q/R les plus proches sémantiquement dans la
   base vectorielle (pas besoin que le client tape la question mot
   pour mot — la recherche est sémantique, pas un simple `Ctrl+F`).
3. Les blocs trouvés sont donnés en contexte au LLM (Groq), qui
   reformule une réponse naturelle en respectant la langue du client.

**Règle importante** : chaque bloc Q/R doit être **autonome et
compréhensible sans le reste du fichier** (pas de "comme dit plus
haut" ou "voir ci-dessus") — puisqu'un bloc peut être récupéré seul,
sans son contexte environnant.

## Structure

```text
data/knowledge_base/
├── sav/
│   ├── retours.txt        → politique de retour produit          (+ retours.pdf)
│   ├── livraison.txt      → délais, zones, frais de livraison    (+ livraison.pdf)
│   ├── garantie.txt       → durée et conditions de garantie      (+ garantie.pdf)
│   └── reclamations.txt   → procédure de réclamation, escalade
├── ecommerce/
│   ├── paiement.txt       → moyens de paiement acceptés          (+ paiement.pdf)
│   ├── produits.csv       → catalogue produits (10 000+ lignes)
│   └── promotions.txt     → codes promo, soldes, fidélité        (+ promotions.pdf)
└── general/
    └── faq.txt            → questions générales                 (+ faq.pdf)
```

## ⚠️ Deux formats, deux usages différents — ne pas les confondre

- **`.txt` (Q/R)** : la **source de vérité**, c'est ce que le pipeline
  RAG (Tâche 4) indexe dans ChromaDB. Si tu modifies une politique,
  modifie le `.txt`.
- **`.pdf`** : un **artefact de présentation généré automatiquement**
  à partir du `.txt` correspondant (via `scripts/generate_policy_pdfs.py`),
  utile pour un affichage/téléchargement côté site web ou pour une
  démo/soutenance. Le RAG ne les lit PAS directement (un PDF doit être
  reconverti en texte avant d'être chunké, ce qui casserait la
  découpe propre "un bloc Q/R = un chunk"). **Si tu modifies un `.txt`,
  relance le script pour régénérer le PDF correspondant** — sinon ils
  se désynchronisent.
- **`produits.csv`** : catalogue généré par combinatoire via
  `scripts/generate_products_catalog.py` (valeur × puissance × package
  pour les résistances, longueur × couleur × densité pour les rubans
  LED, etc. — comme le fait un vrai distributeur de composants). Pour
  regénérer/ajuster le catalogue, modifie le script puis relance-le
  (`./venv/Scripts/python.exe scripts/generate_products_catalog.py`).

**Tout le contenu actuel (txt/csv/pdf) est marqué `⚠️ CONTENU EXEMPLE`**
— généré pour la démo, à valider/remplacer avant toute mise en
production réelle.

## Ajouter une nouvelle catégorie/fichier Q/R

Crée un nouveau `.txt` dans le sous-dossier approprié (ou un nouveau
sous-dossier), en suivant le même format Q/R. Le script d'ingestion
(Tâche 4) parcourra automatiquement tout `data/knowledge_base/**/*.txt`
— aucune configuration supplémentaire n'est nécessaire pour qu'un
nouveau fichier soit pris en compte.
