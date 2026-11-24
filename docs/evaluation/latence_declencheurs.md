# Latence des déclencheurs d'escalade à règles

Mesuré par `scripts/measure_escalation_latency.py` (le 23/11/2026), sur `POST /chat/`, API démarrée en local.

## Méthode

- **Messages** : messages de `data/intents/test.json` que la règle concernée détecte réellement (`IntentClassifier.classify`, sans LLM), et dont l'étiquette est la bonne. Seuls 4 messages (demande explicite), 3 (frustration) et 3 (suivi de commande, sans numéro) sont détectés : **moins de 20 messages distincts par catégorie**. Chaque message a donc été réutilisé, dans une **session neuve à chaque appel**, jusqu'à 20 appels par catégorie.
- **Appel** : un `POST /chat/` par message, au format de l'application (`{"message": …, "channel": "web"}`, session attribuée et signée par le serveur). Chronométrage côté client avec `time.perf_counter`, jusqu'à la réponse complète. Deux appels d'échauffement (« bonjour ») non comptés. Appels espacés de 3,2 s pour rester sous la limite de débit (`RATE_LIMIT_CHAT` = 20/minute par IP).
- **Suivi de commande** : le transfert n'a lieu qu'au **2e message** sans numéro valide (le 1er reçoit une relance qui demande le numéro). Chaque mesure enchaîne donc deux messages dans la même session ; la latence retenue est celle du 2e (le transfert), celle de la relance est donnée à part. Sans numéro, la base des commandes n'est pas interrogée.
- **Temps serveur** : champ `processing_time_ms` de la réponse. Le code n'expose pas de temps par étape sur les chemins d'escalade (les champs `retrieval_ms` et `llm_ms` n'existent que sur le chemin RAG) : temps par étape **non mesuré**.

### Messages retenus

| Catégorie | Messages distincts | Langues des messages | Langues des 20 appels |
| --- | --- | --- | --- |
| Demande explicite | 4 : « je veux un humain », « passez-moi un responsable », « can I talk to a human please », « nheb na7ki m3a wa7ed » | fr 2, en 1, tn 1 | fr 10, en 5, tn 5 |
| Frustration | 3 : « c'est scandaleux, j'attends depuis dix jours », « I'm fed up with you », « your customer service is terrible and nobody cares » | fr 1, en 2 | fr 7, en 13 |
| Suivi de commande | 3 : « suivi de ma commande », « my order hasn't arrived », « وين الكوموند متاعي » | fr 1, en 1, tn 1 | fr 7, en 7, tn 6 |

Aucun message en arabe littéraire n'est détecté par les règles dans ce jeu.

## Résultats

### Latence de bout en bout (client, ms)

| Catégorie | n | Médiane | p95 | Min | Max |
| --- | --- | --- | --- | --- | --- |
| Demande explicite | 20 | 13,0 | 21,7 | 9,3 | 21,7 |
| Frustration | 20 | 12,5 | 19,5 | 10,6 | 21,6 |
| Suivi de commande (2e message, transfert) | 20 | 20,0 | 30,2 | 13,1 | 36,0 |
| Suivi de commande (1er message, relance) | 20 | 18,7 | 28,6 | 11,1 | 31,3 |

### Temps de traitement côté serveur (`processing_time_ms`, ms)

| Catégorie | n | Médiane | p95 | Min | Max |
| --- | --- | --- | --- | --- | --- |
| Demande explicite | 20 | 6,5 | 9,1 | 4 | 10 |
| Frustration | 20 | 6,0 | 8,1 | 5 | 10 |
| Suivi de commande (transfert) | 20 | 12,0 | 20,0 | 6 | 20 |

### Appel au LLM évité ?

| Catégorie | Escalade signalée dans la réponse (`escalated`, `escalation_reason`) | Réponse = message fixe d'escalade, sans source | Appel au LLM |
| --- | --- | --- | --- |
| Demande explicite | 20/20 (`explicit`) | 20/20 | évité |
| Frustration | 20/20 (`frustration`) | 20/20 | évité |
| Suivi de commande | 20/20 (`order_tracking`) | 20/20 | évité |

La réponse est comparée au texte renvoyé par `_get_escalation_message(motif, langue)` ; aucune source RAG n'est renvoyée. Les latences (10 à 36 ms) sont aussi incompatibles avec un appel à Groq (médiane d'environ 2 s sur le chemin RAG).

Réponse renvoyée, une fois par catégorie :

| Catégorie | Message | Réponse |
| --- | --- | --- |
| Demande explicite | « je veux un humain » | « Je vous mets en relation avec un conseiller humain. Quelqu'un va prendre le relais très rapidement. » |
| Frustration | « c'est scandaleux, j'attends depuis dix jours » | « Je comprends votre frustration et je suis désolé pour la gêne occasionnée. Je vous mets immédiatement en relation avec un conseiller humain qui pourra mieux vous aider. » |
| Suivi de commande | « suivi de ma commande » (2e fois) | « Je n'arrive pas à retrouver votre commande. Je vous mets en relation avec un conseiller qui pourra vérifier son statut. » |

## Vérification en base

Après les appels (écritures PostgreSQL en tâche de fond, attendues 3 s) : 62 utilisateurs de test (2 d'échauffement + 60 sessions mesurées), 62 conversations, 164 messages. **60 conversations au statut `escalated`** (2 `active` : l'échauffement), et motifs enregistrés dans les messages du bot : `explicit` 20, `frustration` 20, `order_tracking` 20.

## Nettoyage

Suppression des seules lignes créées, par identifiant : 164 messages, 62 conversations, 62 utilisateurs (`external_id` exacts `web:<session_id>` des sessions renvoyées par le serveur), 62 sessions Redis (`session:web:<session_id>`). Relecture : 0 ligne restante pour ces identifiants. Totaux de la base identiques avant et après la mesure : 120 utilisateurs, 124 conversations, 506 messages.

Un premier passage a été mesuré avec des résultats très proches (médianes 14,1 / 13,9 / 20,1 ms), mais son nettoyage automatique a échoué (deux boucles asyncio dans le script, corrigé depuis) : ses 62 sessions ont été retrouvées par des critères stricts (utilisateurs `web:` créés pendant la mesure, dont tous les messages sont des messages de test), puis supprimées par identifiant ; même retour aux totaux de départ.

Les identifiants de session ne sont pas préfixés « latbench- » : `/chat/` attribue lui-même un UUID signé, et le secret de signature n'étant pas fixé (`WS_SESSION_SECRET` vide, secret éphémère du processus), un identifiant choisi par le client serait refusé (403). La liste exacte des identifiants créés est enregistrée dans `latence_declencheurs_sessions.json`.

## Versions et machine

- Python 3.13.5, FastAPI 0.115.0, Uvicorn 0.30.0, SQLAlchemy 2.0.36, httpx 0.27.0 (client de mesure)
- API lancée en local : `uvicorn app.main:app --host 127.0.0.1 --port 8000` (un seul processus), `RAG_RETRIEVAL_MODE` = advanced, `INTENT_MODEL_ENABLED` = false (règles seules)
- PostgreSQL 16, Redis 7, ChromaDB 1.4.1 en conteneurs Docker sur la même machine
- CPU Intel Core i9-11900H, 15,7 Go de RAM, sans GPU, Windows 11

## Limites

- **Moins de 20 messages distincts par catégorie** (4, 3 et 3) : la latence porte sur 20 appels, mais la variété des formulations est faible ; aucune frustration en tunisien et aucun message en arabe littéraire ne sont détectés par les règles.
- **Serveur local, sans charge concurrente, latence réseau nulle** : les valeurs sont des minimums ; en production, il faut ajouter le réseau et la charge.
- **Suivi de commande mesuré dans un seul cas** : transfert après une relance sans numéro. Les deux autres cas, numéro introuvable après relance et base des commandes indisponible, ne sont **pas mesurés** (le second exigerait d'arrêter PostgreSQL).
- **Temps par étape non mesuré** : le code n'en expose pas sur les chemins d'escalade.
- Le temps client inclut la sérialisation HTTP locale ; l'écriture PostgreSQL se fait après la réponse (tâche de fond) et n'est pas comptée, comme pour un vrai client.
