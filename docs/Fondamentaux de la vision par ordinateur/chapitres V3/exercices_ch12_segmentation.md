# Exercices — Chapitre 12 · Où couper ? seuillage et segmentation classique

---

## Exercice 1 · Binariser une page ancienne mal éclairée

![Page d'un livre ancien en lumière rasante : encre noire sur papier ivoire, mais un dégradé d'éclairage assombrit le côté gauche, avec quelques taches d'oxydation](../figures/ex_ch12_livre_ancien.jpg)

**Ce que vous voyez.** Un document dont le fond s'assombrit d'un côté. La mission : obtenir un texte noir net sur fond blanc partout, première étape de toute lecture automatique de document.

**Pipeline VNStudio**
`Image Source` → `Split Half` :
— gauche : `Threshold (Advanced)` (seuil global)
— droite : `Threshold (Advanced)` (seuil adaptatif)
→ `Output Display`

Le seuil global cherche une seule coupure pour toute l'image ; le seuil adaptatif s'ajuste localement.

---

**Questions**

1. Sur le seuil global, le texte du côté sombre ressort-il, ou se noie-t-il dans un fond noirci ? Le seuil adaptatif fait-il mieux sur cette zone ? Comparez les deux moitiés.

2. Élargissez la fenêtre du seuil adaptatif. Que se passe-t-il quand elle devient plus grande que les taches d'oxydation ? Et quand elle devient plus petite que l'espace entre deux lignes ?

3. Le seuil global trouve tout seul sa coupure entre encre et papier. Sur une page bien contrastée, tombe-t-il au bon endroit ? Sur la page mal éclairée, pourquoi une seule coupure ne peut-elle pas convenir aux deux côtés à la fois ?

4. **Défi.** Réglez la chaîne pour produire un texte lisible sur toute la page, des deux côtés, sans que les taches d'oxydation ressortent comme des lettres. Quel réglage y arrive ? Combien de mots restent illisibles malgré tout ?

---

## Exercice 2 · Séparer des cellules qui se touchent

![Vue microscopique de cellules en culture serrées : certaines isolées, d'autres collées en doublets ou en amas, sur fond noir, contours fluorescents](../figures/ex_ch12_cellules_confluentes.jpg)

**Ce que vous voyez.** Des cellules collées que le simple seuillage voit comme une seule masse. La mission : les recompter une par une, problème quotidien en biologie.

**Pipeline VNStudio**
`Image Source` → `Threshold (Advanced)` → `Distance Transform` → `Watershed` → `Region Properties` → `Output Display`

Le watershed part du cœur de chaque cellule (les points les plus profonds de la carte de distance) et fait monter les bassins jusqu'à ce qu'ils se rencontrent.

---

**Questions**

1. Avec le seuillage seul, combien de régions le comptage trouve-t-il pour un amas de trois cellules collées ? Avec le watershed, combien en obtient-on ?

2. Affichez la carte de distance colorée. Combien de cœurs distincts voyez-vous dans l'amas de trois ? Un par cellule, ou moins ?

3. Le watershed trace une frontière entre cellules voisines. Tombe-t-elle à l'endroit de la vraie membrane, ou ailleurs ? Le découpage vous paraît-il juste ?

4. **Défi.** Sur une image bruitée, le watershed découpe parfois une cellule en plusieurs morceaux (sur-découpage). Lissez la carte de distance avant de chercher les cœurs. À partir de quel lissage le sur-découpage disparaît-il sans souder deux cellules proches ? Recomptez et comparez au comptage manuel.

---

## Exercice 3 · Découper une plage en zones de couleur

![Photographie d'une plage tropicale à quatre zones nettes : ciel bleu, mer turquoise, sable doré, palmier vert, couleurs saturées mais bords adoucis par les reflets](../figures/ex_ch12_plage.jpg)

**Ce que vous voyez.** Une scène à quatre régions de couleur bien distinctes mais aux frontières floues. La mission : comparer deux façons de découper l'image par la couleur et voir laquelle colle le mieux au réel.

**Pipeline VNStudio**
`Image Source` → `Grid Compare` :
— K-Means (4 groupes), lancé deux fois
— Mean Shift *(à créer)*
— image originale
→ `Output Display`

K-Means exige qu'on lui dise le nombre de zones ; Mean Shift le découvre seul.

---

**Questions**

1. Lancez K-Means deux fois. Les deux découpages sont-ils identiques ? Où voyez-vous des différences ? Pourquoi un démarrage au hasard donne-t-il des résultats variables ?

2. Mean Shift ne demande pas le nombre de zones. Combien en trouve-t-il ? Plus ou moins que quatre ? Élargissez sa portée de couleur : le nombre de zones change-t-il ?

3. Sur la transition douce ciel/mer, K-Means trace une frontière nette et tranchée. Mean Shift fait-il pareil, ou crée-t-il des zones intermédiaires ? Lequel respecte mieux ce que voit l'œil ?

4. **Défi.** Réglez chacune des deux méthodes pour isoler proprement le palmier vert du reste, sans rogner sur le ciel ni la mer. Laquelle y arrive le plus facilement ? Pour découper une scène dont on ignore le nombre de régions, laquelle choisiriez-vous ?

---

*Corrigés disponibles en annexe.*
