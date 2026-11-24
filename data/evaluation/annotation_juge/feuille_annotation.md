# Feuille d'annotation : validation du juge Ragas

Consignes : `docs/evaluation/annotation_juge/consignes.md`. Valeurs : 0, 0,5 ou 1. Reporter les notes dans `feuille_annotation.csv` (même identifiant).

## A01

**Question.** كم تكلفة التوصيل

**Réponse de référence.** La livraison est gratuite à partir de 150 DT d'achat. En dessous, les frais sont de 8 DT pour le Grand Tunis et de 12 DT pour le reste du pays.

**Passages récupérés.**

> **Passage 1**
>
> Q: Quels sont les frais de livraison ?
> R: Livraison gratuite à partir de 150 DT d'achat. En dessous, les frais sont de 8 DT pour le Grand Tunis et 12 DT pour le reste du pays.

> **Passage 2**
>
> Q: Proposez-vous des tarifs dégressifs pour les commandes en grande quantité ?
> R: Oui, à partir de 20 unités d'une même référence, une remise quantité peut être appliquée. Contactez le service client avec la liste souhaitée pour obtenir un devis.

> **Passage 3**
>
> Q: Le paiement à la livraison (cash) est-il disponible partout ?
> R: Oui, dans toute la Tunisie, sans frais supplémentaire, avec un plafond de 500 DT par commande pour ce mode de paiement.

> **Passage 4**
>
> Q: Existe-t-il une livraison express ?
> R: Oui, une option express (livraison en 24h sur le Grand Tunis) est disponible pour 15 DT supplémentaires.

**Réponse générée.**

> تكلفة التوصيل تعتمد على قيمة طلبكم وموقعكم:
>
> - **الطلبات التي تبلغ قيمتها 150 د.ت أو أكثر**: توصيل مجاني في جميع أنحاء تونس.  
> - **الطلبات التي تقل عن 150 د.ت**:  
>   - **المنطقة الكبرى (Grand Tunis)**: 8 د.ت.  
>   - **بقية أنحاء البلاد**: 12 د.ت.
>
> يرجى إبلاغنا بموقعكم لتحديد الرسوم بدقة. إذا كان لديكم أي استفسار آخر، نحن في خدمتكم.

| fidelite | pertinence | rappel | commentaire |
| --- | --- | --- | --- |
|  |  |  |  |

---

## A02

**Question.** Can I return a product?

**Réponse de référence.** Oui, sous 7 jours calendaires après réception, si le produit n'est ni ouvert ni utilisé. Les composants électroniques déballés ne sont pas repris sauf défaut de fabrication.

**Passages récupérés.**

> **Passage 1**
>
> Q: Puis-je être remboursé sans retourner le produit défectueux ?
> R: Pour les produits de faible valeur (moins de 20 DT), un remboursement direct sur photo peut être accordé sans retour, à la discrétion du service SAV. Au-delà, un retour est généralement demandé.

> **Passage 2**
>
> Q: Dans quel état le produit doit-il être pour être retourné ?
> R: Le produit doit être neuf, non utilisé, dans son emballage d'origine non ouvert, avec tous les accessoires et la facture d'achat.

> **Passage 3**
>
> Q: Quel est le délai pour retourner un produit ?
> R: Vous disposez de 7 jours calendaires à partir de la date de réception pour retourner un produit non ouvert et non utilisé.

> **Passage 4**
>
> Q: J'ai reçu le mauvais produit, que faire ?
> R: Contactez le service client avec une photo du produit reçu et votre numéro de commande. Nous organisons l'échange sans frais supplémentaires.

**Réponse générée.**

> Yes, you can return a product provided it meets our return conditions:
>
> - The item must be brand‑new, unused, and still in its original, unopened packaging.  
> - All accessories and the purchase invoice must be included.  
> - The return must be initiated within **7 calendar days** from the date you received the product.
>
> If the product is of low value (under 20 DT), we may be able to process a refund based solely on a photo, at the discretion of our SAV team.  
>
> Please let us know if you’d like to start a return, and we’ll guide you through the next steps.

| fidelite | pertinence | rappel | commentaire |
| --- | --- | --- | --- |
|  |  |  |  |

---

## A03

**Question.** Avez-vous un capteur de distance VL53L0X ?

**Réponse de référence.** Oui, le capteur VL53L0X est en stock en trois versions : capteur seul (nu) à 32,98 DT, breakout board à 50,93 DT et module complet à 54,04 DT.

**Passages récupérés.**

> **Passage 1**
>
> Capteur VL53L0X (capteur seul (nu)) | Catégorie: Capteurs | Prix: 32.98 DT | Disponibilité: en stock | Caractéristiques: Distance laser ToF | Capteur VL53L0X — Distance laser ToF. Livré en version capteur seul (nu).

> **Passage 2**
>
> Capteur VL53L0X (breakout board) | Catégorie: Capteurs | Prix: 50.93 DT | Disponibilité: en stock | Caractéristiques: Distance laser ToF | Capteur VL53L0X — Distance laser ToF. Livré en version breakout board.

> **Passage 3**
>
> Capteur VL53L0X (module complet) | Catégorie: Capteurs | Prix: 54.04 DT | Disponibilité: en stock | Caractéristiques: Distance laser ToF | Capteur VL53L0X — Distance laser ToF. Livré en version module complet.

> **Passage 4**
>
> Capteur Sharp GP2Y0A21 (breakout board) | Catégorie: Capteurs | Prix: 10.95 DT | Disponibilité: en stock | Caractéristiques: Distance infrarouge 10-80cm | Capteur Sharp GP2Y0A21 — Distance infrarouge 10-80cm. Livré en version breakout board.

**Réponse générée.**

> Bonjour,
>
> Oui, nous proposons le capteur de distance VL53L0X sous trois déclinaisons, toutes en stock :
>
> | Variante | Prix | Disponibilité |
> |----------|------|----------------|
> | Capteur VL53L0X (seul, nu) | 32,98 DT | En stock |
> | Capteur VL53L0X (breakout board) | 50,93 DT | En stock |
> | Capteur VL53L0X (module complet) | 54,04 DT | En stock |
>
> N’hésitez pas à me dire laquelle vous intéresse ou si vous avez besoin d’informations complémentaires (caractéristiques, mode de paiement, etc.).

| fidelite | pertinence | rappel | commentaire |
| --- | --- | --- | --- |
|  |  |  |  |

---

## A04

**Question.** chnowa el garantie mta3 el multimetre

**Réponse de référence.** Les instruments de mesure comme les multimètres sont garantis 12 mois contre tout défaut de fabrication.

**Passages récupérés.**

> **Passage 1**
>
> LED UV 3mm (diffusé) | Catégorie: Composants | Prix: 0.71 DT | Disponibilité: en stock | Caractéristiques: UV, 3mm, diffusé | LED UV 3mm, finition diffusé.

> **Passage 2**
>
> LED blanc 3mm (diffusé) | Catégorie: Composants | Prix: 0.17 DT | Disponibilité: en stock | Caractéristiques: blanc, 3mm, diffusé | LED blanc 3mm, finition diffusé.

> **Passage 3**
>
> Ruban LED WS2812B adressable 3m (144 LED/m, IP65 (résistant éclaboussures)) | Catégorie: Éclairage LED | Prix: 64.8 DT | Disponibilité: en stock | Caractéristiques: 3m, 144 LED/m, IP65 (résistant éclaboussures), adressable individuellement | Ruban LED RGB adressable WS2812B, 3m, 144 LED/m, IP65 (résistant éclaboussures).

> **Passage 4**
>
> Ruban LED WS2812B adressable 3m (74 LED/m, IP65 (résistant éclaboussures)) | Catégorie: Éclairage LED | Prix: 58.79 DT | Disponibilité: en stock | Caractéristiques: 3m, 74 LED/m, IP65 (résistant éclaboussures), adressable individuellement | Ruban LED RGB adressable WS2812B, 3m, 74 LED/m, IP65 (résistant éclaboussures).

**Réponse générée.**

> Saha, ma nجمش نعطيك معلومات دقيقة على الضمان متاع الـmultimetre من قاعدة المعطيات اللي عنا. نجّم نتحقق من الموضوع ولا نحولك لمستشار الخدمة بش يعطيك التفاصيل الكاملة. إذا تحب، نبعثلك إيميل أو نكلمك مباشرة. ;)

| fidelite | pertinence | rappel | commentaire |
| --- | --- | --- | --- |
|  |  |  |  |

---

## A05

**Question.** كم تكلفة التوصيل

**Réponse de référence.** La livraison est gratuite à partir de 150 DT d'achat. En dessous, les frais sont de 8 DT pour le Grand Tunis et de 12 DT pour le reste du pays.

**Passages récupérés.**

> **Passage 1**
>
> Q: Quels sont les frais de livraison ?
> R: Livraison gratuite à partir de 150 DT d'achat. En dessous, les frais sont de 8 DT pour le Grand Tunis et 12 DT pour le reste du pays.

> **Passage 2**
>
> Q: Le paiement à la livraison (cash) est-il disponible partout ?
> R: Oui, dans toute la Tunisie, sans frais supplémentaire, avec un plafond de 500 DT par commande pour ce mode de paiement.

> **Passage 3**
>
> Câble ruban 50 conducteurs (5m) | Catégorie: Connectique | Prix: 9.82 DT | Disponibilité: en stock | Caractéristiques: 50 conducteurs, 5m | Câble plat ruban 50 conducteurs, 5m.

> **Passage 4**
>
> Câble ruban 20 conducteurs (5m) | Catégorie: Connectique | Prix: 12.74 DT | Disponibilité: en stock | Caractéristiques: 20 conducteurs, 5m | Câble plat ruban 20 conducteurs, 5m.

**Réponse générée.**

> تكلفة التوصيل تعتمد على قيمة طلبك وموقعك:
>
> - **الطلبات التي قيمتها 150 د.ت أو أكثر**: توصيل مجاني في جميع أنحاء تونس.  
> - **الطلبات التي قيمتها أقل من 150 د.ت**:  
>   - **المنطقة الكبرى (Grand Tunis)**: 8 د.ت.  
>   - **بقية أنحاء البلاد**: 12 د.ت.  
>
> إذا كان لديك أي سؤال آخر أو تحتاج مساعدة في إتمام طلبك، فأنا هنا للمساعدة.

| fidelite | pertinence | rappel | commentaire |
| --- | --- | --- | --- |
|  |  |  |  |

---

## A06

**Question.** Vous avez des piles 18650 en stock ?

**Réponse de référence.** Oui, les piles/batteries 18650 sont en stock en packs de 4 (9,44 DT), de 10 (23,43 DT) et de 20 (6,32 DT).

**Passages récupérés.**

> **Passage 1**
>
> Pile/Batterie 18650 (pack de 10) | Catégorie: Alimentation | Prix: 23.43 DT | Disponibilité: en stock | Caractéristiques: Type 18650, pack de 10 | Piles/batteries 18650, conditionnement pack de 10.

> **Passage 2**
>
> Pile/Batterie 18650 (pack de 4) | Catégorie: Alimentation | Prix: 9.44 DT | Disponibilité: en stock | Caractéristiques: Type 18650, pack de 4 | Piles/batteries 18650, conditionnement pack de 4.

> **Passage 3**
>
> Pile/Batterie 18650 (pack de 20) | Catégorie: Alimentation | Prix: 6.32 DT | Disponibilité: en stock | Caractéristiques: Type 18650, pack de 20 | Piles/batteries 18650, conditionnement pack de 20.

> **Passage 4**
>
> Batterie 18650 2200mAh (générique) | Catégorie: Alimentation | Prix: 11.92 DT | Disponibilité: en stock | Caractéristiques: Li-ion 3.7V, 2200mAh, générique | Batterie rechargeable 18650 2200mAh, version générique.

**Réponse générée.**

> Bonjour,
>
> Oui, nous avons des piles 18650 en stock :
>
> - **Pack de 10** – 23,43 DT  
> - **Pack de 4** – 9,44 DT  
> - **Pack de 20** – 6,32 DT  
>
> Nous proposons également une **batterie 18650 2200 mAh (générique)** à 11,92 DT.
>
> N’hésitez pas si vous avez besoin de précisions ou si vous souhaitez passer commande.

| fidelite | pertinence | rappel | commentaire |
| --- | --- | --- | --- |
|  |  |  |  |

---

## A07

**Question.** alimentation 12V 5A

**Réponse de référence.** Le bloc secteur 12V 5A est disponible en stock à 24,73 DT.

**Passages récupérés.**

> **Passage 1**
>
> Bloc secteur 12V 5A | Catégorie: Alimentation | Prix: 24.73 DT | Disponibilité: en stock | Caractéristiques: Voir fiche technique | Bloc secteur 12V 5A.

> **Passage 2**
>
> Bloc secteur 5V 2A | Catégorie: Alimentation | Prix: 12.46 DT | Disponibilité: en stock | Caractéristiques: Voir fiche technique | Bloc secteur 5V 2A.

> **Passage 3**
>
> Panneau solaire 12V 5W | Catégorie: Alimentation | Prix: 45.17 DT | Disponibilité: en stock | Caractéristiques: Voir fiche technique | Panneau solaire 12V 5W.

> **Passage 4**
>
> Fiche alimentation DC 5.5x2.1mm mâle | Catégorie: Connectique | Prix: 1.17 DT | Disponibilité: en stock | Caractéristiques: Voir fiche technique | Fiche alimentation DC 5.5x2.1mm mâle.

**Réponse générée.**

> Bonjour,
>
> Voici les informations concernant le bloc secteur 12 V 5 A :
>
> - **Catégorie** : Alimentation  
> - **Prix** : 24,73 DT  
> - **Disponibilité** : En stock  
> - **Caractéristiques** : Voir la fiche technique (connecteur standard, protection contre les courts‑circuits, etc.)
>
> N’hésitez pas à me dire si vous avez besoin de la fiche technique, d’un devis, ou de toute autre assistance (commande, paiement, livraison, etc.).

| fidelite | pertinence | rappel | commentaire |
| --- | --- | --- | --- |
|  |  |  |  |

---

## A08

**Question.** What is the warranty on a multimeter?

**Réponse de référence.** Les instruments de mesure (multimètres, oscilloscopes) sont garantis 12 mois contre tout défaut de fabrication.

**Passages récupérés.**

> **Passage 1**
>
> Multimètre numérique (professionnelle, True-RMS) | Catégorie: Instruments de Mesure | Prix: 39.05 DT | Disponibilité: en stock | Caractéristiques: Gamme professionnelle, mesure True-RMS | Multimètre professionnelle, fonction True-RMS.

> **Passage 2**
>
> Multimètre numérique (milieu de gamme, True-RMS) | Catégorie: Instruments de Mesure | Prix: 125.01 DT | Disponibilité: en stock | Caractéristiques: Gamme milieu de gamme, mesure True-RMS | Multimètre milieu de gamme, fonction True-RMS.

> **Passage 3**
>
> Multimètre numérique (milieu de gamme, basique) | Catégorie: Instruments de Mesure | Prix: 113.53 DT | Disponibilité: en stock | Caractéristiques: Gamme milieu de gamme, mesure basique | Multimètre milieu de gamme, fonction basique.

> **Passage 4**
>
> Multimètre numérique (entrée de gamme, True-RMS) | Catégorie: Instruments de Mesure | Prix: 96.13 DT | Disponibilité: en stock | Caractéristiques: Gamme entrée de gamme, mesure True-RMS | Multimètre entrée de gamme, fonction True-RMS.

**Réponse générée.**

> I’m sorry, but I don’t have the specific warranty details for our multimeters in the information I have right now. Would you like me to check this for you or connect you with one of our advisors?

| fidelite | pertinence | rappel | commentaire |
| --- | --- | --- | --- |
|  |  |  |  |

---

## A09

**Question.** Raspberry Pi 4 8GB prix

**Réponse de référence.** Le Raspberry Pi 4 Model B (8Go) coûte 246,64 DT, mais il est actuellement en rupture de stock.

**Passages récupérés.**

> **Passage 1**
>
> Raspberry Pi 4 Model B (8Go) | Catégorie: Cartes Programmables | Prix: 246.64 DT | Disponibilité: rupture de stock | Caractéristiques: Mini-ordinateur monocarte, WiFi/Bluetooth selon modèle | Raspberry Pi 4 Model B (8Go) pour projets avancés (serveur, robotique, vision).

> **Passage 2**
>
> Raspberry Pi 4 Model B (4Go) | Catégorie: Cartes Programmables | Prix: 205.34 DT | Disponibilité: en stock | Caractéristiques: Mini-ordinateur monocarte, WiFi/Bluetooth selon modèle | Raspberry Pi 4 Model B (4Go) pour projets avancés (serveur, robotique, vision).

> **Passage 3**
>
> Raspberry Pi 4 Model B (2Go) | Catégorie: Cartes Programmables | Prix: 164.2 DT | Disponibilité: stock faible | Caractéristiques: Mini-ordinateur monocarte, WiFi/Bluetooth selon modèle | Raspberry Pi 4 Model B (2Go) pour projets avancés (serveur, robotique, vision).

> **Passage 4**
>
> Raspberry Pi 5 (8Go) | Catégorie: Cartes Programmables | Prix: 322.08 DT | Disponibilité: en stock | Caractéristiques: Mini-ordinateur monocarte, WiFi/Bluetooth selon modèle | Raspberry Pi 5 (8Go) pour projets avancés (serveur, robotique, vision).

**Réponse générée.**

> The Raspberry Pi 4 Model B (8 GB) is priced at **246.64 DT**.

| fidelite | pertinence | rappel | commentaire |
| --- | --- | --- | --- |
|  |  |  |  |

---

## A10

**Question.** What is the warranty on a multimeter?

**Réponse de référence.** Les instruments de mesure (multimètres, oscilloscopes) sont garantis 12 mois contre tout défaut de fabrication.

**Passages récupérés.**

> **Passage 1**
>
> Q: Quelle est la durée de garantie sur les instruments de mesure (multimètres, oscilloscopes) ?
> R: 12 mois contre tout défaut de fabrication.

> **Passage 2**
>
> Multimètre numérique (milieu de gamme, True-RMS) | Catégorie: Instruments de Mesure | Prix: 125.01 DT | Disponibilité: en stock | Caractéristiques: Gamme milieu de gamme, mesure True-RMS | Multimètre milieu de gamme, fonction True-RMS.

> **Passage 3**
>
> Multimètre numérique (entrée de gamme, True-RMS) | Catégorie: Instruments de Mesure | Prix: 96.13 DT | Disponibilité: en stock | Caractéristiques: Gamme entrée de gamme, mesure True-RMS | Multimètre entrée de gamme, fonction True-RMS.

> **Passage 4**
>
> Résistance 5.1MΩ 1/4W ±10% (CMS 0603) | Catégorie: Composants | Prix: 0.2 DT | Disponibilité: en stock | Caractéristiques: 5.1MΩ, 1/4W, tolérance ±10%, CMS 0603 | Résistance 5.1MΩ, 1/4W, ±10%, boîtier CMS 0603.

**Réponse générée.**

> The warranty for multimeters (as well as other measurement instruments) is **12 months** against any manufacturing defect.

| fidelite | pertinence | rappel | commentaire |
| --- | --- | --- | --- |
|  |  |  |  |

---

## A11

**Question.** alimentation 12V 5A

**Réponse de référence.** Le bloc secteur 12V 5A est disponible en stock à 24,73 DT.

**Passages récupérés.**

> **Passage 1**
>
> Bloc secteur 12V 5A | Catégorie: Alimentation | Prix: 24.73 DT | Disponibilité: en stock | Caractéristiques: Voir fiche technique | Bloc secteur 12V 5A.

> **Passage 2**
>
> Alimentation dédiée ruban LED 12V 5A | Catégorie: Éclairage LED | Prix: 20.35 DT | Disponibilité: en stock | Caractéristiques: Voir fiche technique | Alimentation dédiée ruban LED 12V 5A.

> **Passage 3**
>
> Convertisseur DC-DC XL4015 step-down 5A (sortie fixe 12V) | Catégorie: Modules | Prix: 7.28 DT | Disponibilité: en stock | Caractéristiques: Module XL4015 step-down 5A, sortie fixe 12V | Régulateur de tension XL4015 step-down 5A pour adapter une source d'alimentation.

> **Passage 4**
>
> Panneau solaire 12V 5W | Catégorie: Alimentation | Prix: 45.17 DT | Disponibilité: en stock | Caractéristiques: Voir fiche technique | Panneau solaire 12V 5W.

**Réponse générée.**

> Bonjour,
>
> Voici les deux alimentations 12 V / 5 A que nous proposons :
>
> | Produit | Catégorie | Prix | Disponibilité |
> |---|---|---|---|
> | **Bloc secteur 12V 5A** | Alimentation | 24,73 DT | En stock |
> | **Alimentation dédiée ruban LED 12V 5A** | Éclairage LED | 20,35 DT | En stock |
>
> Les deux sont disponibles immédiatement. Si vous avez besoin de précisions supplémentaires (fiche technique, compatibilité, etc.) ou si vous souhaitez passer commande, n’hésitez pas à me le faire savoir.

| fidelite | pertinence | rappel | commentaire |
| --- | --- | --- | --- |
|  |  |  |  |

---

## A12

**Question.** 9adeh el livraison l sfax

**Réponse de référence.** Oui, Liss Strike livre à Sfax. Hors Grand Tunis, les frais sont de 12 DT (gratuit à partir de 150 DT d'achat) et le délai est de 3 à 6 jours ouvrés.

**Passages récupérés.**

> **Passage 1**
>
> Q: Existe-t-il une livraison express ?
> R: Oui, une option express (livraison en 24h sur le Grand Tunis) est disponible pour 15 DT supplémentaires.

> **Passage 2**
>
> Q: Livrez-vous le week-end ?
> R: Les livraisons ont lieu du lundi au vendredi. Une commande passée le week-end est traitée dès le lundi ouvré suivant.

> **Passage 3**
>
> Q: Il manque un article dans mon colis, que faire ?
> R: Signalez-le sous 48h après réception avec votre numéro de commande. Nous vérifions avec l'entrepôt et vous renvoyons l'article manquant sans frais.

> **Passage 4**
>
> Bouton d'arrêt d'urgence | Catégorie: Composants | Prix: 11.69 DT | Disponibilité: en stock | Caractéristiques: Voir fiche technique | Bouton d'arrêt d'urgence.

**Réponse générée.**

> Ma3lich, ma 3andich ma3loumet d9i9a 3la thaman el livraison le Sfax. Najem n3ayetlek l’équipe ta3na w ykounou y3touk el ma3loumet el moudakika. T9adar tba3athna message w n3awdou n9aymouha m3ak. Merci!

| fidelite | pertinence | rappel | commentaire |
| --- | --- | --- | --- |
|  |  |  |  |

---

## A13

**Question.** 3andi mochkla fil livraison

**Réponse de référence.** Si le produit est arrivé cassé ou défectueux, prenez une photo du produit et de l'emballage et contactez Liss Strike sous 48h via le chat ou à contact@lissstrike.tn avec le numéro de commande ; un remplacement ou un remboursement sera proposé.

**Passages récupérés.**

> **Passage 1**
>
> Barrette 3 broches (droit, pas 2.0mm) | Catégorie: Connectique | Prix: 3.88 DT | Disponibilité: en stock | Caractéristiques: 3 broches, droit, pas 2.0mm | Barrette de connecteurs 3 broches, droit, pas 2.0mm.

> **Passage 2**
>
> Pince brucelles courbée | Catégorie: Outillage | Prix: 4.49 DT | Disponibilité: en stock | Caractéristiques: Voir fiche technique | Pince brucelles courbée.

> **Passage 3**
>
> Troisième main avec loupe | Catégorie: Outillage | Prix: 19.87 DT | Disponibilité: en stock | Caractéristiques: Voir fiche technique | Troisième main avec loupe.

> **Passage 4**
>
> Flux de soudure (pot) | Catégorie: Outillage | Prix: 5.87 DT | Disponibilité: en stock | Caractéristiques: Voir fiche technique | Flux de soudure (pot).

**Réponse générée.**

> عسلامة، نأسف على المشكلة في التوصيل. باش نجموا نعاونك أسرع، يلزمنا شوية تفاصيل إضافية:
>
> - رقم الطلب (الـ Order ID) إذا كان متوفر
> - تاريخ الطلب أو تاريخ الشحن المتوقع
> - وصف للمشكلة (مثلاً: ما وصلش الطلب، وصل متأخر، أو وصل بضاعة ناقصة)
>
> من بعد ما توصلنا بالمعلومات هاذي، نتحققوا من حالة الشحنة ونرجعوا لك بأسرع وقت. إذا تحب، تنجم تبعثهم لينا هنا أو تتصل بخدمة الحرفاء على الرقم 71 555 555. شكراً لتفهمك.

| fidelite | pertinence | rappel | commentaire |
| --- | --- | --- | --- |
|  |  |  |  |

---

## A14

**Question.** ما هي مدة الضمان

**Réponse de référence.** La garantie dépend du produit : 6 mois pour les cartes programmables et l'outillage, 3 mois pour les modules et capteurs, 12 mois pour les instruments de mesure, contre tout défaut de fabrication.

**Passages récupérés.**

> **Passage 1**
>
> Q: Quelle est la durée de garantie sur l'outillage (fer à souder, pinces) ?
> R: 6 mois, hors usure normale (panne de fer à souder, lames émoussées).

> **Passage 2**
>
> Q: Livrez-vous le week-end ?
> R: Les livraisons ont lieu du lundi au vendredi. Une commande passée le week-end est traitée dès le lundi ouvré suivant.

> **Passage 3**
>
> Q: Combien de temps pour être remboursé après un retour accepté ?
> R: Le remboursement est effectué sous 5 à 10 jours ouvrés après réception et vérification du produit retourné, sur le même moyen de paiement utilisé à l'achat.

> **Passage 4**
>
> Q: Combien de temps pour traiter une réclamation ?
> R: Sous 3 à 5 jours ouvrés après réception de toutes les informations nécessaires (photos, numéro de commande).

**Réponse générée.**

> مدة الضمان تختلف حسب نوع المنتج. وفقًا للمعلومات المتوفرة لدينا، فإن الضمان على الأدوات (مثل مكواة اللحام والملقط) هو **ستة أشهر**، ولا يشمل البلى العادي. 
>
> بالنسبة لبقية المنتجات (اللوحات القابلة للبرمجة، الحساسات، الوحدات، إلخ) لا تتوفر لدينا تفاصيل محددة حول مدة الضمان. إذا رغبت في معرفة الضمان الخاص بمنتج معين، يرجى تزويدنا باسم المنتج أو رقم الطلب وسنقوم بالتحقق من ذلك أو تحويلك إلى أحد المستشارين.

| fidelite | pertinence | rappel | commentaire |
| --- | --- | --- | --- |
|  |  |  |  |

---

## A15

**Question.** Can I return a product?

**Réponse de référence.** Oui, sous 7 jours calendaires après réception, si le produit n'est ni ouvert ni utilisé. Les composants électroniques déballés ne sont pas repris sauf défaut de fabrication.

**Passages récupérés.**

> **Passage 1**
>
> Q: Quels produits ne peuvent pas être retournés ?
> R: Les composants électroniques déballés (résistances, capteurs, modules) ne sont pas repris une fois l'emballage ouvert, sauf défaut de fabrication. Les logiciels/licences ne sont pas remboursables après activation.

> **Passage 2**
>
> Q: Dans quel état le produit doit-il être pour être retourné ?
> R: Le produit doit être neuf, non utilisé, dans son emballage d'origine non ouvert, avec tous les accessoires et la facture d'achat.

> **Passage 3**
>
> Q: Puis-je être remboursé sans retourner le produit défectueux ?
> R: Pour les produits de faible valeur (moins de 20 DT), un remboursement direct sur photo peut être accordé sans retour, à la discrétion du service SAV. Au-delà, un retour est généralement demandé.

> **Passage 4**
>
> Q: Quel est le délai pour retourner un produit ?
> R: Vous disposez de 7 jours calendaires à partir de la date de réception pour retourner un produit non ouvert et non utilisé.

**Réponse générée.**

> Yes, you can return a product provided it meets our return conditions:
>
> * The item must be **new, unused, and in its original, unopened packaging** with all accessories and the purchase invoice.
> * Returns must be initiated **within 7 calendar days** from the date you received the item.
> * Certain items cannot be returned once opened, such as electronic components (e.g., resistors, sensors, modules) and software/licenses after activation.
>
> If the product is low‑value (under 20 DT), we may be able to process a refund based on a photo without requiring a physical return, at the discretion of our SAV team.
>
> Let us know the specific item you’d like to return, and we can guide you through the next steps.

| fidelite | pertinence | rappel | commentaire |
| --- | --- | --- | --- |
|  |  |  |  |

---

## A16

**Question.** 9adeh el livraison l sfax

**Réponse de référence.** Oui, Liss Strike livre à Sfax. Hors Grand Tunis, les frais sont de 12 DT (gratuit à partir de 150 DT d'achat) et le délai est de 3 à 6 jours ouvrés.

**Passages récupérés.**

> **Passage 1**
>
> Q: Livrez-vous en dehors de Tunis (autres villes/gouvernorats) ?
> R: Oui, la livraison n'est pas limitée à Tunis : Sfax, Sousse, Bizerte, Gabès, Kairouan et tous les autres gouvernorats sont couverts.

> **Passage 2**
>
> Q: Livrez-vous le week-end ?
> R: Les livraisons ont lieu du lundi au vendredi. Une commande passée le week-end est traitée dès le lundi ouvré suivant.

> **Passage 3**
>
> Q: Quel est le délai de livraison standard ?
> R: Entre 2 et 4 jours ouvrés pour le Grand Tunis, et 3 à 6 jours ouvrés pour le reste de la Tunisie.

> **Passage 4**
>
> Barrette 9 broches (coudé 90°, pas 2.0mm) | Catégorie: Connectique | Prix: 1.56 DT | Disponibilité: en stock | Caractéristiques: 9 broches, coudé 90°, pas 2.0mm | Barrette de connecteurs 9 broches, coudé 90°, pas 2.0mm.

**Réponse générée.**

> ما عنديش معلومات دقيقة على ثمن التوصيل لسفكس. نجم نتحقق من الموضوع أو نحولك لمستشار الخدمة بش يعطيك التفاصيل اللازمة. إذا تحب، نبعثلك إيميل أو نكلمك على الرقم متاعنا. شكراً لتفهمك.

| fidelite | pertinence | rappel | commentaire |
| --- | --- | --- | --- |
|  |  |  |  |

---

## A17

**Question.** Avez-vous un capteur de distance VL53L0X ?

**Réponse de référence.** Oui, le capteur VL53L0X est en stock en trois versions : capteur seul (nu) à 32,98 DT, breakout board à 50,93 DT et module complet à 54,04 DT.

**Passages récupérés.**

> **Passage 1**
>
> Capteur VL53L0X (capteur seul (nu)) | Catégorie: Capteurs | Prix: 32.98 DT | Disponibilité: en stock | Caractéristiques: Distance laser ToF | Capteur VL53L0X — Distance laser ToF. Livré en version capteur seul (nu).

> **Passage 2**
>
> Capteur VL53L0X (module complet) | Catégorie: Capteurs | Prix: 54.04 DT | Disponibilité: en stock | Caractéristiques: Distance laser ToF | Capteur VL53L0X — Distance laser ToF. Livré en version module complet.

> **Passage 3**
>
> Capteur VL53L0X (breakout board) | Catégorie: Capteurs | Prix: 50.93 DT | Disponibilité: en stock | Caractéristiques: Distance laser ToF | Capteur VL53L0X — Distance laser ToF. Livré en version breakout board.

> **Passage 4**
>
> Module NRF24L01+PA+LNA | Catégorie: Modules | Prix: 39.02 DT | Disponibilité: en stock | Caractéristiques: RF 2.4GHz longue portée | Module NRF24L01+PA+LNA — RF 2.4GHz longue portée.

**Réponse générée.**

> Oui, nous proposons le capteur de distance VL53L0X sous trois déclinaisons :
>
> | Variante | Prix | Disponibilité |
> |----------|------|----------------|
> | Capteur VL53L0X (seul, nu) | 32,98 DT | En stock |
> | Capteur VL53L0X (module complet) | 54,04 DT | En stock |
> | Capteur VL53L0X (breakout board) | 50,93 DT | En stock |
>
> N’hésitez pas à nous préciser la version qui vous intéresse ou à poser d’autres questions sur nos produits.

| fidelite | pertinence | rappel | commentaire |
| --- | --- | --- | --- |
|  |  |  |  |

---

## A18

**Question.** Do you sell ESP32 boards?

**Réponse de référence.** Oui, plusieurs modules ESP32 sont vendus : DevKitC (4MB à 41,91 DT, 8MB à 40,57 DT), ESP32-S3, ESP32-C3 et ESP32-CAM.

**Passages récupérés.**

> **Passage 1**
>
> Module ESP32-CAM (4MB Flash) | Catégorie: Cartes Programmables | Prix: 67.92 DT | Disponibilité: en stock | Caractéristiques: WiFi 802.11 b/g/n, Bluetooth (selon modèle), 4MB Flash | Carte ESP32-CAM pour projets IoT connectés, 4MB Flash de stockage.

> **Passage 2**
>
> Module ESP32-S3 (4MB Flash) | Catégorie: Cartes Programmables | Prix: 45.88 DT | Disponibilité: stock faible | Caractéristiques: WiFi 802.11 b/g/n, Bluetooth (selon modèle), 4MB Flash | Carte ESP32-S3 pour projets IoT connectés, 4MB Flash de stockage.

> **Passage 3**
>
> Module ESP32-CAM (8MB Flash) | Catégorie: Cartes Programmables | Prix: 66.22 DT | Disponibilité: en stock | Caractéristiques: WiFi 802.11 b/g/n, Bluetooth (selon modèle), 8MB Flash | Carte ESP32-CAM pour projets IoT connectés, 8MB Flash de stockage.

> **Passage 4**
>
> Module ESP32 DevKitC (4MB Flash) | Catégorie: Cartes Programmables | Prix: 41.91 DT | Disponibilité: en stock | Caractéristiques: WiFi 802.11 b/g/n, Bluetooth (selon modèle), 4MB Flash | Carte ESP32 DevKitC pour projets IoT connectés, 4MB Flash de stockage.

**Réponse générée.**

> Yes, we have several ESP32 boards in stock:
>
> | Model | Flash | Price (DT) | Availability |
> |-------|-------|------------|--------------|
> | ESP32‑CAM (4 MB) | 4 MB | 67.92 DT | in stock |
> | ESP32‑CAM (8 MB) | 8 MB | 66.22 DT | in stock |
> | ESP32‑S3 | 4 MB | 45.88 DT | low stock |
> | ESP32 DevKitC | 4 MB | 41.91 DT | in stock |
>
> Let me know if you need more details or would like to place an order.

| fidelite | pertinence | rappel | commentaire |
| --- | --- | --- | --- |
|  |  |  |  |

---

## A19

**Question.** ما هي طرق الدفع المتاحة

**Réponse de référence.** Les moyens de paiement acceptés sont la carte bancaire (Visa/Mastercard) en ligne, le paiement à la livraison en espèces, D17 et Flouci.

**Passages récupérés.**

> **Passage 1**
>
> Q: Quels moyens de paiement sont acceptés ?
> R: Carte bancaire (Visa/Mastercard) en ligne, paiement à la livraison en espèces (cash), D17, et Flouci.

> **Passage 2**
>
> Q: Peut-on payer en plusieurs fois ?
> R: Le paiement en plusieurs fois est disponible pour les commandes de plus de 300 DT, via facilité en 3 fois sans frais avec certaines cartes bancaires partenaires.

> **Passage 3**
>
> Q: Le paiement à la livraison (cash) est-il disponible partout ?
> R: Oui, dans toute la Tunisie, sans frais supplémentaire, avec un plafond de 500 DT par commande pour ce mode de paiement.

> **Passage 4**
>
> Q: Que se passe-t-il si mon paiement en ligne échoue ?
> R: Vérifiez vos informations de carte ou réessayez avec un autre moyen de paiement (D17, Flouci, cash à la livraison). Contactez le service client si le problème persiste.

**Réponse générée.**

> تحية طيبة،  
>
> طرق الدفع المتاحة في متجر Liss Strike هي:
>
> - **بطاقة بنكية** (Visa / Mastercard) عبر الدفع الإلكتروني.  
> - **الدفع عند التسليم** نقداً (Cash) في جميع أنحاء تونس، بحد أقصى 500 د.ت. لكل طلب.  
> - **بطاقة D17**.  
> - **بطاقة Flouci**.  
>
> بالإضافة إلى ذلك، يمكن للطلبات التي تتجاوز قيمتها 300 د.ت. الاستفادة من خيار **الدفع بالتقسيط 3 مرات بدون فائدة** مع البطاقات البنكية الشريكة.  
>
> إذا كان لديك أي استفسار آخر، يسعدنا مساعدتك.

| fidelite | pertinence | rappel | commentaire |
| --- | --- | --- | --- |
|  |  |  |  |

---

## A20

**Question.** ESP32 wifi bluetooth

**Réponse de référence.** Plusieurs modules ESP32 (Wi-Fi + Bluetooth) sont proposés, par exemple le Module ESP32 DevKitC en 4MB Flash (41,91 DT) et en 8MB Flash (40,57 DT), tous deux en stock.

**Passages récupérés.**

> **Passage 1**
>
> Q: Le paiement en ligne est-il sécurisé ?
> R: Oui, tous les paiements par carte sont traités via une passerelle sécurisée conforme aux normes 3D Secure. Liss Strike ne stocke aucune donnée de carte bancaire.

**Réponse générée.**

> I’m sorry, but I don’t have specific information about the ESP32 Wi‑Fi/Bluetooth product in our catalog. Would you like me to check the details for you or connect you with a sales representative?

| fidelite | pertinence | rappel | commentaire |
| --- | --- | --- | --- |
|  |  |  |  |

---

## A21

**Question.** Do you sell ESP32 boards?

**Réponse de référence.** Oui, plusieurs modules ESP32 sont vendus : DevKitC (4MB à 41,91 DT, 8MB à 40,57 DT), ESP32-S3, ESP32-C3 et ESP32-CAM.

**Passages récupérés.**

> **Passage 1**
>
> Kit de démarrage ESP32/IoT — niveau avancé | Catégorie: Kits & Prototypage | Prix: 132.12 DT | Disponibilité: en stock | Caractéristiques: Kit avancé orienté ESP32/IoT | Kit complet avancé pour démarrer un projet ESP32/IoT.

> **Passage 2**
>
> Kit de démarrage ESP32/IoT — niveau intermédiaire | Catégorie: Kits & Prototypage | Prix: 112.86 DT | Disponibilité: en stock | Caractéristiques: Kit intermédiaire orienté ESP32/IoT | Kit complet intermédiaire pour démarrer un projet ESP32/IoT.

> **Passage 3**
>
> Module ESP32-CAM (4MB Flash) | Catégorie: Cartes Programmables | Prix: 67.92 DT | Disponibilité: en stock | Caractéristiques: WiFi 802.11 b/g/n, Bluetooth (selon modèle), 4MB Flash | Carte ESP32-CAM pour projets IoT connectés, 4MB Flash de stockage.

> **Passage 4**
>
> Module ESP32-CAM (8MB Flash) | Catégorie: Cartes Programmables | Prix: 66.22 DT | Disponibilité: en stock | Caractéristiques: WiFi 802.11 b/g/n, Bluetooth (selon modèle), 8MB Flash | Carte ESP32-CAM pour projets IoT connectés, 8MB Flash de stockage.

**Réponse générée.**

> Yes, we do. We currently have the following ESP‑based products in stock:
>
> | Product | Flash | Price (DT) | Availability |
> |---|---|---|---|
> | ESP32‑CAM module | 4 MB | 67.92 DT | In stock |
> | ESP32‑CAM module | 8 MB | 66.22 DT | In stock |
> | ESP32/IOT starter kit – intermediate level | – | 112.86 DT | In stock |
> | ESP32/IOT starter kit – advanced level | – | 132.12 DT | In stock |
>
> Let me know if you’d like more details or assistance with an order.

| fidelite | pertinence | rappel | commentaire |
| --- | --- | --- | --- |
|  |  |  |  |

---

## A22

**Question.** chnowa el garantie mta3 el multimetre

**Réponse de référence.** Les instruments de mesure comme les multimètres sont garantis 12 mois contre tout défaut de fabrication.

**Passages récupérés.**

> **Passage 1**
>
> Q: Quelle est la durée de garantie sur les instruments de mesure (multimètres, oscilloscopes) ?
> R: 12 mois contre tout défaut de fabrication.

> **Passage 2**
>
> Gaine thermorétractable Ø3mm (transparent, 1m) | Catégorie: Connectique | Prix: 1.1 DT | Disponibilité: en stock | Caractéristiques: Diamètre 3mm, transparent, ratio 2:1 | Gaine thermorétractable Ø3mm, couleur transparent.

> **Passage 3**
>
> Multimètre numérique (milieu de gamme, basique) | Catégorie: Instruments de Mesure | Prix: 113.53 DT | Disponibilité: en stock | Caractéristiques: Gamme milieu de gamme, mesure basique | Multimètre milieu de gamme, fonction basique.

> **Passage 4**
>
> Multimètre numérique (entrée de gamme, basique) | Catégorie: Instruments de Mesure | Prix: 44.05 DT | Disponibilité: en stock | Caractéristiques: Gamme entrée de gamme, mesure basique | Multimètre entrée de gamme, fonction basique.

**Réponse générée.**

> الضمان على الملتيمتر هو 12 شهر ضد أي عيب تصنيعي. إذا تحتاج أي مساعدة أخرى، راني موجود.

| fidelite | pertinence | rappel | commentaire |
| --- | --- | --- | --- |
|  |  |  |  |

---

## A23

**Question.** Raspberry Pi 4 8GB prix

**Réponse de référence.** Le Raspberry Pi 4 Model B (8Go) coûte 246,64 DT, mais il est actuellement en rupture de stock.

**Passages récupérés.**

> **Passage 1**
>
> Raspberry Pi 4 Model B (8Go) | Catégorie: Cartes Programmables | Prix: 246.64 DT | Disponibilité: rupture de stock | Caractéristiques: Mini-ordinateur monocarte, WiFi/Bluetooth selon modèle | Raspberry Pi 4 Model B (8Go) pour projets avancés (serveur, robotique, vision).

> **Passage 2**
>
> Raspberry Pi 4 Model B (2Go) | Catégorie: Cartes Programmables | Prix: 164.2 DT | Disponibilité: stock faible | Caractéristiques: Mini-ordinateur monocarte, WiFi/Bluetooth selon modèle | Raspberry Pi 4 Model B (2Go) pour projets avancés (serveur, robotique, vision).

> **Passage 3**
>
> Kit de démarrage Raspberry Pi — niveau avancé | Catégorie: Kits & Prototypage | Prix: 80.75 DT | Disponibilité: en stock | Caractéristiques: Kit avancé orienté Raspberry Pi | Kit complet avancé pour démarrer un projet Raspberry Pi.

> **Passage 4**
>
> Raspberry Pi 5 (8Go) | Catégorie: Cartes Programmables | Prix: 322.08 DT | Disponibilité: en stock | Caractéristiques: Mini-ordinateur monocarte, WiFi/Bluetooth selon modèle | Raspberry Pi 5 (8Go) pour projets avancés (serveur, robotique, vision).

**Réponse générée.**

> The Raspberry Pi 4 Model B (8 GB) is listed at **246.64 DT**. Please note that it is currently marked as “rupture de stock.” If you’d like to be notified when it’s back in stock or need help with an alternative, just let me know!

| fidelite | pertinence | rappel | commentaire |
| --- | --- | --- | --- |
|  |  |  |  |

---

## A24

**Question.** 3andi mochkla fil livraison

**Réponse de référence.** Si le produit est arrivé cassé ou défectueux, prenez une photo du produit et de l'emballage et contactez Liss Strike sous 48h via le chat ou à contact@lissstrike.tn avec le numéro de commande ; un remplacement ou un remboursement sera proposé.

**Passages récupérés.**

> **Passage 1**
>
> Pompe à dessouder | Catégorie: Outillage | Prix: 4.87 DT | Disponibilité: en stock | Caractéristiques: Voir fiche technique | Pompe à dessouder.

> **Passage 2**
>
> Q: Peut-on se faire livrer en point relais ?
> R: Cette option n'est pas encore disponible ; la livraison se fait uniquement à domicile ou en retrait boutique.

> **Passage 3**
>
> Q: Existe-t-il une livraison express ?
> R: Oui, une option express (livraison en 24h sur le Grand Tunis) est disponible pour 15 DT supplémentaires.

> **Passage 4**
>
> Tresse à dessouder | Catégorie: Outillage | Prix: 3.43 DT | Disponibilité: en stock | Caractéristiques: Voir fiche technique | Tresse à dessouder.

**Réponse générée.**

> سْلام، نعتذر على الإزعاج. باش نجموا نعاونواك في مشكلة التوصيل، يلزمنا شوية تفاصيل إضافية:
>
> - رقم الطلبية (order number) إذا كان متوفر.
> - واش صاير بالضبط مع التوصيل (مثلاً: ما وصلتش، وصلت متأخرة، العنوان موش صحيح…).
> - العنوان اللي تمّ توصيل الطلبية إليه.
>
> كي تبعثلنا هالمعلومات، نجموا نتحققوا من حالة الشحنة ونقدموك الحل المناسب. إذا تحب تتواصل مباشرة مع أحد المستشارين، نقترح عليك الاتصال بخدمة الحرفاء على الرقم الموجود في موقعنا. شكراً لتفهمك.

| fidelite | pertinence | rappel | commentaire |
| --- | --- | --- | --- |
|  |  |  |  |

---

## A25

**Question.** Quel est le délai pour retourner un produit ?

**Réponse de référence.** Vous disposez de 7 jours calendaires à partir de la date de réception pour retourner un produit non ouvert et non utilisé.

**Passages récupérés.**

> **Passage 1**
>
> Q: Quel est le délai pour retourner un produit ?
> R: Vous disposez de 7 jours calendaires à partir de la date de réception pour retourner un produit non ouvert et non utilisé.

> **Passage 2**
>
> Q: Combien de temps pour être remboursé après un retour accepté ?
> R: Le remboursement est effectué sous 5 à 10 jours ouvrés après réception et vérification du produit retourné, sur le même moyen de paiement utilisé à l'achat.

> **Passage 3**
>
> Q: Dans quel état le produit doit-il être pour être retourné ?
> R: Le produit doit être neuf, non utilisé, dans son emballage d'origine non ouvert, avec tous les accessoires et la facture d'achat.

> **Passage 4**
>
> Q: Quels produits ne peuvent pas être retournés ?
> R: Les composants électroniques déballés (résistances, capteurs, modules) ne sont pas repris une fois l'emballage ouvert, sauf défaut de fabrication. Les logiciels/licences ne sont pas remboursables après activation.

**Réponse générée.**

> Le délai de retour est de **7 jours calendaires** à compter de la date de réception du produit, à condition qu’il soit neuf, non utilisé et dans son emballage d’origine.

| fidelite | pertinence | rappel | commentaire |
| --- | --- | --- | --- |
|  |  |  |  |

---

## A26

**Question.** Le paiement à la livraison est-il possible ?

**Réponse de référence.** Oui, le paiement à la livraison en espèces est disponible dans toute la Tunisie, sans frais supplémentaire, avec un plafond de 500 DT par commande.

**Passages récupérés.**

> **Passage 1**
>
> Q: Le paiement à la livraison (cash) est-il disponible partout ?
> R: Oui, dans toute la Tunisie, sans frais supplémentaire, avec un plafond de 500 DT par commande pour ce mode de paiement.

> **Passage 2**
>
> Q: Peut-on échanger un produit au lieu de le rembourser ?
> R: Oui, l'échange contre un autre produit de valeur équivalente ou supérieure (avec complément de paiement) est possible sous les mêmes conditions que le retour.

> **Passage 3**
>
> Q: Peut-on payer en plusieurs fois ?
> R: Le paiement en plusieurs fois est disponible pour les commandes de plus de 300 DT, via facilité en 3 fois sans frais avec certaines cartes bancaires partenaires.

> **Passage 4**
>
> Q: Qui paie les frais de retour ?
> R: Les frais de retour sont à la charge du client, sauf si le produit est défectueux ou si une erreur d'expédition a été commise par Liss Strike.

**Réponse générée.**

> Oui, le paiement à la livraison (cash) est disponible dans toute la Tunisie. Aucun frais supplémentaire n’est appliqué, mais le montant de la commande ne doit pas dépasser 500 DT.

| fidelite | pertinence | rappel | commentaire |
| --- | --- | --- | --- |
|  |  |  |  |

---

## A27

**Question.** ما هي طرق الدفع المتاحة

**Réponse de référence.** Les moyens de paiement acceptés sont la carte bancaire (Visa/Mastercard) en ligne, le paiement à la livraison en espèces, D17 et Flouci.

**Passages récupérés.**

> **Passage 1**
>
> Q: Quels moyens de paiement sont acceptés ?
> R: Carte bancaire (Visa/Mastercard) en ligne, paiement à la livraison en espèces (cash), D17, et Flouci.

> **Passage 2**
>
> Q: Comment obtenir une facture ?
> R: Une facture électronique est envoyée automatiquement par email après chaque commande. Une facture papier peut être demandée en boutique.

> **Passage 3**
>
> Q: Peut-on payer en plusieurs fois ?
> R: Le paiement en plusieurs fois est disponible pour les commandes de plus de 300 DT, via facilité en 3 fois sans frais avec certaines cartes bancaires partenaires.

> **Passage 4**
>
> Q: Le paiement à la livraison (cash) est-il disponible partout ?
> R: Oui, dans toute la Tunisie, sans frais supplémentaire, avec un plafond de 500 DT par commande pour ce mode de paiement.

**Réponse générée.**

> تحية طيبة،  
>
> طرق الدفع المتاحة في متجر Liss Strike هي:
>
> - **بطاقة بنكية** (Visa / Mastercard) عبر الدفع الإلكتروني.  
> - **الدفع عند التسليم** نقدًا (Cash) في جميع أنحاء تونس، بدون رسوم إضافية وبحد أقصى 500 د.ت. لكل طلب.  
> - **بطاقة D17**.  
> - **بطاقة Flouci**.  
>
> بالإضافة إلى ذلك، يمكن للطلبات التي تتجاوز 300 د.ت. الاستفادة من خيار **الدفع بالتقسيط** على ثلاث دفعات دون فوائد، وذلك عبر بطاقات بنكية شريكة.  
>
> إذا كان لديك أي استفسار آخر، فأنا في خدمتك.

| fidelite | pertinence | rappel | commentaire |
| --- | --- | --- | --- |
|  |  |  |  |

---

## A28

**Question.** Vous avez des piles 18650 en stock ?

**Réponse de référence.** Oui, les piles/batteries 18650 sont en stock en packs de 4 (9,44 DT), de 10 (23,43 DT) et de 20 (6,32 DT).

**Passages récupérés.**

> **Passage 1**
>
> Chargeur batteries 18650 (2 slots) | Catégorie: Alimentation | Prix: 18.76 DT | Disponibilité: en stock | Caractéristiques: Voir fiche technique | Chargeur batteries 18650 (2 slots).

> **Passage 2**
>
> Support batterie 18650 (x1) avec fil | Catégorie: Alimentation | Prix: 2.46 DT | Disponibilité: en stock | Caractéristiques: Voir fiche technique | Support batterie 18650 (x1) avec fil.

> **Passage 3**
>
> Chargeur batteries 18650 (4 slots) | Catégorie: Alimentation | Prix: 28.06 DT | Disponibilité: sur commande | Caractéristiques: Voir fiche technique | Chargeur batteries 18650 (4 slots).

> **Passage 4**
>
> Support batterie 18650 (x2) avec fil | Catégorie: Alimentation | Prix: 4.11 DT | Disponibilité: en stock | Caractéristiques: Voir fiche technique | Support batterie 18650 (x2) avec fil.

**Réponse générée.**

> Bonjour,
>
> Je ne vois aucune référence de piles 18650 dans les informations dont je dispose ; seules les fiches de chargeurs et de supports sont mentionnées. Je ne peux donc pas confirmer leur disponibilité pour le moment.
>
> Souhaitez‑vous que je vérifie cela pour vous auprès de notre service logistique ou que je vous mette en relation avec un conseiller ?

| fidelite | pertinence | rappel | commentaire |
| --- | --- | --- | --- |
|  |  |  |  |

---

## A29

**Question.** Le paiement à la livraison est-il possible ?

**Réponse de référence.** Oui, le paiement à la livraison en espèces est disponible dans toute la Tunisie, sans frais supplémentaire, avec un plafond de 500 DT par commande.

**Passages récupérés.**

> **Passage 1**
>
> Q: Le paiement à la livraison (cash) est-il disponible partout ?
> R: Oui, dans toute la Tunisie, sans frais supplémentaire, avec un plafond de 500 DT par commande pour ce mode de paiement.

> **Passage 2**
>
> Q: Peut-on se faire livrer en point relais ?
> R: Cette option n'est pas encore disponible ; la livraison se fait uniquement à domicile ou en retrait boutique.

> **Passage 3**
>
> Q: Quels moyens de paiement sont acceptés ?
> R: Carte bancaire (Visa/Mastercard) en ligne, paiement à la livraison en espèces (cash), D17, et Flouci.

> **Passage 4**
>
> Q: Peut-on payer en plusieurs fois ?
> R: Le paiement en plusieurs fois est disponible pour les commandes de plus de 300 DT, via facilité en 3 fois sans frais avec certaines cartes bancaires partenaires.

**Réponse générée.**

> Oui, le paiement à la livraison (en espèces) est disponible dans toute la Tunisie. Aucun frais supplémentaire n’est appliqué, avec un plafond de 500 DT par commande.

| fidelite | pertinence | rappel | commentaire |
| --- | --- | --- | --- |
|  |  |  |  |

---

## A30

**Question.** هل يمكنني إرجاع المنتج

**Réponse de référence.** Oui, sous 7 jours calendaires après réception, si le produit n'est ni ouvert ni utilisé.

**Passages récupérés.**

> **Passage 1**
>
> Q: Dans quel état le produit doit-il être pour être retourné ?
> R: Le produit doit être neuf, non utilisé, dans son emballage d'origine non ouvert, avec tous les accessoires et la facture d'achat.

> **Passage 2**
>
> Q: Quel est le délai pour retourner un produit ?
> R: Vous disposez de 7 jours calendaires à partir de la date de réception pour retourner un produit non ouvert et non utilisé.

> **Passage 3**
>
> Q: Mon produit est arrivé cassé ou défectueux, que faire ?
> R: Prenez une photo du produit et de l'emballage, puis contactez-nous sous 48h via ce chat ou par email à contact@lissstrike.tn avec votre numéro de commande. Un remplacement ou remboursement sera proposé.

> **Passage 4**
>
> Q: Puis-je être remboursé sans retourner le produit défectueux ?
> R: Pour les produits de faible valeur (moins de 20 DT), un remboursement direct sur photo peut être accordé sans retour, à la discrétion du service SAV. Au-delà, un retour est généralement demandé.

**Réponse générée.**

> نعم، يمكنك إرجاع المنتج شريطة استيفائه للشروط التالية:
>
> 1. **حالة المنتج**: يجب أن يكون المنتج جديدًا غير مُستَخدم، داخل عبوته الأصلية غير المفتوحة، مع جميع الملحقات وفاتورة الشراء.  
> 2. **المهلة الزمنية**: يحق لك إرجاع المنتج خلال **7 أيام تقويمية** من تاريخ استلامه.  
> 3. **الإجراءات**: يُرجى التواصل معنا عبر هذا الدردشة أو عبر البريد الإلكتروني **contact@lissstrike.tn** مع ذكر رقم طلبك لتلقي تعليمات الإرجاع (عنوان الإرجاع، طريقة الشحن، إلخ).
>
> إذا كان المنتج وصلكم معطوبًا أو به عيب، يرجى التقاط صورة للمنتج والعبوة وإبلاغنا خلال 48 ساعة لتقديم بديل أو استرداد وفقًا لسياسة الضمان.
>
> نحن في خدمتك لأي استفسار إضافي.

| fidelite | pertinence | rappel | commentaire |
| --- | --- | --- | --- |
|  |  |  |  |

---
