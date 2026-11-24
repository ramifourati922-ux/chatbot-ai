# Normalisation de l'arabe pour BM25 (remarque 42, partie A)

Mesure du 24/11/2026 par `scripts/measure_bm25_arabic.py`. Données brutes : `bm25_arabe.json`.
- **Rien n'est modifié sur disque.** `tokenize` et l'index BM25 sont remplacés **en mémoire** (monkeypatch) le temps de la mesure, et le code applicatif n'est pas touché.
- **Production en lecture seule.** La collection de production est seulement lue.
- **Recherche seule.** Ni LLM ni `/chat/`.

## Conclusion

**Ajouter une normalisation arabe à BM25 n'a aucun effet mesurable : 0 changement sur 68 + 68 requêtes.** La raison est structurelle : **aucun des 11 109 documents ne contient de lettre arabe**, et l'index BM25 compte 0 token arabe. Un mot arabe de la question ne peut donc jamais correspondre à un document, qu'il soit normalisé ou non. En arabe, BM25 ne trouve que par les mots latins de la question (« Arduino », « ESP32 », « HC-SR04 », « SG90 », « multimètre ») : 5/17.

En revanche, le défaut de normalisation pèse sur la **recherche dense**, quand la question arrive avec une orthographe inhabituelle. C'est mesuré sur un jeu **synthétique** :
- avec des diacritiques, le mode advanced passe de 16/17 à 5/17 ;
- avec un tatweel, de 16/17 à 14/17.

Retirer les diacritiques et le tatweel de la **question**, avant toute la recherche, ramène ces variantes à 16/17, sans aucun effet sur les questions normales.

## A1. Le code actuel (`app/services/rag/hybrid_retriever.py`)

```python
def tokenize(text: str) -> list:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return [t for t in _TOKEN_RE.findall(text) if t not in _STOPWORDS]   # _TOKEN_RE = r"\w+"
```

- **Mots vides arabes** (12) : `ما`, `ماذا`, `هي`, `هو`, `في`, `من`, `على`, `الى`, `عن`, `هل`, `كم`, `و`.
- **Construction de l'index.**
  - `_build_index()` lit toute la collection par pages de 500, type par type, avec les documents, métadonnées et embeddings.
  - `_CorpusIndex` tokenise ensuite tout le corpus et construit `BM25Okapi`.
- **Quand l'index est construit.**
  - Au premier appel de `_get_index()`, protégé par un verrou à double vérification (`threading.Lock`).
  - Au démarrage, `app/main.py:_preload_rag()` l'appelle si le mode est `hybrid` ou `advanced`.
- **Rechargement.**
  - `refresh_index()` remet seulement `_index = None` ; l'appel suivant reconstruit tout l'index.
  - Aucun appel automatique n'existe : après une réingestion, il faut appeler `refresh_index()` ou redémarrer l'API.
  - Chaque processus garde sa propre copie de l'index.

## A2. Ce que fait `tokenize` aujourd'hui (test)

| Phénomène | Entrée → tokens | Variante → tokens | Mêmes tokens ? | Après `normalize_ar` |
| --- | --- | --- | --- | --- |
| Alif avec hamza | أريد → `اريد` | اريد → `اريد` | **oui** | oui |
| Alif avec hamza | إرجاع → `ارجاع` | ارجاع → `ارجاع` | **oui** | oui |
| Alif madda | آلة → `الة` | اله → `اله` | non (à cause de ة) | oui |
| Alif wasla | ٱلضمان → `ٱلضمان` | الضمان → `الضمان` | **non** | oui |
| Ta marbuta | الضمانة → `الضمانة` | الضمانه → `الضمانه` | **non** | oui |
| Ta marbuta | الفاتورة → `الفاتورة` | الفاتوره → `الفاتوره` | **non** | oui |
| Alif maqsura | على → `[]` (mot vide) | علي → `علي` | **non** | oui, mais voir ci-dessous |
| Diacritiques | مُدَّةُ الضَّمَانِ → `مدة, الضمان` | مدة الضمان → `مدة, الضمان` | **oui** | oui |
| Tatweel | الضمــــان → `الضمــــان` | الضمان → `الضمان` | **non** | oui |
| Article ال | الضمان → `الضمان` | ضمان → `ضمان` | non | non (pas de racinisation) |
| Préposition collée | بالضمان → `بالضمان` | الضمان → `الضمان` | non | non |
| Préposition collée | للشحن → `للشحن` | الشحن → `الشحن` | non | non |

**Ce que NFKD et la suppression des marques combinantes changent réellement en arabe** (test caractère par caractère) :

| Caractère | NFKD | Après suppression des marques combinantes | Effet |
| --- | --- | --- | --- |
| أ U+0623 | U+0627 + U+0654 | ا | hamza retirée ✔ |
| إ U+0625 | U+0627 + U+0655 | ا | hamza retirée ✔ |
| آ U+0622 | U+0627 + U+0653 | ا | madda retirée ✔ |
| ؤ U+0624 / ئ U+0626 | و / ي + U+0654 | و / ي | hamza retirée ✔ |
| ٱ U+0671 (wasla) | inchangé | ٱ | **conservé** ✘ |
| ة U+0629 | inchangé | ة | **conservé** ✘ |
| ى U+0649 | inchangé | ى | **conservé** ✘ |
| ـ U+0640 (tatweel) | inchangé | ـ | **conservé**, et compté par `\w` comme une partie du mot ✘ |
| Harakat U+064B–U+0652, alif suscrit U+0670 | marques combinantes | supprimés | ✔ |
| Formes de présentation (ex. ﻠ U+FEE0) | lettre de base (ل) | ل | ✔ |

Contrairement à ce que dit la remarque, NFKD traite donc **déjà** les hamzas portées par alif, waw et yaa, ainsi que les diacritiques. Il **ne traite pas** l'alif wasla, la ta marbuta, l'alif maqsura ni le tatweel. Rien ne gère l'article ni les prépositions collées : il faudrait une racinisation ou un découpage des préfixes, qui ne sont pas testés ici.

**Effet de bord observé :** `normalize_ar` transforme « على » en « علي », qui ne figure plus dans la liste des mots vides. Le mot vide n'est alors plus filtré (question « paiement en plusieurs fois »). Il faudrait normaliser aussi la liste des mots vides.

## A3. Impact mesuré

Le hit@4 a la même définition que dans `scripts/evaluate_retrieval.py` : une source acceptée parmi les 4 passages. Le banc est `data/evaluation/recherche.json` (17 thèmes × 4 langues). « BM25 seul » prend les 4 premiers résultats BM25, comme `_CorpusIndex.bm25_top`.

### Normalisation dans BM25 (documents et questions)

| Langue | BM25 seul, actuel | BM25 seul, normalisé | Hybrid, actuel | Hybrid, normalisé | Advanced, actuel | Advanced, normalisé | Listes BM25 (top 20) identiques |
| --- | --- | --- | --- | --- | --- | --- | --- |
| fr | 16/17 | 16/17 | 16/17 | 16/17 | 17/17 | 17/17 | 17/17 |
| en | 5/17 | 5/17 | 16/17 | 16/17 | 17/17 | 17/17 | 17/17 |
| **ar** | **5/17** | **5/17** | **17/17** | **17/17** | **16/17** | **16/17** | **17/17** |
| tn | 13/17 | 13/17 | 9/17 | 9/17 | 10/17 | 10/17 | 17/17 |

- **Questions arabes.** 5 sur 17 ont des tokens différents après normalisation (ة → ه et على → علي), mais les 20 premiers résultats BM25 restent identiques pour les 17 : 0 token arabe dans l'index. Les 5 succès de BM25 seul sont tous des questions produit, trouvées au rang 1 grâce à leur mot latin.
- **fr, en, tn.** Tokens identiques pour 51 questions sur 51 et listes identiques : l'effet est nul, comme prévu.
- **Rang du premier bon document.** Identique pour toutes les questions et dans tous les modes (détail dans le JSON).

### Variantes orthographiques (jeu SYNTHÉTIQUE)

Les variantes sont construites mécaniquement à partir des 17 questions arabes. Une variante n'est réellement modifiée que si la question contient le caractère visé : 10 questions sur 17 pour la hamza, 5 sur 17 pour ة, et 17 sur 17 pour les diacritiques et le tatweel.

| Variante | BM25 seul (actuel = normalisé) | Basic, actuel | Hybrid, actuel | Hybrid, BM25 normalisé | Advanced, actuel | Advanced, BM25 normalisé |
| --- | --- | --- | --- | --- | --- | --- |
| Questions d'origine | 5/17 | 15/17 | 17/17 | 17/17 | 16/17 | 16/17 |
| Hamza retirée (أ إ آ → ا) | 5/17 | 15/17 | 17/17 | 17/17 | 17/17 | 17/17 |
| ة → ه | 5/17 | 14/17 | 16/17 | 16/17 | 15/17 | 15/17 |
| Diacritiques ajoutés (une fatha après chaque lettre) | 5/17 | **4/17** | **5/17** | 5/17 | **5/17** | 5/17 |
| Tatweel inséré | 5/17 | 12/17 | 14/17 | 14/17 | 14/17 | 14/17 |

La normalisation dans BM25 ne rattrape aucune variante : les 4 × 17 listes BM25 sont identiques. Les pertes viennent du **modèle d'embedding**, qui reçoit le texte brut.

### Complément : normaliser la question avant toute la recherche

Ce complément n'était pas demandé. La question est normalisée avant `retriever.search`, embedding dense compris, et l'index n'est pas modifié.
- **Légère :** diacritiques et tatweel retirés.
- **Complète :** `normalize_ar`.

| Jeu | Basic (actuel → légère → complète) | Hybrid (actuel → légère → complète) | Advanced (actuel → légère → complète) |
| --- | --- | --- | --- |
| fr / en / tn (51 questions) | inchangé | inchangé | inchangé |
| ar, questions d'origine | 15 → 15 → 15 | 17 → 17 → 17 | 16 → 16 → **15** |
| Hamza retirée | 15 → 15 → 15 | 17 → 17 → 17 | 17 → 16 → 15 |
| ة → ه | 14 → 14 → 15 | 16 → 16 → 17 | 15 → 15 → 15 |
| Diacritiques ajoutés | **4 → 15** → 15 | **5 → 17** → 17 | **5 → 16** → 15 |
| Tatweel inséré | **12 → 15** → 15 | **14 → 17** → 17 | **14 → 16** → 15 |

- **La normalisation complète fait perdre une question réelle.** En advanced, « ما هي مدة ضمان لوحة أردوينو؟ » passe du rang 1 à « absente ». En effet, ة → ه et ى → ي produisent une orthographe que le modèle d'embedding connaît mal.
- **La version légère ne fait aucune perte** sur les questions d'origine. Elle rattrape presque toutes les variantes avec diacritiques ou tatweel.

## A4. Conclusion factuelle

1. **Pour BM25, la normalisation ne manque pas.** Son impact est nul : 0 liste modifiée sur 136 requêtes arabes (originales et variantes). La base est entièrement en français, donc l'index ne contient aucun mot arabe à faire correspondre. Normaliser l'arabe pour BM25 n'aurait de sens qu'**avec des documents en arabe** dans la base.
2. **NFKD traite déjà** les hamzas portées et les diacritiques. Il **ne traite pas** ة, ى, ٱ ni le tatweel. Rien ne gère l'article ni les prépositions collées, ce qui demanderait une racinisation, absente du projet.
3. **Le défaut qui se mesure est ailleurs.** Une question écrite avec des diacritiques ou un tatweel dégrade fortement la recherche **dense**. Retirer diacritiques et tatweel de la question avant l'embedding corrige ce défaut sur le jeu synthétique (advanced : 5 → 16/17 et 14 → 16/17), sans effet sur les 68 questions du banc. L'unification ة/ى/أ n'est pas recommandée pour le dense : elle fait perdre une question.
4. **Limites.**
   - Les variantes sont **synthétiques**. Une fatha sur chaque lettre et un tatweel dans chaque mot sont des cas extrêmes, et on ne sait pas à quelle fréquence de vrais clients écrivent ainsi : la fréquence réelle est **non mesurée**.
   - Le banc ne compte que 17 questions arabes, et un seul passage a été fait (la recherche est déterministe, voir `calibration_seuil_modes.md`).
   - L'expansion de l'arabizi n'est pas appliquée ici : elle ne concerne que le tunisien.

## Versions

Python 3.13.5, numpy 2.5.1, rank_bm25 (`BM25Okapi`), sentence-transformers 5.7.0, client chromadb 1.5.9, serveur ChromaDB 1.4.1, reclassement `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`.
