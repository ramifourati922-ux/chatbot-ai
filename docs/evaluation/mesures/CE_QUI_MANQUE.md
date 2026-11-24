# Ce qui manque avant le rapport (soutenance du 3 décembre 2026)

- **Date de l'audit :** 25/11/2026 vers 00:00, branche `mesures-rapport`.
- **Ce que j'ai fait :** lecture seule, sauf deux choses :
  - `data/eval/intents_test.csv` a été généré (tâche B) ;
  - 2 requêtes ont été envoyées à Groq : une sans token (liste des modèles) et une de 73 tokens, pour lire les en-têtes de quota.
- **Ce que je n'ai pas fait :** rien n'est commité, `app/` n'est pas modifié, aucune mesure n'est lancée.

## A. Audit

| # | Élément | État | Chemin exact | Action à faire par toi |
| --- | --- | --- | --- | --- |
| 1 | Feuille d'annotation remplie | **absent** | `data/evaluation/annotation_juge/feuille_annotation_remplie.csv` | La remplir (voir B2) |
| 1 bis | Feuille vierge | présent, **0 item rempli sur 30** | `data/evaluation/annotation_juge/feuille_annotation.csv` | Partir de ce fichier |
| 2 | Jeu de test des intentions | **incomplet** : 50 candidats, **étiquettes non validées** | `data/eval/intents_test.csv` | Relire et corriger les 50 lignes (voir B1) |
| 3 | RAGas hybrid | **incomplet** : 17 questions notées sur 22 | `docs/evaluation/mesures/ragas_hybrid.partial.json` | Relancer avec `--resume` (voir A3) |
| 4 | Branche `securite-contre-mesures` | **non sauvegardée** : patch appliqué dans le worktree, **non commité** | `C:\Users\ramif\chatbot-ai-securite` | Décider : commit sur cette branche, ou abandon |
| 4 bis | Travail d'évaluation sur `mesures-rapport` | **non sauvegardé** : 72 entrées non suivies (92 fichiers en comptant le contenu des dossiers) + `docker-compose.yml` modifié | `C:\Users\ramif\chatbot-ai` | Commit (après relecture et recherche de secrets), ou au minimum une copie |
| 5 | Scripts ajoutés | **non suivis par Git** | `scripts/measure_faux_refus.py`, `scripts/evaluate_ragas_hybrid.py`, `scripts/measure_securite_llm.py` | À inclure dans le commit |

### A1. Feuille d'annotation
- **`feuille_annotation_remplie.csv` : absent.**
- **`feuille_annotation.csv` :**
  - 30 items (A01 à A30), séparateur `;`, encodage UTF-8 ;
  - 9 colonnes : `item`, `question`, `reponse_de_reference`, `passages_recuperes`, `reponse_generee`, `fidelite`, `pertinence`, `rappel`, `commentaire` ;
  - **remplies sur 0 des 30 lignes :** `fidelite`, `pertinence`, `rappel`, `commentaire`. Les 5 premières colonnes sont pleines.

### A2. `data/eval/intents_test.csv`
- **Avant la tâche B :** 1 ligne (les en-têtes seuls), 0 message.
- **Après la tâche B :** 50 messages candidats, tous marqués « à valider par l'auteur ».
- **Par intention :** human_agent 10, frustration 10, order_tracking 10, help 10, general 10.
- **Par langue :** fr 15, en 10, ar 10, tn 15.
- **Par écriture :** latine 25, arabe 15, arabizi 10.
- **Contrôle de chevauchement :**
  - aucun message n'est identique à l'une des 196 phrases de `data/intents/exemples.json` (après normalisation de la casse et de la ponctuation) ;
  - deux premiers candidats étaient en double : l'un figurait dans `exemples.json`, l'autre dans `dev.json` ou `test.json`. Ils ont été remplacés ;
  - le contrôle ne porte que sur l'identité exacte, pas sur la ressemblance : une paraphrase proche d'un exemple n'est pas détectée.

### A3. RAGas hybrid : ce qui reste
- **Notées :** 17 questions sur 22. **Reste :**
  - 5 questions notées : `ar-garantie`, `ar-paiement`, `tn-garantie`, `tn-sfax`, `tn-probleme` ;
  - 3 hors-sujet, sans juge : `off-couscous`, `off-jupiter`, `off-capitale`.
- **Quota restant du juge `openai/gpt-oss-20b`** (en-têtes lus le 24/11 à 23:59, après un appel de 73 tokens) :

  | En-tête | Valeur |
  | --- | --- |
  | `x-ratelimit-limit-requests` | 1000 |
  | `x-ratelimit-remaining-requests` | 863 |
  | `x-ratelimit-reset-requests` | 3h17m16.8s |
  | `x-ratelimit-limit-tokens` | 8000 |
  | `x-ratelimit-remaining-tokens` | 7927 |
  | `x-ratelimit-reset-tokens` | 547ms |

  - **Le quota journalier de tokens (TPD), celui qui a bloqué RAGas, n'apparaît dans aucun en-tête.** Son reste est donc **inconnu**.
  - Ce qu'on peut dire : l'appel de 73 tokens a réussi, donc le TPD n'était pas entièrement épuisé à 23:59.
  - Rien n'indique que les ~75 000 tokens nécessaires (≈ 15 000 par question au rythme du 24/11) soient disponibles. C'est une estimation.
  - La documentation des limites est à `https://console.groq.com/docs/rate-limits` (page qui répond 200, non lue ici).
- **Commande :** `venv/Scripts/python.exe scripts/evaluate_ragas_hybrid.py --resume`. Si le quota est atteint de nouveau, le script s'arrête et garde un point de reprise.

### A4. Branches Git
**Branches locales :**

| Branche | Commit | Sur origin ? |
| --- | --- | --- |
| backup-avant-reecriture | c45557c | non |
| feat/intentions-entrainees | 490961f | non |
| feat/menu-accueil | 2e7df3c | non |
| feat/qualite-soutenance | 6617d54 | oui (à jour) |
| integration/menu-qualite | a0c0cd3 | non |
| main | c5d26c7 | oui (à jour) |
| **mesures-rapport** (actuelle) | a0c0cd3 | non |
| **securite-contre-mesures** (worktree) | a0c0cd3 | non |

**`securite-contre-mesures`** (dossier `C:\Users\ramif\chatbot-ai-securite`) :
- 4 fichiers de `app/` modifiés **non commités** : `websocket.py`, `dialogue_manager.py`, `order_tracking.py`, `llm_factory.py` ;
- non suivis : `scripts/purge_retention.py`, et des copies des scripts et données de mesure.
- **Un `git worktree remove --force` ou une suppression du dossier ferait tout perdre.** Le patch d'origine reste dans `docs/evaluation/contre_mesures_llm.patch`, lui-même non suivi.

**Ce qui n'est sauvegardé nulle part :**
- tout le travail d'évaluation des remarques 33 à 57 et des mesures du 24/11 : 92 fichiers non suivis dans `C:\Users\ramif\chatbot-ai`, dont `Dockerfile`, `.dockerignore`, les scripts, les rapports et les données d'évaluation ;
- la modification de `docker-compose.yml`.

Les 5 branches locales qui ne sont pas sur origin ne sont pas sauvegardées non plus.

**À noter :**
- `scripts/measure_escalation_latency.py`, dont dépendent `measure_securite_llm.py`, `measure_faux_refus.py` et `measure_hallucination.py` pour le nettoyage, est lui aussi **non suivi**.
- `data/evaluation/annotation_juge/cle_secrete.json` est non suivi. **Ne pas l'ouvrir avant d'avoir annoté.**

### A5. Scripts
| Script | Suivi par Git ? |
| --- | --- |
| `scripts/measure_faux_refus.py` | **non** |
| `scripts/evaluate_ragas_hybrid.py` | **non** |
| `scripts/measure_securite_llm.py` | **non** |

## B. Fichiers à remplir par toi

### B1. `data/eval/intents_test.csv` (50 candidats)
- **Colonnes :**
  - `message` ;
  - `intention_attendue` (`human_agent` | `frustration` | `order_tracking` | `help` | `general`) ;
  - `langue` ;
  - `ecriture` ;
  - `statut`.
- **Format :** séparateur virgule, UTF-8 avec BOM, ce qui permet de l'ouvrir dans Excel.
- **À faire :**
  1. Relire chaque message.
  2. Corriger `intention_attendue` si l'étiquette proposée te semble fausse. **C'est ton jugement qui fait foi.**
  3. Mettre `statut` à `validé`. Supprimer une ligne, ou en ajouter, est possible.
- **Temps estimé :** 20 à 30 minutes.
- **Ensuite :** demander la mesure (exactitude, précision, rappel et F1 par intention, matrice de confusion, routage avec et sans classificateur). Ne pas la lancer avant la validation.

### B2. Feuille d'annotation du juge
La feuille est **utilisable**. Les consignes sont dans `docs/evaluation/annotation_juge/consignes.md`, et la version lisible dans `data/evaluation/annotation_juge/feuille_annotation.md`.

**Attention au nom du fichier.** Les consignes disent de remplir `feuille_annotation.csv`, mais le script de comparaison lit **`feuille_annotation_remplie.csv`**. Procédure exacte :

1. **Copier** `feuille_annotation.csv` vers `feuille_annotation_remplie.csv`, dans le même dossier.
2. **Annoter les 30 items** (A01 à A30) **sans ouvrir `cle_secrete.json`** et sans chercher les notes du juge ni le mode (Basic ou Advanced). Pour chaque ligne, remplir 3 colonnes avec **0**, **0,5** ou **1** :

   | Colonne | Question | 1 | 0,5 | 0 |
   | --- | --- | --- | --- | --- |
   | `fidelite` | Toutes les affirmations de la réponse sont-elles soutenues par les passages affichés ? | toutes | certaines non | la plupart non, ou inventées |
   | `pertinence` | La réponse répond-elle à la question ? | oui | partiellement | non |
   | `rappel` | Les passages contiennent-ils l'information de la réponse de référence ? | toute | une partie | aucune |
   | `commentaire` | facultatif | | | |

   **Cas particulier :** une réponse honnête « je n'ai pas l'information » vaut 1 en fidélité. Sa pertinence se juge à part.
3. **Ne pas modifier** les autres colonnes ni l'ordre des lignes. Garder le séparateur `;`. La virgule décimale (0,5) est acceptée.
4. **Si tu utilises Excel**, enregistrer en « CSV UTF-8 (délimité par des points-virgules) », sinon l'arabe sera abîmé. Le plus simple est de lire `feuille_annotation.md` à l'écran et de saisir les notes dans le CSV.
5. **Lancer** `venv/Scripts/python.exe scripts/compare_juge_humain.py`. Le script calcule l'accord exact, le kappa de Cohen pondéré, les désaccords et le sens du biais.

**Temps estimé :** 60 à 90 minutes, soit 2 à 3 minutes par item, car les passages sont longs. Le calcul prend moins d'une minute.

## C. Politique de Groq : pages à consulter (non lues, aucun résumé)
Chaque URL a été vérifiée le 25/11/2026 : elle répond (HTTP 200). Leur contenu n'a pas été lu.

| URL | Questions à y chercher |
| --- | --- |
| https://groq.com/privacy-policy | Quel pays et quelle entité juridique traitent les données ? Quelles données sont collectées via l'API ? Durée de conservation ? Transferts internationaux et garanties ? |
| https://groq.com/terms-of-use | Les contenus envoyés (prompts, réponses) peuvent-ils servir à entraîner ou améliorer les modèles ? Qui en est propriétaire ? Responsabilités du client ? |
| https://console.groq.com/docs/your-data | Combien de temps les requêtes API sont-elles conservées ? Existe-t-il une option sans conservation (zéro rétention) ? Usage pour l'entraînement ? |
| https://trust.groq.com | Où sont hébergés les serveurs (pays, régions) ? Quelles certifications (SOC 2…) ? Quelle liste de sous-traitants ? Existe-t-il un accord de traitement des données (DPA) téléchargeable ? |
| https://console.groq.com/docs/legal | Quels documents contractuels s'appliquent à l'API (conditions, DPA, politique d'usage) ? |
| https://console.groq.com/docs/rate-limits | Valeurs du quota journalier de tokens (TPD) de `gpt-oss-20b` et `gpt-oss-120b` sur l'offre gratuite |

**URL essayées qui n'existent pas (404)**, à ne pas citer :
- `groq.com/services-agreement` ;
- `groq.com/data-processing-addendum` ;
- `groq.com/subprocessors` ;
- `console.groq.com/docs/data-retention`.

**Pour le rapport :** noter pour chaque fait la page, la date de consultation et la citation exacte. Ces pages changent.

## Checklist finale « à faire par moi »

Les temps sont des estimations.

| Priorité | Tâche | Temps estimé |
| --- | --- | --- |
| **1** | **Sauvegarder le travail**, que rien ne protège aujourd'hui : relire, chercher les secrets, puis commit sur `mesures-rapport` (92 fichiers non suivis, dont les scripts et `measure_escalation_latency.py`) ; décider du sort de `securite-contre-mesures` (commit sur la branche, ou abandon en gardant le `.patch`) | 20 à 30 min |
| **1** | **Annoter les 30 items** du juge (B2), puis lancer `compare_juge_humain.py` | 60 à 90 min |
| **1** | **Terminer RAGas hybrid** : `--resume` (5 questions + 3 hors-sujet), puis refaire la comparaison sur 22 questions | 15 à 30 min de calcul, selon les 429 ; à refaire un autre jour si le quota TPD bloque encore |
| **1** | **Lire les 6 pages Groq** (C) et noter pays, durée de conservation et entraînement, avec date et citation | 30 à 45 min |
| 2 | Valider les 50 étiquettes de `data/eval/intents_test.csv` (B1), puis demander la mesure du classificateur | 20 à 30 min, plus environ 10 min de mesure |
| 2 | Corriger les consignes d'annotation : le nom de fichier attendu est `feuille_annotation_remplie.csv` | 2 min |
| 2 | Décider si le rapport présente les contre-mesures D1–D7 comme une piste (mesurée : 8/44 → 4/44, non significatif) ou comme appliquées | 10 min |
| 3 | Supprimer l'image Docker obsolète `lissstrike-api:test` (6,76 Go) avec `docker rmi lissstrike-api:test` | 1 min |
| 3 | Supprimer le dossier `C:\c\`, créé par erreur lors de la mesure de couverture (remarque 50) | 1 min |
| 3 | Ajouter `WS_SESSION_SECRET` dans `.env` (sinon la clé de session WebSocket change à chaque redémarrage du conteneur) | 5 min |
| 3 | Vérifier pourquoi Docker Desktop s'est arrêté deux fois le 24/11 (mémoire de WSL ?) avant de relancer de longues mesures | 15 min |
