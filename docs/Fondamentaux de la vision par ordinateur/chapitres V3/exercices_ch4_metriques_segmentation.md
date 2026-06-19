# Exercices — Chapitre 4 · Noter un découpage : métriques de segmentation et détection

---

## Exercice 1 · Noter un masque de poumon contre l'avis de l'expert

![Radiographie thoracique en niveaux de gris avec deux contours superposés : en vert, le contour tracé à la main par un radiologue (référence) ; en rouge, le masque produit par un algorithme. Les deux s'accordent sur le centre du poumon, divergent aux bords fins](../figures/ex_ch4_radio_poumon.jpg)

**Ce que vous voyez.** Un masque automatique et un masque expert sur le même organe. La mission : leur attribuer une note de recouvrement et comprendre ce que cette note récompense ou pardonne.

**Pipeline VNStudio**
`Image Source` → `Threshold (Advanced)` (masque auto) → `Mask Overlap` → `Output Display`

Chargez le masque expert comme seconde entrée. Le nœud affiche le score de recouvrement (IoU et Dice) et colorie la zone de désaccord.

---

**Questions**

1. Lisez les deux scores affichés. Lequel est le plus élevé pour ce même masque ? Repérez sur l'image la bande colorée de désaccord, sur le centre ou sur les bords ?

2. Rétrécissez le masque automatique (érodez-le de quelques pixels). Les deux scores baissent ; lequel chute le plus vite ? Pour noter un petit organe, lequel est le plus « indulgent » ?

3. Trouvez la zone où les deux masques divergent le plus. Plus cette zone est large, plus le score baisse : pourquoi le désaccord pèse-t-il deux fois (compté à la fois comme manque et comme excès) ?

4. **Défi.** Réglez le seuillage pour que le masque automatique tienne entièrement à l'intérieur du contour expert (aucun débordement). Le score atteint-il 100 % ? Sinon, qu'est-ce qui l'en empêche, et que faut-il pour le maximiser ?

---

## Exercice 2 · Régler un détecteur d'empreintes entre prudence et excès de zèle

![Scène de relevé d'empreintes : surface granuleuse avec plusieurs empreintes, certaines nettes, d'autres partielles. Des boîtes vertes (bonnes détections), rouges (fausses alarmes) et des empreintes ratées surlignées en orange](../figures/ex_ch4_empreintes.jpg)

**Ce que vous voyez.** Un détecteur qui trouve presque toutes les empreintes mais en invente quelques-unes sur le fond texturé. La mission : trouver le bon seuil de confiance selon l'enjeu.

**Pipeline VNStudio**
`Image Source` → `Print Detector` → `Detection Score` → `Output Display`

Le nœud affiche, pour le seuil de confiance choisi, le nombre de bonnes détections, de fausses alarmes et d'empreintes ratées, ainsi que la précision et le rappel.

---

**Questions**

1. Réglez le seuil très bas (0,1). Le détecteur attrape-t-il toutes les empreintes ? Combien de fausses alarmes invente-t-il en échange ?

2. Montez le seuil jusqu'à 0,9. Les fausses alarmes disparaissent-elles ? Combien de vraies empreintes perdez-vous au passage ? Décrivez le compromis que vous voyez basculer.

3. Trouvez le seuil qui efface toutes les fausses alarmes. À ce réglage, combien d'empreintes manquent encore ? Et le seuil qui n'en rate aucune : combien de fausses alarmes laisse-t-il ?

4. **Défi.** Dans une enquête, rater une empreinte coûte plus cher qu'une fausse alarme à vérifier. Quel seuil privilégier ? Justifiez votre choix avec les chiffres relevés, puis trouvez celui de l'enquête inverse (où chaque vérification est coûteuse).

---

## Exercice 3 · Départager deux découpages de parcelles agricoles

![Image satellitaire de parcelles agricoles délimitées de deux façons : version A aux contours fins et précis, version B aux contours épais et un peu décalés. Les deux couvrent les mêmes parcelles, mais le tracé des bords diffère](../figures/ex_ch4_parcelles.jpg)

**Ce que vous voyez.** Deux découpages qui reconnaissent les mêmes parcelles, mais tracent leurs bords avec un soin différent. La mission : trouver la note qui sait voir cette différence de qualité de bord.

**Pipeline VNStudio**
`Image Source` → `Boundary Score` → `Output Display`

Le nœud compare deux segmentations à une référence et affiche, au choix, le recouvrement global (IoU) ou la note de bord (qualité du tracé des frontières).

---

**Questions**

1. Notez A et B avec le recouvrement global. La note distingue-t-elle clairement les deux versions, ou les juge-t-elle presque équivalentes ?

2. Passez à la note de bord. Cette fois, l'écart entre A et B se creuse-t-il ? Laquelle des deux versions est récompensée pour ses contours fins ?

3. Élargissez la tolérance de la note de bord (le rayon où un bord prédit compte comme « bien placé »). À partir de quelle tolérance les deux versions redeviennent-elles équivalentes ? Pour une cartographie fine, faut-il une tolérance serrée ou large ?

4. **Défi.** Épaississez volontairement les bords de la version A. Sa note de recouvrement bouge-t-elle ? Sa note de bord se dégrade-t-elle ? Expliquez pourquoi un cadastre de précision doit être évalué sur les bords, pas seulement sur le recouvrement des surfaces.

---

*Corrigés disponibles en annexe.*
