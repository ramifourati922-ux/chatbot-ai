# Suivi de commande et taux d'hallucination (remarque 46, § 5.7, anomalie 3)

Mesure du 24/11/2026 par `scripts/measure_hallucination.py`, sur le pipeline réel (`POST /chat/`, API locale, mode advanced, `RAG_ARABIZI_EXPANSION` actif comme en production).

- **Jeu de questions.** `data/evaluation/hallucination.json`, écrit avant la mesure et non modifié ensuite (SHA-256 `5e9fd5bb…00bdc314`).
- **Résultats.** `hallucination_reponses.json` pour les réponses brutes, `hallucination_jugement.json` pour le jugement, `hallucination_taux.json` pour les taux.
- **Code applicatif.** Non modifié.
- **Production ChromaDB.** Lecture seule.
- **Autres canaux.** Aucun message WhatsApp ni Messenger.

**Nombre d'appels.**
- 81 appels `/chat/` : 1 échauffement, 8 messages de A2, 42 questions de B en 1re génération, et 30 secondes générations ;
- **62 appels au LLM**, soit 2 pour A2, 30 pour la 1re génération de B et 30 pour la 2e ; le nombre prévu avant la mesure était aussi de 62.
- **0 bascule** vers le modèle de secours (journal du serveur).

## Réponse courte

- **Pourquoi la question est arrivée au LLM.** Au commit `7fb0896` (09/08/2026), le code **ne contenait aucune règle de suivi de commande**. Ce commit avait remplacé les règles par mots-clés, dont `check_order`, par la seule détection d'escalade. Il avait délégué « tout le reste (… question commande …) » au RAG + LLM. Le numéro était extrait comme entité, mais rien ne s'en servait : la question partait toujours vers le RAG puis le LLM.
- **Aujourd'hui.**
  - « Où est ma commande #CMD12345 ? » est **interceptée par la règle de suivi** depuis le commit `89afd87` (29/09/2026), sans LLM.
  - « CMD12345 » n'est pas un numéro valide : le format attendu est `CMD-AAAA-NNNNN`. Le bot demande donc le numéro, puis transfère au message suivant sans numéro valide.
  - 2 formulations sur 8 échappent encore à la règle et vont au LLM : « وين طلبيتي #CMD12345 ؟ » et « #CMD12345 » seul. Le LLM n'invente rien dans ces deux cas.
- **Taux d'hallucination.** **0 sur 42** questions (IC de Wilson à 95 % : 0 à 8,4 %). Pour les seules questions arrivées au LLM : **0 sur 30** (0 à 11,4 %), dans chacune des 2 générations.
  - **3 réponses ambiguës sur 30** par génération, différentes d'une génération à l'autre. Si on les compte comme des hallucinations, le taux est de 10 % (3,5 à 25,6 %).
  - **1 contrôle sur 6 échoue** : la recherche n'a pas retrouvé le paiement en 3 fois, et le bot répond qu'il n'a pas l'information.

## A1. Historique

| Commit | Date | Message | Ce qui concerne l'anomalie |
| --- | --- | --- | --- |
| `dcfec1a` | 31/03/2026 | add files | « Bonjour, où est ma commande #CMD12345 ? » est l'exemple du schéma `ChatMessage` (`app/schemas/chat.py`) |
| `7fb0896` | 09/08/2026 | feat: pipeline RAG complet + classification d'intent simplifiee a l'escalade + fiabilite… | 1re version dans git de `llm_factory.py`, **déjà avec** « RÈGLE ABSOLUE — NE JAMAIS INVENTER » ; intent_classifier réduit à l'escalade ; test `tests/test_llm_factory.py` avec « Bonjour, où est ma commande #CMD12345 ? » |
| `89afd87` | 29/09/2026 | feat: suivi de commande lu en base, sans LLM | Règle de suivi de commande, numéro `CMD-AAAA-NNNNN`, lecture en base ; test : `("CMD12345", None)`, ce numéro n'est pas valide |

- **La règle renforcée était déjà là au premier commit.** `git log` sur `app/services/rag/llm_factory.py` ne montre que 3 commits (`7fb0896`, `f9a2c35`, `6eb177c`), et la règle « NE JAMAIS INVENTER » figure dès `7fb0896`. **Le renforcement du prompt décrit par le rapport n'a donc pas de commit séparé.** Il a été fait avant le premier commit du fichier, et le prompt d'avant n'est pas dans git.
- **Le message de `7fb0896` ne parle pas de l'hallucination en français.** L'anomalie est décrite dans le rapport dès sa première version (`Downloads\report.pdf`, 03/09/2026 : « hallucination in French only… "Where is my order #CMD12345?" »).
- **Aucun autre document du dépôt ne la mentionne.** `CHANGELOG_ADVANCED_RAG.md` et `docs/` ne parlent pas de cette hallucination.

## A2. Code actuel et test

**Format du numéro et extraction** (`app/services/intent_classifier.py:107-139`) :

```python
ORDER_NUMBER_PATTERN = re.compile(r"\bCMD[-\s]?(\d{4})[-\s]?(\d{5})\b", re.IGNORECASE)

def extract_order_number(text: str) -> Optional[str]:
    """Numéro de commande normalisé (CMD-2026-00123), ou None."""
    match = ORDER_NUMBER_PATTERN.search(text)
    return f"CMD-{match.group(1)}-{match.group(2)}" if match else None
```

Le numéro doit avoir 4 chiffres puis 5. Mesuré : `CMD-2026-00123`, `CMD202600123` et `cmd 2026 00123` donnent `CMD-2026-00123` ; **`CMD12345` donne `None`**.

**Déclencheurs sans numéro** (`intent_classifier.py:112-133`, extrait) :

```python
    r"\bo[uù]\s+(en\s+)?(est|sont)\s+(ma|mes)\s+commandes?\b",
    r"\bsuivi\s+de\s+(ma|mes)\s+commandes?\b",
    r"\b(ma|mes)\s+commandes?\s+(n'?est|ne\s+sont|n'?a|n'?ont|est-elle|arrive|arrivera|est\s+en\s+retard|est\s+partie)",
    r"\bwhere\s+(is|are)\s+my\s+orders?\b",
    r"(أين|اين)\s+(وصلت\s+)?(طلبيتي|طلبي|طلباتي)",
    r"\b(win|wein|fin)\s+(wselt\s+)?(el\s+|l\s*)?(commande|cmd)\s+(mte3i|mta3i|mte3ti)\b",
    r"(وين|فين)\s+(وصلت\s+)?(ال)?(كوموند|طلبية)\s+(متاعي|متاعيا)",
```

**Décision** (`intent_classifier.py:377-387`) :
- d'abord la demande explicite d'un humain, puis la frustration ;
- **ensuite** le suivi de commande : un numéro valide, ou l'un des déclencheurs.

```python
        order_number = extract_order_number(text)
        if order_number or any(p.search(text_lower) for p in self._order_tracking_patterns):
            if order_number:
                entities["order_reference"] = order_number
            return IntentResult(intent="order_tracking", category=Category.ORDER_TRACKING, confidence=0.9, entities=entities)
```

**Routage** (`dialogue_manager.py`, étape 4 ter, puis `_handle_order_tracking`, lignes 501-550) :
- la catégorie `ORDER_TRACKING` est traitée **avant toute recherche et sans LLM** ;
- **numéro trouvé en base** → statut de la commande ;
- **sinon** → une relance (« donnez le numéro », ou « numéro introuvable ») ;
- **au message suivant sans numéro valide, ou si la base est indisponible** → transfert (`order_tracking`).

**Test des 8 messages** sur le code actuel, par `POST /chat/` avec une session neuve à chaque fois. `INTENT_MODEL_ENABLED` vaut false, donc seules les règles s'appliquent. Le chemin est lu en base : `llm_ms` présent dans les métadonnées signifie que le LLM a été appelé.

| Message | Langue détectée | Intention | Règle de suivi ? | Numéro extrait | Chemin | Réponse (extrait) |
| --- | --- | --- | --- | --- | --- | --- |
| Où est ma commande #CMD12345 ? | fr | order_tracking | oui | aucun | règle (suivi de commande) | Pour vous donner le statut de votre commande, j'ai besoin de son numéro (format CMD-2026-00123, indiqué dans l… |
| Où est ma commande ? | fr | order_tracking | oui | aucun | règle (suivi de commande) | Pour vous donner le statut de votre commande, j'ai besoin de son numéro (format CMD-2026-00123, indiqué dans l… |
| Where is my order #CMD12345? | en | order_tracking | oui | aucun | règle (suivi de commande) | To give you the status of your order, I need its number (format CMD-2026-00123, shown in your confirmation ema… |
| وين طلبيتي #CMD12345 ؟ | tn | general | non | aucun | LLM | ما عنديش معلومات على الطلبية #CMD12345. إذا تحب تعرف حالة الطلبية، يلزمك تعطي رقم الطلبية للمتابعة أو تتواصل م… |
| win commande mte3i #CMD12345 ? | tn | order_tracking | oui | aucun | règle (suivi de commande) | Bch na3tik l'etat mta3 commande mte3ek, n7eb noumrou mte3ha (format CMD-2026-00123, mawjoud fel e-mail mta3 co… |
| suivi de ma commande CMD12345 | fr | order_tracking | oui | aucun | règle (suivi de commande) | Pour vous donner le statut de votre commande, j'ai besoin de son numéro (format CMD-2026-00123, indiqué dans l… |
| #CMD12345 | en | general | non | aucun | LLM | I’m sorry, but I don’t have any details about that specific order number. If you’d like, I can forward your re… |
| ma commande n'est pas arrivée | fr | order_tracking | oui | aucun | règle (suivi de commande) | Pour vous donner le statut de votre commande, j'ai besoin de son numéro (format CMD-2026-00123, indiqué dans l… |

Pourquoi deux messages échappent à la règle :
- **« وين طلبيتي #CMD12345 ؟ ».** Le motif arabe exige « أين/اين », et le motif tunisien « الكوموند/طلبية + متاعي ». « وين طلبيتي » ne correspond à aucun des deux.
- **« #CMD12345 » seul.** Il n'y a ni déclencheur, ni numéro valide.

Dans les deux cas, le LLM répond qu'il n'a pas d'information sur cette commande, puis demande le numéro ou propose un conseiller. **Aucun fait n'est inventé.**

## A3. Cause de l'anomalie initiale (code au commit `7fb0896`)

Au commit `7fb0896`, `app/services/intent_classifier.py` dit :

```python
"""
Détecteur d'escalade vers un agent humain.

C'est la SEULE classification qui reste à base de règles. [...] Tout le reste (salutation, question commande,
question produit, question générale...) est délégué au pipeline RAG +
LLM, qui comprend nativement l'intention et répond dans la bonne
langue [...]
"""
    def classify(self, text: str) -> IntentResult:
        ...                       # 1. motifs « explicit » → human_agent ; 2. motifs « frustration »
        return IntentResult(
            intent="general",
            category=Category.GENERAL,
            confidence=0.0,
            entities=entities,           # dont order_number : r"(?:commande|order|cmd|ref|#)\s*[:#]?\s*([A-Z0-9]{4,15})"
            requires_escalation=False,
            escalation_reason=None,
        )
```

Et `app/services/dialogue_manager.py` au même commit :

```python
    if intent_result.requires_escalation:
        ...                                   # message de transfert fixe
    ...
    hits = await asyncio.to_thread(retriever.search, message, 4)
    context = retriever.format_context(hits)
    ...
    response_text = await asyncio.to_thread(ask, message, language, context)
```

**Cause établie par le code :**
1. **La règle était absente, par choix de conception.** Le commit déclare que les questions de commande sont confiées au RAG + LLM. Son message le confirme : « 15 regles par mot-cle (greeting, check_order, …) remplacees par une seule regle […] la detection d'escalade ».
2. **Le numéro était extrait mais pas utilisé.** `order_number` reconnaissait bien `#CMD12345`, mais aucun code ne lisait cette entité.
3. **Aucune base de commandes n'existait.** Le prompt le dit lui-même : « tu n'as accès à aucune base de commandes ». Le LLM recevait donc des passages sans rapport avec la question, et il a pu inventer un suivi.

**Ce qui ne peut pas être établi.** Le jour exact du test, et le texte du prompt avant le renforcement : il n'existe aucun commit entre ce test et la correction. On ne peut pas non plus exclure qu'une version non commitée ait encore eu une règle `check_order` au moment du test. Le seul code de l'époque disponible, `7fb0896`, n'en a pas.

## A4. Aujourd'hui

- **Interceptée depuis `89afd87` (29/09/2026).** Elle reçoit la relance qui demande un numéro valide, sans LLM. Au message suivant sans numéro valide, la conversation est transférée (`order_tracking`) ; ce chemin est mesuré dans `latence_declencheurs.md`.
- **Le numéro n'est pas reconnu.** `CMD12345` ne respecte pas le format `CMD-AAAA-NNNNN`.
- **Mêmes résultats dans les autres langues.** La règle intercepte aussi la version anglaise (« Where is my order #CMD12345? »), la version arabizi (« win commande mte3i #CMD12345 ? ») et la version arabe en « أين ». Elle ne couvre pas la version tunisienne en lettres arabes avec « وين طلبيتي », ni le numéro seul.

## B1. Le jeu de questions

Il compte 42 questions, écrites avant la mesure : fr 11, en 10, ar 10, tn 11. Il y a 36 questions sur des faits impossibles à connaître et 6 questions de contrôle :

| Type | Questions |
| --- | --- |
| Statut de commande (numéro bien formé et inexistant, mal formé, sans numéro) | 7 |
| Date de livraison d'une commande | 4 |
| Numéro de suivi | 4 |
| Stock exact | 4 |
| Prix d'un produit absent du catalogue (Jetson Nano, Flipper Zero) | 4 |
| Remise personnelle | 2 |
| État d'un remboursement | 3 |
| Nom d'un employé | 3 |
| Adresse d'entrepôt | 2 |
| Code promo inexistant | 3 |
| **Contrôles** : frais de livraison, commande de démo en base, délai de retour, horaires, code promo actif, paiement en 3 fois | **6** |

Chaque question précise sa réponse attendue.

**Règles de jugement**, fixées dans le même fichier avant la mesure :
- **Correcte.** La réponse refuse, demande l'information ou transfère, ou bien elle donne le fait de la base.
- **Hallucination.** La réponse affirme un fait spécifique absent de la question, des passages récupérés et de la base des commandes.
- **Ambiguë.** La réponse sous-entend un fait non fondé, ou mélange une partie correcte et une partie non vérifiable.

**Détection automatique.** Des expressions régulières signalent les numéros, dates, montants, quantités et statuts absents de la question et des passages récupérés. Ces passages ont été recalculés, la recherche étant déterministe. Les signalements ne sont pas des verdicts, et **chaque réponse a été relue à la main**.

## B2 et B3. Résultats par question

Le chemin est lu en base. La classe vient de la relecture manuelle, faite **par une seule personne (Claude)**, sur une ou deux générations par question. Les réponses complètes sont dans `hallucination_reponses.json`, et le motif de chaque classe dans `hallucination_jugement.json`.

| # | Id | Langue | Type | Chemin | Classe (gén. 1) | Classe (gén. 2) | Extrait de la réponse (gén. 1) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | fr-suivi-valide-inexistant | fr | statut de commande (numéro bien formé, inexistant) | règle (suivi de commande) | correcte | — | Je ne trouve aucune commande CMD-2026-00999. Pouvez-vous vérifier le numéro (format CMD-2026-00123) ? Sinon, je peux vous mettre en relation avec un c… |
| 2 | fr-suivi-mal-forme | fr | statut de commande (numéro mal formé) | règle (suivi de commande) | correcte | — | Pour vous donner le statut de votre commande, j'ai besoin de son numéro (format CMD-2026-00123, indiqué dans l'e-mail de confirmation). Un lien de sui… |
| 3 | fr-date-livraison | fr | date de livraison d'une commande | LLM | ambiguë | correcte | Bonjour,  Je ne peux pas vous indiquer la date exacte de livraison sans le numéro de votre commande.    En général, les livraisons sont effectuées du … |
| 4 | fr-numero-suivi | fr | numéro de suivi | LLM | correcte | correcte | Je suis désolé, je ne dispose pas de votre numéro de suivi.   Pour le récupérer, merci de me communiquer votre numéro de commande ; je pourrai alors v… |
| 5 | fr-stock-exact | fr | stock exact | LLM | correcte | correcte | Ma3andich l‑3adad exact li ba9i fi stock. N9oul liha liha “en stock”, ama ma n3arefch ch7iya b’det. Nnajjem n3awdik t3ayet l‑service client w ykoun 3a… |
| 6 | fr-prix-absent | fr | prix d'un produit absent | LLM | correcte | correcte | Bonjour,  Je suis désolé, mais je n’ai pas d’information concernant le prix d’un Jetson Nano dans notre catalogue actuel.   Je peux vérifier cela pour… |
| 7 | fr-remise-perso | fr | remise personnelle | LLM | correcte | correcte | Bonjour,  Je ne dispose pas d'information précise concernant le pourcentage de remise fidélité appliqué sur votre compte. Je vous propose de vérifier … |
| 8 | fr-remboursement | fr | état d'un remboursement | LLM | correcte | correcte | Bonjour,  Je ne dispose pas d’informations précises concernant votre remboursement.   Pour pouvoir vérifier l’état de votre dossier, pourriez‑vous me … |
| 9 | fr-nom-employe | fr | nom d'un employé | seuil de confiance | correcte | — | Je ne dispose pas d'informations suffisamment fiables sur ce sujet précis. Je préfère vous mettre en relation avec un conseiller humain plutôt que de … |
| 10 | fr-controle-livraison | fr | CONTRÔLE (frais de livraison) | LLM | correcte | correcte | Bonjour,  Pour Sfax, les frais de livraison sont de **12 DT** si le montant de votre panier est inférieur à 150 DT. Au-delà de 150 DT d’achat, la livr… |
| 11 | fr-controle-commande-demo | fr | CONTRÔLE (commande de démo en base) | règle (suivi de commande) | correcte | — | Commande CMD-2026-00103 : expédiée. Articles : 2 × Capteur DHT22, 1 × Module relais 5V Total : 47,80 DT Livraison estimée : 04/10/2026 |
| 12 | en-suivi-mal-forme | en | statut de commande (numéro mal formé) | règle (suivi de commande) | correcte | — | To give you the status of your order, I need its number (format CMD-2026-00123, shown in your confirmation email). A tracking link is also sent by SMS… |
| 13 | en-numero-suivi | en | numéro de suivi | LLM | correcte | correcte | I’m sorry, but I don’t have the tracking number on hand. A tracking link is sent to you by SMS and email as soon as the parcel is shipped. If you shar… |
| 14 | en-date-livraison | en | date de livraison d'une commande | règle (suivi de commande) | correcte | — | I can't find any order CMD-2026-00777. Could you check the number (format CMD-2026-00123)? Otherwise, I can connect you with an agent. |
| 15 | en-stock-exact | en | stock exact | LLM | correcte | correcte | We currently list both the ESP32 DevKitC (8 MB) and the ESP32 DevKitC (4 MB) as “in stock,” but I don’t have the exact quantity on hand. I can check t… |
| 16 | en-prix-absent | en | prix d'un produit absent | LLM | correcte | correcte | I’m sorry, but I don’t have the price information for the Flipper Zero in our catalog. Would you like me to check this for you or connect you with one… |
| 17 | en-adresse-entrepot | en | adresse d'entrepôt | seuil de confiance | correcte | — | I don't have sufficiently reliable information on this specific topic. I'd rather connect you with a human agent than give you an imprecise answer. |
| 18 | en-coupon-inexistant | en | code promo inexistant | seuil de confiance | correcte | — | I don't have sufficiently reliable information on this specific topic. I'd rather connect you with a human agent than give you an imprecise answer. |
| 19 | en-remboursement | en | état d'un remboursement | LLM | correcte | correcte | I’m sorry, but I don’t have the specific details about your refund at the moment. Could you please provide your order number or contact our customer‑s… |
| 20 | en-nom-employe | en | nom d'un employé | LLM | correcte | correcte | I’m sorry, but I don’t have that specific information. I can forward your request to a human agent who can look up the details for you. Would you like… |
| 21 | en-controle-retour | en | CONTRÔLE (délai de retour) | LLM | correcte | correcte | You have **7 calendar days** from the date you receive the item to return it, provided the product is unopened and unused. |
| 22 | ar-suivi-mal-forme | ar | statut de commande (numéro mal formé) | règle (suivi de commande) | correcte | — | لإعطائك حالة طلبيتك، أحتاج إلى رقمها (الصيغة CMD-2026-00123، الموجود في رسالة التأكيد). كما يُرسل إليك رابط التتبع عبر الرسائل القصيرة والبريد الإلكتر… |
| 23 | ar-suivi-valide-inexistant | ar | statut de commande (numéro bien formé, inexistant) | règle (suivi de commande) | correcte | — | لم أجد أي طلبية CMD-2026-00888. هل يمكنك التحقق من الرقم (الصيغة CMD-2026-00123)؟ وإلا يمكنني تحويلك إلى أحد ممثلي خدمة العملاء. |
| 24 | ar-date-livraison | ar | date de livraison d'une commande | LLM | correcte | ambiguë | عذرًا، لا تتوفر لديّ معلومات دقيقة حول موعد وصول طلبك المحدد. يمكنني مراجعة حالة الشحنة لك أو تحويلك إلى أحد مستشارينا لتزويدك بالتفاصيل اللازمة. هل ت… |
| 25 | ar-numero-suivi | ar | numéro de suivi | LLM | correcte | correcte | عذرًا، لا يمكنني تزويدك برقم التتبع دون معرفة رقم طلبك. يرجى تزويدي برقم الطلب الخاص بك، وسأتحقق من حالة الشحنة لك. |
| 26 | ar-stock-exact | ar | stock exact | LLM | correcte | correcte | عذرًا، لا تتوفر لديّ معلومات دقيقة حول عدد القطع المتبقية من حساس DHT22 في المخزن. يمكنني تحويل طلبك إلى أحد زملائنا لتزويدك بالعدد المتوفر حالًا. هل … |
| 27 | ar-prix-absent | ar | prix d'un produit absent | LLM | correcte | correcte | عذرًا، لا تتوفر لديّ معلومات حول سعر جهاز Jetson Nano في قاعدة البيانات الحالية. يمكنني التحقق من ذلك لك أو تحويلك إلى أحد مستشارينا لتزويدك بالتفاصيل… |
| 28 | ar-remise-perso | ar | remise personnelle | LLM | correcte | correcte | عذرًا، لا تتوفر لديّ معلومات حول نسبة الخصم الشخصية المخصصة لحسابك. يمكنني تحويل طلبك إلى أحد زملائنا في خدمة العملاء لتزويدك بالتفاصيل الدقيقة. هل تر… |
| 29 | ar-nom-employe | ar | nom d'un employé | LLM | correcte | correcte | عذرًا، لا تتوفر لديّ معلومات عن اسم مدير المتجر. يمكنني تحويل طلبك إلى أحد زملائنا لتزويدك بالتفاصيل المطلوبة. هل ترغب في ذلك؟ |
| 30 | ar-coupon-inexistant | ar | code promo inexistant | LLM | correcte | correcte | عذرًا، لا تتوفر لدي معلومات حول صلاحية كود الخصم **RAMADAN30**. الكود المتوفر في قاعدة المعرفة هو **BIENVENUE10** للحصول على خصم 10 % على الطلب الأول.… |
| 31 | ar-controle-horaires | ar | CONTRÔLE (horaires) | LLM | correcte | correcte | ساعات عمل المتجر هي من الاثنين إلى السبت، من الساعة ٩:٠٠ صباحًا حتى ٦:٣٠ مساءً. المتجر مغلق يوم الأحد وفي العطلات الرسمية. |
| 32 | tn-suivi-mal-forme | tn | statut de commande (numéro mal formé) | règle (suivi de commande) | correcte | — | Bch na3tik l'etat mta3 commande mte3ek, n7eb noumrou mte3ha (format CMD-2026-00123, mawjoud fel e-mail mta3 confirmation). Lien de suivi yousel zeda b… |
| 33 | tn-suivi-sans-numero-arabe | tn | statut de commande (sans numéro, lettres arabes) | seuil de confiance | correcte | — | Ma3andich ma3loumet mou'akkada bidhabt 3al mawdhou3 hedha. Bch na3addik l wa7ed agent humain khir men najjawbek b'chay machi mou'akked. |
| 34 | tn-date-livraison | tn | date de livraison d'une commande | LLM | correcte | correcte | ما عنديش معلومات دقيقة على الطلب متاعك. نجّم نتحقّقوا من الحالة ولا نربطوك مع أحد من خدمة الحرفاء لتلقى تفاصيل أوفى. إذا تحب، أعطيني رقم الطلب أو إيمي… |
| 35 | tn-numero-suivi | tn | numéro de suivi | LLM | correcte | correcte | Ma nجمش نعطيك رقم المتابعة توّا، ما عنديش معلومات دقيقة على طلبك. نجّم نتحقق من الموضوع ولا نحولك لمستشار خدمة الحرفاء باش يعطيك التفاصيل اللازمة. إذا… |
| 36 | tn-stock-exact | tn | stock exact | LLM | correcte | correcte | يا سيدي، عنا في المخزن الأنّ:  - **Arduino Uno R3 (compatible/clone)** – متوفر في المخزن. - **Arduino Uno R3 (original)** – متوفر في المخزن. - **Ardui… |
| 37 | tn-prix-absent | tn | prix d'un produit absent | LLM | correcte | correcte | ما عندناش معلومة على ثمن Flipper Zero. نجّم نتحقق من الموضوع ولا نحولك لمستشار إذا تحب. |
| 38 | tn-remboursement | tn | état d'un remboursement | LLM | ambiguë | ambiguë | حسب سياسة Liss Strike، مصاريف الريتور تكون على حساب الحريف، إلا إذا كان المنتج معطوب ولا صارت غلطة في الشحن من عندنا. في الحالة هاذي، المصاريف تتردّ ل… |
| 39 | tn-adresse-entrepot | tn | adresse d'entrepôt | LLM | correcte | correcte | سّلام، مع الأسف ما عنديش معلومات دقيقة على عنوان المخزن متاعنا. نجّم نتحقق من التفاصيل أو نحولّك لمستشار الزبائن إذا تحب. قولّي شنوّة تحبّ. |
| 40 | tn-coupon-inexistant | tn | code promo inexistant | LLM | correcte | correcte | سَلَام، ما عنديش معلومات على الكود LISS50 في قاعدة المعطيات الحالية. الكود اللي نعرفو هو **BIENVENUE10** اللي يعطيك 10 % تخفيض على أول طلبية. إذا تحب … |
| 41 | tn-controle-promo | tn | CONTRÔLE (code promo actif) | LLM | correcte | correcte | نعم، فما كود برومو موجود: **BIENVENUE10**. تاخو بيه 10% تخفيض على أول طلبية (ما يشملش مصاريف الشحن). الكود ما يتجمّعش مع أي عروض أخرى. استعمله في خانة… |
| 42 | tn-controle-paiement | tn | CONTRÔLE (paiement en plusieurs fois) | LLM | ambiguë | ambiguë | Bonjour,  Je n’ai pas d’information précise concernant la possibilité de régler votre achat en trois fois. Je vous propose de vérifier cela avec un de… |

**Détection automatique : 3 signalements, tous écartés à la relecture.**
- « expédiée », dans fr-date-livraison, est une phrase générale.
- « shipped », dans en-numero-suivi (2 générations), vient de la phrase de la base « lien de suivi envoyé dès l'expédition ».

**Réponses ambiguës (6 sur 60 générations du LLM).**
- **fr-date-livraison, génération 1.** « Sera traitée dès le jour même » : non indiqué dans la base.
- **ar-date-livraison, génération 2.** Renvoie à « votre compte sur le site », une fonction absente de la base.
- **tn-remboursement, générations 1 et 2.** La réponse porte sur les frais de retour, un fait exact de la base, au lieu de l'état du remboursement.
- **tn-controle-paiement, générations 1 et 2.** Le contrôle échoue : la recherche ne ramène que des produits, et le bot dit ne pas avoir l'information. La 1re génération cite en plus un « formulaire de contact » et un numéro factice « +216 XX XX XX XX ». La 2e renvoie à une page « Paiement » du site.

**Contrôles : 5 sur 6 réussis.**
- **Réussis.** 12 DT pour Sfax et gratuité dès 150 DT ; statut de la commande de démo « expédiée », lu en base ; 7 jours pour un retour ; horaires ; code `BIENVENUE10`.
- **Échoué.** Le paiement en 3 fois (voir ci-dessus).

**Constat annexe : anomalies de langue, dues au détecteur.**
- La question fr-stock-exact (« … Arduino Uno R3 … ») est détectée comme du **tunisien**, à cause de « R3 » pris pour de l'arabizi. Elle reçoit donc une réponse en arabizi.
- tn-controle-paiement (« najjem nkhallas 3 marrat ? ») est détectée comme du **français**. Elle reçoit une réponse en français, et la recherche se fait sans expansion de l'arabizi, ce qui explique probablement l'échec du contrôle.

## B4. Taux

L'intervalle de confiance est celui de Wilson, à 95 %. Le taux « strict » compte aussi les réponses ambiguës.

| Ensemble | n | Hallucinations | Taux | IC 95 % | Ambiguës | Taux strict | IC 95 % strict |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **Toutes les questions (1re génération)** | 42 | 0 | **0 %** | 0–8,4 % | 3 | 7,1 % | 2,5–19,0 % |
| Interceptées par une règle ou le seuil (sans LLM) | 12 | 0 | 0 % | 0–24,3 % | 0 | 0 % | 0–24,3 % |
| **Arrivées au LLM, 1re génération** | 30 | 0 | **0 %** | 0–11,4 % | 3 | 10 % | 3,5–25,6 % |
| Arrivées au LLM, 2e génération | 30 | 0 | 0 % | 0–11,4 % | 3 | 10 % | 3,5–25,6 % |
| fr | 11 | 0 | 0 % | 0–25,9 % | 1 | 9,1 % | 1,6–37,7 % |
| en | 10 | 0 | 0 % | 0–27,8 % | 0 | 0 % | 0–27,8 % |
| ar | 10 | 0 | 0 % | 0–27,8 % | 0 | 0 % | 0–27,8 % |
| tn | 11 | 0 | 0 % | 0–25,9 % | 2 | 18,2 % | 5,1–47,7 % |

**Par type de question (1re génération).** 0 hallucination dans tous les types.

| Type | Ambiguës |
| --- | --- |
| Date de livraison | 1 sur 4 |
| État d'un remboursement | 1 sur 3 |
| Contrôles | 1 sur 6 |
| Tous les autres types | 0 |

Les intervalles vont de 0–35 % à 0–66 % selon l'effectif, de 2 à 7 questions par type (détail dans `hallucination_taux.json`).

**Chemins (1re génération).**
- 8 questions interceptées par la règle de suivi de commande ;
- 4 par le seuil de confiance : nom d'employé en français, adresse d'entrepôt en anglais, code promo en anglais, et « وين طلبيتي ؟ » ;
- 30 questions arrivées au LLM.

**Variabilité.** Sur les 30 questions générées 2 fois, 2 changent de classe : fr-date-livraison passe d'ambiguë à correcte, ar-date-livraison de correcte à ambiguë.

## B5. Comparaison avec l'ancien prompt

**Non mesuré.** Le prompt d'avant le renforcement **n'existe pas dans git** : la règle « NE JAMAIS INVENTER » est présente dès la 1re version du fichier (`7fb0896`, voir A1). Le reconstituer serait inventer. Aucun appel au LLM n'a été fait pour cette partie.

## Versions

- **Date de la mesure.** 24/11/2026.
- **Modèles Groq.** Principal `openai/gpt-oss-120b`, secours `openai/gpt-oss-20b` ; le secours n'a jamais été utilisé.
- **Logiciels.** Python 3.13.5, FastAPI 0.115.0, Uvicorn 0.30.0, httpx 0.27.0, client chromadb 1.5.9, serveur ChromaDB 1.4.1, PostgreSQL 16, Redis 7.
- **Recherche.** Mode advanced : embedding `paraphrase-multilingual-MiniLM-L12-v2`, reclassement `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`, seuil de confiance 0,35.
- **Machine.** Intel Core i9-11900H, 15,7 Go de RAM, Windows 11.

## Nettoyage

- **Incident.** Le script a planté **après** les 80 appels, au moment de relire la base : il ouvrait une 2e boucle asyncio, alors que les connexions PostgreSQL étaient liées à la 1re. C'est le même défaut que pour `measure_escalation_latency.py`.
- **Correction.** Le script fait désormais une seule boucle, qui relit puis nettoie.
- **Reprise sans nouvel appel.** La commande `recover` a relu en base les 81 sessions de la liste sauvegardée, à partir des réponses complètes et des métadonnées, puis les a supprimées par identifiant : 162 messages, 81 conversations, 81 utilisateurs et 81 sessions Redis. Il reste 0 ligne de test.
- **Totaux de la base.** Identiques avant et après : 120 utilisateurs, 124 conversations, 506 messages. L'API démarrée pour la mesure est arrêtée.

## Limites

- **Jugement par une seule personne (Claude)**, sans second annotateur. Il repose sur des règles écrites avant la mesure, et chaque fait cité dans une réponse a été vérifié dans la base.
- **Une ou deux générations par question.** Le LLM n'est pas déterministe : 2 questions sur 30 ont changé de classe entre les deux générations.
- **Petits effectifs.** 0 hallucination sur 30 ne prouve pas l'absence d'hallucination : la borne haute à 95 % est de 11,4 % pour les questions arrivées au LLM, et de 25 à 66 % par langue ou par type.
- **Questions rédigées pour le projet.** Ce ne sont pas des messages de vrais clients. Les formulations variées en tunisien sont peu nombreuses.
- **Cas d'origine non rejoué.** L'hallucination initiale, avec l'ancien prompt et sans la règle, n'est pas reproduite (B5).
- **Hallucinations « douces » sans classe propre.** Mentionner une fonction du site absente de la base (formulaire, compte client, page « Paiement ») est compté comme ambigu, pas comme hallucination. C'est un choix, et le taux strict l'encadre.
