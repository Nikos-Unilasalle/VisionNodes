# Annexe — Lire une formule : le sens de ses composants

Une formule de ce livre ne se déchiffre pas symbole par symbole, comme on épellerait un mot lettre à lettre. On la lit par *silhouettes* : un œil entraîné reconnaît d'un coup une exponentielle qui escompte, un carré qui pénalise, un cosinus qui mesure un alignement, et il sait aussitôt ce que la formule a décidé de faire. Cette annexe rassemble ces silhouettes. Pour chaque composant courant — le logarithme, la racine, le carré, l'exponentielle, le cosinus, le maximum, la division… — elle donne la forme mentale, ce que le composant fait à une grandeur, les endroits du livre où il revient, et le piège qui l'accompagne.

Le fil conducteur de l'annexe prolonge celui de tout l'ouvrage : **chaque composant d'une formule encode une intention**. Choisir d'élever au carré, c'est déclarer que les grands écarts comptent démesurément ; prendre une valeur absolue, c'est déclarer que seule l'ampleur compte, pas le sens ; diviser, c'est déclarer que seule la proportion compte. Lire une formule, c'est donc lire une suite de ces déclarations.

## Comment se servir de cette annexe

Elle se place avant le recueil de formules parce qu'elle en est la clé de lecture : une fois ces quelques silhouettes acquises, le recueil cesse d'être une liste à mémoriser pour devenir une langue à lire. Les entrées sont rangées non par ordre alphabétique mais **par intention** — comprimer, amplifier, aligner, sélectionner, mettre en proportion —, car c'est ainsi qu'on les choisit en pratique. Aucune n'exige de connaissances mathématiques préalables : tout est ramené à une image concrète, puis vérifié sur un petit calcul que vous pouvez refaire de tête.

---

## 1. Comprimer — ramener les grands écarts à l'échelle humaine

Ces trois composants prennent une grandeur qui peut être énorme, ou s'étaler sur plusieurs ordres de grandeur, et la rabattent vers une échelle maniable.

### `log` — le compresseur d'échelles

```
log(1) = 0                                  le point de référence
log(10) = 1, log(100) = 2, log(1000) = 3    (base 10) : ×10 ajoute 1
log(a·b) = log(a) + log(b)                  un produit devient une somme
```

**La forme.** On lit « logarithme de x ». La courbe monte, mais de plus en plus lentement : passer de 1 à 10 fait gagner autant que passer de 10 à 100, ou de 100 à 1000. Chaque fois qu'on *multiplie* l'entrée par dix, on *ajoute* une marche à la sortie. Le logarithme transforme ainsi une échelle multiplicative en une échelle additive — exactement le mode de comptage de nos sens et de nos instruments.

**Ce qu'il fait à une grandeur.** Monter d'une octave en musique double la fréquence ; deux octaves la quadruplent ; trois la multiplient par huit. On *additionne* les octaves quand les fréquences se *multiplient*. Le logarithme est la fonction qui fait ce pont : il convertit des facteurs en marches régulières. C'est pourquoi le décibel (son), le pH (acidité), l'échelle de Richter (séismes) sont tous logarithmiques — ils rendent comparables des grandeurs qui, brutes, s'étaleraient sur des milliards. Appliqué à une donnée, `log` écrase le haut de l'échelle et étire le bas, ce qui colle à notre perception : on distingue mieux deux sons faibles que deux sons assourdissants.

**Où, dans le livre.** L'entropie d'image et les descripteurs d'Haralick (chapitre 13), le PSNR avec son facteur `10·log₁₀` (chapitre 14), l'entropie croisée des fonctions de coût (chapitre 15), et la log-vraisemblance tapie derrière la distance de Mahalanobis (chapitre 3).

**Vérification chiffrée.** Le PSNR, avec une intensité maximale de 255 et une erreur quadratique moyenne de 25, vaut `10·log₁₀(255²/25) = 10·log₁₀(2601) ≈ 34,15 dB`. Surtout, *diviser l'erreur par deux* ajoute toujours `10·log₁₀(2) ≈ 3,01 dB` : sur une échelle logarithmique, « +3 dB » se lit directement « deux fois moins d'erreur ». Le logarithme a transformé un rapport en une différence lisible.

**Le piège.** `log(0)` vaut moins l'infini : toute entropie ou entropie croisée doit ajouter un petit `ε` aux probabilités nulles, sous peine de produire `−inf`. Et la *base* change le résultat d'un facteur constant — `log₂` compte en bits, `ln` (logarithme népérien) en nats, l'écart valant `ln 2 ≈ 0,693`. Toujours préciser la base employée.

### `√` — l'adoucisseur qui rétablit l'unité

```
√0 = 0,  √1 = 1,  √4 = 2,  √9 = 3       monte, mais en se couchant
√(longueur²) = longueur                  défait un carré, rend l'unité d'origine
```

**La forme.** On lit « racine carrée de x ». La courbe monte sans fin mais en s'aplatissant : pour *doubler* la sortie, il faut *quadrupler* l'entrée. C'est l'allure des rendements décroissants — chaque gain supplémentaire coûte de plus en plus cher.

**Ce qu'elle fait à une grandeur.** Sa fonction la plus utile n'est pas d'adoucir, mais de *rétablir une unité*. Un champ carré de 3 mètres de côté a une aire de 9 mètres carrés ; la racine de l'aire redonne le côté, en mètres. De même, la variance d'un jeu de mesures s'exprime dans le *carré* de leur unité (des pixels carrés, des secondes carrées) — une quantité qu'on ne sait pas se représenter. En prendre la racine donne l'écart-type, dans la *même unité* que les données : une dispersion qu'on peut enfin comparer aux mesures elles-mêmes. La racine ramène une « aire » à une « longueur ».

**Où, dans le livre.** La norme L2 et la distance euclidienne (chapitre 3), la magnitude du gradient `√(Iₓ² + Iᵧ²)` (chapitre 6), et le passage de la variance à l'écart-type partout où l'on mesure une dispersion (chapitre 16).

**Vérification chiffrée.** Un gradient dont les composantes valent `Iₓ = 3` et `Iᵧ = 4` a pour magnitude `√(3² + 4²) = √(9 + 16) = √25 = 5` : c'est le théorème de Pythagore qui ramène deux variations perpendiculaires à une seule longueur. Côté dispersion, une variance de 16 px² donne un écart-type de 4 px — homogène aux données.

**Le piège.** La racine d'un nombre négatif n'existe pas (elle produit `NaN`) : une variance calculée numériquement peut sortir très légèrement négative par arrondi, et il faut la borner à zéro avant la racine. Par ailleurs, `√(Iₓ² + Iᵧ²)` présente un *coin* non dérivable à l'origine (gradient nul) ; on ajoute alors un petit `ε` sous la racine, `√(Iₓ² + Iᵧ² + ε)`, pour lisser ce point.

### `σ` — la sigmoïde, l'interrupteur en douceur

```
σ(x) = 1 / (1 + exp(−x))
σ(−∞) → 0,   σ(0) = 0,5,   σ(+∞) → 1        un « S » qui va de 0 à 1
σ(x) + σ(−x) = 1                             symétrique autour de 0
```

**La forme.** On lit « sigmoïde de x ». C'est un S allongé : tout en bas (loin à gauche) la sortie vaut presque 0, tout en haut (loin à droite) presque 1, et le passage de l'un à l'autre est doux, centré sur 0 où la sortie vaut exactement la moitié.

**Ce qu'elle fait à une grandeur.** Un variateur de lumière ne saute pas brutalement d'éteint à allumé : il monte progressivement, et passé un certain point pousser encore le curseur ne change presque plus rien. La sigmoïde est ce variateur. Elle prend n'importe quel nombre, si grand ou si négatif soit-il, et le rabat dans l'intervalle de 0 à 1 — un nombre qui se lit comme une *probabilité* ou comme l'ouverture d'une *porte*. C'est la version *douce* d'une marche tout-ou-rien (voir le seuil `1[·]`, §4).

**Où, dans le livre.** La sortie d'une décision binaire et les portes des réseaux de neurones (chapitre 15) ; c'est exactement le softmax à deux classes (§5) ; et c'est la version continue du seuil dur `s(x)` du Local Binary Pattern (chapitre 13).

**Vérification chiffrée.** `σ(2) = 1/(1 + e⁻²) ≈ 0,881` et `σ(−2) ≈ 0,119` : un score de +2 se lit « environ 88 % oui », un score de −2 « environ 12 % ». Leur somme vaut 1, ce qui exprime la symétrie : ce que l'un gagne, l'autre le perd.

**Le piège.** Loin de 0, la courbe est presque plate : sa pente s'annule (à `σ = 0,99`, la pente ne vaut que `0,0099`). En apprentissage, cette saturation produit le fameux « gradient qui s'évanouit » — un neurone saturé ne reçoit plus de signal pour se corriger.

---

## 2. Amplifier et séparer — creuser les différences

À l'opposé du groupe précédent, ces composants accentuent les écarts au lieu de les tasser.

### Les puissances — `x²`, et au-delà

```
x²            une parabole : plate près de 0, de plus en plus raide ; (−x)² = x² (aveugle au signe)
xⁿ, n grand   sur [0,1] : reste près de 0, puis bondit vers 1 — creuse le contraste
```

**La forme.** On lit « x au carré », « x puissance n ». Le carré est une cuvette symétrique : au fond, près de zéro, la courbe est presque plate — les petits écarts comptent à peine ; sur les flancs elle s'élève de plus en plus raide — les grands écarts comptent énormément. Et le carré est *aveugle au signe* : `(−3)²` et `3²` valent tous deux 9.

**Ce qu'il fait à une grandeur.** Étirer un ressort de 2 cm demande quatre fois plus d'énergie que de l'étirer de 1 cm, pas deux fois : l'énergie suit le *carré* de l'allongement (`E = ½k·x²`). C'est le geste du carré — transformer un écart en un *coût* qui punit les grands écarts hors de proportion, tout en ignorant leur direction. Ce choix est la fondation des moindres carrés : parce que la dérivée de `x²` est `2x`, une simple droite, minimiser une somme de carrés se résout par des équations linéaires, et la solution optimale se trouve être la *moyenne*. Pour les puissances plus élevées, l'effet s'exagère : sur l'intervalle de 0 à 1, `xⁿ` avec `n` grand reste collé à zéro puis bondit vers 1 tout près de 1 — il creuse le contraste, façon « le gagnant rafle presque tout ».

**Où, dans le livre.** La distance L2, la variance et les moments (chapitres 2 et 3), l'erreur quadratique moyenne (chapitre 14), la partie « près de zéro » de Huber et du Smooth-L1 (chapitres 15 et 16), la variance inter-classe d'Otsu (chapitre 12) ; côté puissances élevées, les moments d'ordre élevé qui « regardent loin du centre » (chapitre 2), l'exposant `γ` de la focal loss (chapitre 15) et le poids `(i−j)²` du contraste GLCM (chapitre 13).

**Vérification chiffrée.** Sur quatre erreurs `{1, 1, 1, 5}`, l'aberrant (le 5) pèse, en valeur absolue, `5/8 = 62 %` du total. Au carré, il pèse `25/28 = 89 %`. Le carré reporte presque tout le poids sur l'aberrant — c'est précisément pourquoi la méthode des moindres carrés est si sensible aux valeurs aberrantes (annoncé au chapitre 16, rappelé à l'entrée `|·|`). Pour l'exposant, la focal loss `(1−ŷ)^γ` avec `γ = 2` multiplie la perte d'un exemple facile (`ŷ = 0,9`) par `(0,1)² = 0,01` — divisée par cent — tandis qu'un exemple difficile (`ŷ = 0,1`) est multiplié par `(0,9)² = 0,81`, à peine réduit. L'exposant déplace l'effort d'apprentissage vers les cas durs.

**Le piège.** Le carré *change l'unité* (le carré d'une longueur est une aire) : il faut souvent reprendre une racine pour revenir à une grandeur lisible (voir `√`). Et il fait dominer les aberrants (les 89 % ci-dessus) — il n'est donc pas robuste. Les puissances de base supérieure à 1 explosent vite numériquement.

### `exp(−·)` — le poids qui escompte, sans jamais s'annuler

```
exp(−x)                    part de 1, décroît, tend vers 0 sans l'atteindre ni passer négatif
exp(−x²)                   la cloche : sommet plat en 0, puis effondrement
exp(a + b) = exp(a)·exp(b) une somme dans l'exposant devient un produit au-dehors
```

**La forme.** Une courbe qui descend de 1 vers 0 sans jamais y toucher, et sans jamais devenir négative. Sa particularité n'est pas de décroître — beaucoup de fonctions le font — mais *la manière*. Chaque unité supplémentaire ne retranche pas une part fixe du poids : elle le multiplie par un même facteur, un peu moins que un (`1/e ≈ 0,37` pour `exp(−x)`). C'est l'arithmétique d'une demi-vie, ou d'un escompte : ce qui reste constant n'est pas la quantité perdue, c'est le taux. La variante en cloche `exp(−x²)` ajoute un plateau près de zéro — les petites valeurs sont à peine pénalisées — avant un effondrement d'autant plus brutal qu'on s'éloigne.

**Ce qu'elle fait à une grandeur.** Elle prend un coût, une distance, un score — une quantité potentiellement grande et sans borne — et la rabat en un poids positif entre 0 et 1, en écrasant les grandes valeurs. C'est l'outil standard pour transformer « loin = sans importance » en un nombre.

Un filtre à densité neutre laisse passer une fraction de la lumière — la moitié, disons. Empilez-en deux et il n'en passe plus que le quart : les fractions transmises se *multiplient*. Le photographe, lui, compte en *stops*, et deux filtres d'un stop chacun font deux stops — sur cette échelle, les épaisseurs s'*additionnent*. Ajouter d'un côté, multiplier de l'autre : l'exponentielle est la fonction qui fait le pont entre ces deux comptages. Ce qu'on ajoute dans l'exposant ressort en produit au-dehors, et c'est tout le contenu de l'identité `exp(a+b) = exp(a)·exp(b)`.

De ce pont découle un fait qui paraîtrait sinon arbitraire. Le poids gaussien en deux dimensions dépend de la distance au centre par `x² + y²` — une somme. Parce que l'exponentielle change cette somme en produit, le poids 2D se scinde exactement en un poids selon x multiplié par un poids selon y : deux filtres empilés, l'un agissant le long des lignes, l'autre le long des colonnes. On peut donc flouter en deux passes 1D successives plutôt qu'en une passe 2D — c'est la séparabilité du gaussien (§5.1), et la raison pour laquelle un flou reste rapide même avec un grand noyau.

**Où, dans le livre.** Le noyau gaussien du filtrage (chapitre 5) et la fenêtre de pondération du tenseur de structure (chapitre 6) ; le softmax, la focal loss et l'InfoNCE des fonctions de coût (chapitre 15) ; la densité gaussienne derrière la distance de Mahalanobis (chapitre 3) ; les noyaux RBF des méthodes à noyau (chapitre 8).

**Vérification chiffrée.** Sur le poids gaussien `exp(−x²/2σ²)`, chaque pas de σ n'enlève pas une part fixe — il escompte : à `x = σ`, poids `0,607` ; à `2σ`, `0,135` ; à `3σ`, `0,011`. Au-delà de quelques σ, le poids n'est plus seulement petit, il est nul pour le calcul : voilà le support quasi borné du flou gaussien.

**Le piège.** `exp` d'un grand argument déborde vers l'infini (`exp(1000)` → `inf`) : tout softmax sérieux soustrait d'abord le maximum, `exp(zᵢ − max z)`, ce qui ne change pas le résultat mais évite l'explosion (l'astuce log-sum-exp). À l'autre bout, `exp(−grand)` tombe à zéro exact par underflow : un poids « doux » devient un zéro dur — souvent bénin, gênant si l'on en reprend ensuite le logarithme. Enfin, le σ vit *dans* l'exposant : il règle le taux d'oubli, pas une portée linéaire. Doubler σ ne double pas le rayon d'influence.

---

## 3. Aligner — mesurer un accord de direction

Ces composants ne mesurent pas une quantité mais un *accord* : à quel point deux directions pointent dans le même sens.

### `cos` et `sin` — la boussole

```
cos(0°) = 1 (alignés)   cos(90°) = 0 (perpendiculaires)   cos(180°) = −1 (opposés)
cos et sin : une onde entre −1 et +1, de période 360° (l'angle « fait le tour »)
```

**La forme.** On lit « cosinus », « sinus ». Le cosinus oscille entre −1 et +1 : il vaut 1 quand deux directions coïncident, 0 quand elles sont perpendiculaires, −1 quand elles s'opposent. Le sinus est la même onde décalée d'un quart de tour ; il mesure la composante *perpendiculaire* là où le cosinus mesure la composante *alignée*.

**Ce qu'ils font à une grandeur.** Plantez un bâton et éclairez-le bien à la verticale : l'ombre qu'il projette sur le sol est la plus longue quand il est couché dans la direction du sol, et nulle quand il est dressé tout droit. Le cosinus, c'est cette longueur d'ombre — quelle part d'une direction se couche le long d'une autre. Il mesure donc un *alignement*, ramené entre −1 et +1 quelles que soient les longueurs en jeu. Pris ensemble, sinus et cosinus encodent un angle ; et ils rendent surtout manipulable une grandeur *cyclique* — un angle qui « fait le tour » — au moyen de deux nombres ordinaires, de sorte que 359° et 1° soient reconnus comme proches.

**Où, dans le livre.** La similarité cosinus (chapitre 3), la transformée de Hough `ρ = x·cos θ + y·sin θ` (chapitre 10), les rotations et la projection caméra (chapitre 8), la base de la DCT (chapitre 10), l'orientation du gradient (chapitre 6).

**Vérification chiffrée.** Deux vecteurs `a = (1, 0)` et `b = (1, 1)` ont pour cosinus `(1·1 + 0·1) / (1 · √2) = 1/1,414 ≈ 0,707`, soit un angle de 45°. Pour `b = (−1, 0)`, le cosinus vaut −1 : 180°, directions opposées.

**Le piège.** Comme l'angle « fait le tour », `arctan` ne distingue pas `(x, y)` de `(−x, −y)` : il faut `arctan2`, qui lit séparément les deux signes pour rendre l'angle complet de 0 à 360° (rappel du chapitre 6 sur l'orientation du gradient). Par ailleurs, la similarité cosinus *ignore la longueur* : deux vecteurs de même direction mais de tailles très différentes ont une similarité de 1 — vertu pour comparer des « directions », piège si l'amplitude compte.

### Le produit scalaire `a·b` — l'accord brut

```
a·b = a₁b₁ + a₂b₂ + …       somme des produits terme à terme
a·b > 0 même sens,  = 0 perpendiculaires,  < 0 sens opposés
a·b = |a|·|b|·cos(angle)    → cos est le produit scalaire « normalisé »
```

**La forme.** On lit « a scalaire b ». C'est une simple somme de produits terme à terme. Le résultat est positif si les deux vecteurs pointent dans des sens voisins, nul s'ils sont perpendiculaires, négatif s'ils s'opposent.

**Ce qu'il fait à une grandeur.** Pour pousser une charge, seule la part de la force *alignée* sur le déplacement travaille ; la part perpendiculaire ne sert à rien (c'est la définition physique du travail). Le produit scalaire ne retient que cette part alignée — mais sans la normaliser : il porte à la fois l'accord de direction *et* les longueurs. Divisez-le par les deux longueurs, et vous retombez sur le cosinus (le lien entre les deux entrées). Fait capital : la réponse de tout filtre linéaire est un produit scalaire entre le noyau et l'imagette qu'il recouvre (chapitre 5).

**Où, dans le livre.** La réponse d'un filtre `= noyau · imagette` (chapitre 5), la similarité cosinus une fois normalisé (chapitre 3), toutes les projections.

**Vérification chiffrée.** Le noyau-gradient `(1, 0, −1)` appliqué à l'imagette `(10, 10, 40)` donne `1·10 + 0·10 − 1·40 = −30` : une forte transition (le bord) se lit comme un grand produit scalaire négatif. Un filtre « répond fort » là où l'image ressemble à son motif.

**Le piège.** Le produit scalaire grandit avec la longueur des vecteurs : il compare donc mal des vecteurs de tailles différentes, d'où la normalisation par les longueurs — qui redonne le cosinus.

### `arctan` et `arctan2` — de la direction vers l'angle

```
arctan(0) = 0°,   arctan(1) = 45°,   arctan(x) → 90° quand x → +∞     prend une pente, rend un angle
arctan ne voit que le rapport y/x  →  plage −90°…+90°  (ne sait pas le quadrant)
arctan2(y, x) lit les deux signes séparément  →  plage −180°…+180°  (angle complet)
```

**La forme.** On lit « arc-tangente ». Là où cosinus et sinus partent d'un angle pour donner une direction, l'arc-tangente fait le chemin *inverse* : elle part d'une direction et rend l'angle. `arctan` prend une pente — un rapport « montée sur avancée » — et renvoie l'inclinaison correspondante : pente nulle → 0°, pente de 1 (autant de montée que d'avancée) → 45°, pente infinie (vertical) → 90°.

**Ce qu'elles font à une grandeur.** Une girouette transforme la direction du vent en un cap qu'on peut lire sur le cadran ; l'arc-tangente fait cela pour un vecteur. Mais une difficulté se cache dans le rapport `y/x`. Annoncer la pente d'une route — « elle monte d'un mètre pour un mètre parcouru » — ne dit pas si vous la montez ou la descendez : le même rapport vaut dans les deux sens. Il manque la *direction de parcours*. C'est exactement l'angle mort de `arctan`, qui n'entend que le rapport : il confond `(x, y)` et `(−x, −y)`, deux directions opposées, et ne sait donc placer l'angle que dans une demi-plage. `arctan2(y, x)` écoute en plus *quel signe* portent séparément `x` et `y` — donc dans quel quadrant pointe le vecteur — et rend l'angle complet, de −180° à +180°.

**Où, dans le livre.** L'orientation du gradient `θ = arctan2(Iᵧ, Iₓ)` (chapitre 6), l'orientation de l'ellipse d'inertie d'une forme `θ = ½·arctan2(2μ₁₁, μ₂₀ − μ₀₂)` (chapitre 2), la direction du flot optique (chapitre 9), la phase d'une réponse de Fourier ou de Gabor (chapitre 10).

**Vérification chiffrée.** Un gradient `(Iₓ, Iᵧ) = (1, 1)` pointe à `arctan2(1, 1) = 45°`. Le gradient opposé `(−1, −1)` a *le même rapport* `y/x = 1`, donc `arctan(1) = 45°` à nouveau — faux, c'est la direction inverse. `arctan2(−1, −1) = −135°` rétablit le bon quadrant : 180° plus loin, comme il se doit. Sans `arctan2`, les deux bords opposés d'un trait fin se verraient attribuer la même orientation.

**Le piège.** L'ordre des arguments est `arctan2(y, x)` — l'ordonnée d'abord, l'abscisse ensuite : l'inverser fait pivoter tous les angles de 90°. La convention d'axe image (l'axe `y` pointe vers le *bas*) inverse le signe de l'angle par rapport au repère mathématique usuel : à signaler dès qu'on rapporte une orientation. Enfin, les angles « font le tour » (rappel de l'entrée `cos`/`sin`) : un écart entre angles se prend modulo 360°, sinon 359° et 1° semblent distants de 358° alors qu'ils ne le sont que de 2°.

---

## 4. Sélectionner et trancher — choisir sans compromis

Ici, plus de moyenne pondérée : on choisit, on replie, on décide.

### `max` / `min` — le sélecteur

```
max(5, 2, 8) = 8        min(5, 2, 8) = 2
on retient une valeur, on jette les autres — aucune moyenne
```

**La forme.** On lit « maximum », « minimum ». Ce n'est pas une courbe lisse mais un *choix* : la sortie est l'une des entrées — la plus grande, ou la plus petite — et toutes les autres sont purement ignorées.

**Ce qu'ils font à une grandeur.** L'eau qui s'écoule trouve le point le plus bas ; le podium ne photographie que le vainqueur. Le min et le max *sélectionnent* au lieu de mélanger. Ils remplacent la grammaire « pondérer puis sommer » des filtres par une grammaire fondée sur l'*ordre* — celle de la morphologie, qui vit dans un treillis plutôt que dans un espace vectoriel (chapitre 11). Une seule valeur extrême décide de tout, ce qui les rend tranchants mais fragiles. Ce sont des opérations dures, discontinues.

**Où, dans le livre.** La morphologie — l'érosion est un min, la dilatation un max (chapitre 11) ; le max-pooling ; la distance de Hausdorff, un max de plus-proches-distances (chapitre 3) ; la suppression des non-maxima qui garde la boîte de confiance maximale (chapitre 4). Le softmax en est le cousin *doux* — son nom dit « maximum adouci » (§5).

**Vérification chiffrée.** Une érosion 1D du signal `(5, 2, 8)` par une sonde de largeur 3 renvoie le min, `2` : l'érosion ronge vers le bas. La dilatation renvoie le max, `8`. Et la distance de Hausdorff : un seul point éloigné fixe à lui seul la valeur, d'où sa fragilité aux aberrants (chapitre 3).

**Le piège.** `max` et `min` sont discontinus et non dérivables : on ne peut pas les optimiser directement par descente de gradient, d'où les substituts « doux » (softmax, soft-min) en apprentissage. Et comme un seul point extrême domine, ils sont fragiles à une valeur aberrante isolée (la fragilité de Hausdorff, chapitre 3).

### La valeur absolue `|·|` — la distance sans direction

```
|3| = 3    |−3| = 3        un « V » : on replie le négatif sur le positif
coin pointu en 0
```

**La forme.** On lit « valeur absolue de x ». C'est un V : la branche négative est repliée sur la positive. Seule l'ampleur subsiste, avec un coin pointu en zéro.

**Ce qu'elle fait à une grandeur.** Un compteur kilométrique compte les kilomètres parcourus, que vous rouliez en avant ou en marche arrière : seule la quantité de route compte, pas le sens. La valeur absolue transforme de même un écart *signé* en une simple ampleur. Une somme de telles ampleurs — la norme L1 — pénalise les erreurs *proportionnellement* (et non hors de proportion comme le carré) : elle est donc plus robuste aux aberrants, et favorise des solutions parcimonieuses, proches de la médiane.

**Où, dans le livre.** La distance L1 / Manhattan (chapitre 3), l'erreur absolue moyenne, la partie « loin de zéro » de Huber et du Smooth-L1 (chapitres 15 et 16), la médiane qui minimise `Σ|écart|` (lien avec la MAD, chapitre 16), l'homogénéité GLCM `1/(1+|i−j|)` (chapitre 13).

**Vérification chiffrée.** Sur les mêmes erreurs `{1, 1, 1, 5}` que l'entrée carré : en valeur absolue, l'aberrant pèse `5/8 = 62 %` du total, contre `89 %` au carré. La valeur absolue laisse l'aberrant peser bien moins — c'est la racine de la robustesse de la norme L1.

**Le piège.** Le coin en zéro rend la fonction non dérivable à l'origine ; le Smooth-L1 arrondit précisément ce coin pour récupérer un gradient propre (lien chapitre 15). Et, aveugle au signe, la valeur absolue ne distingue pas une surestimation d'une sous-estimation.

### L'indicatrice / le seuil `1[·]` — le juge binaire

```
1[x ≥ t] = 1 si x ≥ t, sinon 0       une marche : pas d'entre-deux
```

**La forme.** On lit « un, si la condition est vraie ». C'est une marche : 0 en deçà du seuil, 1 au-delà. La décision la plus tranchée qui soit — aucun entre-deux.

**Ce qu'elle fait à une grandeur.** Le portique d'un manège mesure votre taille face à une barre : ou vous êtes assez grand, ou vous ne l'êtes pas ; un millimètre décide, et dépasser largement la barre ne compte pas plus que la dépasser de justesse. L'indicatrice transforme de même une grandeur continue en un *oui/non*. C'est la brique de base de la binarisation et du comptage — au prix d'oublier, par construction, *de combien* on dépasse.

**Où, dans le livre.** Le seuillage et la binarisation (chapitre 12, où Otsu choisit *où* placer la marche), le `s(x) = 1 si x ≥ 0` du LBP (chapitre 13), le comptage des vrais/faux positifs via un seuil d'IoU (chapitre 4) ; un masque n'est rien d'autre que l'indicatrice d'appartenance à une région.

**Vérification chiffrée.** Un seuil `t = 128` appliqué aux pixels `(120, 130, 250)` donne `(0, 1, 1)`. Notez que 130 et 250 deviennent identiques — la marche oublie l'écart au seuil. Tout l'art est alors de bien placer `t`, ce qu'Otsu automatise (chapitre 12).

**Le piège.** Près d'une frontière bruitée, un pixel qui oscille entre 127 et 129 fait *clignoter* la sortie ; la sigmoïde est le remplaçant doux et dérivable (§1). Et, l'indicatrice jetant toute l'information d'amplitude, le choix du seuil décide de tout.

---

## 5. Mettre en proportion — rendre les choses comparables

Ces composants ne mesurent pas une grandeur isolée : ils la rapportent à une référence.

### La division / le rapport — la mise en proportion

```
a / b : « combien de b dans a ? »          on ramène a à une référence b
un rapport de deux grandeurs de même unité est sans dimension (sans unité)
```

**La forme.** On lit « a divisé par b », ou « le rapport de a à b ». La division compare une grandeur à une référence ; quand les deux ont la même unité, le résultat n'a plus d'unité du tout — il est *sans dimension*.

**Ce qu'elle fait à une grandeur.** Un prix au kilo, une moyenne au bâton, un taux de change : le nombre brut ne dit rien tant qu'on ne l'a pas divisé par une référence pour le rendre comparable. La division retire ainsi une échelle ou une unité, transforme des effectifs en proportions, des coûts en taux. Beaucoup de descripteurs de forme sont des rapports *justement* pour devenir insensibles à la taille (chapitre 1).

**Où, dans le livre.** La circularité, la solidité, l'étendue (chapitre 1, tous des rapports), l'IoU (chapitre 4), la précision et le rappel (chapitre 4), l'histogramme normalisé en probabilités, le coefficient de corrélation (division par les écarts-types).

**Vérification chiffrée.** La circularité vaut `4π·A / P²`. Pour un disque de rayon `r` : `A = π r²` et `P = 2π r`, donc `4π · π r² / (2π r)² = 4π² r² / 4π² r² = 1`. Le rayon se simplifie : la mesure ne dépend pas de la taille (invariante à l'échelle) et vaut 1 pour le disque parfait. ∎ (chapitre 1)

**Le piège.** Une division par zéro, ou par presque-zéro, explose : sur une région minuscule ou vide, circularité et IoU deviennent indéfinies — on ajoute un `ε` ou un garde-fou. Et un rapport *cache les tailles absolues* : une cellule minuscule et une cellule énorme peuvent partager la même circularité de 1. Le rapport oublie l'échelle — ce pour quoi, précisément, on l'a choisi.

### `softmax` — le partage proportionnel

```
softmax(z)ᵢ = exp(zᵢ) / Σⱼ exp(zⱼ)
des scores quelconques → des nombres positifs qui somment à 1 (des probabilités)
```

**La forme.** On lit « softmax ». Il prend une liste de scores, en exponentie chacun, puis divise par le total. La sortie : des nombres positifs qui somment à 1 — une distribution de probabilités. Le plus grand score reçoit la part du lion, mais aucun ne reçoit zéro.

**Ce qu'il fait à une grandeur.** Partager une cagnotte au prorata de la réputation de chacun : non pas « le gagnant rafle tout » (ce serait le `max`, §4), mais le favori emporte la plus grosse part, proportionnelle à l'exponentielle de son score. Une élection *douce*. Le softmax assemble en fait deux silhouettes déjà vues — l'exponentielle (pour rendre positif et écarter les scores en *rapports*) et la division (pour normaliser à 1).

**Où, dans le livre.** La classification (chapitre 15), l'attention, l'InfoNCE de CLIP et SimCLR (chapitre 15) ; cousin doux du `max` (§4).

**Vérification chiffrée.** Pour les scores `(2, 1, 0)` : les exponentielles valent `(7,39 ; 2,72 ; 1,00)`, de somme `11,11` ; les probabilités sont donc `(0,665 ; 0,245 ; 0,090)`, qui somment bien à 1. L'écart *additif* de 1 entre les deux premiers scores ressort en un *rapport* de probabilités `7,39 / 2,72 = 2,72 = e` : la différence est devenue un facteur multiplicatif (rappel de l'entrée `exp`).

**Le piège.** Des scores grands font déborder l'exponentielle ; on soustrait d'abord le maximum, `exp(zᵢ − max z)`, sans changer le résultat (astuce log-sum-exp, déjà signalée à l'entrée `exp`). Et la « température » `τ` — diviser les scores par `τ` avant le softmax — durcit ou adoucit le partage : `τ` petit tend vers le `max` dur, `τ` grand vers le partage uniforme.

---

## Tableau récapitulatif

| Composant | Silhouette en un mot | Ce qu'il fait à une grandeur | Où il revient |
|---|---|---|---|
| `log` | compresse les échelles | un produit devient une somme ; colle à la perception | entropie, PSNR, entropie croisée |
| `√` | rétablit l'unité | ramène une « aire » à une « longueur » | norme L2, écart-type, magnitude du gradient |
| `σ` (sigmoïde) | interrupteur doux | rabat tout réel dans 0–1, lu comme une probabilité | sorties binaires, softmax 2 classes |
| `x²`, `xⁿ` | amplifie les écarts | punit les grands écarts hors de proportion, aveugle au signe | L2, MSE, variance, moments, focal loss |
| `exp(−·)` | escompte | additif → multiplicatif ; distance → poids du proche | gaussien, softmax, RBF, Mahalanobis |
| `cos`, `sin` | boussole | mesure un alignement entre directions, gère le cyclique | similarité cosinus, Hough, rotations |
| `a·b` | accord brut | part alignée, longueurs comprises ; normalisé → cos | réponse de filtre, projections |
| `arctan2` | direction → angle | retrouve l'angle, quadrant compris (là où `arctan` le perd) | orientation du gradient et des formes, flot |
| `max` / `min` | sélecteur | retient un extrême, jette le reste ; dur, fragile | morphologie, Hausdorff, NMS |
| `|·|` | ampleur sans signe | écart signé → ampleur ; pénalité proportionnelle, robuste | L1, MAE, Huber, médiane |
| `1[·]` | juge binaire | grandeur continue → oui/non ; oublie l'amplitude | seuillage, LBP, comptage VP/FP |
| `a / b` | mise en proportion | retire une échelle/unité ; rend comparable | circularité, IoU, précision/rappel |
| `softmax` | partage proportionnel | scores → probabilités (exp puis division) | classification, attention, InfoNCE |

---

## Lire un symbole, c'est lire une décision

L'introduction promettait qu'aucune formule de ce livre n'est un sortilège, et que derrière chaque symbole se cache une image qu'on peut dessiner sur un coin de table. Cette annexe en donne le vocabulaire. Ces composants sont l'alphabet ; les chapitres en font des phrases.

Reste une remarque qui referme le fil de tout l'ouvrage. Chacun de ces composants est lui-même un choix sur ce qui compte. Le carré déclare que les grands écarts comptent par-dessus tout ; la valeur absolue, que seule l'ampleur compte, pas le sens ; le cosinus, que seule la direction compte, pas la longueur ; la division, que seule la proportion compte, pas la taille. Le maximum refuse le compromis ; la sigmoïde le réintroduit. Jusque dans le moindre symbole, donc, la loi du livre tient : *choisir, c'est déclarer ce qui compte*. Quand vous lirez le recueil qui suit, ne lisez pas des suites de signes — lisez, à chaque symbole, la décision qu'il encode.
