# Tâches 1 et 4 : arrêtées, faute de données d'entrée

Constat du 24/11/2026.

## Tâche 1 : validation du juge RAGas, ARRÊTÉE
- **Fichier attendu :** `data/evaluation/annotation_juge/feuille_annotation_remplie.csv`. **Il n'existe pas.**
- **Contenu du dossier :** `feuille_annotation.csv` (la feuille vierge préparée pour la remarque 52), `feuille_annotation.md`, `cle_secrete.json`.
- **Rien n'a été calculé :** ni pourcentage d'accord, ni kappa, ni liste des désaccords.
- **Quand la feuille sera remplie :** l'enregistrer sous ce nom, puis lancer `venv/Scripts/python.exe scripts/compare_juge_humain.py`. Le script est déjà prêt : il calcule l'accord, le kappa de Cohen, les désaccords et le sens du biais.

## Tâche 4 : classificateur d'intentions, ARRÊTÉE
- **Fichier attendu :** `data/eval/intents_test.csv`. **Il n'existait pas.**
- **Modèle créé :** `data/eval/intents_test.csv`, avec la seule ligne d'en-têtes `message,intention_attendue`.
- **Exemples d'entraînement vérifiés :** `data/intents/exemples.json` contient **196** phrases.

  | Intention | fr | en | ar | tn | Total |
  | --- | --- | --- | --- | --- | --- |
  | human_agent | 10 | 10 | 8 | 10 | 38 |
  | frustration | 10 | 10 | 8 | 10 | 38 |
  | order_tracking | 8 | 8 | 6 | 8 | 30 |
  | help | 10 | 10 | 8 | 10 | 38 |
  | general | 17 | 13 | 9 | 13 | 52 |

- **Valeurs attendues dans `intention_attendue`,** si on reprend les intentions apprises : `human_agent`, `frustration`, `order_tracking`, `help`, `general`.
- **Contrôle de chevauchement :** quand le fichier sera rempli, il faudra vérifier qu'aucun message ne figure parmi les 196 phrases. Ce contrôle n'a pas pu être fait, puisque le fichier est vide.
