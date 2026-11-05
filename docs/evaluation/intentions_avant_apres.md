# Intentions apprises : mesure avant / après

Jeu de test : `data/intents/test.json`, 59 messages (frustration 10, general 17, help 11, human_agent 11, order_tracking 10), jamais utilisé pour régler les seuils ni écrire les exemples.
Seuils (calibrés sur `data/intents/dev.json`) : similarité 0.62, transfert 0.82.

- **Avant** : règles seules (`intent_classifier.py`).
- **Après** : règles, puis intentions apprises si aucune règle ne tranche (`INTENT_MODEL_ENABLED=True`).

| Mesure | Avant | Après |
| --- | --- | --- |
| Exactitude globale | 45.8% | 71.2% |
| Faux transferts vers un conseiller | 0 | 0 |
| Transferts manqués | 14 | 12 |
| Temps ajouté par message sans règle (médiane, CPU) | 0 ms | 42 ms |

| Intention | Messages | Précision avant | Rappel avant | Précision après | Rappel après |
| --- | --- | --- | --- | --- | --- |
| human_agent | 11 | 100% | 36% | 100% | 55% |
| frustration | 10 | 100% | 30% | 100% | 30% |
| order_tracking | 10 | 100% | 30% | 100% | 70% |
| help | 11 | 0% | 0% | 77% | 91% |
| general | 17 | 35% | 100% | 53% | 94% |

Erreurs restantes après (17) :

- « une personne peut-elle prendre en charge ma demande ? » : attendu `human_agent`, obtenu `general`
- « please connect me with somebody who works there » : attendu `human_agent`, obtenu `general`
- « أريد موظفا بشريا » : attendu `human_agent`, obtenu `general`
- « هل يمكن لأحد من فريقكم الرد علي؟ » : attendu `human_agent`, obtenu `general`
- « 7ad men el khedma ynajjem yetsal biya ? » : attendu `human_agent`, obtenu `general`
- « votre boutique ne vaut rien, aucun suivi » : attendu `frustration`, obtenu `general`
- « je suis furieux, on m'ignore complètement » : attendu `frustration`, obtenu `general`
- « c'est du vol, vous ne répondez à personne » : attendu `frustration`, obtenu `general`
- « absolutely awful, I keep getting ignored » : attendu `frustration`, obtenu `general`
- « أنتم لا تحترمون زبائنكم أبدا » : attendu `frustration`, obtenu `general`
- « ma fama 7atta 7ad yjewebni, 3ib » : attendu `frustration`, obtenu `help`
- « khedmetkom ma3andha 7atta ma3na » : attendu `frustration`, obtenu `help`
- « j'ai payé il y a 5 jours et toujours aucun colis » : attendu `order_tracking`, obtenu `general`
- « I still haven't got the stuff I bought » : attendu `order_tracking`, obtenu `general`
- « chrit men 3andkom w mazelt ma 5dhit chay » : attendu `order_tracking`, obtenu `general`
- « what do you guys offer? » : attendu `help`, obtenu `general`
- « kifech nraja3 produit ? » : attendu `general`, obtenu `help`

Décisions changées par le modèle (19) :

- « est-il possible de discuter avec quelqu'un de réel ? » : `general` → `human_agent` (attendu `human_agent`)
- « is a member of your staff around to help me? » : `general` → `human_agent` (attendu `human_agent`)
- « ma fama 7atta 7ad yjewebni, 3ib » : `general` → `help` (attendu `frustration`)
- « khedmetkom ma3andha 7atta ma3na » : `general` → `help` (attendu `frustration`)
- « ma livraison est en retard, elle arrive quand ? » : `general` → `order_tracking` (attendu `order_tracking`)
- « when is my parcel going to be delivered? » : `general` → `order_tracking` (attendu `order_tracking`)
- « لم أستلم طلبيتي حتى الآن » : `general` → `order_tracking` (attendu `order_tracking`)
- « el colis mte3i wa9tech ywosel » : `general` → `order_tracking` (attendu `order_tracking`)
- « je veux plus des informations » : `general` → `help` (attendu `help`)
- « j'ai besoin d'un renseignement » : `general` → `help` (attendu `help`)
- « vous vendez quoi ? » : `general` → `help` (attendu `help`)
- « pouvez-vous me guider ? » : `general` → `help` (attendu `help`)
- « i need your help » : `general` → `help` (attendu `help`)
- « I'd like some information » : `general` → `help` (attendu `help`)
- « أحتاج بعض المعلومات » : `general` → `help` (attendu `help`)
- « ماذا لديكم في المتجر؟ » : `general` → `help` (attendu `help`)
- « nhebek t3awani » : `general` → `help` (attendu `help`)
- « chnia 3andkom fel magasin ? » : `general` → `help` (attendu `help`)
- « kifech nraja3 produit ? » : `general` → `help` (attendu `general`)

## Limites de cette mesure

- Petit échantillon (une soixantaine de messages, 10 à 17 par intention) : des tendances, pas des mesures statistiquement solides.
- Messages écrits pour le projet, pas recueillis auprès de vrais clients ; les exemples, les seuils et le jeu de test viennent du même auteur.
- La frustration reste mal reconnue (seuil de transfert strict, choisi pour n'envoyer aucune simple question à un conseiller) ; en arabizi, le modèle d'embeddings confond une panne de produit et une plainte contre le service.
- Seule l'intention est mesurée ici, pas la qualité de la réponse qui suit.
