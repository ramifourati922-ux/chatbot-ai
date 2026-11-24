# Données personnelles des canaux WhatsApp et Messenger (remarque 47, § 5.8.2–5.8.3)

Relevé du 24/11/2026.
- **Méthode.** Lecture du code et de la configuration, puis requêtes **en lecture seule** sur PostgreSQL (`SELECT` de comptage) et Redis (`SCAN`, `TTL`).
- **Rien n'est modifié.** Aucune écriture ni suppression, aucun message WhatsApp ou Messenger réel, et le code applicatif n'est pas touché.
- **Affichage.** Les numéros sont masqués (+216 XX XXX 123), et ni clé ni jeton n'est affiché.
- **Périmètre.** Ce document décrit ce que **fait le code**, sans conclusion sur la conformité juridique.

## Synthèse

| Donnée | Où elle est stockée | Durée de conservation | Qui peut la lire | Suppression |
| --- | --- | --- | --- | --- |
| Numéro WhatsApp, brut (chiffres, sans « + ») | Redis : clé `session:<numéro>` et champ `session_id` de la session | **1 h** après la dernière activité, renouvelée à chaque message (`SESSION_TTL = 3600`) | Processus de l'API | Expiration automatique. Si Redis est indisponible, la session est gardée **en mémoire, sans expiration**, jusqu'au redémarrage |
| Numéro WhatsApp, brut | PostgreSQL `users.external_id` (avec `users.channel = 'whatsapp'`) | **Illimitée en l'état** : ni purge, ni tâche planifiée, ni champ d'expiration | Conseillers et admins (`/admin` : liste des transferts, historique, notifications, prospects, **export CSV**) ; admins (`/users`) | **Aucune route.** `DELETE /users/{id}` ne fait que désactiver le compte (`is_active = false`) |
| 8 premiers chiffres du numéro | PostgreSQL `users.display_name` = `User_` + 8 caractères | Illimitée | Admins (`/users`) | Idem |
| Messages du client et réponses (texte, intention, sources, motif d'escalade, durées) | PostgreSQL `messages.content` et `messages.metadata`, liés à `conversations.user_id` | Illimitée | Conseillers (historique des conversations transférées, statistiques) | Idem ; supprimés en cascade avec l'utilisateur (`ON DELETE CASCADE`) |
| Commandes liées au client | PostgreSQL `orders.user_id` | Illimitée | Suivi de commande, par numéro de commande | `ON DELETE SET NULL` : la commande reste, détachée du client |
| PSID Messenger | Mêmes emplacements que le numéro WhatsApp (`session:<psid>`, `users.external_id`, avec `channel = 'messenger'`) | Mêmes durées | Mêmes accès | Mêmes possibilités |
| Identifiant dans les journaux | Sortie standard du processus | Selon l'hébergement : aucun fichier ni rotation dans le code | Qui a accès à la sortie du serveur | — |
| Texte des messages et historique récent | Envoyés à Groq (LLM), pas l'identifiant | Non documenté dans le dépôt | Groq | — |

## A1. Comment le numéro devient l'identifiant

**Webhook WhatsApp** (`app/api/routes/whatsapp.py`) : le numéro de l'expéditeur, tel que Meta l'envoie, devient directement l'identifiant de session.

```python
        message_data = messages[0]
        from_number = message_data.get("from")
        ...
        result = await handle_message(
            message=text_body, session_id=from_number, channel="whatsapp"
        )
```

- **Format.** Le numéro est **utilisé tel quel** : les chiffres envoyés par Meta, sans « + ».
- **Sans préfixe en base.** Le canal est stocké à part, dans `users.channel`.
- **Ni haché, ni signé.** Le canal web, lui, utilise un identifiant signé (`web:<uuid>`, voir `app/api/web_session.py`).

**Session Redis** (`app/services/session_manager.py`) :

```python
    SESSION_TTL = 3600
    PREFIX = "session:"
    ...
    async def get_session(self, session_id: str) -> Optional[dict]:
        key = f"{self.PREFIX}{session_id}"
        data = await self._redis_get(key)
        if data:
            await self._redis_expire(key, self.SESSION_TTL)
```

- **La clé est `session:<numéro>`.** La session contient `session_id`, le numéro, ainsi que l'historique des messages et le contexte.
- **Repli sans expiration.** Si Redis tombe, `_memory_store[key] = value` garde la session en mémoire, sans durée de vie.

**PostgreSQL** (`app/services/dialogue_manager.py:331-333` et `app/db/repositories/user_repository.py:65-87`) :

```python
            # external_id = identifiant de session du canal : numéro
            # WhatsApp, PSID Messenger, client_id WebSocket...
            user, _ = await UserRepository(db).get_or_create(session_id, channel)
...
            external_id=external_id,
            ...
            display_name=display_name or f"User_{external_id[:8]}"
```

- **Colonnes de `users`.** `id`, `external_id` (le numéro), `channel`, `display_name` (`User_` + les 8 premiers chiffres), `language`, `is_active`, `extra_data`, `created_at` et `updated_at`.
- **Conversations et messages.** Ils sont rattachés par `conversations.user_id`. Le texte est dans `messages.content`, les métadonnées dans `messages.metadata`.

**Journaux** (`app/log_privacy.py`) :

```python
def mask_id(identifier) -> str:
    """"21600000021" → "216…21" ; "web:9d093a47-…" → "web:9d09…" ;
    un identifiant court est remplacé par "…"."""
    ...
    if bare.isdigit():
        return f"{prefix}{bare[:3]}…{bare[-2:]}"
```

- **Masquage.** Les journaux ne gardent que l'indicatif du pays et les 2 derniers chiffres.
- **Vérification.** Aucun appel `logger.*` ne contient `session_id`, `from_number`, `psid`, `external_id` ou `customer_id` sans `mask_id`.
- **Pas de texte de message.** Le texte n'est jamais journalisé, d'après le docstring de `log_privacy.py`.

## A2. Durée de conservation : code et mesure

- **Redis.**
  - **Code.** `SESSION_TTL = 3600` s, renouvelé à chaque lecture (`get_session` → `expire`) ; une conversation active reste donc en mémoire tant qu'elle continue, puis 1 h après le dernier message.
  - **Mesure** (`SCAN session:*`, lecture seule) : **0 clé** au moment du relevé, et aucune autre clé dans Redis. Aucune session n'est active, ce qui est cohérent avec la durée d'une heure. Le **TTL réel d'une clé existante n'a donc pas pu être mesuré**, et il aurait fallu écrire pour en créer une.
- **PostgreSQL.**
  - **Code.** Ni purge, ni tâche planifiée, ni colonne d'expiration, ni politique de rétention n'ont été trouvées dans `app/` ou `scripts/`. **La conservation est illimitée en l'état.**
  - **Seuls outils de suppression.** `scripts/cleanup_test_data.py`, réservé aux données de test, et `DELETE /users/{id}`, qui désactive sans supprimer.
  - **Mesures (comptages) :**

    | Canal | Utilisateurs | Conversations | Messages | Plus ancien message |
    | --- | --- | --- | --- | --- |
    | web | 115 | 114 | 400 | 28/09/2026 01:00 UTC |
    | whatsapp | 5 | 10 | 106 | 28/09/2026 23:35 UTC |
    | messenger | 0 | 0 | 0 | — |

  - **Numéros WhatsApp.** Les 5 `external_id` sont des numéros (chiffres seuls), et leurs 5 `display_name` valent `User_` + 8 chiffres. Parmi eux, **4 sont des numéros fictifs de test** (`216000000xx`) et **1 a le format d'un numéro réel** (+216 XX XXX 321), avec 74 messages. Il est stocké en clair, sans limite de durée.
  - **Autres comptes.** Aucun utilisateur n'est désactivé, et 5 commandes sont liées à un utilisateur.
- **Journaux.**
  - `app/main.py` appelle seulement `logging.basicConfig(level=logging.INFO)`. Il n'y a **aucun fichier de journal**, aucun gestionnaire de rotation et aucun dossier `logs/` dans le dépôt.
  - La conservation dépend donc de l'endroit où la sortie standard est récupérée (terminal, Docker, hébergeur) : elle n'est **pas fixée par le code**.
  - L'identifiant y est masqué (`216…21`).
- **Exports et statistiques.**
  - `/admin/leads` et `/admin/leads.csv` (`app/api/routes/admin.py:74-110`, `app/services/analytics.py:294-302`) produisent la liste des prospects, avec un `customer_id` **en clair** (numéro WhatsApp ou PSID). Le champ est décrit ainsi : « N° WhatsApp, PSID Messenger ou session web », avec `recontactable` vrai pour WhatsApp et Messenger.
  - Le CSV téléchargé échappe ensuite à l'application.
  - `/admin/stats` donne des statistiques agrégées par canal.

## A3. Droits et suppression

| Besoin | Présent dans le code ? |
| --- | --- |
| Supprimer les données d'un client à partir de son numéro (route) | **Absent** |
| Anonymiser un client | **Absent** |
| Exporter les données d'un client (droit d'accès) | **Absent** : l'export `leads.csv` est commercial et porte sur tous les prospects |
| `DELETE /users/{user_id}` (`app/api/routes/users.py:105-120`, rôle admin) | Existe, mais il **désactive seulement** (`UserUpdate(is_active=False)`) : messages et numéro restent |
| `scripts/cleanup_test_data.py --id <external_id> --apply` | Existe. Il supprime l'utilisateur, ses conversations et messages en cascade, ses commandes, et sa clé Redis. Il est conçu pour les données de test (motifs `diag-`, `test-`, `216000000xx`), mais `--id` accepte n'importe quel identifiant : c'est le **seul moyen technique de supprimer un client, en ligne de commande, par un administrateur du serveur** |

## A4. Information du client

**Aucune information du client n'a été trouvée.**
- **Lieux fouillés :** `app/`, `data/knowledge_base/`, `static/chat.html`, `static/admin.html`, `README.md` et `docs/`, avec les motifs données, personnel, confidentialité, vie privée, privacy, conserv, enregistr, rétention, RGPD, 2004-63, INPDP, consentement, cookie, خصوصية et بيانات.
- **Rien ne parle au client de la conservation.** Aucun texte ne lui dit que son numéro et ses messages sont conservés, ni combien de temps, par qui ou dans quel but.
- **La seule phrase proche de la base de connaissances** concerne le paiement (`ecommerce/paiement.txt:16`) : « Liss Strike ne stocke aucune donnée de c[arte]… ».

Textes exacts que le client voit au premier contact :

| Langue | Réponse à la salutation | Introduction du menu |
| --- | --- | --- |
| fr | « Bonjour ! Je suis l'assistant Liss Strike. Je peux vous aider sur nos produits, la livraison, les retours ou la garantie. Que puis-je faire pour vous ? » | « Choisissez un sujet, ou écrivez votre question : » |
| en | « Hello! I'm the Liss Strike assistant. I can help you with our products, delivery, returns or warranty. How can I help you? » | « Choose a topic, or type your question: » |
| ar | « مرحباً! أنا المساعد الآلي لـ Liss Strike. يمكنني مساعدتك بخصوص منتجاتنا، التوصيل، الإرجاع أو الضمان. كيف يمكنني مساعدتك؟ » | « اختر موضوعًا، أو اكتب سؤالك: » |
| tn | « Aslema! Ena l'assistant mta3 Liss Strike. Najjem n3awnek fel produits, livraison, retour wala garantie. Chnowa t7eb? » | « Ekhtar sujet, walla ekteb sou2alek : » |

Le message d'accueil dit qu'il s'agit d'un **assistant automatique**, mais pas que la conversation est enregistrée.

## A5. Qui peut lire le numéro

L'authentification est HTTP Basic, sur la table `agents`, avec deux rôles : `agent` et `admin` (`app/api/auth.py:33-55`).

| Écran ou route | Rôle requis | Le numéro est-il visible ? |
| --- | --- | --- |
| `/admin` : liste des conversations transférées (`/admin/escalations`) | conseiller (`require_agent`) | **Oui, en clair** : colonne « customer » (`static/admin.html:285`, champ `customer_id`) |
| `/admin` : historique d'une conversation | conseiller | **Oui** (`static/admin.html:367`, `conv-customer`) |
| Notification du navigateur à chaque nouveau transfert | conseiller | **Oui** : « Client : ${e.customer_id} » (`static/admin.html:492`) |
| `/admin/statistiques` : liste des prospects | conseiller | **Oui** (`static/statistiques.html:320`) |
| `/admin/leads.csv` : export | conseiller | **Oui**, colonne `client` du fichier |
| `/users` : liste, lecture, modification et désactivation des utilisateurs | admin (`require_admin`) | **Oui** : `external_id` et `display_name` |
| Journaux | quiconque lit la sortie du serveur | Masqué (`216…21`) |

## A6. Cadre légal cité dans le dépôt

**Aucune mention n'a été trouvée** de la loi organique n° 2004-63 sur la protection des données personnelles, de l'INPDP, du RGPD, ni d'un document de conformité, dans `README.md`, `docs/` ou `app/`.

Le dépôt traite seulement de la **confidentialité des journaux** : `app/log_privacy.py`, et README lignes 109 et 525 (« journaux sans données personnelles ni secrets »). Ce document ne conclut pas sur la conformité.

## B1. Messenger : ce qui est implémenté et testé

Le canal est défini dans `app/api/routes/messenger.py`, créé par le commit `56b5c7d` (21/08/2026) puis complété par `963b3fb`, `1ad7018`, `f00b235` et `2e7df3c` (07/10/2026).

| Fonction | Implémentée | Où |
| --- | --- | --- |
| Vérification du webhook par Meta (`GET`, `hub.verify_token`) | oui | `verify_webhook` |
| Signature HMAC-SHA256 (`X-Hub-Signature-256`, `MESSENGER_APP_SECRET`) ; refus sans secret | oui | `_verify_signature` (l. 62-78) |
| Démarrage refusé si Messenger est configuré sans secret | oui | `main.lifespan` |
| Filtre `is_echo` (copies des messages envoyés par la page elle-même) | oui | l. 152 |
| Identifiant de session = PSID (`sender.id`) | oui | l. 142, 165 |
| Envoi de la réponse par l'API Graph (`/me/messages`, `access_token` en paramètre) | oui, mais **simulé sans jeton** : « MESSENGER_PAGE_ACCESS_TOKEN non configuré — envoi simulé » | `_send_messenger_message` (l. 82-110) |
| Menu d'accueil en réponses rapides (`quick_replies`) | oui | l. 173-177 |
| 4 langues | oui : même moteur (`handle_message`) et menus de `welcome_menu` en fr, en, ar et tn | — |
| Réponse d'un conseiller au client (`/admin`) | oui | `admin.py:_send_to_customer` |
| Jeton masqué dans les journaux httpx | oui | `log_privacy.RedactQueryFilter` |

**Tests automatisés.** Ils s'exécutent sans réseau, Meta étant simulé : le client de test signe les requêtes avec un secret de test, et l'envoi passe par une boîte d'envoi factice.
- **Commande :** `pytest tests -k "messenger or echo or psid" -m "not integration"`.
- **Résultat : 13 tests réussis**, en 6,45 s. L'un d'eux, `test_sql_echo_is_off_by_default…`, est sélectionné par le mot « echo » mais ne concerne pas Messenger : il reste **12 tests Messenger**.
  - `test_messenger_signature.py` (9) : requête signée acceptée ; signature fausse ou absente refusée ; refus sans secret (2 cas) ; écho de la page ignoré ; canal activé par n'importe quel identifiant Meta (2 cas) ; démarrage refusé sans secret (2 cas).
  - `test_welcome_menu.py` (2) : salutation Messenger servie avec les réponses rapides ; un clic sur une réponse rapide arrive au bot comme la question du bouton.
  - `test_log_privacy.py` (1) : le jeton Messenger est masqué dans le journal httpx.
  - `test_admin_reply.py` contient aussi des tests de réponse de conseiller sur les canaux Meta, simulés.
- **Incident pendant le relevé.** Un premier lancement depuis la racine du dépôt a aussi collecté `test_messenger_manual.py` et `test_whatsapp_manual.py`, deux scripts manuels non suivis qui s'exécutent dès leur import. Ils visent `http://127.0.0.1:8000`, l'API locale, qui était arrêtée. Ils ont échoué avec une erreur de connexion : **aucune requête n'a atteint Meta**, et ces fichiers n'ont pas été modifiés.

**Test réel.** Aucun. Aucun utilisateur ni message du canal `messenger` n'existe en base (0 / 0 / 0). Pour WhatsApp, en comparaison, le code mentionne un « envoi réel vérifié » (`whatsapp.py:33`), et la base contient 106 messages WhatsApp.

## B2. Messenger : ce qui n'a pas été fait

| Étape | État |
| --- | --- |
| Page Facebook réelle reliée à l'application | Non vérifiable dans le dépôt. `docs/webhooks_ngrok_setup.md` §7 décrit la marche à suivre (« Il te faut une Page Facebook ») |
| Jeton d'accès de page (`MESSENGER_PAGE_ACCESS_TOKEN`) | **Vide** dans la configuration actuelle : envoi simulé |
| `MESSENGER_APP_SECRET`, `MESSENGER_VERIFY_TOKEN` | Renseignés (valeurs non affichées). `docs/webhooks_ngrok_setup.md` donne en exemple des valeurs de test (`test-app-secret-messenger-67890`) ; le relevé ne permet pas de savoir si les valeurs actuelles sont réelles |
| Abonnement du webhook chez Meta | Aucune trace : 0 message Messenger en base |
| Revue d'application Meta (permission `pages_messaging`) | **Absente** : aucune mention dans le dépôt. Elle est nécessaire pour répondre à des personnes qui ne sont pas administrateurs ou testeurs de l'application |
| Réception d'un vrai message, envoi réel d'une réponse | **Non fait** |

**Formulation possible pour le rapport.** Le canal Messenger est un **livrable partiel**. La réception, la signature, le filtre `is_echo`, le menu en réponses rapides et la réponse d'un conseiller sont implémentés et couverts par 12 tests automatisés qui simulent Meta. En revanche, aucun échange réel n'a eu lieu : pas de jeton de page, pas de revue Meta, pas de message reçu ou envoyé.

## B3. Différences avec WhatsApp

| Point | WhatsApp | Messenger |
| --- | --- | --- |
| Identifiant de session | Numéro de téléphone (`from`) | **PSID** (`sender.id`) : identifiant propre à la page, qui ne révèle pas directement l'identité et ne permet pas de joindre la personne en dehors de cette page |
| Redis | `session:<numéro>`, 1 h | `session:<psid>`, 1 h |
| PostgreSQL | `users.external_id` = numéro, `display_name` = `User_` + 8 chiffres, conservation illimitée | `users.external_id` = PSID, `display_name` = `User_` + 8 caractères du PSID, conservation illimitée ; **0 ligne aujourd'hui** |
| Journaux | `216…21` | Même masquage si le PSID est numérique, ce qui est le format habituel de Meta : 3 premiers et 2 derniers chiffres. Sinon, 4 premiers caractères suivis de « … » |
| Visibilité pour les conseillers et l'export CSV | En clair | En clair |
| Suppression | Mêmes possibilités (A3) | Mêmes possibilités |

## Versions

Python 3.13.5, FastAPI 0.115.0, SQLAlchemy 2.0.36, redis-py 5.2.0, PostgreSQL 16, Redis 7 (Docker). Code au commit `a0c0cd3`, branche `integration/menu-qualite`.

## Limites

- **TTL Redis non mesuré** sur une clé réelle : il n'y avait aucune session active, et la consigne interdit d'écrire.
- **Hébergement.** La conservation réelle des journaux dépend de l'hébergement de production, absent du dépôt (pas de configuration de journaux Docker pour l'API).
- **Pas d'avis juridique.** Ce relevé ne dit pas si le traitement est conforme à la loi n° 2004-63 ; il décrit seulement le code.
- **Configuration Meta non vérifiable.** L'état réel côté Meta (page, abonnement, revue) n'est pas visible depuis le dépôt ; il est déduit de la configuration et de l'absence de messages Messenger en base.
- **Base de démonstration.** Les comptages portent sur la base locale ; la production peut différer.
