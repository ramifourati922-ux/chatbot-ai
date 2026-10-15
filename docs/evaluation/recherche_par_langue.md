# Recherche RAG par langue (sans LLM)

Banc de test : `data/evaluation/recherche.json`, 68 questions. Mesuré par `scripts/evaluate_retrieval.py`.

- **hit@4** : une bonne source figure dans les 4 passages envoyés au LLM.
- **MRR@4** : moyenne de 1/rang de la première bonne source (1 = toujours en tête).
- **advanced + arabizi** : question tunisienne complétée par la traduction des mots reconnus (`app/services/arabizi.py`), comme en production avec `RAG_ARABIZI_EXPANSION`.

| Mode | Langue | hit@4 | MRR@4 | Temps moyen de recherche |
| --- | --- | --- | --- | --- |
| basic | fr | 15/17 (88%) | 0.80 | 203 ms |
| basic | en | 17/17 (100%) | 0.84 | 202 ms |
| basic | ar | 15/17 (88%) | 0.85 | 195 ms |
| basic | tn | 7/17 (41%) | 0.30 | 199 ms |
| **basic** | **toutes** | **54/68 (79%)** | **0.70** | **200 ms** |
| hybrid | fr | 16/17 (94%) | 0.84 | 226 ms |
| hybrid | en | 16/17 (94%) | 0.79 | 227 ms |
| hybrid | ar | 17/17 (100%) | 0.94 | 219 ms |
| hybrid | tn | 9/17 (53%) | 0.50 | 232 ms |
| **hybrid** | **toutes** | **58/68 (85%)** | **0.77** | **226 ms** |
| advanced | fr | 17/17 (100%) | 1.00 | 1238 ms |
| advanced | en | 17/17 (100%) | 0.97 | 1186 ms |
| advanced | ar | 16/17 (94%) | 0.90 | 1184 ms |
| advanced | tn | 10/17 (59%) | 0.56 | 1252 ms |
| **advanced** | **toutes** | **60/68 (88%)** | **0.86** | **1215 ms** |
| advanced + arabizi | fr | 17/17 (100%) | 1.00 | 1239 ms |
| advanced + arabizi | en | 17/17 (100%) | 0.97 | 1188 ms |
| advanced + arabizi | ar | 16/17 (94%) | 0.90 | 1173 ms |
| advanced + arabizi | tn | 16/17 (94%) | 0.90 | 1332 ms |
| **advanced + arabizi** | **toutes** | **66/68 (97%)** | **0.94** | **1233 ms** |

Questions sans bonne source dans les 4 passages, mode basic (14) :

- [tn] retour-delai : « 9adech men nhar 3andi bech nraja3 produit ? »
- [tn] retour-frais : « chkoun ykhalles el transport ki nraja3 produit ? »
- [fr] livraison-delai : « En combien de temps je reçois mon colis ? »
- [tn] livraison-weekend : « twaslou nhar sebt walla a7ad ? »
- [tn] garantie-exclusions : « chnouwa eli ma ydakhlouch fel garantie ? »
- [tn] reclamation-casse : « el colis wsel w fih composant mkasser, chnouwa na3mel ? »
- [tn] paiement-moyens : « b chnouwa najjem nkhallas 3andkom ? »
- [tn] paiement-plusieurs-fois : « najjem nkhallas b ta9sit ? »
- [tn] promo-fidelite : « 3andkom programme fidélité lel clients ? »
- [tn] faq-horaires : « wa9tech yetsakker el magasin ? »
- [ar] produit-hc-sr04 : « أبحث عن حساس الموجات فوق الصوتية HC-SR04 »
- [fr] produit-sg90 : « Avez-vous des servomoteurs SG90 ? »
- [ar] produit-sg90 : « هل تبيعون محرك سيرفو SG90؟ »
- [tn] produit-sg90 : « tbi3ou servomoteur SG90 ? »

Questions sans bonne source dans les 4 passages, mode hybrid (10) :

- [tn] retour-delai : « 9adech men nhar 3andi bech nraja3 produit ? »
- [tn] retour-frais : « chkoun ykhalles el transport ki nraja3 produit ? »
- [fr] livraison-delai : « En combien de temps je reçois mon colis ? »
- [tn] livraison-weekend : « twaslou nhar sebt walla a7ad ? »
- [en] garantie-cartes : « How long is an Arduino board under warranty? »
- [tn] garantie-exclusions : « chnouwa eli ma ydakhlouch fel garantie ? »
- [tn] reclamation-casse : « el colis wsel w fih composant mkasser, chnouwa na3mel ? »
- [tn] paiement-moyens : « b chnouwa najjem nkhallas 3andkom ? »
- [tn] paiement-plusieurs-fois : « najjem nkhallas b ta9sit ? »
- [tn] faq-horaires : « wa9tech yetsakker el magasin ? »

Questions sans bonne source dans les 4 passages, mode advanced (8) :

- [tn] retour-delai : « 9adech men nhar 3andi bech nraja3 produit ? »
- [tn] retour-frais : « chkoun ykhalles el transport ki nraja3 produit ? »
- [tn] livraison-weekend : « twaslou nhar sebt walla a7ad ? »
- [tn] garantie-exclusions : « chnouwa eli ma ydakhlouch fel garantie ? »
- [ar] reclamation-casse : « وصلني الطرد ومكوّن مكسور، ماذا أفعل؟ »
- [tn] reclamation-casse : « el colis wsel w fih composant mkasser, chnouwa na3mel ? »
- [tn] paiement-moyens : « b chnouwa najjem nkhallas 3andkom ? »
- [tn] paiement-plusieurs-fois : « najjem nkhallas b ta9sit ? »

Questions sans bonne source dans les 4 passages, mode advanced + arabizi (2) :

- [ar] reclamation-casse : « وصلني الطرد ومكوّن مكسور، ماذا أفعل؟ »
- [tn] reclamation-casse : « el colis wsel w fih composant mkasser, chnouwa na3mel ? »

## Limites

- Peu de thèmes, questions écrites pour le projet : des tendances, pas des mesures définitives.
- Les questions arabes sur un produit gardent son nom en lettres latines (« ESP32 »), comme les clients l'écrivent.
- Mesure la recherche seule, pas la réponse rédigée par le LLM (voir l'évaluation RAGas).
- Lexique arabizi écrit après avoir vu les échecs en tunisien de `recherche.json` : sa généralisation est vérifiée sur des questions tunisiennes nouvelles (`recherche_tunisien_nouvelles.json`).
- Temps mesurés sur un ordinateur portable, sans GPU.
