# Recherche RAG par langue (sans LLM)

Banc de test : `data/evaluation/recherche_tunisien_nouvelles.json`, 18 questions. Mesuré par `scripts/evaluate_retrieval.py`.

- **hit@4** : une bonne source figure dans les 4 passages envoyés au LLM.
- **MRR@4** : moyenne de 1/rang de la première bonne source (1 = toujours en tête).
- **advanced + arabizi** : question tunisienne complétée par la traduction des mots reconnus (`app/services/arabizi.py`), comme en production avec `RAG_ARABIZI_EXPANSION`.

| Mode | Langue | hit@4 | MRR@4 | Temps moyen de recherche |
| --- | --- | --- | --- | --- |
| basic | tn | 8/18 (44%) | 0.38 | 202 ms |
| hybrid | tn | 11/18 (61%) | 0.50 | 246 ms |
| advanced | tn | 9/18 (50%) | 0.42 | 1291 ms |
| advanced + arabizi | tn | 11/18 (61%) | 0.54 | 1374 ms |

Questions sans bonne source dans les 4 passages, mode basic (10) :

- [tn] retour-etat : « lazem el produit ykoun msakker fi carton mte3ou bech nraja3ou ? »
- [tn] echange : « najjem nbadel el produit b produit ekher ? »
- [tn] remboursement-delai : « ba3d ma nraja3 el produit, wa9tech ywalliw flousi ? »
- [tn] garantie-capteurs : « el capteurat 3andhom garantie 9adech ? »
- [tn] article-manquant : « el colis wsel w na9es fih article, chnouwa na3mel ? »
- [tn] mauvais-produit : « jani produit ghalet mouch eli commandit »
- [tn] paiement-securise : « el khlass bel carta 3al site mdhamoun ? »
- [tn] soldes : « wa9tech el soldes 3andkom ? »
- [tn] parrainage : « ki njib sa7bi yechri, nerba7 chay ? »
- [tn] produit-fer-souder : « nlawej 3la fer à souder mli7 »

Questions sans bonne source dans les 4 passages, mode hybrid (7) :

- [tn] retour-etat : « lazem el produit ykoun msakker fi carton mte3ou bech nraja3ou ? »
- [tn] remboursement-delai : « ba3d ma nraja3 el produit, wa9tech ywalliw flousi ? »
- [tn] article-manquant : « el colis wsel w na9es fih article, chnouwa na3mel ? »
- [tn] mauvais-produit : « jani produit ghalet mouch eli commandit »
- [tn] paiement-securise : « el khlass bel carta 3al site mdhamoun ? »
- [tn] soldes : « wa9tech el soldes 3andkom ? »
- [tn] parrainage : « ki njib sa7bi yechri, nerba7 chay ? »

Questions sans bonne source dans les 4 passages, mode advanced (9) :

- [tn] remboursement-delai : « ba3d ma nraja3 el produit, wa9tech ywalliw flousi ? »
- [tn] garantie-capteurs : « el capteurat 3andhom garantie 9adech ? »
- [tn] article-manquant : « el colis wsel w na9es fih article, chnouwa na3mel ? »
- [tn] mauvais-produit : « jani produit ghalet mouch eli commandit »
- [tn] facture : « kifech nekhou facture ? »
- [tn] paiement-securise : « el khlass bel carta 3al site mdhamoun ? »
- [tn] soldes : « wa9tech el soldes 3andkom ? »
- [tn] parrainage : « ki njib sa7bi yechri, nerba7 chay ? »
- [tn] produit-fer-souder : « nlawej 3la fer à souder mli7 »

Questions sans bonne source dans les 4 passages, mode advanced + arabizi (7) :

- [tn] retour-etat : « lazem el produit ykoun msakker fi carton mte3ou bech nraja3ou ? »
- [tn] garantie-capteurs : « el capteurat 3andhom garantie 9adech ? »
- [tn] article-manquant : « el colis wsel w na9es fih article, chnouwa na3mel ? »
- [tn] mauvais-produit : « jani produit ghalet mouch eli commandit »
- [tn] soldes : « wa9tech el soldes 3andkom ? »
- [tn] parrainage : « ki njib sa7bi yechri, nerba7 chay ? »
- [tn] produit-fer-souder : « nlawej 3la fer à souder mli7 »

## Limites

- Peu de thèmes, questions écrites pour le projet : des tendances, pas des mesures définitives.
- Les questions arabes sur un produit gardent son nom en lettres latines (« ESP32 »), comme les clients l'écrivent.
- Mesure la recherche seule, pas la réponse rédigée par le LLM (voir l'évaluation RAGas).
- Lexique arabizi écrit après avoir vu les échecs en tunisien de `recherche.json` : sa généralisation est vérifiée sur des questions tunisiennes nouvelles (`recherche_tunisien_nouvelles.json`).
- Temps mesurés sur un ordinateur portable, sans GPU.
