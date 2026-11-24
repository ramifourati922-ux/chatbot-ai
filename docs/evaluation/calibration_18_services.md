# Seuil de confiance face à 18 questions sur des services non proposés

Mesuré par `scripts/measure_calibration_services.py` le 23/11/2026 : recherche en mode `advanced` (collection de production `liss_strike_kb` en lecture seule), puis issue réelle dans `POST /chat/` (API locale, session neuve par question).

## Les 18 questions

Source : script de mesure `calib18.py` (19/11/2026) qui a produit le tableau `tab:calib18` du rapport v5 ; reprises à l'identique. Elles ne sont pas versionnées dans le dépôt. Toutes sont en français (langue détectée : `fr` pour les 18).

Deux d'entre elles sont en réalité **couvertes par la base** : n° 4 (FAQ : « la livraison est pour l'instant disponible uniquement en Tunisie ») et n° 16 (paiement : « en 3 fois sans frais » au-delà de 300 DT). Les 16 autres portent sur un service que la base ne mentionne pas.

## Résultats par question

Score = 1 − plus petite distance cosinus parmi les passages retenus ; seuil 0,35. « Passages » = passages retenus après le filtre 0,75 et le reranking (au plus 4). Meilleur document = passage à la plus petite distance.

| N° | Question | Distance min | Score | Passages | Meilleur document | Arrêtée par le seuil | Issue réelle dans `/chat/` |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Faites-vous la réparation d'ordinateurs portables ? | 0,601 | 0,399 | 4 | policy `sav/garantie.txt` (« Le produit est-il réparé ou remplacé sous garantie ? ») | non | LLM : pas d'information, propose un conseiller |
| 2 | Proposez-vous la location de matériel électronique ? | 0,448 | 0,552 | 4 | product `LS-OU-000030` (établi de travail électronique) | non | LLM : pas d'information, propose un conseiller |
| 3 | Avez-vous une boutique à Paris ? | 0,589 | 0,411 | 4 | policy `sav/livraison.txt` | non | LLM : non, boutique en Tunisie uniquement (horaires exacts de la base) |
| 4 | Livrez-vous en Algérie ? *(couverte)* | 0,343 | 0,657 | 4 | policy `general/faq.txt` | non | LLM : non, Tunisie uniquement — **correct** |
| 5 | Proposez-vous des formations en robotique ? | 0,342 | 0,658 | 4 | product `LS-KP-000333` (kit robotique éducatif) | non | LLM : pas d'information, renvoie au service client |
| 6 | Concevez-vous des circuits imprimés sur mesure pour les entreprises ? | 0,489 | 0,511 | 4 | product `LS-IM-000006` (multimètre) | non | LLM : pas d'information, propose un conseiller |
| 7 | Vendez-vous des téléphones portables reconditionnés ? | 0,672 | 0,328 | 4 | policy `sav/livraison.txt` | **oui** | escalade `low_rag_confidence`, message fixe, sans LLM (vérifié) |
| 8 | Acceptez-vous le paiement en cryptomonnaie ? | 0,458 | 0,542 | 4 | policy `ecommerce/paiement.txt` (« Quels moyens de paiement sont acceptés ? ») | non | LLM : liste les moyens acceptés, « la cryptomonnaie n'est pas mentionnée » |
| 9 | Installez-vous des panneaux solaires à domicile ? | 0,645 | 0,355 | 4 | product `LS-CO-008319` (LED UV) | non | LLM : refus hors sujet (« je ne peux vous aider que sur les sujets liés à Liss Strike ») |
| 10 | Développez-vous des applications mobiles sur commande ? | 0,618 | 0,382 | 4 | product `LS-CP-000041` (Raspberry Pi 5) | non | LLM : refus hors sujet |
| 11 | Proposez-vous un abonnement mensuel de composants ? | 0,473 | 0,527 | 4 | policy `ecommerce/paiement.txt` (« Peut-on payer en plusieurs fois ? ») | non | LLM : pas d'information, propose un conseiller |
| 12 | Vendez-vous des pièces détachées automobiles ? | 0,665 | 0,335 | 4 | product `LS-CN-000998` (câble ruban) | **oui** | escalade sans LLM ; `/chat/` non appelé (un seul contrôle, n° 7) |
| 13 | Recrutez-vous des stagiaires cet été ? | 0,617 | 0,383 | 4 | policy `ecommerce/paiement.txt` (« commander en tant qu'école… ») | non | LLM : refus hors sujet |
| 14 | Livrez-vous par drone ? | 0,701 | 0,299 | 4 | product `LS-MO-000001` (module relais) | **oui** | escalade sans LLM ; `/chat/` non appelé |
| 15 | Organisez-vous des ateliers d'électronique pour enfants ? | 0,610 | 0,390 | 4 | product `LS-OU-000030` (établi de travail électronique) | non | LLM : pas d'information, propose un conseiller |
| 16 | Puis-je payer en plusieurs fois sans frais ? *(couverte)* | 0,261 | 0,739 | 4 | policy `ecommerce/paiement.txt` (« Peut-on payer en plusieurs fois ? ») | non | LLM : oui, 3 fois sans frais au-delà de 300 DT — **correct** |
| 17 | Acceptez-vous les chèques-cadeaux d'autres magasins ? | 0,425 | 0,575 | 4 | policy `sav/livraison.txt` | non | LLM : « Nous n'acceptons pas » — **affirmation non fondée sur la base** |
| 18 | Faites-vous de la maintenance de serveurs ? | 0,622 | 0,378 | 4 | policy `ecommerce/promotions.txt` | non | LLM : « Nous ne proposons pas », puis décrit l'activité de la boutique (conforme à la FAQ) |

Aucune des 15 réponses générées ne signale d'escalade (`escalated` = false) : quand le LLM « propose un conseiller », c'est une phrase de la réponse, pas un transfert effectif.

### Réponses citées

- n° 1 : « Je n'ai pas d'information précise concernant la réparation d'ordinateurs portables chez Liss Strike. […] Souhaitez-vous que je vous transfère à un conseiller ? »
- n° 7 (seuil) : « Je ne dispose pas d'informations suffisamment fiables sur ce sujet précis. Je préfère vous mettre en relation avec un conseiller humain plutôt que de vous donner une réponse imprécise. »
- n° 10 : « Je suis désolé, mais je ne peux répondre qu'aux questions relatives aux produits, aux services et au support de Liss Strike (SAV, commandes, livraisons, garanties, etc.). »
- n° 16 : « Oui. Le paiement en plusieurs fois (3 fois) est possible sans frais pour les commandes de plus de 300 DT, à condition d'utiliser une des cartes bancaires partenaires proposées. »
- n° 17 : « Nous n'acceptons pas les chèques-cadeaux provenant d'autres magasins. »

## Totaux

| Issue | Questions | N° |
| --- | --- | --- |
| Arrêtées par le seuil (score < 0,35), sans LLM | **3** | 7, 12, 14 |
| Refus hors sujet par le garde-fou du *prompt* | **3** | 9, 10, 13 |
| LLM : « pas d'information », propose un conseiller ou le service client | **6** | 1, 2, 5, 6, 11, 15 |
| LLM : réponse négative fondée sur la base | **2** | 3, 8 |
| LLM : réponse négative non fondée sur un passage | **2** | 17 (règle inventée), 18 (plausible, cohérente avec la FAQ) |
| LLM : question couverte, réponse correcte | **2** | 4, 16 |
| **Réponse qui affirme à tort un service indisponible** | **0** | — |

Scores de confiance :

| Groupe | n | Min | Médiane | Max |
| --- | --- | --- | --- | --- |
| 18 questions sur des services | 18 | 0,299 | 0,405 | 0,739 |
| dont les 16 réellement non couvertes | 16 | 0,299 | 0,395 | 0,658 |
| Questions produit légitimes de la calibration (`scripts/calibrate_threshold.py`) | 10 | 0,368 | 0,613 | 0,745 |
| Questions hors sujet de la calibration | 4 | 0,273 | 0,357 | 0,429 |

Les scores des 16 questions non couvertes chevauchent ceux des questions légitimes : 12 sur 16 dépassent 0,368, le plus faible score légitime. Un seuil plus haut qui les arrêterait rejetterait aussi des questions légitimes.

## Vérification de la phrase du rapport v4

> « Dix-huit questions supplémentaires, sur des services plausibles mais indisponibles, n'ont jamais obtenu moins de 0,35 sans être déjà arrêtées par le garde-fou hors-sujet. »

**Inexacte, et mal construite.**

- Elle est fausse dans les faits : 3 questions sur 18 obtiennent moins de 0,35 ; elles sont arrêtées par le seuil, et le LLM n'est jamais appelé pour elles.
- Le garde-fou hors sujet du *prompt* n'arrête que 3 des 15 questions qui passent le seuil.
- Elle est aussi contradictoire dans sa logique : le garde-fou agit dans le LLM, donc **après** le seuil. Une question ne peut pas être « déjà arrêtée » par lui avant d'obtenir son score.

Formulation exacte permise par les données :

> Sur 18 questions portant sur des services plausibles mais non proposés, 3 sont arrêtées par le seuil de confiance (score de 0,30 à 0,34) et transférées sans appel au LLM. Les 15 autres (score de 0,36 à 0,74) sont transmises au LLM : 3 reçoivent un refus hors sujet, 6 une réponse indiquant l'absence d'information avec une proposition de conseiller, 4 une réponse négative, et les 2 questions en réalité couvertes par la base une réponse correcte. Aucune réponse n'affirme à tort qu'un service indisponible est proposé ; une seule énonce une règle absente de la base (refus des chèques-cadeaux d'autres magasins).

Le tableau `tab:calib18` du rapport v5 (3 questions de 0,30 à 0,34 ; 13 de 0,36 à 0,66 ; 2 couvertes à 0,66 et 0,74) est confirmé par cette mesure.

## Méthode

1. Recherche seule, dans le processus du script, avec `retriever.search(question, 4)` en mode `advanced` : hybride BM25 + dense (RRF), reranking cross-encoder `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` sur 20 candidats, filtre de distance 0,75, signal de confiance `cosine`, seuil 0,35. Mêmes réglages que `/chat/`. Pour une session neuve, la requête de recherche est le message lui-même.
2. Issue réelle : `POST /chat/` sur l'API locale, une session neuve par question, appels espacés de 3,2 s (limite de 20 requêtes par minute et par IP). Le LLM est appelé pour les 15 questions au-dessus du seuil. Une seule question sous le seuil (n° 7) est envoyée, pour vérifier le message d'escalade ; les deux autres ne le sont pas, car le LLM n'est pas appelé pour elles.
3. Jugement des réponses : sur le texte, en vérifiant chaque fait cité dans la base (`data/knowledge_base/`) : horaires de la boutique, 24 gouvernorats, D17 et Flouci, paiement en 3 fois. Aucune mention des chèques-cadeaux d'autres magasins dans la base.
4. Nettoyage : 17 sessions créées (1 d'échauffement + 16 questions), supprimées par identifiant : 34 messages, 17 conversations, 17 utilisateurs et 17 sessions Redis. 0 ligne restante. Les totaux de la base sont identiques avant et après (120 utilisateurs, 124 conversations, 506 messages). L'API démarrée pour la mesure a été arrêtée. Identifiants : `calibration_18_services_sessions.json`.

## Versions et machine

- Python 3.13.5, FastAPI 0.115.0, Uvicorn 0.30.0, client chromadb 1.5.9 ; serveur ChromaDB 1.4.1, PostgreSQL 16, Redis 7 (Docker, même machine)
- Modèle d'embedding `paraphrase-multilingual-MiniLM-L12-v2` ; LLM appelé par `/chat/` selon la configuration de l'application (Groq)
- CPU Intel Core i9-11900H, sans GPU, Windows 11

## Limites

- **18 questions seulement, toutes en français**, rédigées pour le projet : rien n'est mesuré en anglais, en arabe ni en tunisien.
- **Une seule génération par question** : la réponse du LLM peut varier d'un appel à l'autre ; le décompte des issues (refus, « pas d'information », réponse négative) n'est pas stable à coup sûr.
- **Jugement manuel**, par une seule personne, sans second annotateur.
- **Classement des réponses négatives** : « non fondée » signifie qu'aucun passage de la base ne le dit, pas que l'affirmation est fausse.
- **Questions n° 12 et 14** : l'issue « escalade » est déduite du code (score sous le seuil, chemin vérifié sur la n° 7), pas observée directement sur `/chat/`.
