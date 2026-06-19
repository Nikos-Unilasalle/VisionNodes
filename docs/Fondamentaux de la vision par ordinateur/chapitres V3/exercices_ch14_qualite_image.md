# Exercices — Chapitre 14 · Bonne image, pour qui ? la mesure de qualité

---

## Exercice 1 · Deux dégradations, un même score chiffré, une perception opposée

![Trois versions d'un portrait : (A) original net, (B) version grenue couverte de bruit, (C) version douce et floue. À l'œil, B reste lisible (les contours tiennent), C perd les détails fins](../figures/ex_ch14_portrait_compare.jpg)

**Ce que vous voyez.** Deux façons d'abîmer une image qui paraissent très différentes à l'œil. La mission : constater qu'une note « pixel à pixel » peut les déclarer équivalentes, et qu'une note « de structure » les départage.

**Pipeline VNStudio**
`Image Source (A)` + `Image Source (B ou C)` → `SSIM / PSNR` *(à créer)* → `Output Display`

Le nœud affiche deux notes : le PSNR (écart pixel à pixel) et le SSIM (ressemblance de structure), plus une carte qui montre où la structure se dégrade.

---

**Questions**

1. Réglez le bruit de B et le flou de C jusqu'à ce que leur PSNR soit identique. À PSNR égal, les deux images vous semblent-elles vraiment de même qualité ?

2. Lisez maintenant leur SSIM. Lequel est le plus élevé ? La structure (visage, contours) tient-elle mieux sous le bruit ou sous le flou ?

3. Sur la carte de structure de l'image floue, quelles zones s'effondrent le plus : le fond uni ou les cheveux et la peau ? Pourquoi le flou frappe-t-il d'abord les détails fins ?

4. **Défi.** Remplacez le bruit de B par quelques pixels « grillés » épars (sel et poivre). Pour un même PSNR, le SSIM juge-t-il cette dégradation pire ou plus douce que le flou ? Quelle note correspond le mieux à votre propre jugement visuel ?

---

## Exercice 2 · Classer une rafale de photos de la plus floue à la plus nette

![Série de 6 photos d'un même paysage à mise au point croissante : la 1 très floue, jusqu'à la 6 parfaitement nette](../figures/ex_ch14_serie_nettet.jpg)

**Ce que vous voyez.** Une rafale de netteté croissante. La mission : faire trier ces images automatiquement, sans image de référence — exactement ce que fait l'autofocus d'un appareil.

**Pipeline VNStudio**
`Image Source` → `Focus Metric` → `Output Display`

Le nœud attribue à chaque image un score de netteté, d'autant plus élevé que les détails fins sont présents.

---

**Questions**

1. Mesurez le score de netteté des 6 photos. Le classement par score correspond-il à l'ordre visuel du plus flou au plus net ? Y a-t-il une inversion ?

2. Le nœud propose plusieurs façons de mesurer la netteté. Essayez-en deux et comparez les classements obtenus. Tombent-ils d'accord, ou une photo change-t-elle de rang ?

3. Sur la photo la plus nette, mesurez le score sur trois zones : le feuillage texturé, le ciel uni, l'herbe. Où le score est-il le plus haut ? Qu'est-ce que cela implique si une scène est en partie vide de détails ?

4. **Défi.** Servez-vous du score pour bâtir un autofocus : parmi la rafale, lequel choisiriez-vous comme « meilleure prise » ? Floutez ensuite légèrement la gagnante et vérifiez que son score retombe sous celui de la vraie meilleure. Le critère est-il fiable pour décider tout seul ?

---

## Exercice 3 · Reconnaître la signature de deux bruits de capteur

![Trois images de la même scène (objet sur fond uni) : (A) propre, (B) bruit de capteur qui enfle dans les zones claires, (C) bruit uniforme partout, sombre comme clair](../figures/ex_ch14_bruit_compare.jpg)

**Ce que vous voyez.** Deux bruits d'origine physique différente. La mission : reconnaître lequel est lequel rien qu'en observant comment le bruit se répartit selon la luminosité, pour choisir le bon débruitage.

**Pipeline VNStudio**
`Image Source` → `Noise Profile` → `Output Display`

Le nœud mesure l'intensité du bruit séparément dans les zones sombres et claires, et la trace en fonction de la luminosité.

---

**Questions**

1. Sur l'image B, le bruit est-il plus fort dans les zones claires ou sombres ? Sur l'image C, varie-t-il avec la luminosité, ou reste-t-il constant partout ?

2. À partir de ces profils, attribuez à chaque image son type de bruit : celui qui « grandit avec la lumière » (capteur) et celui qui « est partout pareil » (amplificateur). Qu'est-ce qui les trahit ?

3. Appliquez un filtre médian à chaque image bruitée. Sur laquelle le résultat est-il le plus propre ? Pourquoi le médian excelle-t-il contre les pixels isolés qui sautent dans les zones sombres ?

4. **Défi.** Choisissez le débruitage adapté à chaque bruit (médian pour les pixels isolés, lissage doux pour le bruit uniforme). Comparez le résultat à un débruitage unique appliqué aux deux. Connaître la signature du bruit améliore-t-il vraiment le nettoyage ?

---

*Corrigés disponibles en annexe.*
