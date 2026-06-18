# Chapitre 2 — Peser une forme : les moments d'image

![Une plaque de carton découpée en forme d'animal, en équilibre sur la pointe d'un crayon, pendant qu'un personnage note des chiffres](../figures/fig_ch2_couverture.jpg)
*Découpez la silhouette dans du carton et toute la mécanique du solide s'applique : où elle tient en équilibre, autour de quel axe elle tourne le plus facilement. Les moments d'image ne mesurent rien d'autre.*

---

Au chapitre précédent, plusieurs descripteurs reposaient sur des notions laissées en suspens. L'excentricité s'appuyait sur les demi-axes d'une « ellipse équivalente » dont on n'avait pas dit d'où elle venait, et l'on promettait des invariants capables de reconnaître une forme quelle que soit sa pose. Tout cela sort d'un même outil : les **moments d'image**. Un moment transforme une région de pixels en une poignée de nombres qui en résument la masse, la position, l'orientation et l'étalement — la fiche d'identité chiffrée de la silhouette.

L'image juste vient de la mécanique. Découpez le masque de l'objet dans une plaque de carton d'épaisseur uniforme : les moments décrivent alors exactement les propriétés physiques de cette plaque, sa masse, son point d'équilibre, l'axe autour duquel elle tourne le plus facilement. Ce n'est pas une analogie vague mais une correspondance exacte, et le chapitre s'en sert d'un bout à l'autre pour donner un sens concret à des formules qui, écrites brutes, paraissent abstraites.

Le fil du chapitre tient en une phrase : **plus l'ordre d'un moment est élevé, plus il regarde loin du centre, et plus il amplifie le bruit**. Le mot « ordre » sera défini en 2.1 ; retenez pour l'instant qu'il classe les moments du plus simple au plus détaillé. L'aire (ordre 0) est très robuste ; le centre de gravité (ordre 1) l'est presque autant ; l'orientation (ordre 2) devient fragile pour les formes rondes ; les invariants de Hu (ordre 3) peuvent varier de moitié pour deux pixels de bruit sur le contour. Chaque section éclaire un étage de cette échelle de fragilité.

### Un peu de vocabulaire avant de commencer

*   **Pixel et coordonnées** : On note `I(x, y)` l'intensité du pixel situé à la colonne `x` et la ligne `y`.
*   **Moments binaires** : Les moments calculés sur un **masque binaire** (où `I(x, y)` vaut 1 pour l'objet et 0 pour le fond).
*   **Moments pondérés** : Les moments calculés sur des images en niveaux de gris, où chaque pixel pèse selon sa clarté réelle.

---

## 2.1 — Moments bruts : poser des questions à la forme

> *Peser chaque pixel selon l'endroit où il se trouve*

### L'intention

On voudrait interroger une silhouette avec des questions de plus en plus précises : combien de matière ? où est-elle ? comment est-elle étalée ? Idéalement, un seul mécanisme répondrait à toutes ces questions, en changeant juste un réglage.

### La forme recherchée

Le mécanisme est une somme sur tous les pixels de l'objet — mais une somme où chaque pixel ne compte pas pareil : il est pesé par sa position, élevée à une certaine puissance. Élever à une puissance veut simplement dire multiplier un nombre par lui-même un certain nombre de fois (la position au carré, c'est la position multipliée par elle-même). En tournant le bouton de ces puissances, on change la question posée.

Régler les deux puissances à zéro ne pèse rien — n'importe quel nombre élevé à la puissance zéro vaut 1 — : on compte alors simplement les pixels. Les régler à 1 pèse chaque pixel par sa position : on apprend où se trouve la masse. Les régler à 2 pèse par la position au carré, ce qui donne énormément de poids aux pixels lointains : on apprend comment la masse s'étale autour du centre. C'est exactement la hiérarchie des grandeurs de la mécanique du solide, terme à terme.

### La formule

```
M_pq = Σ_x Σ_y x^p · y^q · I(x,y)
```

Le grand Σ (sigma) est un symbole de sommation : il veut dire « additionne, pour tous les pixels ». Le couple (p, q) fixe la puissance appliquée à chaque coordonnée, et la somme p + q s'appelle l'**ordre** du moment — le « niveau de détail » annoncé en introduction. La correspondance mécanique se lit directement :

```
M₀₀ = masse totale          (= aire A pour un masque binaire)
M₁₀ = moment statique en x  (la masse, pondérée par où elle est)
M₀₁ = moment statique en y
M₂₀, M₀₂ = moments d'inertie par rapport aux axes
M₁₁ = produit d'inertie     (la masse penche-t-elle en diagonale ?)
```

Cette correspondance n'est pas décorative : les propriétés des sections suivantes — centre de gravité, axes principaux — ne sont pas des recettes de vision inventées pour l'occasion, mais des résultats de mécanique connus de longue date, transposés tels quels à une image. ∎

### Exemple chiffré — le masque jouet du chapitre

Tout le chapitre s'appuie sur un même masque 3 × 3, assez petit pour que chaque calcul tienne sur un coin de feuille :

```
y\x   0  1  2
0     0  1  1
1     1  1  1
2     1  1  0
```

Sept pixels, deux coins manquants en haut à gauche et en bas à droite : la forme penche le long de la diagonale qui va du coin haut-droit au coin bas-gauche.

Pour M₀₀, on compte : **M₀₀ = 7**. Pour M₁₀ = Σ x·I, le plus simple est de compter les pixels par colonne : la colonne x = 0 en a 2, la colonne x = 1 en a 3, la colonne x = 2 en a 2.

```
M₁₀ = 0·(2) + 1·(3) + 2·(2) = 7
M₀₁ = 7                              (mêmes comptes par ligne, par symétrie)
M₂₀ = Σ x² = 0·(2) + 1·(3) + 4·(2) = 11
M₀₂ = 11
M₁₁ = Σ x·y = (1·0)+(2·0)+(0·1)+(1·1)+(2·1)+(0·2)+(1·2) = 5
```

Ces six nombres — 7, 7, 7, 11, 11, 5 — suffiront pour tout le reste du chapitre.

### En image, l'axe y descend

En traitement d'image, l'axe y croît **vers le bas** : la ligne 0 est en haut. Les formules restent vraies, mais les angles d'orientation se retrouvent mesurés dans le sens horaire, à l'inverse du repère mathématique habituel. C'est la cause classique des orientations « à l'envers » : le calcul est juste, c'est le repère qui n'est pas celui auquel on pense.

### Paramètres opérationnels (VNStudio / Python)

Dans le nœud `Image Moments` (ou via `cv2.moments` en Python), le comportement de l'analyse dépend des réglages suivants :

*   **Moments binaires vs pondérés (`binaryImage`)** :
    *   Dans VNStudio, ce paramètre correspond à la case à cocher **Binary Mode** ; en Python (OpenCV), il se nomme `binaryImage` dans la fonction `cv2.moments`.
    *   Si le paramètre est réglé sur `True` (Binaire), toutes les valeurs de pixels non nulles sont traitées comme valant strictement 1. L'analyse ne mesure alors que la pure **géométrie de la silhouette** (sa forme géométrique pure).
    *   Si le paramètre est réglé sur `False` (Pondéré), chaque pixel pèse dans la sommation selon sa valeur de clarté réelle (0 à 255). Le centroïde calculé correspond alors au **centre de luminosité** de l'objet, qui se déplacera vers les zones les plus brillantes même si la silhouette extérieure reste identique.
*   **Ordre maximum des moments** :
    *   Configure le niveau de détail de la sommation. Les ordres 0 et 1 (masse et centre de gravité) sont insensibles au bruit. L'ordre 2 (inertie et orientation) est sensible au bruit sur les formes proches du disque parfait. L'ordre 3 (Hu moments) est très sensible aux petites variations de pixels sur les contours.

### Dans VNStudio

Dans votre canvas :
`Image Source` ──> `Threshold` ──> `Image Moments` ──> `Inspector`.

Le nœud `Image Moments` calcule en continu l'ensemble des moments bruts et centrés d'après les formules ci-dessus. Le nœud de conversion `Grayscale` placé en amont garantit que les images couleur sont correctement projetées sur un seul canal avant le calcul.

**Exercice de dépannage (échec contrôlé) :** L'exercice consiste à charger une image contenant deux disques blancs distincts et identiques sur fond noir. En connectant cette image au nœud `Image Moments`, le lecteur constate dans l'inspecteur que le centroïde calculé se positionne au milieu du vide séparant les deux disques, là où il n'y a aucun pixel d'objet. Cela illustre de façon flagrante comment l'hypothèse tacite d'une seule silhouette connexe fait échouer la localisation géométrique de l'objet réel dès que les composants se séparent dans l'image.

---

## 2.2 — Centroïde : le point d'équilibre

> *L'endroit où la plaque de carton tient sur une pointe*

### L'intention

On veut un point unique qui localise l'objet — pour le suivre d'une image à l'autre, l'aligner sur une autre acquisition, ou y planter un marqueur. Un point qui ne dépende que de la forme, pas du hasard d'un pixel.

### La forme recherchée

C'est le point d'équilibre de la silhouette : l'endroit où la plaque de carton tiendrait posée sur une pointe de crayon. Vu depuis ce point, la masse ne penche d'aucun côté, les contributions de gauche annulant celles de droite. C'est précisément la définition d'un **centre de gravité**, ici appelé **centroïde**.

### La formule

```
x̄ = M₁₀ / M₀₀ ,   ȳ = M₀₁ / M₀₀
```

La barre au-dessus de x̄ se lit « x barre » et désigne une moyenne. La formule dit cela exactement : la somme des positions (M₁₀) divisée par le nombre de pixels (M₀₀). Diviser une somme par un effectif, c'est faire une moyenne — le centroïde n'est rien d'autre que la position moyenne des pixels. Voir la forme `a/b`, annexe C : une mise en proportion qui efface l'effectif. ∎

### Exemple chiffré

Sur le masque jouet : x̄ = 7/7 = 1 et ȳ = 7/7 = 1. Le centroïde tombe sur le pixel central — cohérent avec la symétrie de la forme, dont les deux coins manquants se compensent.

Le centroïde est l'ancrage de presque toute analyse spatiale. En vidéo, suivre un objet revient souvent à suivre la suite de ses centroïdes. En astronomie, le centroïde d'une étoile sur le capteur localise la source avec une précision **inférieure au pixel** (le §2.8 expliquera pourquoi). En recalage d'images, aligner deux acquisitions commence souvent par superposer leurs barycentres.

### Subtilité — le centroïde peut tomber hors de l'objet

Le point d'équilibre d'une forme n'est pas forcément dans la forme. Pour un masque en U, en croissant, ou pour deux objets reliés par un isthme fin, le centroïde tombe dans le creux — comme le centre de gravité d'un anneau, situé au milieu du trou, là où il n'y a pas de matière. Tout algorithme qui plante un marqueur au centroïde gagne à le vérifier. C'est d'ailleurs pourquoi la transformée de distance (chapitre 10), qui trouve le point le plus *intérieur* de la forme, est souvent préférée pour poser une étiquette de pays sur une carte.

### Subtilité — (x, y) ou (ligne, colonne) ?

Les outils ne rangent pas les coordonnées dans le même ordre : les uns raisonnent en (x, y), d'autres en (ligne, colonne), c'est-à-dire (ȳ, x̄). Mélanger les deux conventions transpose silencieusement tous les résultats — un écart qui ne se voit que sur une forme non symétrique, donc rarement sur le cas de test.

### Dans VNStudio

Canvas : `Image Source` → `Threshold` → `Image Moments` → `Inspector`. L'inspecteur affiche les coordonnées du centroïde et le nœud le dessine en surimpression sur l'objet ; on voit immédiatement s'il tombe hors de la forme (cas du U ou du croissant).

---

## 2.3 — Moments centraux : décrire la forme depuis son propre centre

> *Mesurer les écarts au centroïde, pas au coin de l'image*

### L'intention

Les moments bruts mélangent deux choses : la forme de l'objet et l'endroit où il se trouve dans l'image. On veut ne garder que la forme, pour qu'un objet déplacé reste identique à lui-même.

### La forme recherchée

Il suffit de mesurer les coordonnées **depuis le centroïde** plutôt que depuis le coin de l'image — décrire l'objet « par rapport à son propre centre » au lieu de « par rapport au coin de la pièce ». La description cesse alors de dépendre de l'endroit où l'objet est posé. C'est la première des trois insensibilités que le chapitre construit pas à pas. Le terme technique est **invariance** : une mesure est invariante à une transformation quand cette transformation ne la change pas. Ici, invariance par **translation** (le déplacement) ; viendront ensuite l'échelle (le zoom, en 2.4) et la rotation (en 2.7).

### La formule

```
μ_pq = Σ_x Σ_y (x − x̄)^p · (y − ȳ)^q · I(x,y)
```

La lettre μ se lit « mu ». La seule différence avec les moments bruts est qu'on remplace la position x par l'écart au centroïde (x − x̄) : on mesure tout depuis le centre de l'objet. Déplacer la forme déplace son centroïde d'autant, si bien que cet écart ne change pas : les μ_pq sont donc aveugles à la position. En pratique, on ne reparcourt pas l'image — on déduit les μ_pq des moments bruts par quelques soustractions, par exemple à l'ordre 2 :

```
μ₂₀ = M₂₀ − x̄·M₁₀
μ₀₂ = M₀₂ − ȳ·M₀₁
μ₁₁ = M₁₁ − x̄·M₀₁
```

Inutile de retenir ces formules ; il suffit de savoir qu'elles existent, ce qui permet de tout calculer en un seul passage sur l'image. ∎

### Exemple chiffré (suite du masque jouet)

```
μ₂₀ = 11 − 1×7 = 4
μ₀₂ = 11 − 1×7 = 4
μ₁₁ = 5 − 1×7 = −2
```

Le signe de μ₁₁ se lit comme une tendance : négatif, il signifie que lorsque y augmente (on descend dans l'image), x tend à diminuer. La masse s'étire le long de la diagonale descendante vers la gauche — exactement ce que montre le dessin, avec ses coins manquants en haut-gauche et bas-droite.

### Les moments d'ordre 3 mesurent l'asymétrie

À l'ordre 2, les écarts au centroïde sont élevés au carré : un pixel à gauche et un pixel à droite contribuent pareil, car le carré efface le signe (un nombre négatif au carré devient positif). À l'ordre 3, le cube **conserve le signe** : les deux côtés ne se compensent plus, et le moment mesure de quel côté la masse penche.

```
μ₃₀ : asymétrie gauche/droite de la masse
μ₀₃ : asymétrie haut/bas
```

Un caractère manuscrit comme « e » ou « a » a une asymétrie marquée que μ₃₀ capture ; un « o » symétrique a μ₃₀ ≈ μ₀₃ ≈ 0. Ces moments d'ordre 3 sont la matière première des invariants de Hu (§2.7). Pour le fil du chapitre, retenez que le cube amplifie les pixels lointains bien plus que le carré : l'ordre 3 est plus expressif, et plus fragile.

### Dans VNStudio

Canvas : `Image Source` → `Threshold` → `Image Moments` → `Inspector`. Les moments centraux figurent dans la sortie du même nœud, à côté des moments bruts ; l'inspecteur les liste séparément.

---

## 2.4 — Moments normalisés : oublier la taille

> *Deux photos d'un même objet, l'une de près, l'autre de loin*

### L'intention

Un même logo, imprimé en petit sur une étiquette ou en grand sur une façade, devrait donner les mêmes nombres. Après la position (2.3), on veut maintenant être insensible à la **taille** : invariance d'échelle.

### La forme recherchée

On divise chaque moment par une puissance de l'aire. L'idée tient en une compensation : agrandir une forme gonfle son moment, mais gonfle aussi son aire. Avec la bonne puissance de l'aire au dénominateur, les deux gonflements s'annulent et le rapport ne bouge plus. Voir la forme `a/b`, annexe C — un rapport qui efface l'échelle. Tout l'enjeu est de trouver cette « bonne puissance ».

### La formule

```
η_pq = μ_pq / μ₀₀^γ ,   γ = (p + q)/2 + 1
```

La lettre η se lit « êta », γ se lit « gamma » et désigne ici l'exposant cherché.

Pour comprendre cette formule géométriquement, faisons une expérience de pensée : dessinons un carré de côté L sur notre table.
1. Son aire (le moment d'ordre 0, `μ₀₀`) grandit comme une surface, c'est-à-dire proportionnellement à `L²`.
2. Un moment d'ordre `p + q` (comme `μ_pq`) somme les coordonnées des pixels élevées aux puissances `p` et `q`. Sa valeur totale grandit donc à la fois selon l'aire (`L²`) et selon la distance des pixels au centre (`L^(p+q)`). Sa valeur croît donc proportionnellement à `L^(p + q + 2)`.
3. Pour annuler l'effet de la taille L dans le rapport `μ_pq / μ₀₀^γ`, nous devons faire en sorte que le haut et le bas grandissent à la même vitesse. Nous voulons donc que `L^(p + q + 2)` soit égal à `(L²)^γ`, ce qui s'écrit `L^(p + q + 2) = L^(2γ)`.
4. Pour que cela fonctionne quelle que soit la taille L, les exposants doivent être égaux : `p + q + 2 = 2γ`.
5. En divisant par 2, on trouve le fameux exposant : `γ = (p + q)/2 + 1`.

Ce n'est pas un nombre choisi au hasard : c'est la seule valeur géométrique qui rende le rapport insensible au zoom. ∎

### Exemple chiffré

Sur le masque jouet : η₂₀ = μ₂₀/μ₀₀² = 4/49 ≈ 0,0816 (à l'ordre 2, γ = 2). Agrandissons mentalement la forme d'un facteur 10 : elle compte désormais 700 pixels, μ₂₀ devient environ 4 × 10⁴ et μ₀₀² environ 49 × 10⁴. Le rapport reste ≈ 0,0816 — c'est cette stabilité qui permet de reconnaître la même forme à toutes les tailles.

### Limite — exacte en théorie, approchée en pratique

Le raisonnement suppose qu'agrandir une forme multiplie proprement ses pixels. En réalité, une petite forme agrandie est re-dessinée sur la grille : les marches d'escalier du contour ne se transforment pas exactement, et η fluctue de quelques pourcents. L'invariance d'échelle est excellente entre une forme de 1 000 pixels et une de 100 000 ; elle se dégrade nettement sous quelques dizaines de pixels, où chaque pixel de contour pèse trop lourd.

### Dans VNStudio

Canvas : `Image Source` → `Threshold` → `Image Moments` → `Inspector`. Les moments normalisés sont une troisième famille de sorties du nœud ; relier deux tailles d'un même objet à deux branches du canvas permet de vérifier d'un coup d'œil qu'ils coïncident.

---

## 2.5 — Orientation principale : l'axe de moindre effort

> *La règle plate pivote sans peine autour de son grand axe*

![fig_ch2_obs3_orientation](../figures/fig_ch2_obs3_orientation.pdf)

### L'intention

On veut connaître l'axe le long duquel la forme s'allonge — pour redresser un caractère, aligner une empreinte, normaliser la pose d'une cellule avant de la classer.

### La forme recherchée

L'analogie mécanique donne l'image directement. Prenez une règle plate : elle pivote sans effort autour de son grand axe, où la matière est collée contre l'axe, et difficilement autour de son petit axe, où la matière en est éloignée. Le grand axe — celui de la rotation facile — est l'**orientation principale** de la forme. On la cherche comme l'axe « de moindre effort » passant par le centroïde.

### La formule

```
θ = ½ · arctan2(2μ₁₁, μ₂₀ − μ₀₂)
```

θ se lit « thêta » et désigne l'angle cherché. La fonction `arctan2` est une variante de l'arc tangente qui, contrairement à la simple `arctan`, tient compte du quadrant : elle distingue un axe penché vers le haut d'un axe penché vers le bas, là où `arctan` les confondrait. Un point mérite d'être compris, car il explique la forme de la formule : on y trouve l'angle **double** 2θ, pas θ. La raison est qu'un axe n'a pas de sens de parcours — une règle orientée à 30° ou à 30° + 180° pointe dans la même direction. Travailler avec 2θ encode naturellement cette ambiguïté, et le facteur ½ ramène le résultat dans l'intervalle utile. ∎

### Exemple chiffré

Masque jouet : 2μ₁₁ = −4 et μ₂₀ − μ₀₂ = 0. Donc arctan2(−4, 0) = −90°, et **θ = −45°**. La forme est orientée le long de la diagonale descendante — ce que le signe de μ₁₁ annonçait en 2.3, et qu'on vérifie d'un coup d'œil sur le dessin (rappel du §2.1 : l'angle se lit dans le repère image, y vers le bas).

En télédétection, l'histogramme des orientations de bâtiments révèle la trame d'une ville ; en microscopie, celui des fibres de collagène quantifie l'anisotropie d'un tissu.

### Subtilité — l'orientation d'un objet rond n'existe pas

Quand la forme est ronde (ou carrée vue de face), elle s'étale autant dans toutes les directions : il n'y a plus d'axe privilégié, et la formule devient indéterminée. Un seul pixel de bruit fait alors basculer θ de 90°. Demander l'orientation d'un disque, c'est demander dans quelle direction pointe une boule de pétanque — la question n'a pas de réponse, et l'algorithme en donnera pourtant une.

On accompagne donc toujours θ d'une mesure de fiabilité, l'**anisotropie** (littéralement « le fait de ne pas être pareil dans toutes les directions »), qui dit à quel point la forme a vraiment une direction dominante :

```
aniso = √((μ₂₀−μ₀₂)² + 4μ₁₁²) / (μ₂₀+μ₀₂)
```

Elle vaut 0 pour un disque (aucune direction privilégiée) et tend vers 1 pour un segment. En pratique, θ n'est pas fiable quand l'anisotropie est faible (sous 0,2 environ). C'est la première manifestation chiffrée du fil : l'ordre 2 fonctionne très bien, sauf dans son cas dégénéré — la forme ronde — où il devient brutalement instable.

### Dans VNStudio

Canvas : `Image Source` → `Threshold` → `Region Properties` → `Inspector`. Le nœud trace l'axe principal par-dessus l'objet et l'inspecteur donne l'angle et l'anisotropie côte à côte, ce qui signale d'emblée les formes rondes où l'angle n'a pas de sens.

---

## 2.6 — Ellipse équivalente : le résumé d'une silhouette

> *L'ellipse qui pèse comme la forme, sans la mesurer*

![fig_ch2_obs1_ellipse_overflow](../figures/fig_ch2_obs1_ellipse_overflow.pdf)

### L'intention

On cherche le résumé le plus dépouillé d'une silhouette : une seule ellipse qui répartit sa masse comme la forme réelle — même centre, même orientation, même façon de s'étaler.

### La forme recherchée

On reprend l'image du **nuage de points** du chapitre 1 : une silhouette est une nuée de pixels. On cherche ses deux directions privilégiées, celle où il s'étale le plus (le grand axe) et celle, perpendiculaire, où il s'étale le moins (le petit axe). Deux nombres mesurent ces étalements, qu'on note λ₁ (lambda-un, le grand) et λ₂ (le petit). Ces deux nombres portent un nom savant — les **valeurs propres** de la matrice qui décrit le nuage — mais il est inutile de savoir les calculer : il suffit de retenir ce qu'ils disent. **λ₁, c'est de combien la forme s'étire dans sa direction la plus longue ; λ₂, dans sa direction la plus courte.** Ce sont les deux « rayons » de l'ellipse qui résumerait le nuage.

### La formule

```
demi-grand axe : a = 2√λ₁
demi-petit axe : b = 2√λ₂
excentricité   : e = √(1 − λ₂/λ₁)
```

L'excentricité n'est rien d'autre que la comparaison des deux étalements — l'excentricité promise au chapitre 1, enfin reliée à sa source. Étalements égaux (forme ronde) : le rapport λ₂/λ₁ vaut 1, et e tombe à 0. Petit étalement minuscule face au grand (forme en aiguille) : le rapport tend vers 0, et e tend vers 1. ∎

### Exemple chiffré (suite et fin du masque jouet)

En combinant μ₂₀ = 4, μ₀₂ = 4 et μ₁₁ = −2 :

```
λ₁ ≈ 0,857   →  demi-grand axe a = 2√λ₁ ≈ 1,85
λ₂ ≈ 0,286   →  demi-petit axe b = 2√λ₂ ≈ 1,07
excentricité : e = √(1 − λ₂/λ₁) = √(1 − 1/3) ≈ 0,82
```

Une forme nettement allongée, le long de la diagonale θ = −45° trouvée en 2.5. Sept pixels ont suffi à dérouler toute la chaîne : moments bruts → centroïde → moments centraux → orientation → ellipse.

### Piège — l'ellipse ne mesure pas la taille de l'objet

C'est sans doute l'erreur la plus répandue du chapitre. L'ellipse équivalente égalise la **répartition de masse**, pas les **dimensions**. Le grand axe de l'ellipse équivalente d'un rectangle **dépasse d'environ 15 % la longueur réelle** du rectangle. L'intuition : pour qu'une ellipse, effilée à ses bouts, loge autant de masse loin du centre qu'un rectangle aux bouts pleins, elle doit être plus longue que lui.

Pour mesurer la dimension réelle d'une pièce, d'une bactérie ou d'un trait, on emploie le **rectangle orienté minimal** (la plus petite boîte inclinée qui contient l'objet, vue au §1.2) ou le **diamètre de Feret** (la plus grande distance entre deux points du contour). L'ellipse équivalente décrit la répartition de masse (orientation, excentricité) ; elle ne mesure pas. Confondre les deux usages introduit une erreur systématique d'environ 15 %, du genre qui passe inaperçu toute une campagne de mesures.

### Dans VNStudio

Canvas : `Image Source` → `Threshold` → `Region Properties` → `Inspector`. Le nœud superpose l'ellipse équivalente sur l'objet et l'inspecteur donne grand axe, petit axe et excentricité. Une vérification utile : tracer un rectangle synthétique de longueur connue et constater que le grand axe ressort ~15 % trop grand.

---

## 2.7 — Les sept invariants de Hu : la signature d'une forme

> *Reconnaître une chanson quelle que soit la tonalité*

### L'intention

Il reste une invariance à conquérir : la **rotation**. Les η_pq sont insensibles à la position et à la taille, mais tourner la forme les mélange entre eux. On veut une poignée de nombres qui ne bougent ni quand l'objet se déplace, ni quand il grandit, ni quand il tourne : une signature de la forme « pure », débarrassée de sa pose.

### La forme recherchée

Hu (1962) a trouvé sept combinaisons des moments d'ordre 2 et 3 que la rotation laisse intactes. L'image utile est celle d'une **empreinte digitale** de la forme, ou d'une chanson reconnaissable quelle que soit la tonalité où on la chante : peu importe l'angle de présentation, la signature reste la même.

Ces sept expressions (touffues, mêlant les η) ne sont pas à reproduire ni à mémoriser. Ce qui compte est de comprendre pourquoi elles résistent à la rotation. Quand on tourne une forme, ses moments changent très régulièrement : c'est seulement l'« angle » de certaines quantités qui bouge, pas leur taille. Hu a assemblé les η de manière que cet angle s'élimine de lui-même — comme la longueur d'une flèche reste la même quand on la fait pivoter, alors que ses coordonnées horizontale et verticale, elles, changent. Ce qui survit à l'élimination de l'angle est, par construction, insensible à la rotation.

### Deux propriétés à connaître

**φ₇ change de signe en miroir** — le seul des sept (φ se lit « phi »). Une forme et son reflet ont les mêmes φ₁ à φ₆ mais des φ₇ opposés. Précieux quand le sens compte (distinguer « b » de « d », « p » de « q »), à exclure quand il ne compte pas, sous peine de séparer artificiellement des objets identiques vus de dos.

**La dynamique est énorme.** Les φ s'étagent de très grands à très petits nombres (de l'ordre de 0,1 jusqu'à 0,000…1 avec vingt zéros) : comparés directement, les petits seraient écrasés par les grands. On les ramène à des ordres de grandeur comparables par le logarithme — la fonction qui transforme « multiplier par 10 » en « ajouter 1 », et compresse ainsi des écarts gigantesques. Voir la forme *log*, annexe C.

### Exemple — reconnaissance de caractères

C'est l'application historique. Un « A » conserve sa signature petit, grand, tourné ou déplacé. Un « O » très symétrique a ses moments d'ordre 3 quasi nuls, donc φ₃ à φ₇ ≈ 0 ; un « R » asymétrique les a nettement non nuls. La distance entre deux signatures de Hu (en échelle log — voir chapitre 3) suffit à un classifieur des plus simples.

### Hu aujourd'hui : encore utile ?

Pour la reconnaissance générale, les descripteurs appris (réseaux de neurones) dominent largement. Les moments de Hu gardent trois créneaux bien réels : quand on a peu ou pas de données d'entraînement ; quand il faut une invariance **prouvable** et non simplement constatée (métrologie, certification industrielle) ; quand le budget de calcul est minuscule (capteurs embarqués). La question utile n'est pas « Hu ou réseau de neurones ? » mais « mon problème exige-t-il une garantie mathématique, ou une performance statistique ? ».

### Dans VNStudio

Canvas : `Image Source` → `Threshold` → `Hu Moments` → `Inspector`. Le nœud sort les sept invariants déjà ramenés en échelle logarithmique. Brancher le même objet tourné sur une seconde branche montre que la signature reste stable, sauf le signe de φ₇ pour une image en miroir.

---

## 2.8 — Moments pondérés par l'intensité

> *Rendre les pixels clairs plus lourds que les sombres*

### L'intention

Jusqu'ici, tous les pixels du masque pèsent pareil. Sur une image en niveaux de gris, on aimerait que les pixels clairs comptent davantage — pour suivre un profil lumineux, localiser une source au plus fin.

### La forme recherchée et la formule

Toutes les formules du chapitre s'appliquent sans changement : il suffit de remplacer le masque binaire par les intensités, c'est-à-dire de poser I(x, y) = niveau de gris au lieu de 0 ou 1. Seule l'interprétation change :

```
centroïde binaire  : centre géométrique du masque
centroïde pondéré  : barycentre lumineux (tiré vers les zones claires)
```

Le masque binaire traite tous les pixels comme aussi lourds les uns que les autres ; la version pondérée rend les pixels clairs plus lourds. Le point d'équilibre se déplace alors vers les zones lumineuses. ∎

### Exemple chiffré

En astronomie, une étoile s'étale sur quelques pixels avec un profil lumineux en cloche ; le centroïde pondéré moyenne ce profil et localise la source au **sous-pixel** — bien plus finement que le simple pixel le plus brillant. C'est le principe des mesures astrométriques de précision. De même, en caractérisation de faisceau laser, les moments pondérés d'ordre 2 définissent la largeur du faisceau (méthode D4σ, norme ISO 11146).

### Sensibilité — le fond doit être soustrait d'abord

Les moments pondérés héritent de tout ce qui affecte l'intensité : vignettage (les bords d'image plus sombres), fond non uniforme, pixels saturés. Un fond résiduel non soustrait tire le centroïde pondéré vers le centre de la fenêtre de mesure. En astrométrie, la soustraction de fond se fait *avant* tout calcul de moment.

### Dans VNStudio

Canvas : `Image Source` → `Background Subtract` → `Image Moments (weighted)` → `Inspector`. En branchant aussi le masque binaire sur une seconde entrée, l'inspecteur affiche l'écart entre le centroïde géométrique et le centroïde lumineux — la quantité exploitée en astrométrie.

---

## Tableau récapitulatif — quel moment pour quelle question ?

| Question | Outil | Ordre | Invariances | Fragilité |
|---|---|---|---|---|
| Quelle est la taille de l'objet ? | M₀₀ (aire) | 0 | — | très robuste |
| Où est-il ? | centroïde M₁₀/M₀₀, M₀₁/M₀₀ | 1 | — | très robuste |
| Dans quel sens est-il orienté ? | θ (μ₁₁, μ₂₀, μ₀₂) | 2 | translation | instable si forme ronde |
| Comment sa masse est-elle répartie ? | ellipse équivalente (λ₁, λ₂) | 2 | translation | ≠ dimensions réelles |
| Est-il allongé ? | excentricité e | 2 | translation, rotation | instable si forme ronde |
| Le reconnaître à toute pose ? | Hu φ₁–φ₆ | 2–3 | translation, rotation, échelle | sensible au bruit de bord |
| Le distinguer de son miroir ? | signe de φ₇ | 3 | translation, rotation, échelle | le plus fragile de tous |
| Position sous-pixel d'une source ? | centroïde pondéré | 1 | translation | sensible au fond résiduel |

---

## Encadré final — chaque détail se paie en fragilité

Les moments héritent de toutes les erreurs de segmentation, mais pas au même degré. Chaque montée en ordre élève les écarts au centroïde à une puissance de plus : les pixels du bord — précisément ceux que la segmentation place mal — pèsent de plus en plus lourd. D'où l'échelle de fragilité du chapitre :

```
ordre 0 (aire)        : erreur ∝ bruit de bord       — robuste
ordre 1 (centroïde)   : erreur sub-pixel             — très robuste
ordre 2 (orientation) : instable si forme isotrope   — filtrer par anisotropie
ordre 3 (Hu φ₃–φ₇)    : ±50 % pour 2 px de bruit     — fragile
```

Vous connaissez peut-être cette hiérarchie sous une autre forme : en statistiques, la moyenne d'un échantillon est plus stable que sa variance, elle-même plus stable que son asymétrie puis son aplatissement. Ce sont les mêmes moments, appliqués à une liste de nombres au lieu d'une image — et le parallèle, une fois vu, ne s'oublie plus.

Le chapitre 1 montrait qu'un descripteur garde une chose et en jette une autre ; les moments ajoutent que chaque supplément de détail se paie en fragilité. Le chapitre 6 retrouvera presque mot pour mot cet échange, quand dériver une image — l'analogue continu de la montée en ordre — amplifiera le bruit de la même manière.

---

## Figures à créer

| Identifiant | Section | Contenu | Format |
|---|---|---|---|
| `fig_ch2_couverture` | chapeau | Illustration : silhouette de carton en équilibre sur une pointe, chiffres notés à côté | JPG/PNG |
| `fig_ch2_01_ordre_question` | 2.1 | Schéma : même masque, trois « boutons » d'ordre (0, 1, 2) → comptage / position / étalement | SVG |
| `fig_ch2_obs3_orientation` | 2.5 | Déjà existant (PDF) : règle plate, axe de rotation facile vs difficile | — |
| `fig_ch2_obs1_ellipse_overflow` | 2.6 | Déjà existant (PDF) : ellipse équivalente débordant le rectangle (+15 %) | — |
| `fig_ch2_obs2_mu30_asymmetry` | 2.3 | Déjà existant (PDF) : forme symétrique (μ₃₀≈0) vs asymétrique (μ₃₀≠0) | — |
| `fig_ch2_02_hu_signature` | 2.7 | Même lettre « A » à 4 poses différentes → même vecteur de Hu | SVG |
