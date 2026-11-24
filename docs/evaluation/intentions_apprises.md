# Intentions apprises par exemples (remarque 48, § 5.10)

Mesure du 24/11/2026 par `scripts/measure_intents_learned.py`.
- **Données.** Brutes et par message dans `intentions_apprises.json`.
- **Conditions.** Classifieur local à base d'embeddings, sans LLM ni `/chat/`, et ChromaDB n'est pas utilisé. `INTENT_MODEL_ENABLED` reste `false` sur disque : il n'est activé qu'**en mémoire**, dans le script. Le code applicatif n'est pas modifié.
- **Contrôle.** Pour chacun des 139 messages, la décision calculée par le script a été comparée à celle du vrai code (`semantic_intent.classify`, seuils actuels) : **identiques**.

## Réponse courte

- **Ce qui existe.** C'est un classifieur au **plus proche voisin**. Le message est comparé à 196 phrases d'exemple par similarité cosinus, avec le modèle d'embeddings du RAG. L'exemple le plus proche donne l'intention, s'il dépasse un seuil : 0,62 pour l'aide et le suivi de commande, 0,82 pour un transfert. Le classifieur ne joue **qu'après les règles**, et il est **désactivé par défaut**.
- **Les seuils sont justifiés, mais pas dans le rapport.** Le commentaire de `app/config.py` décrit un calibrage sur `data/intents/dev.json` (46 messages), refait ici à l'identique :
  - **0,62** est au milieu d'un plateau (0,56 à 0,66 donnent la même exactitude) ;
  - **0,82** se place juste au-dessus du seul cas dangereux du jeu de calibrage (0,796).
- **Évaluation.**
  - Sur `test.json` (59 messages, déjà publié), l'exactitude passe de 45,8 % à 71,2 %, avec 0 faux transfert.
  - Sur un **jeu complémentaire de 80 messages écrit pour cette mesure**, elle passe de 37,5 % à 70,0 %, toujours avec 0 faux transfert.
  - **Le rappel des transferts reste faible** : 41 % sur les 139 messages.
- **Seuils.**
  - Le seuil bas est peu sensible.
  - Le seuil haut est **au bord**. À 0,75 ou en dessous, de vraies questions de commande en tunisien sont transférées à tort. Au-dessus de 0,85, le rappel des transferts chute.
- **196 exemples ne suffisent pas à saturer.** Avec 50 % des exemples, l'exactitude tombe de 71 % à 63–68 %.
- **Faiblesse principale.** La frustration, et le tunisien.

## A1. Algorithme et place dans le traitement

Le code est dans `app/services/semantic_intent.py` :

```python
NEGATIVE = "general"
ESCALATION_INTENTS = frozenset({"human_agent", "frustration"})
LEARNED_INTENTS = ("human_agent", "frustration", "order_tracking", "help")

def nearest(text: str) -> LearnedIntent:
    """L'exemple le plus proche du message, quelle que soit son intention
    (y compris "general"), sans seuil."""
    index = _get_index()
    scores = index.matrix @ _normalized(_embed(text))
    best = int(np.argmax(scores))
    return LearnedIntent(index.labels[best], float(scores[best]), index.texts[best])

def threshold_for(intent: str) -> float:
    if intent in ESCALATION_INTENTS:
        return settings.INTENT_ESCALATION_THRESHOLD
    return settings.INTENT_SIMILARITY_THRESHOLD

def classify(text: str) -> Optional[LearnedIntent]:
    match = nearest(text)
    if match.intent == NEGATIVE or match.score < threshold_for(match.intent):
        return None
    return match
```

- **Plus proche voisin, sur un seul exemple.** On prend le **maximum** de similarité, sans moyenne par intention, sans vote et sans apprentissage. L'embedding est celui du RAG (`paraphrase-multilingual-MiniLM-L12-v2`, vecteurs normalisés).
- **Contre-exemples.** Si l'exemple le plus proche appartient à `general`, le message reste une question pour le RAG.
- **Deux seuils** (`app/config.py`) :
  - `INTENT_SIMILARITY_THRESHOLD = 0.62` s'applique à `order_tracking` et `help` ;
  - `INTENT_ESCALATION_THRESHOLD = 0.82` s'applique à `human_agent` et `frustration`.
  - Sous le seuil de son intention, le message part au RAG ; au-dessus, l'intention est retenue.
  - Il n'y a pas de zone intermédiaire : chaque intention n'a qu'un seuil.
- **Conséquence de chaque intention retenue** (`dialogue_manager._learned_intent`) :
  - `human_agent` → transfert (`explicit`) ;
  - `frustration` → transfert (`frustration`) ;
  - `order_tracking` → la même règle de suivi de commande ;
  - `help` → réponse d'aide fixe et menu d'accueil, sans RAG ni LLM.
- **Place dans l'ordre des étapes** (`dialogue_manager._handle_message`) :

  ```python
      intent_result = _intent_classifier.classify(message)
      intent_source = "regle" if intent_result.category != Category.GENERAL else None
      if intent_source is None and settings.INTENT_MODEL_ENABLED:
          learned = await _learned_intent(message)
  ```

  1. D'abord les règles : demande explicite, frustration, suivi de commande, politesse.
  2. Le modèle **seulement si aucune règle n'a tranché**, et si l'interrupteur est actif.
  3. En cas de panne du modèle : les règles seules.
  - L'origine de la décision est enregistrée (`intent_source` = `regle` ou `modele`).
- **Coût.** Voir B5 : environ 42 ms par message sans règle, une matrice de 294 Ko, et 1,7 s de préchargement.

## A2. Les 196 exemples

Le fichier est `data/intents/exemples.json`. Il est organisé en `{intention: {langue: [phrases]}}`, avec une description en tête.

| Intention | fr | en | ar | tn | Total |
| --- | --- | --- | --- | --- | --- |
| human_agent | 10 | 10 | 8 | 10 | 38 |
| frustration | 10 | 10 | 8 | 10 | 38 |
| order_tracking | 8 | 8 | 6 | 8 | 30 |
| help | 10 | 10 | 8 | 10 | 38 |
| general (contre-exemples) | 17 | 13 | 9 | 13 | 52 |
| **Total** | 55 | 51 | 39 | 51 | **196** |

**Longueur :** 2 à 11 mots, médiane 5. **Doublons exacts :** 0.

**Constitution.**
- **Non documentée.** Le commit `490961f` (07/10/2026, « feat: intentions apprises sur des phrases d'exemple, derrière un interrupteur ») dit seulement : « data/intents/ : exemples (fr, en, ar, tn), dev.json pour calibrer, test.json pour mesurer, sans recouvrement (vérifié par un test) ».
- **Aucune source ne précise la méthode.** Ni le message de commit, ni les commentaires, ni `docs/` ne disent si les phrases ont été écrites à la main, générées par un LLM ou reprises d'un autre jeu.
- **Seuls éléments écrits :**
  - la description du fichier : « Ne pas copier ici les phrases de dev.json et test.json » ;
  - la limite notée dans `intentions_avant_apres.md` : « les exemples, les seuils et le jeu de test viennent du même auteur ».
- C'est le seul commit qui touche à `data/intents/`.

**Le test de non-recouvrement** (`tests/test_semantic_intent.py:55-56`) compare des textes normalisés, donc il ne repère que les **égalités exactes**. Le chevauchement mesuré par similarité est le suivant :

| Jeu | Phrases | Identiques | Similarité > 0,95 | Meilleure similarité (médiane) |
| --- | --- | --- | --- | --- |
| `dev.json` (calibrage) | 46 | 0 | 1 | 0,722 |
| `test.json` (mesure) | 59 | 0 | **2** | 0,699 |
| `test_appris.json` (nouveau) | 80 | 0 | 0 (max 0,935) | 0,727 |
| `recherche.json` | 68 | 0 | 1 | 0,617 |
| `recherche_tunisien_nouvelles.json` | 18 | 0 | 1 | 0,659 |
| `ragas_results.json` | 25 | **1** | 2 | 0,613 |

**Cas au-dessus de 0,95 :**
- **Fuite vers `test.json`.**
  - « je veux plus des informations » ↔ l'exemple « je veux plus d'informations » (`help`, 0,997) ;
  - « vous vendez quoi ? » ↔ « qu'est-ce que vous vendez ? » (`help`, 0,971).
  - Deux des 11 messages `help` du jeu de test ont donc un quasi-double dans les exemples, ce qui **gonfle le rappel de `help` sur `test.json`**.
- **`dev.json`.** « que vendez-vous exactement ? » ↔ « qu'est-ce que vous vendez ? » (0,971).
- **Bancs de recherche.** Les quasi-doubles sont des contre-exemples `general` : « Quels sont les frais de livraison ? », identique à une question Ragas ; « ما هي طرق الدفع المتاحة » (0,954) ; « كم سعر وحدة ESP32؟ » ↔ « combien coûte un ESP32 ? » (0,970) ; « kifech nkalmekom ? » ↔ « kifech nkoumandi ? » (0,964). Ils sont sans effet sur l'évaluation des intentions, mais montrent que des questions des bancs ont servi de modèles aux contre-exemples.

## A3. Origine des seuils 0,62 et 0,82

- **Git.** `git log -S"0.62"` et `-S"0.82"` sur `app/config.py` et `semantic_intent.py` ne renvoient qu'un commit : `490961f` (07/10/2026).
- **Justification écrite, dans `app/config.py`** :

  > « Calibrées sur data/intents/dev.json (scripts/evaluate_intents.py --calibrate) : aide / commande : contre-exemples ≤ 0.56, bonnes réponses ≥ 0.67 → 0.62, au milieu ; transfert : le cas dangereux est une panne de produit en arabizi (« el capteur hedha ma ye5demch mli », proche d'une phrase de frustration à 0.796), les vraies demandes d'humain sont ≥ 0.83 → 0.82. Plusieurs vraies frustrations restent sous ce seuil : on préfère en rater une […] que transférer une simple question. »

- **Vérification : `evaluate_intents.py --calibrate`, relancé le 24/11.**
  - Toutes les combinaisons du seuil bas entre 0,56 et 0,66, avec un seuil haut de 0,80 ou 0,82, donnent **0 faux transfert et 82,6 % d'exactitude** sur `dev.json`. **0,62 est donc au milieu d'un plateau**, pas un optimum.
  - Le cas dangereux est bien à 0,796 (`general`, dont l'exemple le plus proche est `frustration`), et les vraies demandes d'humain sont à 0,834, 0,852 et 0,857. **0,82 est fixé par un seul message.**
- La justification existe donc dans le code, **mais elle manque dans le rapport**. Elle repose sur 46 messages.

## A4. Évaluation existante

`scripts/evaluate_intents.py` compare les règles seules aux règles complétées par le modèle. Il calcule la précision, le rappel, l'exactitude, les faux transferts et le temps ajouté. Il sépare deux jeux : `dev.json` pour calibrer (46 messages) et `test.json` pour mesurer (59 messages, « jamais utilisé pour choisir les seuils ni les exemples »).

Résultat publié dans `docs/evaluation/intentions_avant_apres.md`, et **reproduit à l'identique ici** :

| Mesure | Règles seules | Règles + modèle |
| --- | --- | --- |
| Exactitude | 45,8 % | 71,2 % |
| Faux transferts | 0 | 0 |
| Transferts manqués | 14 | 12 |

**Indépendance de `test.json`.** Aucune phrase n'est identique aux exemples, mais **2 sont des quasi-doubles** (A2). Les deux jeux ont aussi le même auteur. `test.json` n'est donc **pas entièrement indépendant** des exemples. Il ne porte pas d'annotation de langue : la langue utilisée ci-dessous est celle du détecteur.

## B1. Jeu complémentaire `data/intents/test_appris.json`

- **Écriture.** 80 messages, écrits à la main par Claude le 24/11/2026, **avant toute mesure**. Le contenu des exemples n'avait pas été lu : seuls leurs effectifs étaient connus.
- **Gel.** Le fichier n'a pas été modifié ensuite (SHA-256 `3c524ba9…2e646b7`).
- **Répartition.** 20 messages par langue (fr, en, ar, tn en arabizi) : `human_agent` 4, `frustration` 4, `order_tracking` 3, `help` 3, `general` 6.
- **Pièges dans `general`.**
  - un « agent » qui désigne un produit (agent de gravure, produit nettoyant) ;
  - la critique d'un produit (« ce produit est de mauvaise qualité ») ;
  - « comment passer une commande » ;
  - une question générale sur le délai de livraison ;
  - la panne d'un produit ;
  - une question de stock.
- **Découpage.** Moitiés A et B fixées dans le fichier avant la mesure, en alternant à l'intérieur de chaque langue et de chaque intention.
- **Recouvrement avec les exemples.** Aucune phrase identique ; similarité maximale 0,935.

## B2. Règles seules et règles + classifieur (seuils 0,62 / 0,82)

### Par intention (P = précision, R = rappel)

| Intention | n (test / appris) | `test.json` règles P / R | `test.json` + modèle P / R / F1 | `test_appris` règles P / R | `test_appris` + modèle P / R / F1 | Les deux : règles F1 → + modèle F1 |
| --- | --- | --- | --- | --- | --- | --- |
| human_agent | 11 / 16 | 100 % / 36 % | 100 % / 55 % / 71 % | 100 % / 31 % | 100 % / 56 % / 72 % | 50 % → 71 % |
| frustration | 10 / 16 | 100 % / 30 % | 100 % / 30 % / 46 % | 100 % / 6 % | 100 % / 25 % / 40 % | 27 % → 42 % |
| order_tracking | 10 / 12 | 100 % / 30 % | 100 % / 70 % / 82 % | — / 0 % | 100 % / 83 % / 91 % | 24 % → 87 % |
| help | 11 / 12 | — / 0 % | 77 % / 91 % / 83 % | — / 0 % | 69 % / 92 % / 79 % | — → 81 % |
| general | 17 / 24 | 35 % / 100 % | 53 % / 94 % / 68 % | 32 % / 100 % | 54 % / 92 % / 68 % | 50 % → 68 % |
| **Exactitude** | 59 / 80 | 45,8 % | **71,2 %** | 37,5 % | **70,0 %** | 41,0 % → 70,5 % |

### Décisions « transfert » et « RAG » (139 messages)

| Décision | Règles seules : P / R | Règles + modèle : P / R |
| --- | --- | --- |
| Transfert vers un conseiller (`human_agent` ou `frustration`) | 100 % / 25 % (13 sur 53) | **100 % / 42 %** (22 sur 53) |
| Question pour le RAG (`general`) | 33 % / 100 % | 54 % / 93 % |

- **Faux transferts** (client envoyé à un humain à tort) : **0** avec les règles seules, **0** avec le modèle.
- **Demandes de transfert manquées.** 40 avec les règles seules, **31** avec le modèle. Il en reste 19 sur 32 dans `test_appris`, surtout des frustrations dans toutes les langues et des demandes d'humain indirectes. Exemples : « Quelqu'un de votre équipe peut-il me rappeler ? », « Worst service ever, you never reply to my emails », « 7awelni l conseiller men fadhlek ».

### Par langue (exactitude ; transferts reconnus / manqués / faux)

| Langue | n | Règles seules | Règles + modèle |
| --- | --- | --- | --- |
| fr | 42 | 50 % (7 / 9 / 0) | 81 % (9 / 7 / 0) |
| en | 36 | 42 % (4 / 10 / 0) | 72 % (6 / 8 / 0) |
| ar | 27 | 30 % (1 / 10 / 0) | 70 % (3 / 8 / 0) |
| tn | 34 | 38 % (1 / 11 / 0) | **56 %** (4 / 8 / 0) |

Pour `test.json`, la langue est celle du détecteur ; pour `test_appris.json`, elle est annotée.

### Matrice de confusion, règles + modèle (139 messages ; lignes = attendu, colonnes = obtenu)

| Attendu ↓ / obtenu → | human_agent | frustration | order_tracking | help | general |
| --- | --- | --- | --- | --- | --- |
| human_agent (27) | **15** | 0 | 0 | 1 | 11 |
| frustration (26) | 0 | **7** | 0 | 4 | 15 |
| order_tracking (22) | 0 | 0 | **17** | 0 | 5 |
| help (23) | 0 | 0 | 0 | **21** | 2 |
| general (41) | 0 | 0 | 0 | 3 | **38** |

Avec les règles seules, tout ce qui n'est pas reconnu tombe dans `general` : 18 `human_agent`, 22 `frustration`, 19 `order_tracking` et 23 `help`.

### Messages dont le modèle change la décision (52 sur 139)

- **44 corrigés** : un oubli des règles est rattrapé.
- **3 dégradés**, tous en tunisien et tous envoyés vers `help`. Ce sont de vraies questions pour le RAG, qui reçoivent la réponse d'aide au lieu d'une réponse :
  - « kifech nraja3 produit ? » (0,749) ;
  - « el produit hedha qualité mte3ou khayba, yeskhon fissa3 » (0,822) ;
  - « el capteur ma y3ati 7atta mesure, chnowa na3mel ? » (0,790).
- **5 erreurs changées**, toutes en tunisien. Une frustration ou une demande d'humain reste non reconnue, mais elle passe de `general` à `help`. Exemples : « ma fama 7atta 7ad yjewebni, 3ib » et « ynajem 7ad men 3andkom y3ayetli ? ».
- **Aucun changement ne crée de faux transfert.**

## B3. Sensibilité aux seuils (139 messages)

Le seuil haut reste à 0,82 pendant que le seuil bas varie, et inversement.

| Seuil bas | Exactitude | Transfert P / R (faux) | RAG P / R |
| --- | --- | --- | --- |
| 0,50 | 71 % | 100 % / 42 % (0) | 54 % / 85 % |
| 0,55 | 71 % | 100 % / 42 % (0) | 54 % / 85 % |
| 0,60 | 71 % | 100 % / 42 % (0) | 54 % / 90 % |
| **0,62 (actuel)** | **71 %** | **100 % / 42 % (0)** | **54 % / 93 %** |
| 0,65 | 70 % | 100 % / 42 % (0) | 52 % / 93 % |
| 0,70 | 68 % | 100 % / 42 % (0) | 50 % / 93 % |
| 0,75 | 65 % | 100 % / 42 % (0) | 48 % / 95 % |

| Seuil haut | Exactitude | Transfert P / R (faux) | RAG P / R |
| --- | --- | --- | --- |
| 0,70 | 76 % | 94 % / 55 % (**2**) | 61 % / 93 % |
| 0,75 | 73 % | 93 % / 49 % (**2**) | 58 % / 93 % |
| 0,80 | 71 % | 100 % / 43 % (0) | 54 % / 93 % |
| **0,82 (actuel)** | **71 %** | **100 % / 42 % (0)** | **54 % / 93 %** |
| 0,85 | 68 % | 100 % / 36 % (0) | 51 % / 93 % |
| 0,90 | 64 % | 100 % / 25 % (0) | 48 % / 93 % |
| 0,95 | 64 % | 100 % / 25 % (0) | 48 % / 93 % |

Les tableaux séparés de `test.json` et de `test_appris.json` sont dans le JSON. Ils montrent les mêmes tendances.

**Lecture :**
- **Seuil bas.** Il est **peu sensible** : 0,50 à 0,65 donnent 70 à 71 %. 0,62 est dans un plateau, ce qui confirme le calibrage. Au-delà de 0,70, l'aide et le suivi de commande sont moins reconnus.
- **Seuil haut : au bord.**
  - **En dessous de 0,80**, des faux transferts apparaissent. Ce sont 2 questions de commande en tunisien : « chrit men 3andkom w mazelt ma 5dhit chay » (0,781, proche d'un exemple `human_agent`) et « el 7aja eli chritha el jem3a li fatet tba3thet walla le ? » (0,767, proche d'un exemple `frustration`).
  - **Au-dessus de 0,85**, le rappel des transferts chute (36 %, puis 25 %).
  - 0,80–0,82 est la dernière valeur sans faux transfert sur ces jeux : le choix est **cohérent avec la règle « aucun faux transfert », mais il n'a aucune marge**.
- **Proposition testée honnêtement** : choisie sur la moitié A, validée sur la moitié B, selon la règle « exactitude maximale sur A sans faux transfert ; à égalité, la plus proche des seuils actuels ».

  | Moitié | Seuils | Exactitude | Transferts reconnus / manqués / **faux** |
  | --- | --- | --- | --- |
  | A (choix) | 0,62 / 0,82 (actuels) | 75 % | 8 / 8 / 0 |
  | A (choix) | **0,65 / 0,70** (proposés) | 80 % | 10 / 6 / 0 |
  | B (validation) | 0,62 / 0,82 (actuels) | 65 % | 5 / 11 / 0 |
  | B (validation) | 0,65 / 0,70 (proposés) | 72 % | 8 / 8 / **1** |

  **Sur B, la proposition fait apparaître un faux transfert** : une question de commande en tunisien envoyée à un conseiller. **Elle n'est pas retenue**, et il n'y a pas de « valeur optimale » à annoncer. Baisser le seuil haut gagne du rappel au prix de faux transferts, et ce compromis est un choix métier. Sur ce découpage, les seuils actuels **ne sont pas arbitraires**.

## B4. Ablation : 50 % des exemples (5 tirages, graines 0 à 4)

Les 98 exemples sont tirés au hasard parmi les 196, sans stratification. La mesure porte sur les 139 messages, avec les seuils actuels.

| Mesure | 196 exemples | 98 exemples (min – max sur 5 tirages) |
| --- | --- | --- |
| Exactitude | 71 % | 63 – 68 % (médiane 64 %) |
| Transfert : rappel (faux) | 42 % (0) | 34 – 38 % (0 dans les 5 tirages) |
| Rappel `human_agent` | 56 % | 41 – 48 % |
| Rappel `frustration` | 27 % | 19 – 27 % |
| Rappel `order_tracking` | 77 % | 59 – 77 % |
| Rappel `help` | 91 % | 61 – 87 % |
| Rappel `general` | 93 % | 90 – 95 % |
| Exactitude fr | 81 % | 76 – 79 % |
| Exactitude en | 72 % | 58 – 69 % |
| Exactitude ar | 70 % | 59 – 67 % |
| Exactitude **tn** | 56 % | **47 – 59 %** |

Avec la moitié des exemples, tout baisse sauf `general` et les faux transferts. Les 196 exemples ne sont donc **pas en saturation** : en ajouter, surtout pour la frustration et le tunisien, devrait encore améliorer le résultat. C'est une extrapolation, pas une mesure. Le tunisien est le plus instable selon le tirage.

## B5. Coût (CPU)

| Mesure | Valeur |
| --- | --- |
| Préchargement (`semantic_intent.warmup` : embeddings des 196 exemples, modèle déjà chargé) | 1,74 s |
| Matrice des exemples (196 × 384 float32) | 294 Ko |
| Allocation nette pendant le préchargement (tracemalloc ; pic) | 334 Ko ; 3,0 Mo |
| Classification d'un message (embedding + produit scalaire), n = 139 | médiane 41,7 ms, p95 55,7 ms, max 69,8 ms |
| Mémoire du modèle d'embeddings | **non mesurée à part** : le modèle est partagé avec le RAG, donc il n'ajoute rien |

Le coût ne concerne que les messages qu'aucune règle n'a reconnus.

## Proposition pour le rapport

Le § 5.10 peut être développé à partir de A1, de A3 (le calibrage sur `dev.json`, avec la phrase de `config.py`), de B2 (les deux jeux) et de B3 (le seuil haut au bord). La conclusion honnête est la suivante :

> Le classifieur double à peu près l'exactitude des intentions (de 41 % à 70 % sur 139 messages), sans aucun faux transfert. Il laisse cependant passer 58 % des demandes de transfert, surtout les frustrations, et il est moins bon en tunisien. Il est donc livré **désactivé par défaut**, comme une perspective à consolider avec plus d'exemples et de vrais messages de clients.

## Versions et matériel

- Python 3.13.5, numpy 2.5.1, sentence-transformers 5.7.0, modèle `paraphrase-multilingual-MiniLM-L12-v2`
- Seuils : `INTENT_SIMILARITY_THRESHOLD` 0,62, `INTENT_ESCALATION_THRESHOLD` 0,82 ; `INTENT_MODEL_ENABLED` vaut `false` sur disque
- Intel Core i9-11900H, 15,7 Go de RAM, sans GPU, Windows 11

## Limites

- **Petits échantillons.** 139 messages au total, et 22 à 41 par intention. Une erreur représente 2 à 5 points de rappel.
- **Jeux écrits pour le projet.** `test_appris.json` a été écrit par Claude, qui connaissait le domaine et les règles, et non recueilli auprès de clients. `test.json`, `dev.json` et les exemples ont un seul auteur, et leur mode de rédaction n'est pas documenté.
- **Fuite possible.** 2 messages de `test.json` sur 59 sont des quasi-doubles d'exemples `help` (similarité 0,97 et 0,997). Le jeu complémentaire n'en a aucun (maximum 0,935).
- **Un seul découpage 50/50**, et seulement 40 messages par moitié.
- **Langue de `test.json`.** C'est celle du détecteur, qui se trompe parfois (voir `hallucination.md`).
- **Ablation non stratifiée.** Les tirages ne gardent pas la même proportion par intention et par langue.
- **Une seule phase mesurée.** On mesure l'intention, pas la qualité de la réponse qui suit.
