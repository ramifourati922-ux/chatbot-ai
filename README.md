# Liss Strike — Assistant de service client multilingue

**Chatbot RAG qui répond en français, anglais, arabe et tunisien, et passe la main à un conseiller humain quand il le faut.**

![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-async-009688?logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-7-DC382D?logo=redis&logoColor=white)
![ChromaDB](https://img.shields.io/badge/ChromaDB-1.4.1-FF6F00)
![Tests](https://img.shields.io/badge/tests-566%20au%20vert-2EA44F)

[Fonctionnalités](#fonctionnalités) ·
[Architecture](#architecture) ·
[Démarrage rapide](#démarrage-rapide) ·
[Utilisation](#utilisation) ·
[Limites connues](#limites-connues)

---

## À propos

**Liss Strike** est une boutique tunisienne d'électronique pour *makers*
(cartes programmables, capteurs, modules, outillage). Son assistant :

- répond aux questions des clients **uniquement à partir de la base de
  connaissances** de la boutique (pipeline RAG : recherche des passages
  pertinents, puis rédaction de la réponse par un LLM qui n'a le droit
  d'utiliser que ces passages) ;
- comprend **4 façons d'écrire** : français, anglais, arabe littéraire et
  dialecte tunisien, en lettres arabes ou en arabizi (« 3andi mochkla ») ;
- sert **4 canaux** avec un seul moteur : site web (HTTP et WebSocket),
  WhatsApp et Messenger ;
- **transfère** la conversation à un conseiller humain dans 5 situations,
  et outille les conseillers avec un tableau de bord dédié.

## Fonctionnalités

### Comprendre le message

| Brique | Ce qu'elle fait |
| --- | --- |
| **Détection de langue** | Règles dédiées à l'arabe et au tunisien (arabizi compris), `langdetect` pour le reste. La langue détectée est imposée au LLM pour la réponse. |
| **Classification par règles** | Sans LLM, donc déterministe et instantanée : demande d'un humain, frustration envers le *service* (« votre service est nul » transfère, « ce produit est nul » non), politesse, suivi de commande. |
| **Mémoire conversationnelle** | Les 6 derniers messages sont transmis au LLM ; une question de suivi (« et le délai ? ») est rattachée à la précédente pour la recherche. |

### Répondre sans inventer (RAG « Advanced »)

1. **Recherche hybride** : recherche sémantique (embeddings, ChromaDB) et
   recherche par mots-clés (BM25), fusionnées par *Reciprocal Rank Fusion*.
2. **Reranking** : un cross-encoder multilingue relit les 20 meilleurs
   candidats et garde les 4 plus pertinents.
3. **Génération** par un LLM (Groq) avec une consigne stricte : répondre
   uniquement à partir des passages trouvés, dire « je n'ai pas
   l'information » plutôt qu'inventer, refuser les questions hors sujet.

### Suivi de commande, sans LLM

- **Statut lu en base** (table `orders`), jamais généré par le LLM :
  numéro, statut, articles, total et date de livraison estimée, en fr, en,
  ar et tn.
- **Numéro `CMD-AAAA-NNNNN`** reconnu quelle que soit l'écriture (« cmd
  2026 00123 », casse, tirets ou espaces).
- **Une seule relance** si le numéro manque ou est introuvable, puis
  transfert à un conseiller.

### Transférer au bon moment (5 déclencheurs)

| Raison | Déclencheur | Appel au LLM |
| --- | --- | --- |
| `explicit` | Le client demande un humain | Non |
| `frustration` | Mécontentement envers le service | Non |
| `low_rag_confidence` | Confiance de la recherche sous le seuil (0,35) | Non |
| `repeated_rag_failure` | 3 réponses « je n'ai pas l'information » consécutives | Oui (réponses précédentes) |
| `order_tracking` | Commande toujours introuvable (ou sans numéro) après une relance | Non |

### Outiller les conseillers (`/admin`)

- **Liste des conversations transférées** : client, canal, raison,
  dernière question, temps d'attente ; notification du navigateur à chaque
  nouveau transfert.
- **Historique complet** et **réponse au client sur son canal d'origine**
  (WhatsApp, Messenger, ou chat du site s'il est encore connecté).
- **Prise en main** : dès la première réponse du conseiller, le bot se tait
  pour ce client. Il reprend après « Marquer traitée », ou après 1 h sans
  message du conseiller. Les réponses du conseiller rejoignent la mémoire
  du bot.
- **Un compte par conseiller** (mot de passe haché avec bcrypt), rôles
  `conseiller` et `admin` ; chaque réponse, prise en main et résolution est
  rattachée à son auteur.
- **Statistiques** (`/admin/statistiques`, sur 7, 30 ou 90 jours) : taux de
  conversations traitées sans conseiller, volumes par canal, par langue et
  par jour, réponses par type, transferts par raison, temps de réponse
  (médiane et 90e centile), et **questions sans réponse** : celles qui ont
  mené à un transfert « réponse non trouvée » ou à une réponse « je n'ai
  pas l'information », regroupées et comptées, à ajouter à la base de
  connaissances.
- **Prospects** (même page, export CSV) : clients qui se sont renseignés
  sur un produit, avec les produits d'intérêt (nom, prix), le nombre de
  questions, la dernière question, l'intention d'achat exprimée (prix,
  disponibilité, achat, dans les 4 langues) et le canal pour les
  recontacter. Déduits de l'historique (références produits citées par
  les réponses RAG), sans table ni saisie supplémentaires.

### Persistance et sécurité

- **Sessions** dans Redis (1 h) et **historique permanent** dans
  PostgreSQL, enregistré en arrière-plan sans retarder la réponse.
- **Webhooks Meta signés** (HMAC-SHA256), **sessions web attribuées et
  signées par le serveur**, CORS, limitation de débit par IP, journaux
  sans données personnelles ni secrets.

## Architecture

Les routes ne contiennent aucune logique métier : elles vérifient
l'appelant, puis passent le message au moteur unique,
`dialogue_manager.handle_message`.

```mermaid
flowchart TB
    subgraph canaux["Canaux"]
        WEB["Site web<br/>POST /chat/ · WS /ws"]
        WA["WhatsApp<br/>webhook signé"]
        MS["Messenger<br/>webhook signé"]
    end
    API["API FastAPI<br/>signatures Meta · sessions signées · CORS · débit"]
    DM["dialogue_manager<br/>langue → intention → réponse ou transfert"]
    ADMIN["Tableau /admin<br/>conseillers"]
    REDIS[("Redis<br/>sessions, 1 h")]
    PG[("PostgreSQL<br/>conversations, comptes, commandes")]
    CHROMA[("ChromaDB + BM25<br/>11 109 chunks")]
    MODELS["Modèles locaux (CPU)<br/>embeddings · reranker"]
    GROQ["Groq<br/>LLM (externe)"]
    META["API Graph de Meta<br/>envoi (externe)"]

    WEB & WA & MS --> API --> DM
    ADMIN --> API
    DM --> REDIS & PG & CHROMA
    DM --> MODELS & GROQ
    API --> META
```

### Parcours d'un message

Les vérifications s'enchaînent dans un ordre fixe ; le LLM n'est appelé
qu'en fin de parcours, pour une question dont la recherche a trouvé des
passages fiables.

```mermaid
flowchart TD
    A[Message entrant] --> P{Conversation prise<br/>en main par un conseiller ?}
    P -->|oui| Z[Le bot se tait<br/>message enregistré]
    P -->|non| B[Détection de langue<br/>fr / en / ar / tn]
    B --> C[Classification par règles]
    C -->|demande d'humain<br/>ou frustration| T[Transfert au conseiller<br/>sans LLM]
    C -->|politesse| R1[Réponse toute prête<br/>sans LLM]
    C -->|suivi de commande| O[Statut lu en base<br/>sans LLM]
    O -->|introuvable après<br/>une relance| T
    C -->|question| S[Question de suivi ?<br/>rattachée à la précédente]
    S --> R[Recherche hybride<br/>BM25 + dense + RRF<br/>puis reranking]
    R --> K{Confiance<br/>≥ 0,35 ?}
    K -->|non| T
    K -->|oui| L[LLM Groq<br/>passages + historique]
    L --> F{3e « je n'ai pas<br/>l'information »<br/>d'affilée ?}
    F -->|oui| T
    F -->|non| H[Réponse au client]
    T --> D[Tableau de bord /admin]
```

Chaque échange est conservé dans Redis (1 h) et PostgreSQL.

## Stack technique

| Composant | Technologie |
| --- | --- |
| API | FastAPI (async), Uvicorn |
| LLM | Groq : `openai/gpt-oss-120b`, repli sur `openai/gpt-oss-20b` |
| Embeddings | `paraphrase-multilingual-MiniLM-L12-v2` (sentence-transformers, local, 384 dimensions) |
| Recherche lexicale | BM25 (`rank-bm25`) |
| Reranker | `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` (multilingue) |
| Base vectorielle | ChromaDB 1.4.1 (image Docker épinglée par digest) |
| Sessions | Redis 7 (repli en mémoire si indisponible) |
| Base relationnelle | PostgreSQL 16, SQLAlchemy async, Alembic |
| Détection de langue | `langdetect` + règles dédiées arabe / tunisien |
| Évaluation | RAGas 0.4.3 (`scripts/evaluate_ragas.py`) |
| Tests | pytest, pytest-asyncio |
| Infrastructure | Docker Compose (PostgreSQL, Redis, ChromaDB, Adminer) |

## Résultats mesurés

Les chiffres ci-dessous viennent de
[`CHANGELOG_ADVANCED_RAG.md`](CHANGELOG_ADVANCED_RAG.md) et de
[`docs/evaluation/`](docs/evaluation/), où le protocole et ses limites
sont détaillés.

**Base de connaissances** : 11 109 chunks indexés (59 questions-réponses
de politiques SAV et e-commerce, 11 050 produits).

**Évaluation RAGas, Basic RAG contre Advanced RAG** (22 questions notées
en fr, en, ar et tn, juge `gpt-oss-20b`) :

| Métrique | Basic RAG | Advanced RAG |
| --- | --- | --- |
| Context Precision | 0,645 | **0,913** |
| Context Recall | 0,599 | **0,800** |
| Faithfulness | 0,532 | **0,689** |
| Answer Relevancy | 0,485 | **0,600** |
| Source attendue dans le top 4 | 77 % | **95 %** |

Le gain porte sur le français et l'anglais ; **l'arabe régresse** avec le
reranker (Context Recall 0,92 → 0,55). Échantillon réduit (3 à 4
questions en arabe et en tunisien) : ce sont des tendances, pas des
mesures statistiquement solides.

**Latences** (CPU, sans GPU) :

| Mesure | Valeur |
| --- | --- |
| Recherche Advanced (hybride + reranking), médiane sur 9 questions | 1 084 ms (max 1 505 ms) |
| dont reranking des 20 candidats | 883 ms (médiane) |
| Réponse RAG de bout en bout, scénario de démo vérifié | 1,2 à 1,9 s |
| Politesse et transfert explicite (sans LLM), même scénario | 7 à 22 ms |

## Démarrage rapide

### Prérequis

- Python 3.13
- Docker Desktop
- Une clé API [Groq](https://console.groq.com/keys) (offre gratuite)

### Installation

```bash
# 1. Dépendances
python -m venv venv
venv\Scripts\activate              # Windows ; Linux/macOS : source venv/bin/activate
pip install -r requirements.txt

# 2. Configuration : copier le modèle, puis renseigner au minimum
#    GROQ_API_KEY et ADMIN_PASSWORD (voir le tableau ci-dessous)
cp .env.example .env

# 3. Services : PostgreSQL, Redis, ChromaDB, Adminer
docker compose up -d

# 4. Schéma de la base, puis indexation de la base de connaissances (~11 min sur CPU)
alembic upgrade head
python scripts/ingest_knowledge_base.py
python scripts/seed_demo_orders.py   # optionnel : commandes fictives CMD-2026-00101 à 00105

# 5. Lancement
uvicorn app.main:app --reload
```

Au premier lancement, les modèles d'embeddings et de reranking sont
téléchargés depuis Hugging Face (environ 470 Mo pour le reranker). Si le
téléchargement reste bloqué, définir `HF_HUB_DISABLE_XET=1`.

### Configuration

Toutes les variables sont décrites dans [`.env.example`](.env.example).
Les principales :

| Variable | Requise | Rôle |
| --- | --- | --- |
| `GROQ_API_KEY` | **Oui** | Clé de l'API Groq (génération des réponses) |
| `ADMIN_USERNAME`, `ADMIN_PASSWORD` | **Oui**, au premier démarrage | Création du premier compte admin de `/admin` ; sans compte en base ni mot de passe, l'API refuse de démarrer |
| `DATABASE_URL`, `REDIS_URL`, `CHROMA_HOST`, `CHROMA_PORT` | Non | Adresses des services (valeurs adaptées à `docker compose`) |
| `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_VERIFY_TOKEN` | Pour WhatsApp | Identifiants Meta du canal WhatsApp |
| `WHATSAPP_APP_SECRET` | **Oui** si WhatsApp est configuré | Vérification des signatures Meta ; sans lui, l'API refuse de démarrer |
| `MESSENGER_PAGE_ACCESS_TOKEN`, `MESSENGER_VERIFY_TOKEN` | Pour Messenger | Identifiants Meta du canal Messenger |
| `MESSENGER_APP_SECRET` | **Oui** si Messenger est configuré | Vérification des signatures Meta ; sans lui, l'API refuse de démarrer |
| `CORS_ALLOWED_ORIGINS` | Non | Origines web autorisées (défaut : `localhost:8000` et `127.0.0.1:8000`) |
| `WS_SESSION_SECRET` | Recommandée | Clé de signature des sessions web ; vide = clé aléatoire à chaque démarrage |
| `RAG_RETRIEVAL_MODE` | Non | `advanced` (défaut), `hybrid` ou `basic` |
| `RAG_CONFIDENCE_THRESHOLD` | Non | Seuil de confiance sous lequel la question est transférée (défaut : 0,35) |
| `RATE_LIMIT_CHAT`, `RATE_LIMIT_WS_MESSAGES`, `RATE_LIMIT_WS_CONNECTIONS`, `RATE_LIMIT_USERS` | Non | Limites de débit par adresse IP |
| `RATE_LIMIT_LOGIN_FAILURES` | Non | Échecs de connexion tolérés avant blocage (défaut : 5 en 15 minutes, par IP et par identifiant) |
| `SQL_ECHO` | Non | Journal SQL, pour déboguer uniquement (désactivé par défaut) |

> [!WARNING]
> **Ne jamais utiliser `docker compose down -v`.** L'option `-v` supprime
> les volumes Docker : la base de connaissances indexée dans ChromaDB
> (environ 11 min pour la reconstruire) et toutes les données PostgreSQL.
>
> ```bash
> docker compose stop     # arrête les conteneurs, garde tout (recommandé)
> docker compose down     # supprime les conteneurs, garde les volumes (chroma_data, postgres_data)
> ```

## Utilisation

### Interfaces

| Adresse | Rôle |
| --- | --- |
| <http://localhost:8000/chat-demo> | Interface de démonstration (chat en temps réel) |
| <http://localhost:8000/admin> | Tableau de bord des conseillers (identifiants requis) |
| <http://localhost:8000/admin/statistiques> | Statistiques, questions sans réponse et prospects (identifiants requis) |
| <http://localhost:8000/docs> | Documentation interactive de l'API (Swagger) |
| <http://localhost:8080> | Adminer (administration PostgreSQL) |

### Points d'entrée de l'API

| Canal / usage | Route |
| --- | --- |
| Web (HTTP) | `POST /chat/` |
| Web (temps réel) | `GET /chat/session` (identifiant signé), puis `WS /ws/{client_id}?signature=…` |
| WhatsApp Business Cloud API | `GET` / `POST /webhook/whatsapp` |
| Facebook Messenger | `GET` / `POST /webhook/messenger` |
| Conseillers | `GET /admin`, `GET /admin/me`, `GET /admin/stats?days=30`, `GET /admin/leads`, `GET /admin/leads.csv`, `GET /admin/escalations`, `GET /admin/escalations/{id}/messages`, `POST /admin/escalations/{id}/reply`, `POST /admin/escalations/{id}/resolve` |
| Comptes conseillers (rôle admin) | `GET` / `POST /admin/agents`, `POST /admin/agents/{id}/deactivate`, `/activate`, `PUT /admin/agents/{id}/password` |
| Utilisateurs (rôle admin) | `/users/` |
| Supervision | `GET /health` |

### Exemple : `POST /chat/`

Le premier message ouvre une session : le serveur attribue un
`session_id` et renvoie sa `session_signature`.

```bash
curl -X POST http://localhost:8000/chat/ \
  -H "Content-Type: application/json" \
  -d '{"message": "Quels sont les frais de livraison ?"}'
```

Pour continuer la conversation, renvoyer les deux valeurs reçues ; un
`session_id` sans signature valide est refusé (403).

```bash
curl -X POST http://localhost:8000/chat/ \
  -H "Content-Type: application/json" \
  -d '{"message": "Et le délai ?", "session_id": "<session_id>", "session_signature": "<session_signature>"}'
```

La réponse contient aussi l'intention détectée, la confiance, les sources
consultées, le temps de traitement et, le cas échéant, la raison du
transfert.

**Démonstration** : un scénario vérifié en 8 étapes, une checklist de
démarrage et une transcription de secours sont dans
[`docs/demo/`](docs/demo/).

## Guides de configuration

<details>
<summary>Comptes des conseillers (/admin, /users/)</summary>

Les routes `/admin/…` exposent les identifiants des clients (numéros
WhatsApp…) et leurs questions ; les routes `/users/` permettent de
lister, créer, modifier et désactiver leurs comptes. Chaque conseiller a
**son propre compte** (table `agents`, mot de passe haché avec bcrypt),
vérifié en **HTTP Basic** :

| Rôle | Accès |
| --- | --- |
| `conseiller` | `/admin` : liste, historique, réponse au client, prise en main, « Marquer traitée » |
| `admin` | Tout ce qui précède, plus `/users/` et la gestion des comptes conseillers (`/admin/agents`) |

**Premier compte** : au démarrage, si aucun compte n'existe, un compte
**admin** est créé à partir de `ADMIN_USERNAME` et `ADMIN_PASSWORD` :

```env
ADMIN_USERNAME=admin
ADMIN_PASSWORD=un-vrai-mot-de-passe
```

- Ces deux variables ne servent **qu'à cette création** : ensuite, les
  comptes vivent en base, et modifier `ADMIN_PASSWORD` dans `.env` n'a
  plus d'effet (changer le mot de passe par l'API, ci-dessous). L'API
  refuse de démarrer si aucun compte n'existe et que `ADMIN_PASSWORD`
  est absent.
- **Gestion des comptes** (rôle `admin`, depuis `/docs` ou curl ; pas
  d'écran dédié) : `GET` / `POST /admin/agents` (lister, créer),
  `POST /admin/agents/{id}/deactivate` et `/activate`,
  `PUT /admin/agents/{id}/password`. Le dernier admin actif ne peut pas
  être désactivé. Mot de passe : 8 caractères minimum, 72 octets
  maximum (limite de bcrypt).
- **Traçabilité** : chaque réponse enregistre le conseiller qui l'a
  envoyée (affiché dans l'historique de `/admin`) ; la prise en main et
  « Marquer traitée » enregistrent aussi leur auteur. Un compte
  désactivé ne peut plus se connecter, mais son historique est conservé.
- Le navigateur affiche sa propre invite de connexion à l'ouverture de
  `/admin` ; l'en-tête indique le conseiller connecté. HTTP Basic n'a pas
  de vraie déconnexion : pour changer de compte, fermer le navigateur.

> [!IMPORTANT]
> Avec HTTP Basic, les identifiants sont transmis encodés (base64), non
> chiffrés : **HTTPS est indispensable** en dehors d'une machine locale.

</details>

<details>
<summary>Origines autorisées (CORS)</summary>

Seules les origines listées dans `CORS_ALLOWED_ORIGINS` (séparées par des
virgules) peuvent appeler l'API depuis un navigateur. Sans cette
variable, ce sont `http://localhost:8000` et `http://127.0.0.1:8000`.
La même liste s'applique au WebSocket `/ws/{client_id}` : une connexion
dont l'en-tête `Origin` n'y figure pas (ou qui n'en a pas) est fermée
avec le code 1008.

- `/chat-demo` et `/admin` ouverts en local (`localhost:8000` ou
  `127.0.0.1:8000`) : aucune configuration nécessaire.
- Pour une page ouverte depuis une autre adresse, **y compris
  `/chat-demo` exposé via ngrok** (son WebSocket envoie alors l'origine
  ngrok), ajouter cette origine exacte (schéma, domaine, port, sans `/`
  final) :

```env
CORS_ALLOWED_ORIGINS=http://localhost:8000,https://xxxx.ngrok-free.app
```

</details>

<details>
<summary>WhatsApp en conditions réelles</summary>

Testé de bout en bout avec un vrai téléphone : message reçu par le
webhook (signature vérifiée), réponse du bot générée puis envoyée par
l'API Graph et reçue sur WhatsApp. Configuration utilisée : **numéro de
test fourni par Meta**, un seul destinataire autorisé, serveur local
exposé par ngrok (voir
[`docs/webhooks_ngrok_setup.md`](docs/webhooks_ngrok_setup.md)).

Conditions nécessaires, en plus de l'URL du webhook, du jeton de
vérification et de l'abonnement au champ `messages` dans l'application
Meta :

- **`WHATSAPP_APP_SECRET`** : le secret de l'application Meta, recopié
  exactement (32 caractères hexadécimaux). Valeur erronée : chaque
  message reçu est rejeté en 403 (signature invalide). **Absent** alors
  que le canal est configuré (`WHATSAPP_PHONE_NUMBER_ID`,
  `WHATSAPP_ACCESS_TOKEN` ou `WHATSAPP_VERIFY_TOKEN`) : l'API **refuse de
  démarrer** ; et sans lui, le webhook refuse toute requête (aucun
  message n'est jamais accepté sans signature vérifiée).
- **Application abonnée au compte WhatsApp Business (WABA)** : étape
  distincte des champs webhook de l'application, faite par l'API Graph
  (`POST /{id-du-WABA}/subscribed_apps`, vérifiable par un `GET` sur la
  même adresse). Sans elle, les messages réels n'arrivent jamais au
  webhook, alors que le bouton « Test » du tableau de bord fonctionne.
- **`WHATSAPP_ACCESS_TOKEN`** : jeton de l'application, avec la
  permission `whatsapp_business_messaging` ; **`WHATSAPP_PHONE_NUMBER_ID`** :
  identifiant du numéro qui envoie.
- **En développement** : le numéro de test ne peut écrire qu'aux
  destinataires ajoutés **et validés** dans la configuration de l'API.
  Jeton invalide ou destinataire non autorisé : erreur Meta `131005`
  (« Access denied »), réponse du bot non délivrée.

Limites actuelles :

- **Jeton d'accès temporaire** (environ 24 h) : passé ce délai, les
  réponses ne partent plus. Un utilisateur système avec jeton permanent
  est nécessaire pour un usage durable (pas encore fait).
- **API Graph en version `v18.0`** : ancienne mais fonctionnelle ; la
  mise à jour vers une version récente n'est pas encore faite.

</details>

## Tests

```bash
pytest tests/                        # suite complète : 566 tests, ~2 min 30
pytest tests/ -m "not integration"   # 441 tests unitaires, ~15 s, sans aucun service
pytest tests/ -m integration         # 125 tests d'intégration
```

Les tests couvrent la détection de langue, la classification (escalade,
politesse, faux positifs), la recherche hybride et le reranking, la
mémoire conversationnelle, le compteur de boucle RAG, l'orchestrateur
complet (les 5 types de transfert), le suivi de commande, la persistance
PostgreSQL, le tableau de bord `/admin` (historique, réponse au client,
prise en main), l'authentification de `/admin` et `/users/`, CORS et
l'origine du WebSocket, les signatures (webhooks Meta, sessions web), la
limitation de débit, les journaux et la structure de la base de
connaissances.

- **Tests unitaires** : ni Docker, ni clé Groq, ni modèle téléchargé.
  C'est la partie à lancer en intégration continue.
- **Tests d'intégration** (marqueur `integration`) : ils ont besoin des
  services (`docker compose up -d`), d'une base de connaissances indexée
  et d'une clé Groq, ou chargent les modèles d'embeddings et de
  reranking ; sans ces services, ils sont ignorés (*skipped*). Un test
  qui utilise une fixture de base de données est marqué automatiquement
  (voir [`tests/conftest.py`](tests/conftest.py)).
- Certains tests d'intégration appellent réellement Groq (consommation du
  quota gratuit) et écrivent des conversations dans la base PostgreSQL
  locale ; [`scripts/cleanup_test_data.py`](scripts/cleanup_test_data.py)
  les supprime.

## Structure du projet

```text
app/
├── main.py                    # application FastAPI, contrôles au démarrage, préchargement des modèles
├── config.py                  # configuration (variables d'environnement)
├── log_privacy.py             # journaux sans données personnelles ni secrets
├── api/routes/                # chat, websocket, whatsapp, messenger, admin, agents, users
├── services/
│   ├── dialogue_manager.py    # orchestrateur : langue, règles, RAG, LLM, persistance
│   ├── analytics.py           # statistiques, questions sans réponse, prospects (/admin/stats, /admin/leads)
│   ├── intent_classifier.py   # transfert, frustration, politesse, suivi de commande (règles)
│   ├── language_detector.py   # fr / en / ar / tn
│   ├── order_tracking.py      # statut des commandes, lu en base
│   ├── session_manager.py     # sessions Redis
│   ├── agent_auth.py          # comptes conseillers (bcrypt)
│   └── rag/                   # embeddings, ChromaDB, BM25, reranker, LLM
└── db/, models/, schemas/     # PostgreSQL (SQLAlchemy) et schémas Pydantic
alembic/                       # migrations de la base
data/knowledge_base/           # politiques SAV (.txt) et catalogue produits (.csv)
scripts/                       # ingestion, données de démo, nettoyage, calibration, évaluation RAGas
static/                        # chat.html (démo client), admin.html et statistiques.html (conseillers)
tests/                         # suite pytest (566 tests)
docs/                          # démo, évaluation RAGas, webhooks, captures d'écran
```

## Documentation

| Document | Contenu |
| --- | --- |
| [`CHANGELOG_ADVANCED_RAG.md`](CHANGELOG_ADVANCED_RAG.md) | Passage au RAG avancé (recherche hybride, reranking, calibration, évaluation RAGas), correctifs après revue, anomalies documentées (symptôme, diagnostic, cause, correction) |
| [`data/knowledge_base/README.md`](data/knowledge_base/README.md) | Contenu et format de la base de connaissances, ré-indexation |
| [`docs/demo/`](docs/demo/) | Scénario de démonstration, checklist du jour J, transcription vérifiée |
| [`docs/evaluation/`](docs/evaluation/) | Résultats RAGas détaillés (JSON et Markdown) |
| [`docs/webhooks_ngrok_setup.md`](docs/webhooks_ngrok_setup.md) | Exposer le serveur local en HTTPS et configurer les webhooks WhatsApp et Messenger |
| [`docs/screenshots/`](docs/screenshots/) | Captures d'écran (voir la note ci-dessous) |

Les captures `admin_*`, `chat_demo_*` et `figure27` à `figure29` sont
antérieures aux derniers correctifs : elles montrent par exemple
`/admin` avant l'authentification et le chat avant le suivi de commande.

## Limites connues

| Domaine | Limite |
| --- | --- |
| Mise en production | Pas de `Dockerfile` pour l'API ni d'intégration continue ; offre gratuite de Groq |
| Sécurité | Pas d'authentification des clients ; HTTP Basic pour les conseillers |
| Qualité des réponses | Reranker moins bon en arabe |
| Suivi de commande | Données fictives ; le numéro de commande est la seule clé d'accès |

## Feuille de route

- [x] Séparation des tests unitaires et d'intégration (marqueur `integration`)
- [ ] `Dockerfile` et intégration continue (tests unitaires à chaque push,
      tests d'intégration avec PostgreSQL et Redis en services)
- [x] Limitation des tentatives de connexion sur `/admin` et `/users/`
- [ ] Connexion par session plutôt que HTTP Basic ; écran de gestion des
      comptes
- [ ] Authentification des clients sur l'API
- [ ] Reranking réservé au français et à l'anglais (régression mesurée en
      arabe) ; normalisation de l'arabizi avant la recherche
- [ ] Notifications hors navigateur (e-mail, push) pour les conseillers
- [ ] Suivi de commande relié à un back-office

## Auteur

Projet réalisé par Rami Fourati.
