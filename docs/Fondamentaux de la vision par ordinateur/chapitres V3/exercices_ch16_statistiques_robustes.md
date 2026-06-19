# Exercices — Chapitre 16 · Se méfier des données : les statistiques robustes

---

## Exercice 1 · Compter une température fiable malgré les capteurs chauds

![Image thermique d'un atelier en fausses couleurs : fond bleu-vert uniforme autour de 20 °C, trois moteurs en surchauffe apparaissant en rouge vif vers 80 °C, et une fenêtre froide en bleu sombre](../figures/ex_ch16_thermique.jpg)

**Ce que vous voyez.** Une scène où quelques pixels extrêmes (les moteurs chauds) risquent de fausser l'estimation de la température ambiante. La mission : estimer la température du fond sans se laisser tromper par les points chauds.

**Pipeline VNStudio**
`Image Source` → `Region Properties` → `Output Display`

Le nœud affiche dans l'inspecteur la moyenne, la médiane et l'écart absolu médian (MAD) de la zone sélectionnée.

---

**Questions**

1. Relevez la moyenne et la médiane de l'image entière. Laquelle annonce une température proche du fond réel (20 °C) ? De combien de degrés la moyenne s'éloigne-t-elle à cause des moteurs ?

2. Avec l'outil de sélection, masquez les trois moteurs chauds, puis relisez les deux valeurs. Laquelle a bougé, laquelle est restée stable ? Qu'est-ce que cela vous apprend sur la valeur à privilégier pour un capteur de surveillance ?

3. Comparez l'écart-type classique et le MAD affichés. Le premier est gonflé par les moteurs, le second non. Lequel utiliseriez-vous pour fixer un seuil d'alerte « température anormale » qui ne se déclenche pas en permanence ?

4. **Défi.** Ajoutez de plus en plus de points chauds (peignez des zones rouges dans l'image source). À partir de quelle proportion de pixels chauds la médiane se met-elle enfin à grimper ? Vérifiez qu'elle tient bon presque jusqu'à ce que la moitié de l'image soit chaude.

---

## Exercice 2 · Retrouver la ligne d'horizon dans une scène encombrée

![Photographie d'un bord de mer : l'horizon sépare nettement ciel et mer, mais la scène contient aussi un voilier, un parasol incliné et un ponton en biais qui dessinent de fausses lignes](../figures/ex_ch16_horizon.jpg)

**Ce que vous voyez.** Une ligne dominante (l'horizon) noyée parmi des éléments qui ne la respectent pas. La mission : faire trouver l'horizon automatiquement malgré ces intrus.

**Pipeline VNStudio**
`Image Source` → `Canny Edge Detector` → `RANSAC Line Fit` → `Draw Overlay` → `Output Display`

Le nœud RANSAC trace la droite consensus et affiche le nombre de points qui la soutiennent (inliers).

---

**Questions**

1. Lancez le pipeline. La droite tracée suit-elle bien l'horizon, ou se laisse-t-elle attirer par le ponton et le voilier ? Notez le nombre d'inliers affiché.

2. Remplacez RANSAC par un simple ajustement de droite sur tous les points de contour (option « moindres carrés » du nœud). La droite penche-t-elle maintenant vers les intrus ? Comparez les deux tracés superposés.

3. Augmentez le seuil de tolérance de RANSAC (la distance en pixels pour qu'un point compte comme inlier). À partir de quelle valeur le ponton commence-t-il à être avalé dans le consensus et à fausser l'horizon ?

4. **Défi.** Couvrez la moitié de l'image de fausses lignes (ajoutez des objets inclinés). RANSAC retrouve-t-il toujours l'horizon ? Augmentez le nombre d'itérations du nœud et observez à partir de combien de tirages le résultat redevient stable d'un lancement à l'autre.

---

## Exercice 3 · Calibrer un capteur de distance avec des mesures parasites

![Nuage de points d'une calibration de télémètre : distance mesurée en fonction de la distance réelle, une belle tendance droite, sauf quatre points très au-dessus (réflexions parasites sur un obstacle)](../figures/ex_ch16_calibration_capteur.jpg)

**Ce que vous voyez.** Des mesures fiables pour la plupart, avec quatre relevés aberrants dus à des réflexions. La mission : trouver la vraie droite de calibration sans que ces quatre points la tordent.

**Pipeline VNStudio**
`CSV Reader` (mesures) → `Robust Line Fit` → `Scatter Plot` → `Output Display`

Le nœud propose trois modes d'ajustement : ordinaire (L2), Huber (résistant), médian (très résistant). Il affiche la pente trouvée et superpose la droite au nuage.

---

**Questions**

1. Ajustez en mode ordinaire. La droite passe-t-elle au milieu des bons points, ou est-elle tirée vers le haut par les quatre parasites ? Notez la pente.

2. Basculez en mode Huber, puis médian. La droite revient-elle se poser sur la tendance correcte ? Comparez les trois pentes : laquelle colle le mieux à la grappe des bonnes mesures ?

3. Réglez le curseur de tolérance du mode Huber du plus serré au plus large. Trouvez la plage où la droite ignore les quatre parasites tout en suivant fidèlement les bons points. Que se passe-t-il si vous serrez trop ?

4. **Défi.** Ajoutez quelques parasites supplémentaires dans le CSV. Jusqu'à combien de mesures erronées le mode médian tient-il avant de basculer ? Comparez avec le mode ordinaire, qui décroche dès le premier parasite. Pour un capteur embarqué, quel mode choisiriez-vous ?

---

*Corrigés disponibles en annexe.*
