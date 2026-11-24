# Résumé des mesures pour le rapport (24/11/2026)

**Branches.**
- Les mesures sont faites sur la branche `mesures-rapport`, issue de `a0c0cd3`. La branche principale n'est pas touchée.
- Les contre-mesures sont appliquées sur la branche `securite-contre-mesures`, dans le worktree `C:\Users\ramif\chatbot-ai-securite`. Le patch y est appliqué, mais pas commité.
- Rien n'est commité ni poussé.

**Incident.**
- Docker Desktop s'est arrêté une fois pendant les mesures : ChromaDB et PostgreSQL étaient injoignables.
- La première exécution de la tâche 3 a été **invalidée**, avec 0 appel LLM consommé et 0 écriture en base, puis relancée après le redémarrage.
- Les scripts s'arrêtent désormais d'eux-mêmes en cas de « service indisponible ».

| Tâche | Résultat chiffré | Limites | Fichiers bruts |
| --- | --- | --- | --- |
| 1. Validation du juge RAGas | **Non faite** : `feuille_annotation_remplie.csv` est absente, il n'y a que la feuille vierge | — | `taches1_4_arrets.md` |
| 2. RAGas, mode hybrid | **Partiel : 17 questions sur 22** (arrêt sur le quota journalier de tokens du juge gpt-oss-20b). Sur ces 17 questions, Basic / Hybrid / Advanced : CP 0,750 / 0,861 / 0,971 ; CR 0,676 / 0,794 / 0,877 ; F 0,610 / 0,848 / 0,805 ; AR 0,557 / 0,685 / 0,659 ; hit@4 76,5 / 94,1 / 100 % ; recherche (médiane) 171 / 149 / 1104 ms. Juge : 291 requêtes HTTP (143 × 200, 145 × 429, 3 × 400), 68 notes sur 68 obtenues, 0 échec. Génération : 18 requêtes, 0 × 429 | Il manque les 3 questions en tunisien et 2 des 4 en arabe, donc les moyennes sont plus hautes que sur 22. Basic et Advanced datent du 27/09, Hybrid du 24/11. Une seule exécution, juge non validé | `ragas_hybrid.partial.json`, `ragas_comparaison_17.json`, `tache2_ragas_hybrid.md` |
| 3. Contre-mesures D1–D7 | Attaques réussies (pipeline) : **8/44 = 18,2 %** (IC95 9,5–32,0) → **4/44 = 9,1 %** (IC95 3,6–21,2). En LLM direct : 1/15 → 2/15. Injection indirecte 3/5 → 0/5 ; commande d'un autre client corrigée. McNemar (pipeline, 5 corrigées et 1 nouvelle) : p ≈ 0,22, **non significatif**. Faux refus : **0/22 avant et 0/22 après** (IC95 0–14,9 %). Appels LLM : 43 + 43 + 22 + 22, aucun 429 | 44 attaques, une exécution par côté, température 0,3 (inj-05 a basculé d'une exécution à l'autre). Rien contre la toxicité (tox-02) ni contre une consigne passée par l'historique (role-04) | `securite_llm_avant.json`, `securite_llm_apres.json`, `securite_llm_relecture_*.json`, `faux_refus_avant.json`, `faux_refus_apres.json`, `tache3_securite.md` |
| 4. Classificateur d'intentions | **Non faite** : `data/eval/intents_test.csv` était absent ; un modèle vide a été créé (`message,intention_attendue`). Nombre d'exemples d'entraînement vérifié : **196** | Chevauchement non vérifiable tant que le fichier est vide | `data/eval/intents_test.csv`, `taches1_4_arrets.md` |
| 5. Données personnelles (code) | Envoyés à Groq : message intégral + 6 derniers messages (500 caractères chacun) + 4 passages RAG, **sans masquage** ; pas d'identifiant ni de données de commande. Redis : identifiant en clair et 20 messages, TTL **1 h** (sans expiration en repli mémoire). PostgreSQL : identifiant, texte des messages et commandes, durée **illimitée**, **aucune purge** ; `DELETE /users` ne fait que désactiver le compte | Lecture du code seulement, aucune conclusion juridique | `tache5_donnees_personnelles.md` |

**Scripts ajoutés :**
- `scripts/measure_faux_refus.py` ;
- `scripts/evaluate_ragas_hybrid.py` ;
- `scripts/measure_securite_llm.py`, avec l'arrêt sur panne ajouté.
