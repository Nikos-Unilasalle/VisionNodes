# Exercices — Chapitre 1 · Décrire une forme avec des nombres

---

## Exercice 1 · Trier des cellules par la forme de leur contour

![Vue en microscopie optique de cellules sanguines : au centre, quelques globules rouges bien ronds et lisses ; sur les bords, des neutrophiles au noyau lobé et découpé comme une feuille de chêne](../figures/ex_ch1_cellules_sang.jpg)

**Ce que vous voyez.** Deux familles de cellules côte à côte. Les globules rouges sont des disques réguliers. Les neutrophiles ont un contour très découpé, mais leur silhouette globale reste compacte. La mission : les séparer automatiquement par la forme.

**Pipeline VNStudio**
`Image File` → `Threshold` → `Find Contours` → `Region Properties` → `Display`

Réglez `Retrieval Mode` sur `RETR_EXTERNAL` et `Contour Approximation` sur `CHAIN_APPROX_SIMPLE`. L'inspecteur affiche pour chaque cellule sa circularité et sa rondeur.

---

**Questions**

1. Cliquez sur un globule rouge, puis sur un neutrophile, et relevez leur circularité et leur rondeur. Pour quelle famille les deux nombres sont-ils proches ? Pour laquelle s'écartent-ils nettement ?

2. La rondeur du neutrophile reste haute alors que sa circularité s'effondre. Lequel des deux descripteurs « voit » le contour découpé, lequel ne regarde que la silhouette d'ensemble ?

3. Poussez le curseur `Simplification (Epsilon)` jusqu'à 15 pixels sur un neutrophile. Sa circularité remonte-t-elle ? Sa rondeur bouge-t-elle ? Pourquoi lisser le contour réveille l'un et laisse l'autre indifférent ?

4. **Défi.** Branchez un `Filter Contours` sur la circularité. Trouvez le seuil qui ne laisse passer que les globules rouges. Combien en comptez-vous ? Existe-t-il une cellule à la frontière que le seuil classe mal ?

---

## Exercice 2 · Détecter les graines abîmées sur une chaîne de tri

![Graines de haricots vues de dessus sur fond blanc : certaines entières et bien bombées, d'autres écrasées et creusées d'un sillon profond, et deux ou trois collées par paires en forme de huit](../figures/ex_ch1_haricots.jpg)

**Ce que vous voyez.** Trois populations dans le même bac : graines saines, graines fendues, paires collées. Une chaîne de tri doit les séparer toute seule.

**Pipeline VNStudio**
`Image File` → `Threshold` → `Find Contours` → `Contour Properties` → `Region Properties` → `Display`

Activez l'overlay de l'enveloppe convexe pour la voir se dessiner par-dessus chaque graine.

---

**Questions**

1. Relevez la solidité et la convexité d'une graine de chaque population. Pour quelle population la solidité chute-t-elle le plus ? Pour laquelle la convexité chute-t-elle ?

2. La graine fendue a un sillon profond mais un contour extérieur assez lisse. Lequel des deux descripteurs trahit le sillon ? Regardez l'enveloppe convexe pour comprendre où se cache l'écart.

3. La paire collée garde une convexité élevée malgré la fusion. En observant comment l'enveloppe enveloppe les deux lobes, expliquez pourquoi le bord reste « lisse » alors que la surface, elle, a un creux.

4. **Défi.** Réglez les filtres pour que la chaîne accepte les graines saines et rejette les deux autres populations, en un seul passage. Quelle combinaison de seuils (solidité, convexité) y arrive ? Reste-t-il un cas ambigu que le tri laisse passer à tort ?

---

## Exercice 3 · Reconnaître une pièce quelle que soit son orientation

![Composants électroniques sur un tapis de contrôle : des résistances cylindriques couchées à l'horizontale, des condensateurs debout à la verticale, et quelques pièces tombées en diagonale à 45°](../figures/ex_ch1_composants.jpg)

**Ce que vous voyez.** Les mêmes pièces, mêmes dimensions, mais orientées différemment selon leur chute sur le tapis. Le système de tri doit reconnaître les résistances quelle que soit leur inclinaison.

**Pipeline VNStudio**
`Image File` → `Threshold` → `Find Contours` → `Oriented Bounding Box` → `Region Properties` → `Region Properties` → `Display`

Activez les overlays de la boîte droite (bleue) et de la boîte orientée (orange).

---

**Questions**

1. Relevez l'étendue et la rectangularité d'une résistance à 0°, 45° et 90°. Lequel des deux nombres s'effondre quand la pièce tourne ? Lequel reste stable ?

2. L'étendue chute fortement à 45°. Regardez la boîte bleue dans l'overlay : qu'est-ce qui enfle autour de la pièce quand elle bascule en diagonale ?

3. La rectangularité, elle, ne bronche pas. Quelle propriété de la boîte orange (qui pivote avec la pièce) garantit cette stabilité ?

4. **Défi.** Une résistance allongée et une petite vis cylindrique ont la même rectangularité élevée. La rectangularité seule ne suffit donc pas à les distinguer. Ajoutez l'élongation au tri et trouvez le seuil qui sépare les deux pièces. Combien de résistances comptez-vous sur le tapis ?

---

*Corrigés disponibles en annexe.*
