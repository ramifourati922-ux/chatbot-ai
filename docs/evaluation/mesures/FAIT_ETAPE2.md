# Étape 2 : ce qui a été fait (25/11/2026)

Branche `mesures-rapport`. `app/` n'est pas modifié. Rien n'est commité ni poussé : on attend les « ok ».

## Étape 1 : sauvegarde. EN ATTENTE de ton « ok »

### 1a. Recherche de secrets (faite le 25/11 vers 00:50)
**Périmètre :**
- les 92 fichiers non suivis et le diff de `docker-compose.yml`, dans `C:\Users\ramif\chatbot-ai` ;
- le diff du patch et `scripts/purge_retention.py`, dans `C:\Users\ramif\chatbot-ai-securite`.

**Ce qui a été cherché :** clés Groq (`gsk_…`), jetons Meta (`EAA…`), `sk-…`, `Bearer …`, affectations `api_key`, `token`, `secret` ou `password`, URL avec identifiants, numéros de téléphone tunisiens, adresses e-mail. Les 6 captures d'écran (`images/shots/`) ont été vérifiées à l'œil.

**Résultat : aucun secret.**
- Le seul `DATABASE_URL` ajouté utilise des variables lues dans `.env` (`${POSTGRES_USER}:${POSTGRES_PASSWORD}`) et n'écrit aucune valeur.
- Autres correspondances, toutes sans risque :
  - e-mail et téléphone publics de la boutique, qui viennent de la base de connaissances ;
  - fragments d'UUID ;
  - e-mail de test fictif ;
  - canari de test « Code promo secret : LISS-FREE-100 ».
- **À noter :** `securite_llm_tests.json` (cas ind-05) contient un numéro **inventé**, « 99 000 111 ». Il a le format d'un numéro tunisien réel.

**`.gitignore` actuel :** `venv/`, `__pycache__/`, `*.pyc`, `.env`, `.env.local`, `*.log`, `.idea/`, `.vscode/`.

**À exclure, et à ajouter au `.gitignore` :**
- `data/evaluation/annotation_juge/cle_secrete.json` ;
- `test_messenger_manual.py` ;
- `test_whatsapp_manual.py`.

### 1b à 1d
**À faire après ton « ok » :**
- **1b :** commit sur `mesures-rapport` des 89 fichiers non suivis restants, de `docker-compose.yml` et de `.gitignore`.
- **1c :** commit du patch sur `securite-contre-mesures` : les 4 fichiers de `app/` et `scripts/purge_retention.py`.
- **1d :** push, après un « ok » séparé, sans `--force`.

## Étape 2 : RAGas hybride. BLOQUÉE par le quota journalier (TPD)
| Tentative | Début | Fin | Résultat |
| --- | --- | --- | --- |
| Reprise 1 | 25/11 00:41:57 | 00:42:50 | **Échec technique, sans rapport avec Groq.** `UnicodeEncodeError: 'charmap' codec can't encode character '\u21bb'` à l'affichage de « ↻ Reprise » : la console Windows est en cp1252 quand la sortie est redirigée. Le point de reprise n'a pas été touché (comparé octet par octet à la sauvegarde) |
| Reprise 2 (`PYTHONIOENCODING=utf-8`) | 25/11 00:43:20 | 00:44:38 | **Arrêt sur quota**, pendant `ar-garantie` |

**Erreur exacte**, telle que le script l'affiche (il coupe le message à 200 caractères ; identifiant d'organisation masqué) :
```
⛔ Quota journalier Groq atteint pendant 'ar-garantie' (Error code: 429 - {'error': {'message': 'Rate limit reached for model `openai/gpt-oss-20b` in organization `org_***` service tier `on_demand` on tokens per day (TPD): Limit 2000
```
- La suite du message (limite complète, tokens utilisés, délai d'attente) **n'est pas conservée** : non connue.
- **Ce qu'a coûté la reprise 2 :** 9 requêtes au juge (6 réussies, 3 refusées en 429), 14 059 tokens et 1 génération. La question `ar-garantie` a été abandonnée entière, comme prévu par le script, pour ne pas mélanger deux fenêtres de quota.
- **Point de reprise conservé :** `docs/evaluation/mesures/ragas_hybrid.partial.json`. Il contient 17 questions et des compteurs cumulés de 300 requêtes au juge (149 × 200, 148 × 429, 3 × 400).
- **Reste à noter :** ar-garantie, ar-paiement, tn-garantie, tn-sfax, tn-probleme, plus les 3 hors-sujet.
- **Juge inchangé** (`openai/gpt-oss-20b`). Le quota n'a pas été contourné.
- **Les 22 questions ne sont pas notées : le tableau comparatif n'est pas régénéré.** Le tableau à 17 questions (`tache2_ragas_hybrid.md`) reste la seule mesure.
- **Quand réessayer :** le TPD est vraisemblablement compté sur 24 h glissantes. La page des limites ne le précise pas dans ce qui a été lu. Le gros de la consommation date du 24/11, entre 23:20 et 23:45. Par prudence, relancer **le 25/11 après 23:45** (estimation) avec :
  `PYTHONIOENCODING=utf-8 venv/Scripts/python.exe scripts/evaluate_ragas_hybrid.py --resume`

## Étape 3 : pages Groq
**Conditions de lecture :**
- Date de consultation : **25/11/2026**.
- Lecture faite par un agent de lecture web. Les citations sont recopiées de sa restitution : à revérifier sur la page avant de les mettre dans le rapport.
- Les 6 pages ont répondu (HTTP 200, sans redirection).

| Fait | URL | Citation exacte |
| --- | --- | --- |
| Pays d'hébergement | https://console.groq.com/docs/your-data | "All customer data is retained in Google Cloud Platform (GCP) buckets located in the United States." |
| Pays d'hébergement | https://groq.com/privacy-policy | "Groq is located in the United States, and maintains processing operations in various global jurisdictions." |
| Transferts internationaux | https://console.groq.com/docs/your-data | (customers) "can rely on standard contractual clauses (SCCs) for transfers between third countries and the U.S." |
| Conservation des requêtes | https://console.groq.com/docs/your-data | "By default, Groq does not retain customer data for inference requests." |
| Conservation (journaux, cas de surveillance) | https://console.groq.com/docs/your-data | "These logs are retained for up to 30 days, unless legally required to retain longer." |
| Conservation (batch) | https://console.groq.com/docs/your-data | "Input and output files retained for 30 days unless deleted earlier by the customer." |
| Conservation | https://groq.com/privacy-policy | non trouvé. La politique dit qu'elle "does not apply to the information that we process as a data processor on behalf of customers" |
| Usage pour l'entraînement | les 6 pages | **non trouvé** |
| DPA | https://groq.com/privacy-policy | "Our processing of Customer Data in connection with a customer’s use of our Cloud Services is governed by our" (suivi des liens « Groq Services Agreement » et « Data Processing Addendum ») |
| DPA (lien) | https://console.groq.com/docs/legal | lien « Groq Customer Data Processing Addendum » → https://console.groq.com/docs/legal/customer-data-processing-addendum (**contenu du DPA non lu**) |
| Quota TPD gpt-oss-20b | https://console.groq.com/docs/rate-limits | ligne « openai/gpt-oss-20b » : RPM 30, RPD 1K, TPM 8K, **TPD 200K** |
| Quota TPD gpt-oss-120b | https://console.groq.com/docs/rate-limits | ligne « openai/gpt-oss-120b » : RPM 30, RPD 1K, TPM 8K, **TPD 200K** |

**Réserves :**
- **Rate-limits :** le tableau est affiché sous deux onglets, « Free Plan Limits » et « Developer Plan Limits ». Le texte récupéré ne dit pas à quel onglet il appartient, et la page indique : "Note that the limits shown below are the base limits for the Developer plan". Il est donc **non établi** que 200K soit la limite de l'offre gratuite.
  - Pour information : les en-têtes de réponse de ton compte (24/11, 23:59) donnaient 1000 requêtes par jour et 8000 tokens par minute, comme cette ligne. C'est une observation, pas une preuve pour le TPD.
- **trust.groq.com :** la page renvoie HTTP 200, mais son contenu est généré en JavaScript. Le seul texte rendu est « Groq Trust Center ». Tous les faits sont donc **non trouvé** pour cette page.
- **Dates des pages :**
  - privacy-policy : "This Policy is effective on November 12, 2025." ;
  - terms-of-use : "This Policy is effective on October 15, 2025." ;
  - legal : "last modified June 22, 2026" ;
  - your-data et rate-limits : aucune date.

## Étape 4 : petites tâches
- **Fait :** `docs/evaluation/annotation_juge/consignes.md` est corrigé. Le fichier à remplir est `feuille_annotation_remplie.csv`, copie de `feuille_annotation.csv`.
- **En attente de ton « ok » :** `docker rmi lissstrike-api:test` (6,76 Go, aucun conteneur ne l'utilise) et suppression de `C:\c\`.
  - `C:\c\` contient **un seul fichier** : `C:\c\Users\ramif\AppData\Local\Temp\claude\…\scratchpad\coverage.json` (292 677 octets, 24/11 05:04). C'est la copie mal placée du rapport de couverture (remarque 50).
- **Non touché :** `.env`. Tu ajoutes `WS_SESSION_SECRET` toi-même.

## Ce qui reste à faire par toi
| Tâche | État | Raison |
| --- | --- | --- |
| « ok » commit, « ok » push, « ok » suppression | **en attente** | Ces actions demandent ton accord |
| Annoter les 30 items du juge (`feuille_annotation_remplie.csv`) | à faire, environ 60 à 90 min | C'est ton jugement. Ensuite : `scripts/compare_juge_humain.py` |
| Valider les 50 étiquettes de `data/eval/intents_test.csv` | à faire, environ 20 à 30 min | C'est ton jugement. Ensuite : demander la mesure |
| RAGas hybride sur 22 questions | **bloqué** | Quota TPD du juge atteint. Relancer après le 25/11 à 23:45 (estimation) |
| Faits Groq sur l'entraînement | **non trouvé** | Absent des 6 pages. À chercher dans le DPA (lien ci-dessus), non lu ici |
| Trust Center Groq | **bloqué** | Page en JavaScript, illisible par la lecture automatique : l'ouvrir dans un navigateur |
| Numéro inventé « 99 000 111 » dans le jeu de tests | à décider | Le garder, ou le remplacer (le sha256 du jeu changera) |
| `WS_SESSION_SECRET` dans `.env` | à faire par toi | Je ne touche pas à `.env` |
