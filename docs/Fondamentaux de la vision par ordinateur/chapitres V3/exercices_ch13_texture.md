# Exercices — Chapitre 13 · Le grain des choses : la texture

---

## Exercice 1 · Classer quatre matériaux par leur grain

![Quatre carrés de texture côte à côte sur fond gris : (A) tissu de coton blanc uniforme, (B) bois de chêne aux veines parallèles horizontales, (C) béton rugueux aléatoire, (D) céramique à motif géométrique régulier à 45°](../figures/ex_ch13_textures_glcm.jpg)

**Ce que vous voyez.** Quatre matériaux dont le grain est radicalement différent. La mission : trouver les chiffres qui les distinguent automatiquement, comme le ferait un système de tri de matériaux.

**Pipeline VNStudio**
`Image Source` (recadrez sur chaque texture) → `GLCM Features` → `Output Display`

Le nœud mesure trois indicateurs de texture : le contraste (rugosité), l'homogénéité (régularité), l'énergie (répétition d'un motif).

---

**Questions**

1. Relevez les trois indicateurs pour chaque texture. Lequel des quatre matériaux a le contraste le plus fort ? Lequel a l'homogénéité la plus haute ?

2. Le bois a des veines horizontales. Faites mesurer la texture dans le sens des veines, puis perpendiculairement. Le contraste change-t-il selon la direction ? Qu'est-ce que cela révèle sur l'orientation du grain ?

3. Le béton est désordonné, la céramique très répétitive. Lequel des deux a l'énergie la plus haute ? Pourquoi un motif qui se répète à l'identique « concentre » sa signature au lieu de l'étaler ?

4. **Défi.** Réglez les indicateurs pour séparer les quatre matériaux sans erreur : quel duo de chiffres suffit à les ranger en quatre tas distincts ? Faites ensuite pivoter le bois de 90° et vérifiez s'il atterrit toujours dans le bon tas, ou s'il faut mesurer dans plusieurs directions pour devenir insensible à la rotation.

---

## Exercice 2 · Reconnaître une texture à l'échelle du micro-motif

![Les mêmes quatre matériaux qu'à l'exercice 1, mais à fort grossissement : fibres entrelacées du coton, anneaux du bois, granules du béton, carrés nets de la céramique](../figures/ex_ch13_textures_lbp.jpg)

**Ce que vous voyez.** Les mêmes textures vues au plus près, à l'échelle du motif élémentaire. La mission : construire une signature de texture fondée sur ces micro-motifs.

**Pipeline VNStudio**
`Image Source` → `LBP` *(à créer)* → `Histogram` → `Output Display`

Le nœud résume le voisinage de chaque pixel en un code de micro-motif, et l'histogramme de ces codes devient la signature de la texture. Modes disponibles : classique, ou insensible à la rotation.

---

**Questions**

1. Calculez la signature des quatre textures et affichez les histogrammes côte à côte. Lequel est très « pointu » (un ou deux motifs dominants) ? Lequel est étalé (tous les motifs présents) ? Reliez cela à la régularité visuelle.

2. Comparez deux à deux les signatures. Quelle paire de matériaux a les histogrammes les plus ressemblants ? Êtes-vous surpris du résultat à l'œil ?

3. Faites pivoter le bois de 45°. En mode classique, sa signature change-t-elle ? En mode insensible à la rotation, reste-t-elle stable ? Quel mode choisir pour reconnaître un matériau quelle que soit son orientation, et que perd-on en finesse ?

4. **Défi.** Pour la paire la plus difficile à séparer (question 2), réglez le rayon du voisinage du nœud LBP jusqu'à ce que leurs signatures se distinguent enfin. Quel rayon y arrive ? Vérifiez que les autres matériaux restent bien séparés à ce réglage.

---

## Exercice 3 · Cartographier l'orientation des crêtes d'une empreinte

![Photographie d'une empreinte digitale sur fond blanc : crêtes noires parallèles légèrement courbées, espacées d'environ 12 pixels, avec quelques fourches (minuties)](../figures/ex_ch13_empreinte.jpg)

**Ce que vous voyez.** Une texture quasi-périodique dont l'orientation tourne lentement, avec des points singuliers (les fourches). La mission : dresser la carte d'orientation des crêtes, première étape de toute reconnaissance d'empreinte.

**Pipeline VNStudio**
`Image Source` → `Gabor Bank` *(à créer)* (8 orientations, espacement 12 px) → `Colormap` → `Output Display`

Le banc passe huit filtres orientés et garde, pour chaque pixel, l'orientation qui répond le plus fort. Le résultat est une carte d'orientation locale.

---

**Questions**

1. Sur une zone de crêtes horizontales, quelle orientation le banc retient-il ? Et sur une zone où les crêtes montent en diagonale ? La carte suit-elle bien la direction visible des crêtes ?

2. Suivez la carte d'orientation le long d'une boucle de l'empreinte. La transition d'une orientation à l'autre est-elle brutale ou douce ? Qu'est-ce que cela dit de la façon dont les crêtes tournent ?

3. Repérez les fourches (minuties) : sur la carte d'énergie, ressortent-elles en zones sombres (réponse faible et ambiguë) ? Pourquoi une fourche casse-t-elle la belle régularité locale des crêtes ?

4. **Défi.** Réglez l'espacement du banc bien au-delà de 12 pixels. L'empreinte est-elle encore détectée, ou la réponse s'effondre-t-elle ? Trouvez la plage d'espacement où les crêtes ressortent le mieux — c'est elle qui correspond à leur vraie fréquence.

---

*Corrigés disponibles en annexe.*
