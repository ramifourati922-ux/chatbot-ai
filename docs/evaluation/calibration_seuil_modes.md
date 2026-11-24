# Calibration du seuil de confiance (0,35) dans les trois modes de recherche

Mesure du 24/11/2026 : `scripts/calibrate_threshold.py`, lancé tel quel 4 fois, plus 3 répétitions en pleine précision qui importent ses fonctions sans le modifier.
- **Recherche seule.** Ni `/chat/` ni le LLM ne sont appelés, et rien n'est écrit en base.
- **Production en lecture seule.** La collection `liss_strike_kb` est seulement lue.
- **Encodage de la console.** Le script plante sous Windows à l'impression de « → » (console cp1252). Il a donc été lancé avec `PYTHONIOENCODING=utf-8`, sans aucune modification.

Rapport visé : `Rapport_PFE_LissStrike_v4_Latex/chapitre/06c-Chapitre4.tex`, lignes 129 à 133. Le tableau `tab:calibdist` du v5 (`06d-Chapitre5.tex:255-256`) donne déjà les bonnes valeurs par mode.

## 1. Sortie brute (exécution 1 sur 4)

```
=== basic ===
  [Capteurs              ] cos=0.626  top1='Capteur VL53L0X (capteur seul (nu)) '  <- Avez-vous un capteur de distance VL53L0X ?
  [Connectique           ] cos=0.549  top1='Câbles Dupont Femelle-Femelle 40cm (lot de 65'  <- Je cherche des cables Dupont male-femelle
  [Alimentation          ] cos=0.676  top1='Chargeur batteries 18650 (2 slots) '  <- Vous avez des piles 18650 en stock ?
  [Moteurs & Roues       ] cos=0.591  top1='Moteur pas-à-pas NEMA14 mini (1.5A) '  <- Combien coute un moteur pas-a-pas NEMA17 ?
  [Afficheurs            ] cos=0.672  top1='Afficheur 7 segments 4 chiffre(s) (jaune) '  <- Avez-vous un afficheur 7 segments 4 chiffres ?
  [Eclairage LED         ] cos=0.727  top1='Contrôleur LED RGB (télécommande IR) '  <- Je voudrais un controleur LED RGB avec telecommande
  [Instruments de Mesure ] cos=0.702  top1='Analyseur logique 8 canaux '  <- Vous vendez des analyseurs logiques 8 canaux ?
  [Outillage             ] cos=0.368  top1='Étain à souder sans plomb (100g) '  <- Avez-vous de l'etain a souder sans plomb ?
  [Cartes Programmables  ] cos=0.599  top1='Carte Arduino Due (compatible (clone)) '  <- Est-ce que la carte Arduino Due est disponible ?
  [Modules               ] cos=0.745  top1='Module relais 16 canal(aux) 12V '  <- Je cherche un module relais 16 canaux
  [hors-sujet            ] cos=0.531  top1="Q: Livrez-vous à l'international, en dehors d"  <- Quelle est la recette du couscous tunisien ?
  [hors-sujet            ] cos=0.351  top1='Panneau solaire 6V 2W '  <- Combien de lunes a la planete Jupiter ?
  [hors-sujet            ] cos=0.363  top1='Q: Livrez-vous en dehors de Tunis (autres vil'  <- Quelle est la capitale de la France ?
  [hors-sujet            ] cos=0.273  top1='Q: Existe-t-il une offre de parrainage ?'  <- Raconte-moi une blague

=== hybrid ===
  [Capteurs              ] cos=0.626  top1='Capteur VL53L0X (capteur seul (nu)) '  <- Avez-vous un capteur de distance VL53L0X ?
  [Connectique           ] cos=0.549  top1='Câbles Dupont Femelle-Femelle 40cm (lot de 65'  <- Je cherche des cables Dupont male-femelle
  [Alimentation          ] cos=0.676  top1='Chargeur batteries 18650 (2 slots) '  <- Vous avez des piles 18650 en stock ?
  [Moteurs & Roues       ] cos=0.575  top1='Driver moteur A4988 (1 moteur) '  <- Combien coute un moteur pas-a-pas NEMA17 ?
  [Afficheurs            ] cos=0.672  top1='Afficheur 7 segments 4 chiffre(s) (jaune) '  <- Avez-vous un afficheur 7 segments 4 chiffres ?
  [Eclairage LED         ] cos=0.727  top1='Contrôleur LED RGB (télécommande IR) '  <- Je voudrais un controleur LED RGB avec telecommande
  [Instruments de Mesure ] cos=0.702  top1='Analyseur logique 8 canaux '  <- Vous vendez des analyseurs logiques 8 canaux ?
  [Outillage             ] cos=0.368  top1='Étain à souder sans plomb (100g) '  <- Avez-vous de l'etain a souder sans plomb ?
  [Cartes Programmables  ] cos=0.599  top1='Carte Arduino Due (compatible (clone)) '  <- Est-ce que la carte Arduino Due est disponible ?
  [Modules               ] cos=0.745  top1='Module relais 16 canal(aux) 12V '  <- Je cherche un module relais 16 canaux
  [hors-sujet            ] cos=0.531  top1="Q: Livrez-vous à l'international, en dehors d"  <- Quelle est la recette du couscous tunisien ?
  [hors-sujet            ] cos=0.351  top1='Panneau solaire 6V 2W '  <- Combien de lunes a la planete Jupiter ?
  [hors-sujet            ] cos=0.363  top1='Q: Livrez-vous en dehors de Tunis (autres vil'  <- Quelle est la capitale de la France ?
  [hors-sujet            ] cos=0.273  top1='Q: Existe-t-il une offre de parrainage ?'  <- Raconte-moi une blague

=== advanced ===
  [Capteurs              ] cos=0.626  reranker=0.998  top1='Capteur VL53L0X (capteur seul (nu)) '  <- Avez-vous un capteur de distance VL53L0X ?
  [Connectique           ] cos=0.543  reranker=0.898  top1='Câbles Dupont Femelle-Femelle 50cm (lot de 80'  <- Je cherche des cables Dupont male-femelle
  [Alimentation          ] cos=0.597  reranker=1.000  top1='Pile/Batterie 18650 (pack de 10) '  <- Vous avez des piles 18650 en stock ?
  [Moteurs & Roues       ] cos=0.507  reranker=0.998  top1='Moteur pas-à-pas NEMA17 1.8° (1.5A) '  <- Combien coute un moteur pas-a-pas NEMA17 ?
  [Afficheurs            ] cos=0.672  reranker=0.999  top1='Afficheur 7 segments 4 chiffre(s) (vert) '  <- Avez-vous un afficheur 7 segments 4 chiffres ?
  [Eclairage LED         ] cos=0.727  reranker=0.974  top1='Contrôleur LED RGB (télécommande IR) '  <- Je voudrais un controleur LED RGB avec telecommande
  [Instruments de Mesure ] cos=0.702  reranker=0.986  top1='Analyseur logique 8 canaux '  <- Vous vendez des analyseurs logiques 8 canaux ?
  [Outillage             ] cos=0.368  reranker=0.839  top1='Étain à souder sans plomb (100g) '  <- Avez-vous de l'etain a souder sans plomb ?
  [Cartes Programmables  ] cos=0.599  reranker=1.000  top1='Carte Arduino Due (original) '  <- Est-ce que la carte Arduino Due est disponible ?
  [Modules               ] cos=0.745  reranker=0.992  top1='Module relais 16 canal(aux) 5V '  <- Je cherche un module relais 16 canaux
  [hors-sujet            ] cos=0.429  reranker=0.039  top1='Q: Qui est Liss Strike ?'  <- Quelle est la recette du couscous tunisien ?
  [hors-sujet            ] cos=0.351  reranker=0.001  top1='Panneau solaire 5V 1W '  <- Combien de lunes a la planete Jupiter ?
  [hors-sujet            ] cos=0.363  reranker=0.001  top1='Q: Livrez-vous en dehors de Tunis (autres vil'  <- Quelle est la capitale de la France ?
  [hors-sujet            ] cos=0.273  reranker=0.005  top1='Q: Existe-t-il une offre de parrainage ?'  <- Raconte-moi une blague

=== Résumé ===
basic / cosinus        produits min=0.368 (max=0.745)  |  hors-sujet max=0.531 (min=0.273)  →  NON séparables, marge=-0.163
hybrid / cosinus       produits min=0.368 (max=0.745)  |  hors-sujet max=0.531 (min=0.273)  →  NON séparables, marge=-0.163
advanced / cosinus     produits min=0.368 (max=0.745)  |  hors-sujet max=0.429 (min=0.273)  →  NON séparables, marge=-0.062
advanced / reranker    produits min=0.839 (max=1.000)  |  hors-sujet max=0.039 (min=0.001)  →  séparables, marge=+0.800

Seuils : cosinus = 0.35 (défaut), reranker = 0.045 (RAG_CONFIDENCE_SIGNAL=reranker)
```

Le top1 est le premier passage renvoyé. Le score cosinus vaut 1 moins la plus petite distance parmi les passages retenus, et ce n'est pas forcément celle du top1.

## 2. Tableau récapitulatif

Scores en pleine précision, arrondis à 3 décimales (voir la section 3).

| Question | Basic | Hybrid | Advanced (cosinus) | Advanced (reclassement) |
| --- | --- | --- | --- | --- |
| Capteur de distance VL53L0X | 0,626 | 0,626 | 0,626 | 0,998 |
| Câbles Dupont mâle-femelle | 0,549 | 0,549 | 0,543 | 0,898 |
| Piles 18650 | 0,676 | 0,676 | 0,597 | 1,000 |
| Moteur pas-à-pas NEMA17 | 0,591 | 0,575 | 0,507 | 0,998 |
| Afficheur 7 segments 4 chiffres | 0,672 | 0,672 | 0,672 | 0,999 |
| Contrôleur LED RGB avec télécommande | 0,727 | 0,727 | 0,727 | 0,974 |
| Analyseurs logiques 8 canaux | 0,702 | 0,702 | 0,702 | 0,986 |
| Étain à souder sans plomb | **0,368** | **0,368** | **0,368** | 0,839 |
| Carte Arduino Due | 0,599 | 0,599 | 0,599 | 1,000 |
| Module relais 16 canaux | 0,745 | 0,745 | 0,745 | 0,992 |
| *Hors sujet* : recette du couscous | **0,531** | **0,531** | **0,429** | 0,039 |
| *Hors sujet* : lunes de Jupiter | 0,351 | 0,351 | 0,351 | 0,001 |
| *Hors sujet* : capitale de la France | 0,363 | 0,363 | 0,363 | 0,001 |
| *Hors sujet* : blague | 0,273 | 0,273 | 0,273 | 0,005 |

| Indicateur | Basic | Hybrid | Advanced (cosinus) | Advanced (reclassement, seuil 0,045) |
| --- | --- | --- | --- | --- |
| Plus faible score légitime | 0,368 | 0,368 | 0,368 | 0,839 |
| Plus fort score hors sujet | 0,531 | 0,531 | 0,429 | 0,039 |
| Écart entre les deux groupes (légitime min − hors sujet max) | −0,163 | −0,163 | −0,062 | +0,800 |
| Marge au-dessus du seuil (légitime min − seuil) | 0,018 (0,0176) | 0,018 (0,0176) | 0,018 (0,0176) | 0,794 |
| Hors sujet acceptés à tort (score ≥ seuil) | **3 sur 4** (couscous, capitale, Jupiter) | **3 sur 4** | **3 sur 4** | 0 sur 4 |
| Légitimes rejetés à tort (score < seuil) | 0 sur 10 | 0 sur 10 | 0 sur 10 | 0 sur 10 |

Jupiter vaut 0,350758 : il ne dépasse le seuil que de 0,0008.

## 3. Reproductibilité

- **4 exécutions du script.** Sorties identiques à l'octet près (`diff`).
- **3 répétitions en pleine précision**, dans un même processus, sur les 3 modes. Écart nul à 10⁻⁶ près pour chaque question, en cosinus comme en reclassement, et le top1 est identique à chaque fois.

| Question | Advanced, cosinus (min–max sur 3) | Advanced, reclassement (min–max sur 3) |
| --- | --- | --- |
| VL53L0X | 0,625595–0,625595 | 0,997798–0,997798 |
| Dupont | 0,542590–0,542590 | 0,898256–0,898256 |
| 18650 | 0,596924–0,596924 | 0,999652–0,999652 |
| NEMA17 | 0,506655–0,506655 | 0,998478–0,998478 |
| 7 segments | 0,672399–0,672399 | 0,999222–0,999222 |
| LED RGB | 0,727352–0,727352 | 0,973632–0,973632 |
| Analyseur logique | 0,702472–0,702472 | 0,985765–0,985765 |
| Étain | 0,367567–0,367567 | 0,839455–0,839455 |
| Arduino Due | 0,599162–0,599162 | 0,999939–0,999939 |
| Relais 16 canaux | 0,744692–0,744692 | 0,991695–0,991695 |
| Couscous | 0,429196–0,429196 | 0,039227–0,039227 |
| Jupiter | 0,350758–0,350758 | 0,000884–0,000884 |
| Capitale | 0,362805–0,362805 | 0,000584–0,000584 |
| Blague | 0,272854–0,272854 | 0,004626–0,004626 |

À index constant, le HNSW de production et le modèle de reclassement, sur CPU, sont donc déterministes ici. Les scores ne peuvent changer que si **l'index ou la base changent**, c'est-à-dire après une réingestion ou une modification de la base de connaissances.

## 4. Rapprochement avec le rapport v4

Le passage concerné est `06c-Chapitre4.tex:129-133`.

| Valeur du v4 | Retrouvée aujourd'hui ? | Mode | Origine et date |
| --- | --- | --- | --- |
| 0,391 (plus faible légitime « à l'origine ») | **non** : aujourd'hui 0,368 (étain), dans les 3 modes | — | **1re calibration**. Commit `234bfef` du 29/08/2026, commentaire de `app/config.py` : « Questions produit légitimes : confiance entre 0.391 et 0.745 ». Recherche dense seule, avant l'Advanced RAG. Le script `test_calibration.py` n'a jamais été versionné (aucune trace dans `git log --all`), et la question qui avait 0,391 n'est pas notée. Même valeur dans `Downloads\report.pdf` (03/09/2026). Le 25/09/2026 (`298a9b9`), le minimum était déjà 0,368 dans les 3 modes ; la cause de ce passage de 0,391 à 0,368 est **non établie**. |
| 0,368 (étain à souder) | **oui**, 0,367567 | basic, hybrid, advanced | `298a9b9` (25/09/2026) puis aujourd'hui, inchangée |
| 0,745 | **oui**, 0,744692 (relais 16 canaux) | basic, hybrid, advanced | `234bfef` (29/08) et `298a9b9` (25/09), inchangée |
| ~0,28 (« environ 0,27 à 0,28 ») | **compatible** : blague à 0,273 | basic, hybrid, advanced | `234bfef` (29/08/2026), commentaire de `config.py` : « confiance ~0.27-0.28 ». Le 25/09, `CHANGELOG_ADVANCED_RAG.md:198-200` donnait 0,267 (basic et hybrid) et 0,263 (advanced). Aujourd'hui 0,273 : la cause de ce petit écart est **non établie**. |
| 0,363 (capitale de la France) | **oui**, 0,362805 | basic, hybrid, advanced | `298a9b9` (25/09/2026), inchangée |
| 0,351 (Jupiter) | **oui**, 0,350758 | basic, hybrid, advanced | Absente de git (`git log -S"0.351"` ne renvoie rien). Mesurée avec `calibrate_threshold.py` le 05/11/2026, pendant la rédaction du rapport. |
| 0,531 (couscous) | **oui en basic et hybrid seulement** (0,530601). **En advanced : 0,429.** | basic, hybrid | Le couscous n'est associé à 0,531 nulle part dans git : `git log -S"0.531"` ne renvoie que des scores Ragas `answer_relevancy` (`f43153c`). Mesurée le 05/11/2026 avec `calibrate_threshold.py`. Avant, la valeur était **0,500** (`298a9b9` du 25/09 ; `config.py` ; `CHANGELOG_ADVANCED_RAG.md:205` ; `report.pdf` du 03/09). |
| marge de 0,018 | **oui**, 0,0176 | basic, hybrid, advanced | `298a9b9` (25/09/2026), inchangée |
| « 3 acceptations à tort sur 4 » | **oui**, dans les 3 modes | basic, hybrid, advanced | Valable depuis le 29/09/2026 au moins. Le 25/09, `CHANGELOG_ADVANCED_RAG.md:207` et `config.py` disaient « seuls 2 hors-sujet sur 4 escaladent (Jupiter, blague) ». Jupiter est aujourd'hui à 0,351, donc accepté. La cause de ce changement pour Jupiter est **non établie**. |
| « valables dans les trois modes » | **en partie** | — | Le minimum (0,368), le maximum (0,745) et les 3 hors sujet acceptés sont les mêmes dans les 3 modes. Mais le couscous vaut 0,531 en basic et hybrid et **0,429 en advanced**, et 3 scores légitimes diffèrent en advanced (Dupont 0,543, piles 0,597, NEMA17 0,507). |

### Cause établie du passage de 0,500 à 0,531 pour le couscous

En basic, le top1 du couscous est le passage FAQ « Livrez-vous à l'international, en dehors de la Tunisie ? ». Sa réponse a été rédigée par le commit `1993dbb` du 29/09/2026, intitulé « réponses FAQ manquantes ».
- **Avant :** « [À REMPLIR : préciser si livraison internationale disponible ou non…] ».
- **Après :** « Non, la livraison est pour l'instant disponible uniquement en Tunisie… ».

Un recalcul hors ligne, avec le même modèle d'embedding, donne pour le couscous **0,5002 face à l'ancien texte** et **0,5306 face au nouveau**, soit exactement 0,500 avant et 0,531 après. En advanced, le reclassement fait sortir d'autres passages, et le plus proche des passages retenus est à 0,429 (top1 « Qui est Liss Strike ? »).

**Diagnostic.** Le v4 mélange trois états de la base, sans les dater :
- 0,391 et environ 0,28 : 29/08, recherche dense seule ;
- 0,368, 0,745 et 0,018 : 25/09 et toujours valables ;
- 0,531, 0,363 et 0,351 : base actuelle, après le 29/09, en basic et hybrid.

La mesure récente en advanced (hors sujet maximum 0,429) ne contredit pas 0,531 : les deux valeurs ne viennent pas du même mode.

## 5. Valeurs à corriger et formulation exacte

**À corriger dans le v4 :**
- **« 0,391 ».** C'est la valeur de la 1re calibration (29/08/2026, recherche dense seule), qui n'est plus valable. La présenter datée, ou la remplacer par 0,368.
- **« environ 0,27 à 0,28 ».** C'est la valeur du 29/08. Aujourd'hui, la blague vaut 0,273 dans les 3 modes.
- **« recette du couscous (0,531) ».** C'est juste en basic et hybrid, mais 0,429 en advanced, qui est le mode par défaut. Il faut préciser le mode.
- **« dans les trois modes ».** C'est vrai pour le minimum, le maximum et le nombre d'acceptations à tort, mais pas pour tous les scores.

**Restent justes :**
- 0,368 (étain), 0,745, la marge de 0,018 (0,0176) ;
- 0,363 (capitale), 0,351 (Jupiter) ;
- « 3 hors sujet sur 4 dépassent le seuil », dans les 3 modes ;
- 0 question légitime rejetée à tort.

**Formulation proposée :**

> Le seuil a été calibré une première fois le 29/08/2026, en recherche dense seule : les 10 questions légitimes obtenaient entre 0,391 et 0,745. Avec la base actuelle, les scores sont reproductibles d'une exécution à l'autre. La plus faible question légitime, « Avez-vous de l'étain à souder sans plomb ? », obtient 0,368 dans les trois modes de recherche, soit une marge de 0,018 seulement au-dessus du seuil de 0,35 ; aucune question légitime n'est rejetée à tort. Côté hors sujet, seule la demande de blague (0,273) passe sous le seuil. Les trois autres le dépassent dans les trois modes : la capitale de la France (0,363), Jupiter (0,351, à moins d'un millième du seuil) et la recette du couscous (0,531 en recherche dense et hybride, 0,429 en mode avancé). Le seuil n'arrête donc qu'une question hors sujet sur quatre ; les trois autres sont refusées par la consigne du *prompt*. Le score du couscous est passé de 0,500 à 0,531 quand la réponse de la FAQ sur la livraison internationale a été rédigée (29/09/2026) : ces scores dépendent du contenu de la base et doivent être remesurés après chaque modification.

## Versions

- Python 3.13.5, numpy 2.5.1, sentence-transformers 5.7.0
- Client chromadb 1.5.9 ; serveur ChromaDB 1.4.1 (image `chromadb/chroma:1.4.1`, l'API répond « 1.0.0 »)
- Modèle d'embedding `paraphrase-multilingual-MiniLM-L12-v2`
- Modèle de reclassement `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`, `RERANK_CANDIDATES` = 20
- Seuils : cosinus 0,35 (`RAG_CONFIDENCE_SIGNAL` = cosine), reclassement 0,045
- Collection de production : 11 109 documents ; HNSW cosinus, `ef_search` 100, `max_neighbors` 16 ; CPU, sans GPU

## Limites

- **14 questions seulement**, toutes en français, et une seule formulation par question.
- **Origines non établies.** On ne sait pas pourquoi le minimum légitime est passé de 0,391 (29/08) à 0,368 (25/09), ni pourquoi la blague est passée de 0,267 à 0,273. On ne sait pas non plus pourquoi Jupiter, sous le seuil le 25/09 d'après le CHANGELOG, est aujourd'hui à 0,351. Il n'est pas possible de rejouer l'index ou la base de ces dates : `test_calibration.py` n'a jamais été versionné et les anciens index n'existent plus.
- **Ambiguïté dans git.** `aeec4f3` (25/09) note « confiance 0.391 / 0.444 » pour les questions hors sujet Jupiter et capitale de la France. Le même nombre 0,391 désigne donc, dans un autre tableau, un score hors sujet : ce n'est pas la même mesure que la calibration du 29/08.
- **Déterminisme démontré à index constant seulement.** Une réingestion reconstruit le HNSW et peut déplacer les scores. Le seuil de 0,35 n'a qu'une marge de 0,018 côté légitime et de 0,0008 côté Jupiter.
- **Rien sur le comportement final.** Le comportement de bout en bout, c'est-à-dire le refus par le *prompt* des hors sujet acceptés, n'est pas mesuré ici : ni le LLM ni `/chat/` n'ont été appelés.
