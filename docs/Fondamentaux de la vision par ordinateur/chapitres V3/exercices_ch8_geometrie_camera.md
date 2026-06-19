# Exercices — Chapitre 8 · Géométrie de la caméra : projeter, perdre, retrouver

---

## Exercice 1 · Redresser une affiche photographiée de travers

![Photographie d'une affiche de concert collée en oblique sur un mur : le texte est net mais l'affiche est vue en perspective, ses bords supérieurs paraissent plus courts que les inférieurs et les lignes parallèles convergent](../figures/ex_ch8_affiche_oblique.jpg)

**Ce que vous voyez.** Une surface plane vue de biais. La mission : la remettre à plat, face caméra, comme un scanner — l'opération de base pour numériser un document photographié.

**Pipeline VNStudio**
`Image Source` → `RANSAC Homography` (4 coins) → `Output Display`

Pointez les quatre coins de l'affiche dans l'image, puis les quatre coins du rectangle voulu. Le nœud redresse la surface.

---

**Questions**

1. Après redressement, les lignes de texte sont-elles bien horizontales ? L'affiche forme-t-elle un vrai rectangle ? Vérifiez avec un profil de ligne posé sur une ligne de texte.

2. Déplacez un des quatre coins de quelques pixels. Le redressement se dégrade-t-il beaucoup ? Pourquoi placer les coins avec soin est-il décisif pour ce genre d'opération ?

3. Pointez les coins d'une autre surface plane de la scène (une porte, une fenêtre). Le même outil la redresse-t-il aussi ? Qu'est-ce qui doit rester vrai de la surface pour que ça marche (plane, pas bombée) ?

4. **Défi.** Essayez de redresser une affiche collée sur un mur courbé. Quelle partie ressort bien droite, quelle partie reste déformée ? Concluez sur la limite de l'outil quand la surface n'est pas vraiment plane.

---

## Exercice 2 · Corriger les lignes courbées d'un objectif grand-angle

![Fenêtre à croisillons photographiée au grand-angle : les barres horizontales se courbent vers les bords de l'image (effet barillet), tandis qu'au centre elles paraissent droites](../figures/ex_ch8_fenetre_grandangle.jpg)

**Ce que vous voyez.** Des lignes que l'on sait droites, mais que l'objectif a bombées. La mission : redresser cette déformation, indispensable avant toute mesure géométrique sur une photo grand-angle.

**Pipeline VNStudio**
`Image Source` → `Distortion Correction` *(à créer)* → `Output Display`

Le nœud propose un curseur de correction qui redresse progressivement les lignes courbées.

---

**Questions**

1. Sans correction, posez un profil de ligne sur une barre horizontale. La courbe est-elle bombée ? Où la déformation est-elle la plus forte : au centre ou sur les bords ?

2. Poussez le curseur de correction jusqu'à ce que la barre redevienne plate selon le profil. Notez le réglage. Les barres du bord se redressent-elles en même temps que celles du centre ?

3. Comparez une barre près du centre et une barre tout au bord. Laquelle avait le plus besoin d'être corrigée ? Pourquoi le bord d'une image grand-angle souffre-t-il le plus ?

4. **Défi.** Après correction, toutes les barres sont-elles parfaitement droites, ou certaines penchent-elles encore ? Enchaînez un redressement de perspective (exercice 1) pour aligner le croisillon sur une grille parfaite. Quelle déformation relève de l'objectif, laquelle relève de l'angle de prise de vue ?

---

## Exercice 3 · Mesurer la profondeur d'une scène avec deux caméras

![Paire d'images stéréo d'une bibliothèque : vue gauche et vue droite décalées de quelques centimètres. Les livres du premier plan se décalent beaucoup d'une vue à l'autre, le fond presque pas](../figures/ex_ch8_stereo_bibliotheque.jpg)

**Ce que vous voyez.** La même scène vue par deux yeux légèrement écartés. La mission : transformer ce décalage en carte de profondeur, comme la vision binoculaire humaine.

**Pipeline VNStudio**
`Image Source (gauche)` + `Image Source (droite)` → `Stereo Disparity` *(à créer)* → `Colormap` → `Output Display`

Le nœud mesure, pour chaque point, son décalage entre les deux vues et en déduit une carte colorée de proche à lointain.

---

**Questions**

1. Sur la carte colorée, les livres du premier plan ressortent-ils en « proche » ou en « loin » ? Pourquoi un objet proche se décale-t-il davantage entre les deux vues qu'un objet lointain ?

2. Cliquez sur un point d'un livre de la vue gauche. Dans la vue droite, le même point est-il sur la même hauteur (même ligne) ? Qu'est-ce que cela permet : chercher la correspondance sur toute l'image, ou seulement le long d'une ligne ?

3. Repérez une zone du fond uniforme (un mur nu). La carte de profondeur y est-elle fiable ou bruitée ? Pourquoi une surface sans motif est-elle difficile à mettre en correspondance ?

4. **Défi.** Réglez la taille du bloc de comparaison du plus petit au plus grand. Sur les dos de livres texturés, lequel donne une carte plus nette ? Sur le mur uni, lequel est moins bruité ? Décrivez le compromis et choisissez un réglage pour cette scène.

---

*Corrigés disponibles en annexe.*
