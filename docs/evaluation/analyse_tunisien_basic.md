# Les 3 questions tunisiennes à 0,000 en mode Basic (remarque 54)

Analyse du 24/11/2026 par `scripts/analyse_tunisien_basic.py`, en lecture seule de `docs/evaluation/ragas_results.json` (SHA-256 identique avant et après : `ead140586ddc71706f294b81b5d456ab568a86ddce308d32a36ff8bee36a2b63`). Aucun appel à Groq ni à un LLM, aucune écriture en base, code applicatif inchangé.

## 1. Les 3 questions, en Basic et en Advanced

### `tn-garantie` (catégorie sav)

- **Question :** chnowa el garantie mta3 el multimetre
- **Référence :** Les instruments de mesure comme les multimètres sont garantis 12 mois contre tout défaut de fabrication.
- **Sources attendues :** sav/garantie.txt

#### Basic

- **retrieved_sources :** LS-CO-008314, LS-CO-008298, LS-EL-000089, LS-EL-000083 ; **hit_at_4 :** False ; **confiance :** 0.438 (= 1 − distance minimale : 0.562) ; **would_escalate :** False
- **Scores :** CP 0,000, CR 0,000, F 0,000, AR 0,000 ; **erreurs :** aucune
- **Classement :** (a) refus. « ma nجمش نعطيك معلومات دقيقة على الضمان […] نحولك لمستشار الخدمة » : pas d'information, proposition de conseiller ; aucun fait affirmé.

**Réponse générée (en entier) :**

> Saha, ma nجمش نعطيك معلومات دقيقة على الضمان متاع الـmultimetre من قاعدة المعطيات اللي عنا. نجّم نتحقق من الموضوع ولا نحولك لمستشار الخدمة بش يعطيك التفاصيل الكاملة. إذا تحب، نبعثلك إيميل أو نكلمك مباشرة. ;)

**Contextes transmis au juge : 4** (200 premiers caractères)

1. LED UV 3mm (diffusé) | Catégorie: Composants | Prix: 0.71 DT | Disponibilité: en stock | Caractéristiques: UV, 3mm, diffusé | LED UV 3mm, finition diffusé.
2. LED blanc 3mm (diffusé) | Catégorie: Composants | Prix: 0.17 DT | Disponibilité: en stock | Caractéristiques: blanc, 3mm, diffusé | LED blanc 3mm, finition diffusé.
3. Ruban LED WS2812B adressable 3m (144 LED/m, IP65 (résistant éclaboussures)) | Catégorie: Éclairage LED | Prix: 64.8 DT | Disponibilité: en stock | Caractéristiques: 3m, 144 LED/m, IP65 (résistant écla
4. Ruban LED WS2812B adressable 3m (74 LED/m, IP65 (résistant éclaboussures)) | Catégorie: Éclairage LED | Prix: 58.79 DT | Disponibilité: en stock | Caractéristiques: 3m, 74 LED/m, IP65 (résistant éclab

#### Advanced

- **retrieved_sources :** sav/garantie.txt, LS-CN-000899, LS-IM-000003, LS-IM-000001 ; **hit_at_4 :** True ; **confiance :** 0.404 (= 1 − distance minimale : 0.596) ; **would_escalate :** False
- **Scores :** CP 1,000, CR 1,000, F 0,500, AR 0,398 ; **erreurs :** aucune
- **Classement :** (d) correcte. « الضمان على الملتيمتر هو 12 شهر ضد أي عيب تصنيعي » : 12 mois contre tout défaut de fabrication, comme la référence et le passage 1.

**Réponse générée (en entier) :**

> الضمان على الملتيمتر هو 12 شهر ضد أي عيب تصنيعي. إذا تحتاج أي مساعدة أخرى، راني موجود.

**Contextes transmis au juge : 4** (200 premiers caractères)

1. Q: Quelle est la durée de garantie sur les instruments de mesure (multimètres, oscilloscopes) ? ⏎ R: 12 mois contre tout défaut de fabrication.
2. Gaine thermorétractable Ø3mm (transparent, 1m) | Catégorie: Connectique | Prix: 1.1 DT | Disponibilité: en stock | Caractéristiques: Diamètre 3mm, transparent, ratio 2:1 | Gaine thermorétractable Ø3mm
3. Multimètre numérique (milieu de gamme, basique) | Catégorie: Instruments de Mesure | Prix: 113.53 DT | Disponibilité: en stock | Caractéristiques: Gamme milieu de gamme, mesure basique | Multimètre mi
4. Multimètre numérique (entrée de gamme, basique) | Catégorie: Instruments de Mesure | Prix: 44.05 DT | Disponibilité: en stock | Caractéristiques: Gamme entrée de gamme, mesure basique | Multimètre ent

### `tn-sfax` (catégorie sav)

- **Question :** 9adeh el livraison l sfax
- **Référence :** Oui, Liss Strike livre à Sfax. Hors Grand Tunis, les frais sont de 12 DT (gratuit à partir de 150 DT d'achat) et le délai est de 3 à 6 jours ouvrés.
- **Sources attendues :** sav/livraison.txt

#### Basic

- **retrieved_sources :** sav/livraison.txt, sav/livraison.txt, sav/reclamations.txt, LS-CO-008460 ; **hit_at_4 :** True ; **confiance :** 0.482 (= 1 − distance minimale : 0.518) ; **would_escalate :** False
- **Scores :** CP 0,000, CR 0,000, F 0,000, AR 0,000 ; **erreurs :** aucune
- **Classement :** (a) refus. « ma 3andich ma3loumet d9i9a 3la thaman el livraison le Sfax. Najem n3ayetlek l'équipe » : pas d'information sur le prix, proposition de rappel.

**Réponse générée (en entier) :**

> Ma3lich, ma 3andich ma3loumet d9i9a 3la thaman el livraison le Sfax. Najem n3ayetlek l’équipe ta3na w ykounou y3touk el ma3loumet el moudakika. T9adar tba3athna message w n3awdou n9aymouha m3ak. Merci!

**Contextes transmis au juge : 4** (200 premiers caractères)

1. Q: Existe-t-il une livraison express ? ⏎ R: Oui, une option express (livraison en 24h sur le Grand Tunis) est disponible pour 15 DT supplémentaires.
2. Q: Livrez-vous le week-end ? ⏎ R: Les livraisons ont lieu du lundi au vendredi. Une commande passée le week-end est traitée dès le lundi ouvré suivant.
3. Q: Il manque un article dans mon colis, que faire ? ⏎ R: Signalez-le sous 48h après réception avec votre numéro de commande. Nous vérifions avec l'entrepôt et vous renvoyons l'article manquant sans frai
4. Bouton d'arrêt d'urgence | Catégorie: Composants | Prix: 11.69 DT | Disponibilité: en stock | Caractéristiques: Voir fiche technique | Bouton d'arrêt d'urgence.

#### Advanced

- **retrieved_sources :** sav/livraison.txt, sav/livraison.txt, sav/livraison.txt, LS-CN-000341 ; **hit_at_4 :** True ; **confiance :** 0.47 (= 1 − distance minimale : 0.53) ; **would_escalate :** False
- **Scores :** CP 0,833, CR 0,500, F 0,000, AR 0,000 ; **erreurs :** aucune
- **Classement :** (a) refus. « ما عنديش معلومات دقيقة على ثمن التوصيل لسفكس » : pas d'information sur le prix, alors que les passages donnent la couverture de Sfax et le délai de 3 à 6 jours (pas les frais).

**Réponse générée (en entier) :**

> ما عنديش معلومات دقيقة على ثمن التوصيل لسفكس. نجم نتحقق من الموضوع أو نحولك لمستشار الخدمة بش يعطيك التفاصيل اللازمة. إذا تحب، نبعثلك إيميل أو نكلمك على الرقم متاعنا. شكراً لتفهمك.

**Contextes transmis au juge : 4** (200 premiers caractères)

1. Q: Livrez-vous en dehors de Tunis (autres villes/gouvernorats) ? ⏎ R: Oui, la livraison n'est pas limitée à Tunis : Sfax, Sousse, Bizerte, Gabès, Kairouan et tous les autres gouvernorats sont couverts.
2. Q: Livrez-vous le week-end ? ⏎ R: Les livraisons ont lieu du lundi au vendredi. Une commande passée le week-end est traitée dès le lundi ouvré suivant.
3. Q: Quel est le délai de livraison standard ? ⏎ R: Entre 2 et 4 jours ouvrés pour le Grand Tunis, et 3 à 6 jours ouvrés pour le reste de la Tunisie.
4. Barrette 9 broches (coudé 90°, pas 2.0mm) | Catégorie: Connectique | Prix: 1.56 DT | Disponibilité: en stock | Caractéristiques: 9 broches, coudé 90°, pas 2.0mm | Barrette de connecteurs 9 broches, co

### `tn-probleme` (catégorie sav)

- **Question :** 3andi mochkla fil livraison
- **Référence :** Si le produit est arrivé cassé ou défectueux, prenez une photo du produit et de l'emballage et contactez Liss Strike sous 48h via le chat ou à contact@lissstrike.tn avec le numéro de commande ; un remplacement ou un remboursement sera proposé.
- **Sources attendues :** sav/reclamations.txt, sav/livraison.txt

#### Basic

- **retrieved_sources :** LS-OU-000027, sav/livraison.txt, sav/livraison.txt, LS-OU-000028 ; **hit_at_4 :** True ; **confiance :** 0.498 (= 1 − distance minimale : 0.502) ; **would_escalate :** False
- **Scores :** CP 0,000, CR 0,000, F 0,000, AR 0,000 ; **erreurs :** aucune
- **Classement :** (a) au sens large : demande de précisions et renvoi (pas un refus d'information). « يلزمنا شوية تفاصيل إضافية: رقم الطلبية […] نقترح عليك الاتصال بخدمة الحرفاء على الرقم الموجود في موقعنا » : demande le numéro et la nature du problème, renvoie au service client ; ne donne pas la procédure de la référence (photo, 48 h, contact@lissstrike.tn).

**Réponse générée (en entier) :**

> سْلام، نعتذر على الإزعاج. باش نجموا نعاونواك في مشكلة التوصيل، يلزمنا شوية تفاصيل إضافية:
>
> - رقم الطلبية (order number) إذا كان متوفر.
> - واش صاير بالضبط مع التوصيل (مثلاً: ما وصلتش، وصلت متأخرة، العنوان موش صحيح…).
> - العنوان اللي تمّ توصيل الطلبية إليه.
>
> كي تبعثلنا هالمعلومات، نجموا نتحققوا من حالة الشحنة ونقدموك الحل المناسب. إذا تحب تتواصل مباشرة مع أحد المستشارين، نقترح عليك الاتصال بخدمة الحرفاء على الرقم الموجود في موقعنا. شكراً لتفهمك.

**Contextes transmis au juge : 4** (200 premiers caractères)

1. Pompe à dessouder | Catégorie: Outillage | Prix: 4.87 DT | Disponibilité: en stock | Caractéristiques: Voir fiche technique | Pompe à dessouder.
2. Q: Peut-on se faire livrer en point relais ? ⏎ R: Cette option n'est pas encore disponible ; la livraison se fait uniquement à domicile ou en retrait boutique.
3. Q: Existe-t-il une livraison express ? ⏎ R: Oui, une option express (livraison en 24h sur le Grand Tunis) est disponible pour 15 DT supplémentaires.
4. Tresse à dessouder | Catégorie: Outillage | Prix: 3.43 DT | Disponibilité: en stock | Caractéristiques: Voir fiche technique | Tresse à dessouder.

#### Advanced

- **retrieved_sources :** LS-CN-000266, LS-OU-000016, LS-OU-000021, LS-OU-000026 ; **hit_at_4 :** False ; **confiance :** 0.449 (= 1 − distance minimale : 0.551) ; **would_escalate :** False
- **Scores :** CP 0,000, CR 0,000, F 0,000, AR 0,490 ; **erreurs :** aucune
- **Classement :** (a) au sens large, avec un fait inventé. Demande les mêmes précisions, puis « تتصل بخدمة الحرفاء على الرقم 71 555 555 » : ce numéro ne figure ni dans les passages ni dans la base (le numéro de la FAQ est +216 29943697).

**Réponse générée (en entier) :**

> عسلامة، نأسف على المشكلة في التوصيل. باش نجموا نعاونك أسرع، يلزمنا شوية تفاصيل إضافية:
>
> - رقم الطلب (الـ Order ID) إذا كان متوفر
> - تاريخ الطلب أو تاريخ الشحن المتوقع
> - وصف للمشكلة (مثلاً: ما وصلش الطلب، وصل متأخر، أو وصل بضاعة ناقصة)
>
> من بعد ما توصلنا بالمعلومات هاذي، نتحققوا من حالة الشحنة ونرجعوا لك بأسرع وقت. إذا تحب، تنجم تبعثهم لينا هنا أو تتصل بخدمة الحرفاء على الرقم 71 555 555. شكراً لتفهمك.

**Contextes transmis au juge : 4** (200 premiers caractères)

1. Barrette 3 broches (droit, pas 2.0mm) | Catégorie: Connectique | Prix: 3.88 DT | Disponibilité: en stock | Caractéristiques: 3 broches, droit, pas 2.0mm | Barrette de connecteurs 3 broches, droit, pas
2. Pince brucelles courbée | Catégorie: Outillage | Prix: 4.49 DT | Disponibilité: en stock | Caractéristiques: Voir fiche technique | Pince brucelles courbée.
3. Troisième main avec loupe | Catégorie: Outillage | Prix: 19.87 DT | Disponibilité: en stock | Caractéristiques: Voir fiche technique | Troisième main avec loupe.
4. Flux de soudure (pot) | Catégorie: Outillage | Prix: 5.87 DT | Disponibilité: en stock | Caractéristiques: Voir fiche technique | Flux de soudure (pot).

## 3. D'où viennent les refus

- **Pas du code.** Les 3 réponses Basic ont une confiance de 0,438, 0,482 et 0,498, au-dessus du seuil de 0,35 : `would_escalate` vaut `false` partout. D'ailleurs, l'évaluation Ragas n'utilise pas `dialogue_manager` : `scripts/evaluate_ragas.py` (`run_pipeline`, `_generate`) appelle directement le LLM avec `build_messages`. L'escalade du code (`low_rag_confidence`) ne pouvait donc pas s'appliquer ; elle n'est qu'enregistrée, dans `would_escalate`.
- **Du LLM, qui suit la consigne du prompt système** (`app/services/rag/llm_factory.py`) : « SI LE CONTEXTE NE RÉPOND PAS À LA QUESTION précise posée […] dis-le clairement au client (ex: "je n'ai pas cette information précise") et propose de vérifier ou de le mettre en relation avec un conseiller — NE COMBLE JAMAIS le vide […] ».
- **C'est le comportement voulu** quand les passages ne contiennent pas la réponse. En Basic, `tn-garantie` ne reçoit que des LED et des rubans LED. `tn-sfax` reçoit les livraisons express et du week-end, sans les frais pour Sfax. Dans les deux cas, la base contient pourtant la réponse : 12 mois pour les multimètres dans `sav/garantie.txt`, 12 DT hors Grand Tunis dans `sav/livraison.txt`. **L'échec vient de la recherche, pas de la génération.**
- **Distances.** Le JSON ne stocke que la confiance, c'est-à-dire 1 − la plus petite distance : 0,562, 0,518 et 0,502 pour la distance minimale en Basic. **La distance de chacun des 4 passages n'est pas stockée.** En mode basic, le filtre `MAX_RELEVANT_DISTANCE = 0,75` (`retriever._query_one`) ne garde que des passages à 0,75 ou moins : les 4 passages de chaque question l'ont donc passé.

## 4. Pourquoi 0,000 : ce que fait chaque métrique (ragas 0.4.3, `ragas/metrics/collections/`)

| Métrique | Calcul (code) | Dépend de la réponse ? | Origine du 0 pour les 3 réponses Basic |
| --- | --- | --- | --- |
| Context Precision (`ContextPrecision` = `ContextPrecisionWithReference`, `context_precision/metric.py:81-128`) | Un verdict « utile / pas utile » par passage, **au regard de la référence**, puis une précision moyenne. Si tous les verdicts valent 0, le numérateur est nul, donc le score est 0 | **Non** : seuls la question, la référence et les passages | **(ii) passages non pertinents** : le juge a jugé les 4 passages inutiles pour la référence |
| Context Recall (`context_recall/metric.py:82-129`) | Chaque affirmation de la référence est-elle attribuable aux passages ? Score = part des affirmations attribuées | **Non** | **(ii)** : aucune affirmation de la référence n'est trouvée dans les passages (pas de garantie de 12 mois, pas de frais de 12 DT, pas de procédure de réclamation) |
| Faithfulness (`faithfulness/metric.py:88-161`) | La réponse est découpée en affirmations, puis chacune est vérifiée contre les passages. Score = affirmations soutenues / affirmations. **NaN s'il n'y a aucune affirmation** (l. 119-121) | **Oui** | **(iii)** : ce n'est pas un 0 automatique. Le score vaut 0,0 et non NaN, donc des affirmations ont été extraites, et aucune n'a été jugée soutenue par les passages. Le détail des affirmations et des verdicts **n'est pas stocké** dans le JSON |
| Answer Relevancy (`answer_relevancy/metric.py:93-156`, `strictness=1` dans `evaluate_ragas.py:437`) | Le juge régénère une question à partir de la réponse, avec un indicateur `noncommittal` (réponse évasive). Score = cosinus moyen × (1 si au moins une réponse n'est pas évasive, sinon 0) (l. 153-154) | **Oui** | **(i) 0 par construction quand le juge marque la réponse comme évasive** : un 0,0 exact correspond à `noncommittal = 1`, car un cosinus nul n'arrive pratiquement jamais. L'indicateur lui-même n'est pas stocké |

**Les 0 de Context Precision et de Context Recall ne viennent donc pas du refus.** Ils mesurent la recherche. Preuve dans le JSON : `tn-sfax` en Advanced est **aussi un refus**, mais obtient CP 0,833 et CR 0,500, car ses passages contiennent la couverture de Sfax et le délai de livraison.

## 5. Toutes les réponses de refus (22 questions × 2 modes)

Repérage : le détecteur de l'application (`dialogue_manager._is_no_info_answer`), complété par la relecture des 44 réponses. Deux refus manqués par le détecteur ont été ajoutés : `tn-garantie` Basic, en texte mêlant arabizi et lettres arabes, et `p-18650` Basic.

| Question | Mode | Langue | Refus | Repérage | CP | CR | F | AR |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `p-18650` | basic | fr | oui | relecture | 0,500 | 0,000 | 0,000 | 0,830 |
| `p-nema17` | basic | fr | oui | détecteur | 0,000 | 0,000 | 0,000 | 0,000 |
| `p-esp32` | basic | fr | oui | détecteur | 0,000 | 0,000 | 0,000 | 0,000 |
| `en-warranty` | basic | en | oui | détecteur | 0,000 | 0,000 | 0,000 | 0,000 |
| `tn-garantie` | basic | tn | oui | relecture | 0,000 | 0,000 | 0,000 | 0,000 |
| `tn-sfax` | basic | tn | oui | détecteur | 0,000 | 0,000 | 0,000 | 0,000 |
| `tn-sfax` | advanced | tn | oui | détecteur | 0,833 | 0,500 | 0,000 | 0,000 |

**7 refus** sur 44 réponses : 6 en Basic et 1 en Advanced.
- **Faithfulness = 0 pour 7 refus sur 7.** Ragas pénalise systématiquement les refus sur cette métrique.
- **Answer Relevancy = 0 pour 6 refus sur 7.** L'exception est `p-18650` Basic (0,830) : sa réponse explique ce qu'elle voit (« seules les fiches de chargeurs et de supports sont mentionnées »), et le juge ne l'a pas jugée évasive.
- **CP et CR varient avec les passages**, et non avec le refus : de 0 à 0,833.
- **Hors refus.** Les réponses `tn-probleme`, qui demandent des précisions, obtiennent aussi F = 0. AR vaut 0 en Basic et 0,490 en Advanced.

## 6. Moyennes recalculées sans les refus (aucun recalcul côté juge)

Les scores sont repris tels quels du JSON. Une réponse de refus est retirée de toutes les métriques de son mode. Les `None` restent exclus, comme pour la Faithfulness Basic de `p-arduino-due`.

**Tunisien (3 questions)**

| Mode | CP (n) | CR (n) | F (n) | AR (n) |
| --- | --- | --- | --- | --- |
| basic (publié) | 0,000 (3) | 0,000 (3) | 0,000 (3) | 0,000 (3) |
| basic sans refus | 0,000 (1) | 0,000 (1) | 0,000 (1) | 0,000 (1) |
| advanced (publié) | 0,611 (3) | 0,500 (3) | 0,167 (3) | 0,296 (3) |
| advanced sans refus | 0,500 (2) | 0,500 (2) | 0,250 (2) | 0,444 (2) |
| basic apparié, sans refus dans aucun des deux modes | 0,000 (1) | 0,000 (1) | 0,000 (1) | 0,000 (1) |
| advanced apparié, sans refus dans aucun des deux modes | 0,000 (1) | 0,000 (1) | 0,000 (1) | 0,490 (1) |

**Global (22 questions)**

| Mode | CP (n) | CR (n) | F (n) | AR (n) |
| --- | --- | --- | --- | --- |
| basic (publié) | 0,645 (22) | 0,598 (22) | 0,532 (21) | 0,485 (22) |
| basic sans refus | 0,856 (16) | 0,823 (16) | 0,745 (15) | 0,615 (16) |
| advanced (publié) | 0,913 (22) | 0,800 (22) | 0,689 (22) | 0,600 (22) |
| advanced sans refus | 0,917 (21) | 0,814 (21) | 0,721 (21) | 0,628 (21) |
| basic apparié, sans refus dans aucun des deux modes | 0,856 (16) | 0,823 (16) | 0,745 (15) | 0,615 (16) |
| advanced apparié, sans refus dans aucun des deux modes | 0,891 (16) | 0,787 (16) | 0,705 (15) | 0,606 (16) |

**Lecture.**
- **En tunisien**, il ne reste en Basic que `tn-probleme`, à 0 partout. Comme ce n'est pas un refus, la moyenne Basic reste à 0 avec n = 1. Une moyenne tunisienne sans refus ne repose donc que sur 1 ou 2 réponses.
- **Sur les 16 questions sans refus dans aucun des deux modes**, l'écart Advanced − Basic devient : CP +0,035, CR −0,036, F −0,040 (n = 15), AR −0,009. **Le gain publié vient donc surtout des 6 refus du mode Basic** : 5 questions où la recherche Basic ne trouvait pas les bons passages, et que le mode Advanced résout. Sur les questions déjà bien servies par Basic, Advanced n'apporte pas de gain mesurable.
- **Retirer les refus revient à retirer les cas où la recherche a échoué.** Cela embellit surtout le mode Basic. C'est une **analyse de sensibilité**, pas une correction : un refus honnête reste le bon comportement quand les passages manquent.

## Limites

- **Classement manuel par une seule personne (Claude)**, à partir du texte des réponses. La traduction des passages en tunisien et en arabe est donnée à titre indicatif.
- **Détails intermédiaires du juge non stockés.** Les affirmations extraites, les verdicts, l'indicateur `noncommittal` et la distance de chaque passage ne sont pas dans le JSON. Les explications du point 4 reposent sur le code de ragas 0.4.3 et sur les scores enregistrés.
- **Petit effectif.** 3 questions tunisiennes : aucune conclusion statistique n'est possible.
