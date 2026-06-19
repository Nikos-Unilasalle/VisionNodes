# Exercices — Chapitre 5 · Le pochoir glissant : filtrage et convolution

---

## Exercice 1 · Isoler une échelle de détail dans un portrait

![Portrait à contre-jour : fond légèrement flou, grain de peau visible, rides marquées, cheveux fins se détachant sur le ciel. Trois échelles de détail cohabitent — le grain fin, les rides moyennes, le contour large du visage](../figures/ex_ch5_portrait.jpg)

**Ce que vous voyez.** Une scène où coexistent des détails fins, moyens et larges. La mission : un filtre qui ne garde qu'une seule échelle à la fois, comme on règle la « clarté » ou le « grain » dans un logiciel de retouche.

**Pipeline VNStudio**
`Image Source` → `Gaussian Filter` (doux) → branche A
`Image Source` → `Gaussian Filter` (plus large) → branche B
`Difference` (A − B) → `Colormap` → `Output Display`

La différence de deux flous garde uniquement les détails situés entre les deux échelles. Réglez les deux flous du plus serré au plus large.

---

**Questions**

1. Avec deux flous très doux, quels détails ressortent : le grain de peau, les rides ou le contour du visage ? Élargissez les deux flous : quelle échelle s'allume maintenant ?

2. Quand le résultat ne garde qu'une bande d'échelle, le fond uniforme devient gris neutre. Vérifiez-le. Pourquoi ce type de filtre « oublie » les grandes plages unies et ne réagit qu'aux transitions d'une certaine finesse ?

3. Trouvez le réglage qui fait ressortir le mieux les rides sans le grain de peau ni le contour. Quelle paire de flous y arrive ? Notez-la comme « filtre à rides ».

4. **Défi.** Appliquez le même filtre à une photo de tissu à carreaux. Trouvez le réglage qui fait disparaître complètement le quadrillage. Que se passe-t-il aux croisements des lignes, là où deux bords se rencontrent ?

---

## Exercice 2 · Lisser une surface sans baver sur les bords

![Photographie d'une porte en bois peinte : surface lisse à légère texture de peinture, bord net entre la porte et le mur blanc, une fine fissure et un nœud de bois sombre sur le panneau](../figures/ex_ch5_porte.jpg)

**Ce que vous voyez.** Une surface à lisser (la texture de peinture) avec des détails à sauver absolument (la fissure, le bord porte/mur). La mission : nettoyer le bruit sans noyer les contours.

**Pipeline VNStudio**
`Image Source` → `Split Half` :
— gauche : `Gaussian Filter`
— droite : `Bilateral Filter` *(à créer)*
→ `Output Display`

L'affichage côte à côte compare un flou ordinaire et un flou qui « respecte les bords ».

---

**Questions**

1. Sur le bord porte/mur, comparez les deux moitiés. Laquelle bave et crée un halo, laquelle garde le bord net tout en lissant la surface ?

2. Poussez le réglage « tolérance de couleur » du filtre bilatéral à fond. Que devient-il ? Pourquoi finit-il par se comporter exactement comme le flou ordinaire ?

3. Élargissez la portée du flou bilatéral. La fine fissure survit-elle même quand vous lissez fort ? Jusqu'où pouvez-vous aller avant qu'elle s'efface ?

4. **Défi.** Réglez le bilatéral pour effacer entièrement la texture de peinture tout en gardant nets la fissure, le nœud et le bord. Existe-t-il un réglage parfait, ou faut-il sacrifier un peu de l'un pour gagner sur l'autre ? Décrivez le compromis.

---

## Exercice 3 · Détecter l'orientation des fils d'un tissu

![Morceau de tissu écossais : bandes de couleur formant un quadrillage, avec des fils à dominante horizontale, verticale, et d'autres à 45°](../figures/ex_ch5_tissu_ecossais.jpg)

**Ce que vous voyez.** Une texture dont les orientations dominantes sautent aux yeux. La mission : un filtre qui ne réagit qu'à une direction et une finesse données, pour cartographier les fils.

**Pipeline VNStudio**
`Image Source` → `Gabor Filter` *(à créer)* (4 orientations) → `Grid Compare` → `Output Display`

Chaque filtre ne s'allume que pour les fils qui suivent son orientation. La grille compare les quatre réponses.

---

**Questions**

1. Parmi les quatre cartes (horizontale, verticale, et deux diagonales), laquelle s'allume le plus fort ? Correspond-elle à la direction dominante que vous voyez dans le tissu ?

2. Sur une bande strictement verticale, comparez la réponse du filtre vertical et celle du filtre horizontal. L'un est-il quasi éteint pendant que l'autre brille ? Que dit cela sur la sélectivité du filtre ?

3. Réglez la finesse du filtre (l'espacement auquel il réagit). À quel réglage les fils du tissu ressortent-ils le mieux ? Ce réglage correspond-il à l'espacement visible des fils ?

4. **Défi.** Servez-vous des quatre réponses pour fabriquer une « signature de texture » du tissu écossais. Comparez-la à celle d'un tissu uni. Les deux signatures sont-elles assez différentes pour qu'une machine distingue automatiquement les deux étoffes ?

---

*Corrigés disponibles en annexe.*
