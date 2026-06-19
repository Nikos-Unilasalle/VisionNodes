# Exercices — Chapitre 17 · Retrouver un point : descripteurs locaux et appariement

---

## Exercice 1 · Décrire une silhouette par ses orientations

![Photographie d'un piéton de face sur un trottoir : silhouette bien contrastée sur des façades grises. Bords verticaux du corps, horizontaux des épaules, diagonaux des bras](../figures/ex_ch17_pieton.jpg)

**Ce que vous voyez.** Une silhouette humaine dont la « rose des vents » des contours est très caractéristique. La mission : en tirer une signature de forme stable, à la base de la détection de piétons.

**Pipeline VNStudio**
`Image Source` → `HOG Features` → `Draw Overlay` → `Output Display`

Le nœud découpe l'image en cellules et dessine dans chacune les orientations de contour dominantes.

---

**Questions**

1. Sur la visualisation, où les traits d'orientation sont-ils les plus marqués : sur les bords du corps, la peau, ou le fond ? Pointent-ils en travers des contours, comme attendu ?

2. Sur une cellule posée sur une épaule, quelle orientation domine ? Correspond-elle à la ligne de l'épaule que vous voyez ?

3. Faites pivoter le piéton de 10°. La signature change-t-elle beaucoup, ou tient-elle bon ? La détection survit-elle à un sujet légèrement penché ?

4. **Défi.** Comparez la signature d'un piéton et celle d'un cycliste. Sont-elles plus proches entre elles qu'entre deux piétons différents ? Si les deux se confondent, quel trait de silhouette partagent-ils, et que faudrait-il ajouter pour les distinguer ?

---

## Exercice 2 · Apparier deux vues d'un livre en rejetant les erreurs

![Deux photos du même livre : de face à gauche, légèrement en angle et plus éclairée à droite. Des points d'intérêt cyan sur les deux, reliés par des lignes vertes (bons appariements) et rouges (mauvais)](../figures/ex_ch17_livre_appariement.jpg)

**Ce que vous voyez.** Deux vues du même objet avec un léger changement d'angle et de lumière. Certains appariements sont justes, d'autres faux. La mission : ne garder que les bons, étape clé pour la reconnaissance d'objet et les panoramas.

**Pipeline VNStudio**
`Image Source (gauche)` + `Image Source (droite)` → `ORB Detector` → `Feature Matcher` → `Output Display`

Le détecteur trouve des points caractéristiques ; le matcher les relie et applique un test pour rejeter les appariements ambigus.

---

**Questions**

1. Comptez les appariements verts (gardés) et rouges (rejetés). Quelle part le test rejette-t-il ? Serrez le test : combien d'appariements restent, et paraissent-ils plus sûrs à l'œil ?

2. Comparez un coin net du livre et une zone de texture répétitive (la trame du papier). Pour lequel l'appariement est-il franc et sans hésitation ? Pourquoi une zone qui se répète crée-t-elle des appariements ambigus ?

3. Montez le nombre de points détectés. Le nombre de bons appariements grimpe-t-il autant, ou les nouveaux points sont-ils surtout du bruit ? Le rapport bons/total s'améliore-t-il ?

4. **Défi.** Éclaircissez fortement l'image de droite. Les appariements tiennent-ils malgré ce changement de lumière ? Comparez avec un descripteur SIFT *(à créer)*. Lequel résiste le mieux, et lequel choisiriez-vous pour des photos prises à des heures différentes ?

---

## Exercice 3 · Imposer une cohérence géométrique pour redresser une affiche

![Deux vues d'une affiche : de face et à 30° de côté. Avant nettoyage, quelques appariements faux traînent un peu partout ; après, seuls restent ceux qui s'accordent avec un même mouvement de plan](../figures/ex_ch17_affiche_ransac.jpg)

**Ce que vous voyez.** Des appariements bruts encore truffés d'erreurs. La mission : ne garder que ceux qui racontent tous le même mouvement, puis s'en servir pour remettre l'affiche de face.

**Pipeline VNStudio**
`Image Source (gauche)` + `Image Source (droite)` → `ORB Detector` → `Feature Matcher` → `RANSAC Homography` → `Draw Overlay` → `Output Display`

RANSAC cherche la transformation que soutient le plus grand nombre d'appariements et écarte les autres comme intrus.

---

**Questions**

1. Notez le nombre d'appariements avant RANSAC, puis le nombre d'inliers gardés après. Quelle proportion d'intrus le test simple avait-il laissé passer ?

2. Sur l'image, les inliers gardés relient-ils des points qui se correspondent vraiment ? Les lignes sont-elles maintenant toutes cohérentes, ou en reste-t-il une de travers ?

3. Resserrez la tolérance de RANSAC, puis élargissez-la. Combien d'inliers dans chaque cas ? Décrivez le compromis : trop serré on perd de bons points, trop large on laisse entrer des intrus.

4. **Défi.** Servez-vous de la transformation trouvée pour redresser la vue oblique de l'affiche. Le résultat est-il bien rectangulaire ? Si les coins restent un peu déformés, d'où vient le défaut : objectif non corrigé, surface non plane, ou trop peu d'inliers ?

---

*Corrigés disponibles en annexe.*
