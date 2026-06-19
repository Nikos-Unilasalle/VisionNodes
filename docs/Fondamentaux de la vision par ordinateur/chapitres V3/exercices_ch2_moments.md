# Exercices — Chapitre 2 · Peser une forme : les moments d'image

---

## Exercice 1 · Localiser le centre d'un panneau pour le suivre

![Plaque de signalisation routière vue de face sur fond uni : un panneau triangulaire « cédez le passage », un panneau circulaire « limitation 50 », un panneau rectangulaire « sens interdit »](../figures/ex_ch2_panneaux.jpg)

**Ce que vous voyez.** Trois formes géométriques simples, bien contrastées sur fond blanc. La mission : trouver le centre exact de chacune, comme le ferait un système d'aide à la conduite.

**Pipeline VNStudio**
`Image Source` → `Threshold (Advanced)` → `Connected Components` → `Image Moments` *(à créer)* → `Draw Overlay` → `Output Display`

Le nœud `Image Moments` marque le centre de gravité de chaque panneau et affiche son aire dans l'inspecteur.

---

**Questions**

1. Pour chaque panneau, lisez l'aire et la position du centre. Le centre tombe-t-il bien au milieu visuel de la forme ? Comparez l'aire des trois panneaux.

2. Déplacez un panneau vers la droite dans l'image source. Sa position de centre change-t-elle ? Son aire change-t-elle ? Qu'est-ce que cela implique pour suivre un panneau qui se déplace d'image en image ?

3. Éloignez la « caméra » (réduisez l'image). L'aire diminue-t-elle ? Le centre reste-t-il au bon endroit ? Lequel des deux est fiable pour reconnaître un panneau, lequel dépend de la distance ?

4. **Défi.** Rapprochez deux panneaux jusqu'à ce qu'ils se touchent. Le nœud les voit-il comme un seul objet (un seul centre) ou deux ? Réglez le seuillage pour les re-séparer et retrouver deux centres distincts.

---

## Exercice 2 · Mesurer l'inclinaison de cristaux par l'ellipse équivalente

![Vue microscopique de cristaux de sel gemme : cubes parfaits vus de face apparaissant comme des carrés, et quelques cristaux inclinés dont la projection ressemble à un losange allongé](../figures/ex_ch2_cristaux_sel.jpg)

**Ce que vous voyez.** Des cristaux dont la face visible va du carré parfait au losange étiré selon leur inclinaison. La mission : mesurer cette inclinaison automatiquement.

**Pipeline VNStudio**
`Image Source` → `Threshold (Advanced)` → `Connected Components` → `Image Moments` *(à créer)* → `Draw Overlay` → `Output Display`

Activez l'affichage de l'ellipse équivalente : le nœud dessine sur chaque cristal une ellipse qui épouse son allongement et son orientation.

---

**Questions**

1. Sur un cristal vu de face (carré), à quoi ressemble l'ellipse dessinée : un cercle ou une ellipse étirée ? Et sur un cristal incliné ?

2. Le nœud affiche l'angle d'orientation de chaque ellipse. Relevez-le pour trois cristaux d'inclinaisons différentes. L'angle suit-il bien la direction visible de chaque losange ?

3. Sur un cristal parfaitement carré, l'orientation devient instable et saute d'une mesure à l'autre. Pourquoi une forme sans direction privilégiée rend-elle l'angle impossible à fixer ?

4. **Défi.** Triez les cristaux en deux tas : « vus de face » (ellipse presque ronde) et « inclinés » (ellipse étirée). Quel critère d'allongement de l'ellipse sépare proprement les deux tas ? Combien de cristaux inclinés comptez-vous ?

---

## Exercice 3 · Reconnaître un chiffre manuscrit malgré la taille et l'inclinaison

![Six chiffres arabes manuscrits (1 à 6) tracés à la main sur fond blanc, dans des tailles légèrement différentes et avec de petites rotations naturelles](../figures/ex_ch2_chiffres.jpg)

**Ce que vous voyez.** Les mêmes chiffres écrits par la même personne, mais avec des variations de taille et d'inclinaison. La mission : trouver une « empreinte » de forme qui reste la même malgré ces variations.

**Pipeline VNStudio**
`Image Source` → `Threshold (Advanced)` → `Connected Components` → `Image Moments` *(à créer)* → `Output Display`

Le nœud calcule pour chaque chiffre ses sept invariants de Hu, une empreinte numérique de sa forme.

---

**Questions**

1. Relevez l'empreinte de Hu d'un même chiffre écrit en deux tailles différentes. Les valeurs restent-elles proches ? Qu'est-ce que cela promet pour reconnaître un chiffre quelle que soit sa taille ?

2. Faites pivoter un chiffre de 30° dans l'image source. Son empreinte de Hu change-t-elle beaucoup, ou tient-elle bon ? Comparez avec son aire, qui, elle, n'est pas invariante.

3. Comparez les empreintes de deux chiffres différents (par exemple le 1 et le 8). Sont-elles nettement distinctes ? L'empreinte sert-elle bien à les distinguer ?

4. **Défi.** Retournez un chiffre comme dans un miroir (un 2 devient un 2 inversé). Son empreinte de Hu bouge-t-elle ? Trouvez lequel des sept nombres réagit au miroir alors que les autres l'ignorent — c'est lui qui distingue une forme de son reflet.

---

*Corrigés disponibles en annexe.*
