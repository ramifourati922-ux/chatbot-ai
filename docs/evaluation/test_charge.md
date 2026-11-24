# Test de charge du chat web (remarque 49)

Mesure du 24/11/2026 par `scripts/measure_load.py`. Données brutes : `data/evaluation/test_charge.json`, avec chaque requête.
- **Base de connaissances.** La collection `liss_strike_kb` est seulement lue.
- **Code.** Le code applicatif n'est pas modifié.
- **Canaux.** Aucun message WhatsApp ni Messenger.
- **Base de données.** Les lignes créées sont supprimées par identifiant exact (voir plus bas).

## Réponse courte

- **La boucle d'événements n'est pas bloquée.** Tout le travail lourd (recherche, reclassement, appel Groq) passe par `asyncio.to_thread`. Une tâche de sonde dans la même boucle garde un retard p95 de **6 à 20 ms**, jusqu'à 50 clients simultanés.
- **Le gain de la concurrence est réel mais limité.**
  - Avec le LLM simulé (0,83 s), le débit passe de 0,58 req/s (1 client) à **1,45 req/s (50 clients)**, soit 2,7 fois le traitement séquentiel.
  - Il plafonne parce que la **recherche est limitée par le processeur** : les embeddings et le reclassement sont calculés sur CPU, dans les threads, en concurrence entre eux. Le pool par défaut est de 20 threads.
- **Avec le vrai LLM, la charge s'arrête dès 5 clients simultanés.** Groq renvoie **5 réponses 429** (limite de jetons par minute) sur 15 requêtes. L'application bascule alors sur le modèle de secours, et la montée en charge a été arrêtée là, comme prévu.
- **Le p90 de 3 295 ms n'est pas retrouvé aujourd'hui.** Mesuré ce jour sur 60 requêtes séquentielles, il vaut 7 382 ms. Il est dû à la **latence de Groq**, très variable (LLM : médiane 2 986 ms, p90 6 817 ms), et non à quelques questions : la même question prend 1,4 s puis 6,1 s. La recherche, elle, reste stable (médiane 554 ms, p90 918 ms).

## Étape 0 : lecture du code

### a) Le chat est-il asynchrone de bout en bout ?

**Oui, pour la boucle d'événements.**
- **Point d'entrée de la page web.** `websocket_endpoint` (`app/api/routes/websocket.py:93`) est une coroutine : `await websocket.receive_text()`, puis `await handle_message(...)` (l. 144), puis `await websocket.send_json(...)`.
- **Point d'entrée HTTP.** `POST /chat/` est lui aussi `async`, et fait `await handle_message` (`app/api/routes/chat.py:40,70`).
- **Webhooks WhatsApp et Messenger.** Ils sont `async`, et leurs envois vers Meta passent par `httpx.AsyncClient` (`whatsapp.py:112`, `messenger.py:103`).
- **Dans `handle_message`.**
  - Sessions Redis : `redis.asyncio`.
  - Suivi de commande et persistance : SQLAlchemy asynchrone. La persistance tourne en tâche de fond.
  - Appelés directement dans la boucle, mais très courts : la détection de langue, les règles d'intention (expressions régulières), l'expansion de l'arabizi et la construction de la requête.

### b) Les appels lourds

| Étape | Comment elle est appelée | Où |
| --- | --- | --- |
| Recherche complète : embedding de la question (`HuggingFaceEmbeddings`, synchrone), ChromaDB (`chromadb.HttpClient`, client HTTP **synchrone**), BM25 (numpy), reclassement (`CrossEncoder`, synchrone) | **`asyncio.to_thread`** : tout `retriever.search` s'exécute dans un thread | `dialogue_manager.py:701` : `hits = await asyncio.to_thread(retriever.search, rag_query, 4)` |
| Appel Groq (`ChatGroq.invoke`, synchrone, pas `ainvoke`), y compris la bascule sur le modèle de secours | **`asyncio.to_thread`** | `dialogue_manager.py:761` ; `llm_factory.py:156,164` (`llm.invoke`) |
| Intentions apprises (si elles sont activées) | `asyncio.to_thread` | `dialogue_manager.py:563` |
| Préchargement au démarrage (modèles, index BM25) | `asyncio.to_thread` | `main.py:81` |

Aucun de ces appels n'est attendu nativement en asynchrone, et **aucun ne s'exécute de façon synchrone dans la boucle**. La limite est le **pool de threads par défaut** d'asyncio : `min(32, nombre de CPU + 4)`, soit **20 threads** sur cette machine (16 threads matériels). Au-delà de 20 appels simultanés, les suivants attendent un thread libre.

### c) Lancement en production et cache

- **Lancement.** Le seul fichier de lancement est le `Dockerfile` (non suivi par git). Il contient `CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]` : **un seul processus**, sans `--workers` ni gunicorn. Le README ne donne que `uvicorn app.main:app --reload`, pour le développement. Aucune configuration d'hébergement n'existe dans le dépôt.
- **Cache de réponses : absent.** Les `lru_cache` du code (`config.py:225`, `embedding_service.py:44`, `reranker.py:38`, `vector_store.py:22,27`, `llm_factory.py:86`, `analytics.py:250`) ne gardent que des objets : la configuration, les modèles, les clients. Il n'y avait donc **rien à désactiver**. Chaque requête refait la recherche et l'appel au LLM.

## Méthode

- **Serveur.**
  - C'est le vrai `app.main:app`, avec son démarrage complet (préchargement des modèles et de l'index BM25).
  - Il est lancé **dans le processus du script** par `uvicorn.Server`, en un seul processus comme le `Dockerfile`, sur `127.0.0.1:8000`, en mode advanced avec l'expansion de l'arabizi active.
  - Il tourne dans le processus du script pour que la sonde partage sa boucle d'événements.
- **Point d'entrée : le WebSocket `/ws/{client_id}`**, celui de `static/chat.html`.
  - Chaque requête fait `GET /chat/session` (identifiant signé), ouvre la connexion avec l'en-tête `Origin` de la page, envoie **un** message, reçoit la réponse et ferme.
  - Chaque requête a donc une session neuve, sans historique.
  - **La latence mesurée va de l'envoi du message à la réception de la réponse.**
- **Changé en mémoire seulement : les limites de débit WebSocket** (`RATE_LIMIT_WS_MESSAGES` portée à 100 000/min, `RATE_LIMIT_WS_CONNECTIONS` à 10 000). Elles sont comptées par IP, et tous les clients du test partagent 127.0.0.1 : sans ce changement, le limiteur de l'API aurait lui-même refusé les requêtes. **En production, un seul client est limité à 20 messages par minute.**
- **Questions.** 20 questions distinctes, tirées avec la graine 42 parmi 108 questions des bancs (`recherche.json`, `recherche_tunisien_nouvelles.json`, Ragas avec sources). On ne garde que celles qui vont réellement au LLM : aucune règle ne les intercepte, et leur confiance atteint le seuil. Elles sont envoyées à tour de rôle. **Aucune escalade** n'a eu lieu pendant le test.
- **Mode A (réel).** N = 1, puis 5, avec arrêt au premier 429. Le palier N = 1 compte 60 requêtes (chaque question 3 fois) : il sert aussi à l'étape 3 et de référence séquentielle.
- **Mode B (LLM simulé).** `dialogue_manager.ask` est remplacé en mémoire par une fonction qui dort **0,83 s** et renvoie un texte fixe.
  - J'ai utilisé `time.sleep` plutôt que `asyncio.sleep` : `ask` est exécuté dans un thread (`asyncio.to_thread`), et on ne peut pas y passer une coroutine. Le comportement vu par la boucle est identique à un appel réseau dans un thread.
  - Paliers : N = 1, 5, 10, 20 et 50, avec 3 × N requêtes par palier.
- **Sonde de blocage.** Une tâche de la boucle du serveur dort 10 ms en boucle, et enregistre de combien elle se réveille en retard.
- **Durées de recherche et de LLM.** Ce sont les colonnes `retrieval_ms` et `llm_ms` que l'application enregistre avec chaque message, lues en base avant le nettoyage.
- **Gain par rapport au séquentiel.**
  - Pour chaque requête du palier, on prend la latence médiane de la même question au palier N = 1. Le gain est la somme de ces latences, divisée par le temps total du palier.
  - Pour le mode B, la référence est la médiane du palier N = 1 : seulement 3 requêtes.

## Résultats

| Mode | N | Requêtes | Erreurs | 429 Groq | Médiane (ms) | p90 | p95 | Max | Recherche, médiane (ms) | LLM, médiane (ms) | Durée du palier (s) | Débit (req/s) | Gain vs séquentiel | Sonde : retard p95 / max (ms) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B (LLM 0,83 s) | 1 | 3 | 0 | — | 1 863 | 1 911 | 1 917 | 1 923 | 984 | 830 | 5,2 | 0,58 | 1,07 | 6,3 / 39 |
| B | 5 | 15 | 0 | — | 6 778 | 7 112 | 7 343 | 7 701 | 5 798 | 831 | 21,0 | 0,72 | 1,33 | 9,1 / 49 |
| B | 10 | 30 | 0 | — | 7 856 | 9 657 | 9 934 | 10 907 | 6 892 | 833 | 26,2 | 1,15 | 2,13 | 14,1 / 85 |
| B | 20 | 60 | 0 | — | 13 333 | 15 631 | 15 874 | 16 185 | 12 064 | 837 | 43,3 | 1,39 | 2,58 | 16,5 / 101 |
| B | 50 | 150 | 0 | — | 29 908 | 38 717 | 43 119 | 53 531 | 22 125 | **10 478** | 103,4 | 1,45 | 2,70 | 20,1 / 692 |
| **A (réel)** | 1 | 60 | 0 | 0 | 3 661 | 7 382 | 8 144 | 9 769 | 554 | 2 986 | 234,4 | 0,26 | 1,00 | 6,2 / 22 |
| A | 5 | 15 | 0 | **5** | 12 673 | 16 438 | 18 155 | 18 830 | 1 048 | 10 339 | 36,7 | 0,41 | 1,37 | 6,3 / 15 |

La montée en charge du mode A s'arrête à N = 5 (429). N = 10, 20 et 50 ne sont **pas mesurés**, puisque l'arrêt au premier 429 est demandé et que la limite de jetons de Groq les rendrait non représentatifs.

**Lecture :**
- **La boucle n'est pas bloquée.** Le retard de la sonde reste de 6 à 20 ms au p95 dans tous les paliers. Le pic de 692 ms à N = 50 est isolé : c'est la contention du GIL entre 20 threads de calcul, pas un appel synchrone dans la boucle.
- **Le plafond vient du processeur.**
  - La recherche, qui calcule l'embedding de la question et le reclassement de 20 candidats sur CPU, passe de 1 s seule à 6 s pour 10 clients, puis 12 s pour 20 et 22 s pour 50, alors que le LLM simulé reste à 0,83 s jusqu'à N = 20.
  - Le débit plafonne vers **1,4 à 1,45 req/s** : les attentes réseau se recouvrent, mais pas les calculs.
- **À N = 50, le pool de 20 threads est saturé.** Le « LLM » simulé passe à 10,5 s de médiane : la mesure inclut l'attente d'un thread libre avant le `sleep` de 0,83 s.
- **Mode A, N = 5.** Groq a renvoyé 5 fois « Rate limit reached for model `openai/gpt-oss-120b` … service tier `on_demand` on tokens per minute (TPM) ». Ces 5 requêtes ont été servies par le modèle de secours, `openai/gpt-oss-20b` : c'est le comportement normal de l'application, sans erreur visible pour le client. La latence médiane monte à 12,7 s. **Le facteur limitant en réel est le quota de Groq, avant le processeur.**

## Étape 3 : N = 1, 60 requêtes, mode réel

| Mesure | p50 | p90 | p99 | Moyenne |
| --- | --- | --- | --- | --- |
| Latence de bout en bout (ms) | 3 661 | 7 382 | 9 144 | 3 900 |
| Temps serveur (`processing_time_ms`) | 3 654 | 7 377 | — | — |
| Recherche (`retrieval_ms`) | 554 | 918 | — | — |
| LLM (`llm_ms`) | 2 986 | 6 817 | — | — |

**Les 5 requêtes les plus lentes :**

| Latence (ms) | Recherche (ms) | LLM (ms) | Question |
| --- | --- | --- | --- |
| 9 769 | 526 | 9 238 | famma capteur DHT22 ? |
| 8 710 | 513 | 8 188 | Vous avez des piles 18650 en stock ? |
| 8 514 | 939 | 7 568 | el colis wsel w na9es fih article, chnouwa na3mel ? |
| 8 125 | 425 | 7 691 | Vous vendez des analyseurs logiques 8 canaux ? |
| 7 738 | 597 | 7 131 | Je cherche un capteur ultrason HC-SR04 |

**Le p90 vient-il de quelques questions ? Non.**
- Les 6 requêtes au-dessus du p90 viennent de **5 questions différentes**.
- **La lenteur vient du LLM** : 30 réponses sur 60 dépassent 3 s de LLM, et aucune recherche ne dépasse 2 s.
- **Une même question peut être rapide ou lente** : « Do you have a loyalty program… » prend 1 424, 6 121 et 5 081 ms ; « el colis wsel w na9es fih article… », 2 290, 5 726 et 8 514 ms.

**Comparaison avec le p90 de 3 295 ms du rapport.** La médiane LLM antérieure, d'environ 0,83 s, est la valeur donnée dans la consigne de cette mesure ; elle n'a pas été remesurée ici. Groq était aujourd'hui environ 3,6 fois plus lent en médiane. Le p90 dépend donc surtout du **moment de la mesure et de la charge de Groq**, que le projet ne contrôle pas. Le comparer à l'exigence ENF2 demande de dire qu'il s'agit d'un **temps de service tiers**.

## Base de données

| | Utilisateurs | Conversations | Messages |
| --- | --- | --- | --- |
| Avant | 120 | 124 | 506 |
| Supprimés (par identifiant exact des 334 sessions du test, échauffement compris) | 334 | 334 | 668 |
| Après | 120 | 124 | 506 |

157 sessions Redis ont été supprimées, et il en reste 0 pour ces identifiants. Le décalage entre les 334 sessions et les 157 clés Redis n'a pas été élucidé ; les clés manquantes ont pu expirer ou ne jamais être créées. **0 ligne de test ne subsiste.**

Après l'écriture des résultats, la fermeture de Python a affiché des « RuntimeError: Event loop is closed » : ce sont des connexions de base libérées après la fin de la boucle, **sans effet sur les mesures ni sur le nettoyage**. Cet incident est relevé dans le journal de la mesure.

## Limites

- **Machine.** Intel Core i9-11900H (8 cœurs, 16 threads), 15,7 Go de RAM, sans GPU, Windows 11. Les clients de charge tournent sur la **même machine** que le serveur, et leur coût CPU s'ajoute à celui du serveur. ChromaDB, PostgreSQL et Redis tournent dans Docker, sur la même machine.
- **Réseau vers Groq.** Latence et charge non maîtrisées : une seule fenêtre de mesure, le 24/11/2026. Les quotas du compte (niveau `on_demand`) limitent le mode A à N = 5. Au total, environ 75 appels Groq ont été faits : 60, plus 15 dont 5 servis par le modèle de secours.
- **Un seul processus uvicorn**, comme le `Dockerfile`. Plusieurs workers multiplieraient la capacité de calcul, mais aussi la mémoire, puisque chaque worker charge ses modèles et son index BM25. Ce n'est **pas mesuré**.
- **Petits effectifs.** 20 questions, une seule session par requête, sans historique. Seulement 3 requêtes pour le palier B, N = 1, qui sert de référence au gain du mode B.
- **Limites de débit relevées en mémoire.** En production, un client ne peut pas envoyer plus de 20 messages par minute.
- **Pas de test HTTP séparé.** `POST /chat/` passe par le même `handle_message` que le WebSocket.
