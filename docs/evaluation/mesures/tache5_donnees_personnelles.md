# Tâche 5 : données personnelles

Ce document repose uniquement sur la lecture du code. Il relève des faits, avec le fichier et la ligne, et ne conclut rien sur la conformité légale.

Code lu : branche `mesures-rapport`, issue de `a0c0cd3`. Les contre-mesures D1–D7 n'y sont pas appliquées.

## 1. Données envoyées à Groq (à chaque appel du LLM)

| Donnée | Envoyée ? | Preuve |
| --- | --- | --- |
| Message courant du client, texte intégral | **Oui**, sans masquage | `app/services/rag/llm_factory.py:140` (`HumanMessage(content=user_text)`) ; appel `app/services/dialogue_manager.py:761-763` |
| Historique de la session (messages du client, du bot et du conseiller) | **Oui** : les 6 derniers messages, 500 caractères chacun au plus, sans masquage | `dialogue_manager.py:221` (`HISTORY_MESSAGES_FOR_LLM = 6`), `:762` ; `llm_factory.py:113`, `:134-139` |
| Passages de la base de connaissances (contexte RAG, 4 passages) | Oui | `dialogue_manager.py:701-705` ; `llm_factory.py:131` |
| Prompt système et consigne de langue | Oui | `llm_factory.py:51-83`, `:128-129` |
| Identifiant de session (numéro WhatsApp, PSID Messenger, identifiant web) | **Non** : absent des paramètres de `build_messages` | `llm_factory.py:116-117` |
| Nom affiché, canal | Non | idem |
| Données de commande (statut, articles, total) | Non : le suivi de commande ne passe pas par le LLM | `dialogue_manager.py:637` (règle), `app/services/order_tracking.py:92-105` |
| Masquage ou minimisation avant l'envoi | **Aucun** | aucune transformation entre `build_messages` et `llm.invoke` (`llm_factory.py:152-156`) |

**Ce que le client tape part tel quel à Groq**, avec ses 6 derniers messages : un nom, un numéro de téléphone, une adresse.

## 2. Stockage et durée de conservation

| Où | Ce qui est stocké | Durée | Preuve |
| --- | --- | --- | --- |
| Redis, clé `session:<identifiant>` | Identifiant de session (numéro WhatsApp ou PSID **en clair**), 20 derniers messages, contexte (compteur RAG, relance de commande) | **1 h** après la dernière activité, renouvelée à chaque lecture | `app/services/session_manager.py:26` (`SESSION_TTL = 3600`), `:87`, `:133-141` |
| Mémoire du processus (si Redis est indisponible) | Même contenu | **Aucune expiration**, jusqu'au redémarrage | `session_manager.py:56`, `:63` (`_memory_store[key] = value`) |
| PostgreSQL `users` | `external_id` = numéro WhatsApp, PSID ou `web:<uuid>`, **en clair** ; `display_name` = `User_` suivi des 8 premiers caractères de l'identifiant ; canal ; langue | **Illimitée** | `dialogue_manager.py:331-333` ; `app/db/repositories/user_repository.py:85-87` |
| PostgreSQL `conversations` | Canal, statut, contexte (JSON), dates | Illimitée | `app/models/conversation.py:13-62` |
| PostgreSQL `messages` | **Texte intégral** des messages du client, du bot et du conseiller ; métadonnées (intention, sources, motif d'escalade, durées) | Illimitée | `conversation.py:97-112` ; écriture `dialogue_manager.py:322-369` |
| PostgreSQL `orders` | Numéro, statut, articles, total, client (`user_id`) | Illimitée | `app/models/order.py:35-49` |
| Journaux (sortie standard) | Identifiants masqués (`mask_id`), pas le texte des messages ; mais `client_id` WebSocket et numéro de commande en clair | Selon l'hébergement : aucune rotation dans le code | `app/log_privacy.py:31-41` ; `app/api/routes/websocket.py:49`, `:53` |

## 3. Purge et effacement
- **Purge automatique : aucune.** Il n'y a ni tâche planifiée ni durée de rétention dans `app/config.py`.
- **Suppression d'un client : désactivation seulement.** `DELETE /users/{id}` ne fait que désactiver le compte (`is_active=False`, `app/api/routes/users.py:105-118`). Les données restent.
- **Cascades en base :**
  - la suppression d'un client entraîne celle de ses conversations, puis de ses messages (`conversation.py:25`, `:89`, `ON DELETE CASCADE`) ;
  - ses commandes sont conservées, détachées du client (`order.py:40`, `ON DELETE SET NULL`).
- **`scripts/cleanup_test_data.py`** ne supprime que les données de test.

## 4. Information du client
- **Aucune mention dans le message d'accueil** : seulement « Choisissez un sujet, ou écrivez votre question : » (`app/services/welcome_menu.py:83-88`).
- **Aucune mention dans le widget** : `static/chat.html` ne contient aucune mention sur les données ni lien de confidentialité.
- **Hébergement, pays et rétention chez Groq : non documentés dans le dépôt.**
