# Exercices — Chapitre 6 · Là où l'image bascule : gradients et contours

---

## Exercice 1 · Extraire le contour propre d'une feuille

![Photographie d'une feuille d'automne posée sur le sol : nervures très fines sur un fond uniforme, bord extérieur net, taches et déchirures sur le limbe](../figures/ex_ch6_feuille.jpg)

**Ce que vous voyez.** Une structure avec des bords de contraste très inégal : contour extérieur fort, nervures secondaires à peine marquées. La mission : en tirer un tracé de contour propre et fin.

**Pipeline VNStudio**
`Image Source` → `Split Half` :
— gauche : `Sobel Edge Detector` → `Colormap`
— droite : `Canny Edge Detector` *(à créer)*
→ `Output Display`

Sobel montre la « force » des bords en dégradé ; Canny en tire un trait fin. Canny propose un seuil bas et un seuil haut.

---

**Questions**

1. Comparez les deux moitiés sur une nervure. Laquelle donne un trait large et flou, laquelle un trait fin d'un pixel ? Pour compter ou suivre des nervures, laquelle est exploitable ?

2. Réglez Canny avec ses deux seuils rapprochés, puis écartez-les. Quelles nervures fines apparaissent seulement quand l'écart est grand ? Qu'est-ce que ce double seuil permet de récupérer sans laisser entrer le bruit ?

3. Augmentez le pré-lissage de Canny. Quels détails fins disparaissent en premier ? Pourquoi un peu de flou avant la détection aide, et qu'est-ce qu'on perd à en mettre trop ?

4. **Défi.** Réglez Canny pour obtenir le contour extérieur complet de la feuille en un seul trait fermé, sans les nervures internes ni le bruit du sol. Branchez `Find Contours` derrière et vérifiez qu'il ne compte bien qu'une seule feuille.

---

## Exercice 2 · Distinguer une surface plane, un bord et un coin

![Coin d'une table en bois vu de haut : la surface plane uniforme, le bord rectiligne du plateau, et le coin à 90° où deux bords se rejoignent](../figures/ex_ch6_coin_table.jpg)

**Ce que vous voyez.** Les trois situations de base réunies : du plat, une ligne, un coin. La mission : faire repérer automatiquement les coins, points d'ancrage stables pour le suivi et l'assemblage de panoramas.

**Pipeline VNStudio**
`Image Source` → `Harris / Shi-Tomasi` *(à créer)* → `Colormap` → `Output Display`

Le nœud allume fortement les coins, faiblement les bords, et reste éteint sur les zones plates.

---

**Questions**

1. Sur la carte de réponse, repérez la zone plate, le bord et le coin. Lequel s'allume le plus ? Lequel reste éteint ? La détection colle-t-elle à votre intuition ?

2. Montez le seuil de détection. Les points sur le bord disparaissent-ils avant ceux du coin ? Pourquoi un coin est-il un repère plus « sûr » qu'un point posé sur une ligne ?

3. Comparez les deux modes du nœud (Harris et Shi-Tomasi) sur le même coin. Détectent-ils le même point ? L'un attrape-t-il plus de points sur les bords obliques que l'autre ?

4. **Défi.** Faites pivoter l'image de 45°. Les coins détectés suivent-ils fidèlement la table, ou de nouveaux points apparaissent-ils n'importe où ? Le détecteur est-il fiable quel que soit l'angle de prise de vue ?

---

## Exercice 3 · Pourquoi un bord seul ne révèle pas le vrai mouvement

![Vue stroboscopique d'une balle rayée (rayures noires et blanches) se déplaçant horizontalement sur fond gris : trois positions superposées en teintes différentes](../figures/ex_ch6_balle_rayee.jpg)

**Ce que vous voyez.** Un objet rayé qui se déplace horizontalement. La mission : comprendre, en regardant les flèches de gradient, pourquoi un bord isolé ne suffit jamais à dire dans quelle direction un objet bouge — le fameux « problème de la fenêtre ».

**Pipeline VNStudio**
`Image Source` → `Image Gradient` → `Draw Overlay` (flèches) → `Output Display`

Le nœud dessine en chaque point une petite flèche pointant à travers le bord local, dans le sens où l'image s'éclaircit.

---

**Questions**

1. Sur le bord latéral (vertical) de la balle, dans quel sens pointe la flèche ? Indique-t-elle bien le déplacement horizontal réel de la balle ?

2. Sur une rayure horizontale, dans quel sens pointe la flèche ? À partir de cette seule flèche, pourriez-vous deviner que la balle va vers la droite ?

3. En regardant uniquement une rayure horizontale, le mouvement « vers la droite » et « vers le haut » donnent la même apparence locale. Pourquoi un bord ne renseigne-t-il que sur le déplacement perpendiculaire à lui-même, jamais le long de lui ?

4. **Défi.** Couvrez tout sauf une petite fenêtre posée sur une rayure droite, et essayez de deviner le mouvement de la balle. Impossible ? Élargissez la fenêtre jusqu'à inclure un coin ou le bord latéral. À partir de quel moment le mouvement devient-il déterminé ? C'est exactement ce que font les algorithmes de flot en regardant un voisinage plutôt qu'un point.

---

*Corrigés disponibles en annexe.*
