# Consignes d'annotation : validation du juge Ragas (remarque 52)

Fichier à remplir : `data/evaluation/annotation_juge/feuille_annotation_remplie.csv`, à créer
d'abord comme **copie** de `feuille_annotation.csv` (même dossier ; c'est ce nom que lit
`scripts/compare_juge_humain.py`). Remplir les colonnes vides de la copie, garder le séparateur
« ; » (sous Excel : enregistrer en « CSV UTF-8 (délimité par des points-virgules) »).
Pour lire plus facilement : `feuille_annotation.md` (même contenu, mêmes identifiants A01 à A30).

**Annoter sans consulter les notes du juge ni le mode** (Basic ou Advanced). Ne pas ouvrir
`cle_secrete.json` avant d'avoir terminé les 30 items.

Pour chaque item sont affichés : la question, la réponse de référence, les passages récupérés
(séparés et numérotés) et la réponse générée par le chatbot. Juger avec les seuls éléments affichés.

Valeurs possibles : **0**, **0,5** ou **1**.

| Colonne | Question à se poser | 1 | 0,5 | 0 |
| --- | --- | --- | --- | --- |
| `fidelite` | Toutes les affirmations de la réponse sont-elles soutenues par les passages affichés ? | toutes | certaines ne sont pas soutenues | la plupart ne sont pas soutenues ou sont inventées |
| `pertinence` | La réponse répond-elle à la question posée ? | oui | partiellement | non |
| `rappel` | Les passages affichés contiennent-ils l'information de la réponse de référence ? | toute | une partie | aucune |
| `commentaire` | Libre, facultatif | | | |

Cas particulier : une réponse « je n'ai pas l'information » est notée **1 en fidélité** si elle
est honnête (rien d'inventé). Sa pertinence se juge à part : elle ne répond pas à la question.

Remplir toutes les lignes, sans modifier les autres colonnes ni l'ordre des items.
