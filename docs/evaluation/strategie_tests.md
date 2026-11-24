# Stratégie de tests logiciels (remarque 50)

Relevé du 24/11/2026, au commit `a0c0cd3` (branche `integration/menu-qualite`). Données brutes : `data/evaluation/strategie_tests.json`.
- **État git.** Aucun fichier suivi n'est modifié. Les fichiers non suivis sont les livrables de mesure (`docs/evaluation/`, `scripts/measure_*`), le `Dockerfile`, `.dockerignore`, `escalade.json`, `images/` et les scripts manuels `test_*_manual.py`.
- **Ce qui n'a pas été touché.** Ni `app/` ni les tests n'ont été modifiés. La base de connaissances n'a été que lue.
- **Mesures ajoutées sans modifier le code.** Un plugin pytest externe, chargé avec `-p`, a compté les appels Groq et relevé l'état de la base.

## 1. Inventaire

`pytest tests --collect-only -q` collecte **653 tests**, ce qui confirme le chiffre du rapport. **515** sont unitaires et **138** d'intégration, selon le marqueur `integration` défini dans `tests/conftest.py`.

| Thème | Fichier | Tests | Unitaires | Intégration | Nature : ce qui est réel, ce qui est simulé |
| --- | --- | --- | --- | --- | --- |
| Sécurité des webhooks et des sessions | `test_whatsapp_signature.py` | 9 | 9 | 0 | Client HTTP ASGI. Requêtes signées avec un secret de test (fixture `sign_whatsapp`) ; envoi vers l'API Graph remplacé par une liste d'appels |
| | `test_messenger_signature.py` | 9 | 9 | 0 | Idem pour Messenger, avec une boîte d'envoi factice |
| | `test_chat_session_signature.py` | 9 | 9 | 0 | Client HTTP. Signature HMAC de l'identifiant de session web |
| | `test_websocket_security.py` | 20 | 19 | 1 | `TestClient` WebSocket. Origine, signature, séparation des sessions web et WhatsApp |
| | `test_cors.py` | 9 | 9 | 0 | Client HTTP. En-têtes CORS et requêtes préalables (preflight) |
| Limitation de débit | `test_rate_limit.py` | 12 | 6 | 6 | HTTP et WebSocket (`TestClient`). Les compteurs sont remis à zéro par une fixture automatique |
| | `test_login_throttling.py` | 6 | 6 | 0 | Client HTTP. Échecs de connexion par IP et par identifiant |
| Administration et authentification | `test_admin_auth.py` | 27 | 12 | 15 | HTTP et **PostgreSQL réel** (fixture `agent_accounts` : comptes de test créés puis supprimés, bcrypt au coût 4) |
| | `test_users_auth.py` | 12 | 5 | 7 | HTTP et PostgreSQL |
| | `test_admin_escalations.py` | 7 | 0 | 7 | HTTP et PostgreSQL : file des conversations transférées |
| | `test_admin_reply.py` | 24 | 1 | 23 | HTTP et PostgreSQL. Envoi WhatsApp et Messenger remplacé par une boîte d'envoi |
| Escalade et intentions | `test_intent_classifier.py` | 112 | 112 | 0 | Fonctions pures (règles par expressions régulières) |
| | `test_small_talk.py` | 37 | 27 | 10 | Unitaires pour les règles ; intégration avec PostgreSQL et Redis, plus 1 appel Groq réel |
| | `test_semantic_intent.py` | 25 | 17 | 8 | Unitaires avec embeddings factices (monkeypatch) ; intégration avec le vrai modèle |
| | `test_rag_loop.py` | 17 | 14 | 3 | Réponses du LLM imposées par une fixture (`llm_answers`) ; les 3 tests d'intégration exigent ChromaDB peuplé |
| Suivi de commande | `test_order_tracking.py` | 50 | 38 | 12 | Unitaires (extraction du numéro, mise en forme) ; intégration avec PostgreSQL (commandes de test créées puis supprimées) |
| Recherche, RAG et LLM | `test_hybrid_retriever.py` | 10 | 6 | 4 | Unitaires (RRF, tokenisation) ; intégration avec ChromaDB réel |
| | `test_retriever.py` | 4 | 0 | 4 | ChromaDB réel |
| | `test_reranker.py` | 5 | 3 | 2 | Modèle simulé (monkeypatch) ou vrai modèle de reclassement |
| | `test_embedding_service.py` | 3 | 0 | 3 | Vrai modèle d'embeddings |
| | `test_llm_factory.py` | 4 | 0 | 4 | **Groq réel** (4 appels) |
| | `test_arabizi.py` | 7 | 6 | 1 | Recherche remplacée par une fonction factice |
| | `test_knowledge_base_structure.py` | 25 | 25 | 0 | Lecture des fichiers de la base de connaissances |
| | `test_service_fallback.py` | 6 | 6 | 0 | Recherche ou LLM remplacés par des fonctions qui lèvent une erreur (panne simulée) |
| Langue | `test_language_detector.py` | 67 | 67 | 0 | Fonction pure |
| Dialogue, mémoire et persistance | `test_dialogue_manager.py` | 14 | 0 | 14 | **Redis, ChromaDB et Groq réels** (5 appels) |
| | `test_conversation_memory.py` | 20 | 18 | 2 | Historique factice ; 2 tests avec Groq réel |
| | `test_conversation_persistence.py` | 5 | 0 | 5 | **PostgreSQL réel**, Groq réel (2 appels) |
| Statistiques et prospects | `test_analytics.py` | 17 | 16 | 1 | Calculs sur des enregistrements fabriqués ; 1 test PostgreSQL |
| | `test_leads.py` | 22 | 21 | 1 | Idem |
| Canaux et menu d'accueil | `test_welcome_menu.py` | 49 | 45 | 4 | HTTP ; envoi WhatsApp et Messenger remplacé par une boîte d'envoi |
| Journaux | `test_log_privacy.py` | 10 | 9 | 1 | Capture des journaux ; 1 test avec Groq réel |
| **Total** | 32 fichiers | **653** | **515** | **138** | |

**Totaux par thème :**

| Thème | Tests |
| --- | --- |
| Escalade et intentions | 191 |
| Administration et authentification | 70 |
| Langue | 67 |
| Recherche, RAG et LLM | 64 |
| Sécurité des webhooks et des sessions | 56 |
| Suivi de commande | 50 |
| Canaux et menu d'accueil | 49 |
| Dialogue, mémoire et persistance | 39 |
| Statistiques et prospects | 39 |
| Limitation de débit | 18 |
| Journaux | 10 |

## 2. Nature des tests et environnement

- **Tests unitaires (515).** Ils n'ont besoin d'aucun service : PostgreSQL, Redis, ChromaDB et Groq ne sont pas joints.
  - Les dépendances sont remplacées par `monkeypatch` : recherche factice, LLM qui lève une erreur, embeddings fabriqués, réponses du LLM imposées.
  - Les appels vers Meta sont remplacés par des boîtes d'envoi qui notent les messages au lieu de les envoyer.
  - Les requêtes HTTP et WebSocket passent par les clients de test de FastAPI (`TestClient`, ou `httpx` avec ASGI), sans réseau.
- **Tests d'intégration (138).** Ils sont marqués `integration`, soit à la main, soit automatiquement s'ils utilisent une fixture de base (`DB_FIXTURES` dans `conftest.py`). Ils utilisent les **vrais** PostgreSQL, Redis et ChromaDB, et les vrais modèles. **13 tests appellent réellement Groq, soit 15 appels.**
- **Base de données utilisée : la vraie base de développement.** `conftest.py` utilise `app.db.database`, c'est-à-dire le `DATABASE_URL` du `.env`. **Il n'y a pas de base de test dédiée.** Les tests créent leurs données sous des préfixes (`test-…`) et les suppriment eux-mêmes, mais pas toujours (voir 3).

## 3. Exécution

- **Commande.** `pytest tests -p suiteprobe --cov=app --cov-branch --cov-report=term-missing -rsxX`, une seule exécution.
- **Services.** Ceux de Docker sur la même machine : PostgreSQL 16, Redis 7 et ChromaDB 1.4.1.

| Résultat | Valeur |
| --- | --- |
| Réussis | **653** |
| Échoués | 0 |
| Ignorés (skip) | 0 |
| xfail / xpass | 0 / 0 |
| Avertissements | 5 (dépréciations de bibliothèques, dont `PydanticDeprecatedSince20` sur la configuration par classe) |
| Durée totale | **207,8 s** (3 min 28), couverture comprise |
| Date | 24/11/2026, début à 04:01 UTC |
| Commit | `a0c0cd3` |
| Appels Groq réels | **15**, par 13 tests : `test_llm_factory.py` (4), `test_dialogue_manager.py` (5), `test_conversation_memory.py` (2), `test_conversation_persistence.py` (2), `test_log_privacy.py` (1), `test_small_talk.py` (1). La suite ne peut pas tous les éviter : seul `-m "not integration"` les exclut |

**État de la base, avant et après :**

| | users | conversations | messages | agents | orders | clés Redis |
| --- | --- | --- | --- | --- | --- | --- |
| Avant la suite | 120 | 124 | 506 | 2 | 5 | 0 |
| Après la suite | 123 | 128 | 522 | 2 | 5 | 1 |
| Après suppression par identifiant exact | **120** | **124** | **506** | 2 | 5 | **0** |

**La suite laisse donc des données en base.** Elles ont été supprimées par identifiant exact :
- 3 utilisateurs de test créés pendant l'exécution (`test-memory-…`, `test-rag-loop-…`, `test-rag-satisfaction-…`), avec leurs 3 conversations et 12 messages ;
- 1 conversation de 4 messages, ajoutée à un utilisateur WhatsApp **préexistant** qui porte un numéro fictif de test (`216000000xx`). Seule la conversation a été supprimée, pas l'utilisateur ;
- 1 clé Redis, `session:test-admin-…`.

**Fichiers générés hors du dépôt.**
- Le rapport JSON de couverture a été écrit, à cause d'une erreur de chemin de ma part, dans un dossier `C:\c\Users\ramif\AppData\Local\Temp\claude\…\scratchpad\coverage.json`, qui n'existait pas avant.
- La suppression de `C:\c` a été bloquée par une protection de l'outil : **ce dossier, qui ne contient que ce fichier, est à supprimer à la main**.
- Le fichier `.coverage` créé à la racine du dépôt a été déplacé hors du dépôt.

## 4. Couverture (`--cov=app --cov-branch`)

**Total :**

| Mesure | Valeur |
| --- | --- |
| Lignes | **90,3 %** (2 417 instructions, 235 non exécutées) |
| Branches | **81,6 %** (478 branches, 390 couvertes, 44 partielles) |
| Combiné (lignes et branches, chiffre de coverage.py) | **88,8 %** |

**Modules principaux :**

| Module | Instructions | Non couvertes | Branches | Partielles | Lignes | Combiné |
| --- | --- | --- | --- | --- | --- | --- |
| `services/dialogue_manager.py` | 297 | 4 | 72 | 3 | 98,7 % | 98,1 % |
| `services/rag/hybrid_retriever.py` | 114 | 9 | 28 | 4 | 92,1 % | 90,8 % |
| `services/rag/retriever.py` | 58 | 6 | 22 | 3 | 89,7 % | 86,2 % |
| `services/rag/reranker.py` | 22 | 1 | 4 | 0 | 95,5 % | 96,2 % |
| `services/rag/llm_factory.py` | 43 | 6 | 10 | 2 | 86,0 % | 84,9 % |
| `services/rag/vector_store.py` | 35 | 12 | 4 | 1 | 65,7 % | 61,5 % |
| `services/intent_classifier.py` (règles d'escalade) | 87 | 0 | 24 | 0 | 100 % | 100 % |
| `services/order_tracking.py` | 30 | 0 | 6 | 1 | 100 % | 97,2 % |
| `services/language_detector.py` | 71 | 2 | 26 | 0 | 97,2 % | 97,9 % |
| `services/semantic_intent.py` | 71 | 1 | 12 | 1 | 98,6 % | 97,6 % |
| `services/session_manager.py` | 116 | 18 | 24 | 6 | 84,5 % | 82,9 % |
| `services/agent_auth.py` | 54 | 2 | 12 | 0 | 96,3 % | 97,0 % |
| `services/analytics.py` | 188 | 9 | 62 | 4 | 95,2 % | 94,8 % |
| `api/routes/whatsapp.py` | 88 | 22 | 20 | 2 | 75,0 % | 75,9 % |
| `api/routes/messenger.py` | 87 | 31 | 24 | 3 | 64,4 % | 64,0 % |
| `api/routes/websocket.py` | 69 | 4 | 10 | 0 | 94,2 % | 94,9 % |
| `api/routes/chat.py` | 26 | 0 | 4 | 0 | 100 % | 100 % |
| `api/routes/admin.py` | 118 | 26 | 22 | 0 | 78,0 % | 74,3 % |
| `api/rate_limit.py` | 40 | 0 | 6 | 0 | 100 % | 100 % |
| `api/auth.py` | 19 | 0 | 6 | 0 | 100 % | 100 % |
| `api/web_session.py` | 22 | 0 | 2 | 1 | 100 % | 95,8 % |
| `main.py` | 74 | 20 | 12 | 1 | 73,0 % | 68,6 % |

**Les 5 modules les moins couverts** (au moins 10 instructions, chiffre combiné) :

| Module | Couverture combinée |
| --- | --- |
| `services/rag/vector_store.py` | 61,5 % |
| `db/repositories/conversation_repository.py` | 62,2 % |
| `api/routes/messenger.py` | 64,0 % |
| `db/repositories/user_repository.py` | 67,8 % |
| `main.py` | 68,6 % |

Le détail des 48 fichiers est dans le JSON.

## 5. Intégration continue

Le fichier est `.github/workflows/tests.yml`, avec un seul job, `unit` :

| Point | Contenu |
| --- | --- |
| Déclencheurs | `push` et `pull_request`, sur toutes les branches |
| Environnement | `ubuntu-latest`, Python 3.13, PyTorch CPU puis `requirements.txt` |
| Commande | `python -m pytest tests/ -m "not integration" -q` : **les 515 tests unitaires seulement** |
| Lint | aucun |
| Couverture | non mesurée |
| Services démarrés | **aucun** (ni PostgreSQL, ni Redis, ni ChromaDB). `DATABASE_URL` est factice, et `GROQ_API_KEY` est vide |
| Tests d'intégration | non exécutés en CI. Le fichier précise : « Les tests d'intégration restent à lancer en local avec Docker » |
| Dernier run | **non vérifié** : `gh` n'est pas installé sur la machine, et aucune requête n'a été faite à GitHub |

Le rapport dit « tests exécutés en CI » (ENF6). C'est vrai pour **515 tests sur 653 (79 %)**. Les 138 tests d'intégration ne sont lancés qu'en local.

## 6. Dix tests représentatifs

| Test | Ce qu'il vérifie | Ce qui est simulé |
| --- | --- | --- |
| `tests/test_whatsapp_signature.py::test_wrong_or_missing_signature_is_refused` | Une signature HMAC falsifiée ou absente sur `/webhook/whatsapp` reçoit un 403, et le message n'est pas traité | Secret de test (fixture `sign_whatsapp`) ; envoi vers Meta remplacé par une liste d'appels |
| `tests/test_rate_limit.py::test_ws_too_many_messages_closes_connection` | Au-delà de la limite de messages, le WebSocket est fermé avec « Trop de messages » | `TestClient` WebSocket ; compteurs remis à zéro par une fixture |
| `tests/test_rate_limit.py::test_chat_over_limit_returns_429_with_clear_message` | Au-delà de la limite, `POST /chat/` renvoie 429 avec un message clair | Client HTTP de test |
| `tests/test_dialogue_manager.py::test_escalation_short_circuits_llm` | « je veux parler à un agent humain » est transféré (`explicit`) avec une réponse fixe, avant tout appel au LLM | Rien : intégration avec Redis et la base réels. L'absence d'appel est garantie par le code (retour anticipé), et le test ne l'instrumente pas |
| `tests/test_order_tracking.py::test_found_order_is_answered_from_the_database` | « où est ma commande CMD-… ? » renvoie le statut et la date lus en base, sans source RAG ni transfert, pour chaque statut | Commandes de test créées dans PostgreSQL puis supprimées (fixture `orders`) |
| `tests/test_service_fallback.py::test_llm_failure_transfers_the_client` | Une panne du LLM transfère le client (`service_unavailable`) au lieu de produire une erreur | `ask` remplacé par une fonction qui lève une erreur ; recherche factice |
| `tests/test_language_detector.py::test_technical_unit_notation_is_not_mistaken_for_arabizi` | « capteur 9DOF », « câble de 2m »… restent en français, et ne sont pas pris pour de l'arabizi | Rien : fonction pure |
| `tests/test_rag_loop.py::test_consecutive_no_info_answers_escalate` | Au 3e « je n'ai pas l'information » consécutif, le client est transféré (`repeated_rag_failure`), puis le compteur repart de zéro | Réponses du LLM imposées (fixture `llm_answers`) ; ChromaDB réel |
| `tests/test_login_throttling.py::test_five_failures_then_even_the_right_password_is_refused` | Après 5 mots de passe faux, même le bon mot de passe reçoit un 429 sur `/admin` | Client HTTP de test ; `auth.authenticate` remplacé par une fonction factice (ni base ni bcrypt) ; limite fixée à 5 échecs en 15 minutes |
| `tests/test_websocket_security.py::test_invalid_signature_is_refused` | Un WebSocket dont l'identifiant de session n'a pas une signature valide est fermé (code 1008) | `TestClient` WebSocket |
| `tests/test_websocket_security.py::test_unknown_origin_is_refused` | Les origines non autorisées (`…8000.evil.test`, autre port, `null`) sont refusées à l'ouverture du WebSocket | `TestClient` WebSocket, avec un en-tête `Origin` forgé |

Le tableau compte 11 lignes : deux tests illustrent la limite de débit, l'un en HTTP (429), l'autre en WebSocket (fermeture).

## 7. Tests avec de vrais utilisateurs

**Aucune trace.**
- **Recherche.** Ont été fouillés `README.md`, `docs/` (hors `docs/evaluation/`, produit pendant ces mesures), `CHANGELOG_ADVANCED_RAG.md` et `docs/demo/`, avec les motifs test utilisateur, enquête, questionnaire, retours clients ou personnel, bêta, pilote, satisfaction et entretien.
- **Aucun test avec le personnel de Liss Strike, avec des clients, ni aucune enquête n'est documenté.**
- **Seuls documents proches.** Les scénarios de démonstration pour le jury (`docs/demo/SCENARIO_DEMO_JURY.txt`, `TRANSCRIPTION_DEMO_VERIFIEE.txt`), joués par l'auteur.

## Versions

Python 3.13.5, pytest 8.3.0, pytest-asyncio 0.24.0, pytest-cov 7.1.0 et coverage 7.17.5 (pytest-cov a été **installé dans le venv pour cette mesure**), PostgreSQL 16, Redis 7, ChromaDB 1.4.1. Machine : Intel Core i9-11900H, 15,7 Go de RAM, Windows 11.

## Limites

- **Une seule exécution.** La durée et le succès des tests d'intégration dépendent des services locaux et de Groq. Groq a été appelé 15 fois et n'a pas renvoyé de 429 pendant cette exécution.
- **Couverture mesurée sur l'exécution locale complète.** En CI, avec les seuls tests unitaires, elle serait plus faible ; ce n'est **pas mesuré**.
- **Nature des tests.** Elle est déduite du marqueur `integration` et de la lecture des fichiers (fixtures, monkeypatch, clients). Un fichier peut mêler les deux natures, et les effectifs donnés par fichier séparent bien unitaires et intégration.
- **Pas de base dédiée.** La suite tourne sur la base de développement et y laisse quelques lignes (voir 3).
