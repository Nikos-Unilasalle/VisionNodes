# Exercices — Chapitre 15 · Apprentissage profond : les fonctions de coût

---

## Exercice 1 · Détecter des objets rares sans noyer la cible dans le fond

![Vue aérienne d'un parking quasi vide : des dizaines de places de stationnement vides (le fond, omniprésent) et seulement deux voitures garées (la cible rare à trouver)](../figures/ex_ch15_parking.jpg)

**Ce que vous voyez.** Une scène où la cible (les voitures) est écrasée sous une masse de fond identique. C'est le déséquilibre que la focal loss corrige à l'entraînement : ici on observe ses conséquences sur un détecteur déjà entraîné.

**Pipeline VNStudio**
`Image Source` → `Object Detection (YOLO)` → `Draw Overlay` → `Output Display`

Le nœud affiche les boîtes détectées avec leur score de confiance.

---

**Questions**

1. Lancez la détection avec un seuil de confiance bas (0,1). Combien de boîtes apparaissent ? Combien sont de vraies voitures, combien sont des fausses alarmes posées sur des places vides ?

2. Montez le seuil progressivement. À quelle valeur les fausses alarmes disparaissent-elles ? Reste-t-il les deux vraies voitures, ou en perdez-vous une au passage ?

3. Un détecteur mal entraîné, écrasé par la masse du fond, devient « paresseux » et rate les objets rares. Sur cette image, le vôtre privilégie-t-il plutôt la prudence (rate des voitures) ou l'excès de zèle (invente des voitures) ? Que faudrait-il rééquilibrer ?

4. **Défi.** Trouvez une scène encore plus déséquilibrée (un seul objet minuscule dans une grande image uniforme) et comptez les fausses détections à seuil bas. Comparez avec une scène équilibrée (autant d'objets que de fond). Sur laquelle le détecteur se trompe-t-il le plus, et pourquoi ?

---

## Exercice 2 · Mesurer la qualité d'une segmentation par le recouvrement

![Vue microscopique d'une cellule : à gauche le contour tracé à la main par un biologiste (vérité terrain), à droite le masque produit par un segmenteur automatique, qui déborde un peu sur les bords](../figures/ex_ch15_segmentation_overlap.jpg)

**Ce que vous voyez.** Deux masques de la même cellule. La mission : mesurer leur recouvrement, car c'est exactement ce que la Dice loss optimise pendant l'entraînement.

**Pipeline VNStudio**
`Image Source` → `SAM Segmenter` → `Mask Overlap` → `Output Display`

Le nœud `Mask Overlap` compare le masque automatique au masque de référence et affiche le score de recouvrement (IoU et Dice).

---

**Questions**

1. Segmentez la cellule, puis lisez le score de recouvrement. Le masque automatique colle-t-il bien à la référence, ou déborde-t-il ? Repérez visuellement où ils divergent.

2. Décalez volontairement le masque automatique (déplacez le point de clic SAM). Le score chute-t-il vite ou lentement ? À quel décalage les deux masques ne se touchent plus du tout (recouvrement nul) ?

3. Quand les deux masques ne se chevauchent plus, le score reste bloqué à zéro et ne dit plus dans quelle direction corriger. Pourquoi est-ce un problème quand on démarre un entraînement avec un masque encore très loin de la cible ?

4. **Défi.** Segmentez un amas de plusieurs cellules collées d'un seul clic. Le masque englobe-t-il tout l'amas ou une seule cellule ? Réglez SAM (points positifs et négatifs) pour isoler une seule cellule et faire remonter le score de recouvrement avec son contour de référence.

---

## Exercice 3 · Ajuster une boîte englobante malgré des points parasites

![Photo d'un panneau routier rectangulaire détecté : la majorité des points de contour dessinent bien le rectangle, mais quelques points parasites traînent sur un autocollant collé à côté](../figures/ex_ch15_bbox_fit.jpg)

**Ce que vous voyez.** Une boîte à ajuster autour d'un objet, perturbée par quelques points parasites. C'est le rôle de la Smooth L1 (Huber) en détection : suivre les bons points sans se laisser tirer par les rares aberrants.

**Pipeline VNStudio**
`Image Source` → `Find Contours` → `Robust Box Fit` → `Draw Overlay` → `Output Display`

Le nœud ajuste la boîte avec un mode ordinaire (sensible aux parasites) ou robuste (Huber).

---

**Questions**

1. Ajustez la boîte en mode ordinaire. Englobe-t-elle juste le panneau, ou s'étire-t-elle pour avaler l'autocollant ? Mesurez de combien elle déborde.

2. Passez en mode robuste. La boîte se resserre-t-elle sur le panneau seul ? Comparez les deux résultats superposés.

3. Réglez le curseur de tolérance du mode robuste. Trouvez la plage où la boîte ignore l'autocollant tout en épousant les quatre coins du panneau. Que se passe-t-il aux réglages extrêmes (trop serré, trop large) ?

4. **Défi.** Ajoutez plusieurs autocollants autour du panneau. Le mode robuste tient-il toujours ? Jusqu'à quelle quantité de points parasites la boîte reste-t-elle correcte avant de décrocher ? Pour un système qui annote des milliers d'images sans supervision, quel mode est le plus sûr ?

---

*Corrigés disponibles en annexe.*
