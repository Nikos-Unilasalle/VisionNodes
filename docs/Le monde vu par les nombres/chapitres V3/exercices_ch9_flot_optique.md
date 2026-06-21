# Exercices — Chapitre 9 · Lire le mouvement : flot optique

---

## Exercice 1 · Suivre une barre qui glisse, et voir où le suivi échoue

![Barre verticale noire se déplaçant horizontalement sur fond gris : deux images successives, la barre décalée vers la droite, une flèche indiquant le mouvement réel](../figures/ex_ch9_barre_mouvement.jpg)

**Ce que vous voyez.** Un mouvement simple et connu. La mission : voir où le suivi de mouvement réussit et où il se trompe, pour comprendre ses limites avant de lui faire confiance.

**Pipeline VNStudio**
`Webcam` → `Optical Flow (Lucas-Kanade)` → `Display`

Le nœud pose des flèches de mouvement sur les points qu'il sait suivre.

---

**Questions**

1. Sur le bord latéral de la barre, la flèche pointe-t-elle bien vers la droite ? Sur le bord supérieur (horizontal), les flèches sont-elles cohérentes ou parties dans tous les sens ?

2. En regardant uniquement le bord supérieur horizontal de la barre, pourriez-vous dire qu'elle va vers la droite ? Pourquoi un bord ne renseigne-t-il que sur le mouvement perpendiculaire à lui-même ?

3. Faites glisser la barre en diagonale (45°). Les flèches sur le coin de la barre s'orientent-elles correctement ? Les coins suivent-ils mieux le vrai mouvement que les bords plats ?

4. **Défi.** Faites glisser deux barres en sens opposés dans la même image. Le suivi distingue-t-il les deux mouvements ? Qu'est-ce qui pourrait lui faire confondre une barre avec l'autre, et comment l'éviter ?

---

## Exercice 2 · Doser le lissage du mouvement sur une personne qui marche

![Deux images successives d'une personne marchant dans un couloir : torse et jambes en mouvement, fond fixe. La chemise unie et les cheveux texturés donnent des signaux de mouvement très différents](../figures/ex_ch9_personne_couloir.jpg)

**Ce que vous voyez.** Un sujet en mouvement avec des zones faciles à suivre (texturées) et des zones ambiguës (chemise unie). La mission : régler un curseur qui « remplit » le mouvement des zones sans détail à partir des zones voisines.

**Pipeline VNStudio**
`Webcam` → `Optical Flow` → `Flow Visualizer` → `Display`

Le nœud `Optical Flow` (Farneback) calcule un champ de mouvement partout ; `Flow Visualizer` code la direction en teinte et la vitesse en saturation. Le curseur de lissage propage l'information des zones nettes vers les zones vides.

---

**Questions**

1. Réglez le lissage au minimum. Sur la chemise unie, le mouvement est-il cohérent ou bruité ? Pourquoi une zone sans détail ne sait-elle pas, seule, dans quel sens elle bouge ?

2. Poussez le lissage au maximum. Le champ devient régulier, mais que se passe-t-il à la frontière du corps ? Le mouvement « bave »-t-il sur le fond immobile ?

3. À lissage moyen, comparez le mouvement mesuré sur les cheveux et sur la chemise. Si la chemise paraît immobile alors que la personne marche, quel problème cela pose pour découper le sujet par son mouvement ?

4. **Défi.** Trouvez le réglage de lissage qui donne le meilleur compromis : un corps qui bouge d'un seul tenant, des bords nets, pas de débordement sur le fond. Décrivez ce que vous gagnez et perdez en tournant le curseur dans un sens ou dans l'autre.

---

## Exercice 3 · Choisir entre suivi de points et carte de mouvement complète

![Vue de dessus d'une partie d'échecs : la main du joueur déplace une pièce. Le plateau quadrillé offre des coins en abondance, les cases noires sont des zones lisses sans détail](../figures/ex_ch9_echecs.jpg)

**Ce que vous voyez.** Une scène mêlant zones très texturées (cases, pièces) et zones uniformes (cases noires lisses). La mission : comparer deux manières de mesurer le mouvement et choisir selon le besoin.

**Pipeline VNStudio**
`Webcam` → `Split Half` :
— gauche : `Optical Flow (Lucas-Kanade)` → flèches
— droite : `Optical Flow` → `Flow Visualizer` → carte colorée
→ `Display`

À gauche, un suivi de points choisis ; à droite, un champ de mouvement partout.

---

**Questions**

1. Sur les coins du damier, le suivi de points donne-t-il des flèches précises ? Pose-t-il des flèches sur les cases noires uniformes ? Pourquoi évite-t-il ces zones ?

2. Sur la carte dense, les cases noires reçoivent-elles quand même un mouvement ? Est-il fiable, ou deviné à partir des voisins ?

3. La main bouge vite. Le mouvement mesuré est-il le même partout sur la main, ou plus fort sur les doigts texturés que sur la paume lisse ?

4. **Défi.** Pour savoir quelle pièce a été déplacée et vers quelle case, lequel des deux outils est le plus adapté ? Esquissez un pipeline qui repère automatiquement la case de départ et la case d'arrivée du coup joué.

---

*Corrigés disponibles en annexe.*
