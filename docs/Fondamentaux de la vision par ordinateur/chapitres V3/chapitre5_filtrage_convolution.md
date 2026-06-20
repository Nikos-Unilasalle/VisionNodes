# Chapitre 5 — Le pochoir glissant : filtrage et convolution

![Un artisan choisit un pochoir parmi plusieurs et le fait glisser sur une image ; chaque pochoir suppose une nature différente du motif sous-jacent](../figures/fig_ch5_couverture.jpg)
*Le même geste — un petit pochoir promené sur l'image — lisse, accentue ou détecte selon les nombres qu'on y inscrit. Choisir le pochoir, c'est déjà parier sur ce qu'est le signal.*

---

Chaque pixel d'une image n'existe pas isolément : il est entouré de voisins qui partagent son contexte. Le filtrage exploite ce voisinage — il remplace chaque pixel par une combinaison pondérée de ses proches. Avec le bon choix de pondération, la même mécanique lisse le bruit d'une radiographie, accentue les nervures d'une feuille en microscopie, détecte les craquelures d'une pièce industrielle ou repère les orientations dominantes d'une empreinte digitale.

Le fil du chapitre tient en une phrase : **un filtre est un a priori sur le signal.** Un *a priori*, c'est ce qu'on suppose vrai avant même de regarder. Choisir un filtre, c'est donc déclarer ce qu'on croit savoir du signal d'avance. Le filtre gaussien suppose qu'il varie doucement, sans saut brusque entre voisins. Le bilatéral suppose qu'il est lisse *par morceaux*, avec des sauts francs aux contours mais une régularité à l'intérieur des régions. Le Gabor suppose qu'il contient des ondulations à une certaine fréquence et orientation. Cette hypothèse est inscrite dans les nombres du filtre ; elle décide de ce qu'il voit et de ce qu'il rate. Un filtre mal choisi n'est pas seulement décevant : il impose une hypothèse fausse sur la nature des données, et les dégrade.

Le chapitre construit la convolution depuis ses propriétés, puis dérive les filtres essentiels en montrant à chaque fois quelle hypothèse leur forme encode. Il prolonge le chapitre 3 — la pondération d'un filtre est une façon de mesurer la proximité pertinente entre pixels — et prépare le chapitre 6, où le choix du filtre de dérivation conditionnera la qualité des détecteurs de bords.

### Un peu de vocabulaire avant de commencer

*   **Pixel et voisinage** : Un pixel `I(x, y)` est le point élémentaire de l'image. Son **voisinage** désigne l'ensemble des pixels qui l'entourent directement (par exemple dans une grille de 3×3 ou 5×5 pixels centrée sur lui).
*   **Noyau (kernel)** : Une petite grille de nombres (comme un pochoir) qui définit les coefficients de pondération appliqués à chaque voisin.
*   **Convolution (notée *)** : L'action de faire glisser le noyau sur chaque pixel de l'image pour additionner les valeurs pondérées de son voisinage.

---

## 5.1 — La convolution 2D : le pochoir promené partout pareil

> *Une petite grille de nombres, posée sur chaque pixel à son tour*

### L'intention

On veut une opération qui exploite le voisinage de chaque pixel, mais une opération **uniforme** : le même traitement partout, réglé une seule fois, applicable à l'image entière.

### La forme recherchée

L'image est celle d'un pochoir qui glisse sur une feuille. Le pochoir — appelé **noyau** (*kernel*) — est une petite grille de nombres. On le pose centré sur un pixel, on multiplie chaque case du pochoir par l'intensité qu'elle recouvre, on additionne le tout : c'est la nouvelle valeur du pixel central. On glisse d'un pas, on recommence, jusqu'à couvrir toute l'image. Cette opération s'appelle la **convolution**. Le même pochoir s'applique partout de façon identique — la rivière d'une image satellite reçoit exactement le traitement de la forêt voisine.

### La formule

```
(I * K)(x, y) = Σᵢ Σⱼ I(x − i, y − j) · K(i, j)
```

`I` désigne l'image, `K` le noyau, l'astérisque `*` note la convolution, et le double `Σ` (sigma) additionne les calculs sur toutes les cases du pochoir.

Pour comprendre cette formule géométriquement, attardons-nous sur le signe moins : `x − i` et `y − j`.
1. **L'inversion du pochoir** : Au lieu de poser le pochoir tel quel, les indices négatifs nous obligent mathématiquement à le faire pivoter de 180° (c'est-à-dire le retourner de gauche à droite et de haut en bas) avant d'effectuer les multiplications. C'est l'étape de retournement qui distingue la convolution stricte de la simple corrélation croisée.
2. **Pourquoi cette contrainte ?** Ce retournement garantit que la convolution respecte une propriété mathématique cruciale : l'**associativité**. Grâce à cela, appliquer un filtre A puis un filtre B donne exactement le même résultat qu'appliquer d'abord le filtre B puis le filtre A. De même, on peut fusionner les deux filtres en un seul et l'appliquer en une unique passe. Sans ce retournement, l'ordre d'enchaînement modifierait le résultat, brisant la cohérence géométrique des pipelines de traitement.

Cette uniformité — le filtre ne dépend pas de l'endroit, on dit qu'il est **invariant par translation** — fait la force et la limite de la convolution. Sa force : un filtre réglé une fois s'applique à toute l'image sans recalibrage. Sa limite : si le signal a une structure différente selon la région (fond uniforme contre bord texturé), un seul noyau ne s'y adapte pas — d'où les filtres adaptatifs comme le bilatéral (§5.4).

Deux propriétés méritent d'être nommées. La convolution est **linéaire** (doubler l'image double le résultat). Et elle est **associative** : enchaîner deux filtres revient à appliquer un seul noyau combiné, calculé une fois pour toutes — ce qui économise un passage complet sur l'image quand on lisse puis on dérive. Linéarité et invariance par translation se révèlent caractériser *entièrement* ce genre de filtres : tout traitement à la fois uniforme et linéaire *est* nécessairement une convolution. Ce n'est pas une convention, mais un fait mathématique — la convolution est le seul outil de cette famille. ∎

### La séparabilité : diviser pour régner

Certains noyaux 2D peuvent se décomposer en deux passes 1D : d'abord sur les lignes, puis sur les colonnes. On dit qu'ils sont **séparables**. Le gain est énorme. Pour un pochoir de 21 × 21, la version directe demande 441 multiplications par pixel ; la version séparée, 42 — un facteur 10, décisif pour un traitement exécuté à 30 images par seconde. Le filtre gaussien (§5.2) a cette propriété, ce qui explique pourquoi un flou même large reste rapide sur une image en haute définition.

### Gestion des bords

Au bord de l'image, le pochoir déborde là où il n'y a pas de pixels. Quatre conventions usuelles comblent ce vide : étendre par des zéros (crée des bandes sombres artificielles), répéter en miroir les pixels du bord (le plus neutre, défaut le plus sûr pour le lissage), prolonger le pixel de bord en ligne droite, ou traiter l'image comme périodique (rarement pertinent sur des images naturelles). Le choix affecte les quelques pixels de bordure ; une analyse sérieuse des bords documente donc la convention employée.

### Subtilité — convolution ou corrélation, et le type de données

Beaucoup de bibliothèques calculent en réalité une **corrélation** — la convolution sans une étape de retournement du noyau. Sans effet pour un pochoir symétrique (gaussien, moyenneur), mais pour un pochoir asymétrique (les dérivateurs du chapitre 6), cela inverse le signe : un gradient sort « à l'envers ». Autre point : travailler en nombres entiers sans marge fait saturer et tronque silencieusement les valeurs, surtout avec les noyaux à coefficients négatifs (LoG, DoG) ; on calcule alors en nombres à virgule.

### Dans VNStudio

Canvas : `Image File` → `Blur` → `Display`. Le nœud `Blur` propose le flou moyenneur (Box), gaussien et médian ; pour un noyau personnalisé, le nœud `Python Node` peut implémenter `cv2.filter2D` avec n'importe quel noyau et expose la même convention de bord.

---

## 5.2 — Le noyau gaussien : l'hypothèse de douceur

> *Un spot lumineux flou centré sur chaque pixel*

### L'intention

On veut atténuer le bruit en supposant que le signal est **localement lisse** : la valeur d'un pixel devrait ressembler à celle de ses voisins, et cette ressemblance décroître progressivement avec la distance.

### La forme recherchée

La pondération doit valoir beaucoup au centre et fondre doucement vers les bords — une **cloche**. L'image utile est celle d'un spot lumineux flou centré sur chaque pixel : les zones les plus intensément éclairées (le centre) pèsent le plus dans la moyenne. Plus on élargit le spot, plus le voisinage pris en compte est étendu, plus l'image résulte floue.

### La formule

```
G(x, y) = (1 / 2πσ²) · exp(−(x² + y²) / 2σ²)
```

Le seul réglage qui compte est σ (« sigma »), la largeur de la cloche : il fixe l'étendue du voisinage. Un petit σ encode un a priori de lisseur très local ; un grand σ, un signal supposé uniforme sur de grandes zones. Au-delà d'environ trois fois σ de distance, la pondération devient négligeable. ∎

### Pourquoi la gaussienne et pas une autre cloche ?

Ce n'est pas un choix esthétique. La gaussienne est l'**unique** cloche qui réunit plusieurs bonnes propriétés à la fois. D'abord, elle **ne crée jamais de structure** : élargir le flou ne fait jamais apparaître de nouveau détail qui n'existait pas — un moyenneur en boîte, lui, peut créer de fausses ondulations. C'est le fondement de la « pyramide d'échelle », cette suite de versions de plus en plus floues d'une image, sur laquelle on cherche les structures à différentes tailles. Ensuite, elle est **séparable** (§5.1), donc rapide. Enfin, elle a la propriété d'**auto-similarité** : flouter deux fois de suite équivaut à flouter une seule fois un peu plus fort, ce qui rend ces pyramides prévisibles et stables. Ces qualités font de la gaussienne le filtre de lissage de référence.

### Exemple

Un petit noyau gaussien 3×3, avec les coefficients entiers couramment utilisés :

```
     [ 1  2  1 ]
1/16 · [ 2  4  2 ]
     [ 1  2  1 ]
```

La somme des coefficients vaut 16, d'où la division par 16. Un filtre de lissage doit préserver la luminosité moyenne (ses coefficients somment à 1 une fois normalisés) ; sans cela, chaque passage assombrirait ou éclaircirait l'image. Le centre pèse 25 %, les quatre voisins directs 12,5 % chacun, les diagonales 6,25 % — une cloche en miniature.

### Paramètres opérationnels (VNStudio / Python)

Dans le nœud `Blur` (ou via `cv2.GaussianBlur` en Python), le comportement du lissage est contrôlé par les paramètres opérationnels suivants :

*   **Taille du noyau (`ksize`)** :
    *   Dans VNStudio, ce paramètre correspond au curseur **Kernel Size** ; en Python (OpenCV), il se nomme `ksize` dans `cv2.GaussianBlur`.
    *   Spécifie la largeur et la hauteur de la grille du noyau (ex. : 3×3, 5×5, 7×7). Cette taille doit obligatoirement être représentée par des nombres impairs pour que le noyau possède un pixel central bien défini. Plus la grille est grande, plus le lissage est large, mais plus le coût de calcul augmente.
*   **Écart-type du lissage (`sigmaX`, `sigmaY`)** :
    *   Dans VNStudio, ce paramètre correspond au curseur **Sigma** ; en Python (OpenCV), il se nomme `sigmaX` (et optionnellement `sigmaY`) dans `cv2.GaussianBlur`.
    *   Contrôle la largeur réelle de la cloche gaussienne (le degré de flou). Si vous réglez `sigma` sur `0` en Python, OpenCV calcule automatiquement l'écart-type idéal à partir de la taille du noyau. Si vous réglez `sigma` manuellement, veillez à ce que la taille du noyau soit au moins égale à **6 fois le sigma** (c'est-à-dire `ksize ≈ 6 * sigma`). Si le noyau est trop petit par rapport à `sigma`, la cloche gaussienne est tronquée brusquement sur les bords du pochoir, ce qui génère des artefacts visibles (des bandes d'intensité artificielles sur l'image).
*   **Gestion des bordures (`borderType`)** :
    *   Dans VNStudio, ce paramètre correspond au menu déroulant **Border Type** ; en Python (OpenCV), il correspond à l'argument `borderType` dans `cv2.filter2D`.
    *   Définit comment OpenCV traite les pixels hors-limite lorsque le pochoir déborde des bords de l'image. Le mode par défaut `cv2.BORDER_DEFAULT` (ou `BORDER_REFLECT_101`) recopie l'image par symétrie au niveau des bords, évitant ainsi de créer des bandes noires artificielles qui fausseraient le calcul des moyennes.

### Dans VNStudio

Dans votre canvas :
`Image File` ──> `Grayscale` ──> `Blur` ──> `Display`.

Le nœud `Blur` expose les curseurs `Kernel Size` (taille de grille) et `Sigma` dans l'inspecteur, permettant d'observer en direct le lissage du bruit et la disparition des détails les plus fins au fur et à mesure que la cloche s'élargit.

**Exercice de dépannage :** L'exercice consiste à appliquer un flou avec un **Kernel Size** très large (ex. : 21x21) sur une image claire, en réglant le paramètre **Border Type** sur **Constant (0)** (ce qui remplit le hors-bord de noir). Le lecteur observe sur l'image de sortie un halo sombre artificiel qui bave depuis les bordures vers l'intérieur de l'image. Cela illustre comment un mauvais choix de gestion des bords corrompt l'intensité des pixels périphériques lors des calculs de moyenne locale.

---

## 5.3 — DoG et LoG : voir ce qui change

> *Le chapeau mexicain qui s'allume sur les taches et les bords*

### L'intention

Après les filtres qui voient ce qui est lisse, on veut détecter ce qui *change* — contours, taches, petits blobs. Mais mesurer un changement (dériver) amplifie le bruit ; il faut donc lisser avant.

### La forme recherchée

La logique procède en deux temps. D'abord, on lisse avec un gaussien, ce qui efface le bruit fin qui rendrait toute mesure de variation instable — l'a priori reste que le signal utile est plus lisse que le bruit. Ensuite, on regarde la **courbure** de l'intensité : à quel point elle s'incurve. Sur une crête lumineuse, l'intensité culmine puis redescend, courbure forte ; à une transition franche (un bord), la courbure change de signe et passe par zéro. Détecter un contour revient à chercher ces **passages par zéro**.

Le filtre qui réalise les deux temps d'un coup a la forme d'un **chapeau mexicain** : positif au centre (il s'allume sur une tache claire entourée de sombre), négatif en couronne autour. On le nomme LoG (Laplacian of Gaussian, le laplacien d'une gaussienne — le laplacien étant l'outil mathématique standard qui mesure la courbure) ; dans VNStudio, le nœud `Laplacian` approche ce comportement.

### La formule

```
LoG(x,y) = ((x² + y² − 2σ²) / σ⁴) · G(x,y)
DoG = G_σ1 − G_σ2     (avec σ1 < σ2, typiquement σ2 / σ1 ≈ 1.6)
```

Le **DoG** (*Difference of Gaussians*, différence de deux gaussiennes) approxime le LoG par un raccourci économique : on floute l'image deux fois, à deux degrés, et on soustrait. Il se comporte comme un filtre **passe-bande** : il efface à la fois les très grandes structures (lissées par le flou large) et le bruit fin (lissé par le flou serré), ne laissant passer que les détails d'une taille proche de σ.

C'est la brique du détecteur de points SIFT : en calculant la DoG à plusieurs σ, on repère des blobs **et leur taille** — le même point d'intérêt se retrouve dans une image zoomée ou tournée. En microscopie, cela mesure automatiquement le diamètre de centaines de vésicules en une passe. ∎

### Exemple

Au centre exact d'un blob clair sur fond sombre, la formule du LoG se simplifie : le terme entre parenthèses devient −2σ², et la réponse vaut −2/σ² × G(0,0), **fortement négative**. La courbure de l'intensité y est maximale. Chercher les minima (les valeurs les plus négatives) de la réponse localise les centres de blobs clairs ; pour des blobs sombres, on cherche les maxima.

### Dans VNStudio

Canvas : `Image File` → `Grayscale` → `Laplacian` → `Display`. Le nœud calcule en nombres à virgule (indispensable : la réponse a deux signes, et un calcul en entiers effacerait la moitié négative) et propose une variante DoG plus rapide pour le même effet.

---

## 5.4 — Le filtre bilatéral : lisser sans franchir les bords

> *Ne moyenner deux pixels que s'ils sont proches en place ET en valeur*

### L'intention

Le gaussien lisse partout indistinctement, y compris à travers les contours — cohérent avec son a priori de signal globalement lisse, mais cet a priori est faux aux frontières. Une radiographie, une image satellite, un portrait : tous ont des zones intérieures uniformes séparées par des bords nets. On veut lisser l'intérieur des régions sans franchir leurs bords.

### La forme recherchée

L'a priori devient : le signal est **lisse par morceaux** — régulier dans chaque région, avec des transitions brusques aux contours. On ajoute donc au poids de proximité spatiale du gaussien un second poids, en intensité : deux pixels ne se moyennent que s'ils sont à la fois **proches dans l'espace** ET **proches en valeur**. Un pixel de l'autre côté d'un contour fort a une grande différence d'intensité : son poids tombe à presque zéro, il ne contribue pas, le contour est préservé.

### La formule

```
BF[I](p) = (1/W_p) · Σ_{q∈Ω}  G_σs(‖p − q‖) · G_σr(|I(p) − I(q)|) · I(q)
```

Le détail importe peu ; l'essentiel est qu'il y a **deux cloches gaussiennes multipliées**. La première, G_σs, pèse la distance spatiale (comme au §5.2). La seconde, G_σr, pèse la différence d'intensité : elle s'effondre dès que deux pixels n'ont pas la même clarté. Le produit des deux fait qu'un voisin ne compte que s'il est proche *et* de teinte semblable. Conséquence importante : ce filtre **n'est pas une convolution**, car son poids dépend du contenu de l'image, pas seulement de la position. C'est un filtre **adaptatif** — plus lent, mais qui respecte les bords.

Deux réglages indépendants. σs (spatial) fixe la taille du voisinage ; σr (intensité) fixe la tolérance aux différences de teinte. Un petit σr ne moyenne que des teintes presque identiques (contours bien gardés, lissage faible) ; un grand σr rend le filtre indifférent aux différences et le ramène à un simple gaussien. ∎

### Exemple

Pixel p sur un contour, d'intensité 200. À gauche, voisins à 195 (même côté) ; à droite, voisins à 50 (autre côté). Avec une tolérance σr = 30 :

```
poids du voisin à 195 : très proche en teinte → contribue fortement
poids du voisin à 50  : très différent        → contribution quasi nulle
```

Le pixel se moyenne donc uniquement avec ses voisins du même côté du contour. Le bord reste net. Cet a priori sert au débruitage préservant les contours (scanner, IRM), au lissage de peau en retouche, à l'effet « cartoon », au filtrage de cartes de profondeur en robotique.

### Réglage — l'unité de la tolérance

Le filtre est sensible à l'échelle des valeurs : une tolérance réglée pour des pixels de 0 à 255 n'a pas le même sens sur une image ramenée entre 0 et 1. L'oublier produit un filtre soit transparent (tolérance trop grande), soit inopérant (trop petite) : on vérifie toujours σr par rapport à la plage réelle des données.

### Dans VNStudio

Canvas : `Image File` → `Bilateral Filter` → `Display`. Le nœud expose les deux rayons (spatial et intensité) ; baisser le rayon d'intensité montre les contours se figer pendant que l'intérieur des régions se lisse.

---

## 5.5 — Le filtre de Gabor : chercher une ondulation orientée

> *Un peigne à dents régulières, incliné, dont l'empreinte s'estompe vers les bords*

### L'intention

Certains signaux sont des **ondulations** localisées et orientées : une strie sur un tissu, une nervure de feuille, un sillon d'empreinte digitale. On veut un filtre qui réponde fortement là où l'image ondule à une fréquence donnée, dans une direction donnée.

### La forme recherchée

Le filtre est le produit de deux choses qu'on visualise séparément. Une **enveloppe gaussienne** délimite une petite fenêtre autour du pixel — on ne cherche la strie qu'à proximité, pas dans toute l'image. Une **ondulation** (une sinusoïde, la courbe régulière qui monte et descend) oscille à une certaine fréquence le long d'une direction donnée. L'image juste est celle d'un **peigne à dents régulières**, incliné à l'angle voulu, dont l'empreinte s'estompe vers les bords de la fenêtre : passer ce peigne sur l'image mesure à quel point elle « vibre » à la fréquence du peigne, dans sa direction.

### La formule

```
g(x,y) = exp(−(x'² + γ²y'²) / 2σ²) · cos(2π x'/λ + ψ)
```

Le premier facteur est l'enveloppe (la fenêtre gaussienne), le second l'ondulation (le cosinus). Les réglages : λ (« lambda ») est la longueur d'onde, c'est-à-dire l'espacement des dents du peigne, donc la taille de la texture cherchée ; θ (caché dans les coordonnées x', y') est l'orientation ; σ la taille de la fenêtre. Ce filtre a une qualité remarquable, partagée avec la gaussienne : il localise au mieux à la fois *où* est la strie et *quelle* est sa période. Cette qualité a une trace biologique frappante — les neurones du cortex visuel des mammifères réagissent comme des filtres de Gabor : l'évolution a sélectionné ce filtre pour analyser les textures. ∎

### Le banc de filtres

Un seul Gabor ne capte qu'une fréquence et une orientation. En pratique on construit un **banc** : plusieurs longueurs d'onde × plusieurs orientations (souvent 0°, 45°, 90°, 135°). La réponse de l'image à tout le banc forme une signature de texture riche. C'est ainsi qu'on reconnaît un iris dans un passeport biométrique, ou qu'on distingue les types de couvert végétal sur une image satellite.

### Exemple

Pour détecter des stries verticales espacées de 8 pixels : on règle la longueur d'onde sur 8 et l'orientation pour que l'ondulation varie horizontalement (ce qui détecte des stries verticales). Une zone à cette périodicité exacte produit une réponse maximale ; une zone lisse ou striée autrement, une réponse quasi nulle. En balayant les orientations, on obtient en chaque pixel l'orientation dominante de la texture.

### Réglage — normaliser les filtres du banc

Les noyaux de Gabor n'ont pas tous la même « énergie » selon leurs réglages. Dans un banc comparatif, on normalise chaque noyau pour que les réponses soient comparables d'une orientation à l'autre ; sans cela, les orientations associées aux noyaux les plus énergétiques l'emportent artificiellement.

### Dans VNStudio

Canvas : `Image File` → `Grayscale` → `Gabor Bank` → `Display`. Le nœud `Gabor Bank` applique plusieurs orientations et longueurs d'onde et sort la réponse maximale en chaque pixel, ce qui fait ressortir les textures orientées comme une carte d'intensité.

---

## Tableau récapitulatif — le filtre comme a priori sur le signal

| Filtre | Linéaire ? | Séparable ? | A priori sur le signal | Usage type |
|---|---|---|---|---|
| Gaussien | oui | oui | localement lisse, variation douce | débruitage, pyramide d'échelle |
| Moyenneur (boîte) | oui | oui | localement constant | lissage rapide, grossier |
| LoG | oui | non | contours = passages par zéro de la courbure | détection de contours, blobs |
| DoG | oui | ~oui (2 gaussiens) | structures à une bande de taille | blobs, SIFT, multi-échelle |
| Bilatéral | **non** | non | lisse par morceaux (sauts aux contours) | débruitage préservant les bords |
| Gabor | oui | non | ondulations orientées à une fréquence | texture, biométrie, cortex visuel |

---

## Encadré final — quand l'hypothèse est fausse, le filtre dégrade

Chaque filtre du chapitre porte une déclaration sur le signal, inscrite dans ses nombres et appliquée aveuglément à chaque pixel. Quand l'a priori est vrai — signal effectivement lisse (gaussien), effectivement à sauts nets (bilatéral), effectivement strié à telle fréquence (Gabor) — le filtre excelle. Quand il est faux, il dégrade le signal précisément là où on voulait l'améliorer : le gaussien dit « les variations brusques sont du bruit » et efface alors les contours qu'on voulait garder.

Le chapitre 3 mesurait la proximité pertinente entre objets ; un filtre fait de même entre pixels — le gaussien mesure une proximité spatiale, le bilatéral une proximité conjointe place-intensité, le Gabor une ressemblance d'ondulation. Un descripteur du chapitre 1, une distance du chapitre 3, un filtre ici : chacun encode une hypothèse sur ce qui compte, et reconnaître laquelle on impose explique pourquoi un résultat déçoit quand les données ne respectent pas l'hypothèse.

Le chapitre 6 enchaînera directement : tout détecteur de contour est un filtre de dérivation, et son comportement face au bruit dépend de l'a priori de lisseur qu'il porte en amont. Le chapitre 10 reprendra l'idée dans le domaine des fréquences, où l'on verra qu'un noyau de lissage est un « passe-bas », un noyau de dérivation un « passe-haut », un Gabor un « passe-bande orienté ».

---

## Figures à créer

| Identifiant | Section | Contenu | Format |
|---|---|---|---|
| `fig_ch5_couverture` | chapeau | Illustration : artisan choisissant un pochoir parmi plusieurs et le glissant sur une image | JPG/PNG |
| `fig_ch5_01_pochoir` | 5.1 | Noyau 3×3 posé sur une grille de pixels, produit + somme → pixel de sortie | SVG |
| `fig_ch5_02_separable` | 5.1 | Décomposition d'un noyau 2D en deux passes 1D (lignes puis colonnes) | SVG |
| `fig_ch5_03_cloche_gaussienne` | 5.2 | Courbe en cloche, effet de σ petit vs grand sur l'étendue du voisinage | SVG |
| `fig_ch5_04_chapeau_mexicain` | 5.3 | Profil du LoG (chapeau mexicain) + passage par zéro sur un bord | SVG |
| `fig_ch5_05_bilateral` | 5.4 | Pixel sur un contour : poids forts d'un côté, quasi nuls de l'autre | SVG |
| `fig_ch5_06_gabor_peigne` | 5.5 | Le « peigne » Gabor (ondulation × enveloppe) incliné à un angle θ | SVG |
