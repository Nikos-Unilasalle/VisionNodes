#import "@preview/bookly:4.0.0": *

// --- Helpers locaux ---
#let subtitle(t) = block(above: 0.2em, below: 1.2em, sticky: true)[#text(style: "italic", fill: rgb("#64748b"))[#t]]

#let figtodo(id, desc) = block(above: 2em, below: 2em, width: 100%)[
  #block(width: 100%, inset: (x: 16pt, y: 14pt), radius: 6pt,
    fill: rgb("#fdf3f5"), stroke: 1pt + rgb("#d0a0aa"))[
    #grid(columns: (1fr, auto), column-gutter: 14pt, align: horizon,
      align(left)[
        #text(size: 0.78em, weight: "bold", fill: rgb("#c1002a"), font: "Roboto")[▪ IMAGE]
        #v(0.4em)
        #text(size: 0.9em, fill: rgb("#334155"), font: "Roboto")[#raw(id)]
      ],
      box(width: 42pt, height: 34pt, radius: 3pt, fill: rgb("#fff0f2"), stroke: 1pt + rgb("#c1002a"), clip: true)[
        #align(center)[
          #v(5pt)
          #circle(radius: 4pt, fill: rgb("#c1002a").lighten(35%), stroke: none)
          #v(2pt)
          #polygon(fill: rgb("#c1002a").lighten(55%), stroke: none,
            (0pt, 9pt), (13pt, 0pt), (26pt, 9pt))
          #v(2pt)
        ]
      ]
    )
  ]
]

#let figfull(path) = block(above: 1em, below: 1.4em, width: 100%)[#image(path, width: 100%)]
#let canvas(body) = tip-box(title: "Dans VNStudio")[
  #show heading: it => block(above: 0.5em, below: 0em)[
    #text(font: "Roboto", weight: "regular", size: 0.95em)[#it.body]
  ]
  #set heading(numbering: none)
  #body
]


#chapter(title: [Fonctions de coût], toc: false)[

#block(above: 0pt, below: 2em, width: 100%)[#image("/illustrations/chap15.jpeg", width: 100%)]

#pagebreak()
#block(above: 0em, below: 1em)[
  #grid(columns: (auto, 1fr), column-gutter: 0.6em, align: horizon,
    box(width: 3pt, height: 1.2em, fill: rgb("#c1002a"), radius: 1.5pt),
    text(weight: "bold", font: "Roboto", fill: rgb("#1e293b"))[Table des matières])
]
#suboutline(target: heading.where(outlined: true, level: 2))
#pagebreak()

#subtitle[Un réseau n'apprend pas de l'objectif qu'on vise, mais de la pente d'un substitut. Concevoir un coût, c'est sculpter le versant pour que la bille roule jusqu'à la cible — sans jamais viser la cible elle-même.]

#info-box(title: "Ce que ce chapitre couvre — et ce qu'il ne couvre pas.")[
Un réseau profond n'apprend rien par lui-même : il descend une pente. Ce chapitre traite la quantité qui _crée_ cette pente — la fonction de coût — parce que c'est elle qui encode ce que « réussir » veut dire, et c'est là que se prennent les décisions de vision (quelle erreur punir, quel déséquilibre corriger, quelle géométrie récompenser). Les *architectures* — combien de couches, lesquelles, dans quel ordre — relèvent d'un autre ouvrage ; on n'en donne ici que le strict nécessaire pour comprendre d'où vient le gradient. La section 15.0 pose les trois opérations qui reviennent dans presque tout réseau de vision, non pour les cataloguer, mais parce que chacune, comme un coût, encode un a priori sur ce qui compte. Le reste du chapitre est consacré aux coûts.
]

---

Un réseau de neurones n'apprend rien de l'objectif qu'on lui fixe en pensée : il apprend de la *dérivée* de cet objectif. Entre la métrique qui nous intéresse (la justesse d'une classification, le chevauchement d'une détection, la ressemblance perçue d'une image générée) et ce que la descente de gradient peut réellement minimiser, il y a un fossé : la plupart des métriques sont discrètes, non dérivables, ou plates sur de vastes régions. La fonction de coût est le pont. Elle n'est pas un score mais une *source de gradient* — ce qui compte n'est pas tant sa valeur que la forme de sa pente : où elle pousse fort, où elle s'aplatit, où elle pointe à côté de la cible.

Le fil du chapitre tient en une phrase : *on n'optimise jamais la métrique qu'on vise, mais un substitut dérivable.* Concevoir un coût, c'est sculpter un paysage de gradients qui conduit vers la métrique sans jamais la toucher. Chaque section pose la même question : quelle est la forme du gradient, et où trahit-il la métrique cible — par *saturation* (gradient nul là où il faudrait apprendre), par *explosion* (un exemple aberrant écrase tous les autres), ou par *désalignement* (la pente descend, mais pas vers ce qu'on veut) ?

Les fonctions de coût recyclent presque tout le livre, mais en changent le statut : un score d'évaluation devient un objectif d'optimisation, ce qui impose une contrainte nouvelle — la dérivabilité. La distance L2 redevient le coût MSE ; la similarité cosinus (chapitre 3) est le cœur d'InfoNCE ; l'IoU et le Dice (chapitre 4), métriques d'évaluation, deviennent ici des coûts ; l'erreur de reprojection (chapitre 8) est déjà un coût ; SSIM et LPIPS (chapitre 14) deviennent des coûts perceptuels ; smooth L1 _est_ le M-estimateur de Huber (chapitre 16). Le couple métrique / coût prolonge le chapitre 4 (« aucune métrique unique ne capture tout ») d'un cran : non seulement aucun coût ne capture tout, mais le coût n'est même pas la chose qu'on veut — il en est l'approximation dérivable.

=== Un peu de vocabulaire avant de commencer

- *Fonction de coût (Loss)* : Un score numérique calculant l'erreur commise par le modèle par rapport à la vérité attendue, et que l'on cherche à minimiser.
- *Gradient descendant* : La méthode d'optimisation qui ajuste pas à pas les paramètres du réseau en suivant la pente descendante de la fonction de coût.
- *Rétropropagation (backpropagation)* : L'algorithme calculant l'influence de chaque paramètre du réseau sur l'erreur finale pour orienter les ajustements.

---

=== Section 15.0 — Trois opérations, trois a priori

On présente souvent ces opérations comme des « briques » d'architecture, neutres et interchangeables. Elles ne le sont pas. Chacune impose une hypothèse forte sur la structure du signal — et c'est précisément cette hypothèse qui réduit le nombre de paramètres à apprendre et oriente ce que le réseau _peut_ voir. Trois suffisent à porter presque toute la vision profonde.

==== La convolution comme couche — a priori de localité et d'équivariance

*Définition.* Une couche convolutive produit le canal de sortie `o` à partir des canaux d'entrée `I_c` par :

```
O_o(x,y) = b_o + Σ_c Σ_{i,j} I_c(x+i, y+j) · K_{o,c}(i,j)        puis  σ(·)  (non-linéarité)
```

C'est la convolution du chapitre 5, à une différence décisive : le noyau `K` n'est plus posé par le concepteur, il est *appris* par descente de gradient.

*Économie de paramètres.* Relier une carte `H×W` à une autre par une couche dense coûte `(H·W)²` poids. Une couche convolutive de noyau `k×k` impose deux contraintes : *localité* (un pixel de sortie ne dépend que d'un voisinage `k×k`) et *partage des poids* (le même `K` sur toute l'image). Le coût tombe à `k²` poids par paire de canaux, indépendant de la taille de l'image. ∎ Ce partage _est_ l'hypothèse : un motif utile en un point l'est partout — c'est l'*équivariance par translation*. Déplacez l'entrée, la sortie se déplace d'autant.

*Angle mort.* L'équivariance par translation est exactement ce qu'on veut pour détecter un même motif n'importe où ; c'est exactement ce qu'on ne veut pas quand la position absolue compte (un ciel est en haut, une route en bas). D'où les correctifs : _coordconv_, plongements de position, ou simplement des couches denses en fin de réseau.

*Paramètres opérationnels (VNStudio / Python).* Dans les frameworks d'apprentissage profond (comme PyTorch avec `nn.Conv2d`), les paramètres géométriques contrôlent la taille des cartes de sortie et le champ récepteur :
- *Taille du noyau (`kernel_size`)* : Dans VNStudio, ce paramètre correspond au champ *Kernel Size* ; en PyTorch, il correspond à l'argument `kernel_size` dans `torch.nn.Conv2d`.
- *Pas de glissement (`stride`)* : Dans VNStudio, ce paramètre correspond au champ *Stride* ; en PyTorch, il correspond à l'argument `stride` dans `torch.nn.Conv2d`. Si `stride = 1`, le filtre glisse pixel par pixel. Si `stride = 2`, il saute un pixel sur deux, ce qui réduit de moitié la résolution spatiale de sortie (faisant office de sous-échantillonnage intégré).
- *Remplissage des bords (`padding`)* : Dans VNStudio, ce paramètre correspond au champ *Padding* ; en PyTorch, il correspond à l'argument `padding` dans `torch.nn.Conv2d`. C'est le nombre de pixels de marge ajoutés aux bords (ex. : `padding = 1` pour un noyau 3×3) pour que la carte de sortie conserve exactement les mêmes dimensions spatiales que celle d'entrée.
- *Dilatation (`dilation`)* : Dans VNStudio, ce paramètre correspond au champ *Dilation* ; en PyTorch, il correspond à l'argument `dilation` dans `torch.nn.Conv2d`. Introduit des espaces vides entre les éléments du noyau (ex. : `dilation = 2` élargit le motif sans ajouter de paramètres). Cela permet d'augmenter le champ de vision du filtre (le champ récepteur) sans surcoût de calcul.

*Piège d'implémentation.* Les frameworks (PyTorch, TensorFlow) appellent « convolution » ce qui est en réalité une *corrélation croisée* — le noyau n'est pas retourné (rappel du piège du §5.1). Sans conséquence puisque `K` est appris (le réseau apprend le noyau déjà retourné), mais fatal si vous _initialisez_ une couche avec un noyau de référence (Sobel, gaussien) en attendant le comportement de `cv2.filter2D` : il faut le retourner, ou utiliser `scipy.signal.correlate`.

==== La normalisation — a priori « l'échelle est du bruit »

*Définition.* Une couche de normalisation recentre et remet à l'échelle un vecteur d'activations, puis lui rend deux degrés de liberté appris (`γ`, `β`) :

```
x̂_i = (x_i − μ) / √(σ² + ε)        y_i = γ·x̂_i + β
```

`μ` et `σ²` sont la moyenne et la variance calculées sur un axe choisi : sur le *batch* (BatchNorm), sur les *features* d'un même exemple (LayerNorm, base des Transformers).

*Exemple numérique.* Soit le vecteur d'activations `x = [2, 4, 4, 4, 5, 5, 7, 9]` (ε ≈ 0).

```
μ = (2+4+4+4+5+5+7+9)/8 = 40/8 = 5
σ² = [(−3)²+(−1)²+(−1)²+(−1)²+0²+0²+2²+4²]/8 = (9+1+1+1+0+0+4+16)/8 = 32/8 = 4   ⟹  σ = 2
x̂ = [(2−5)/2, (4−5)/2, …] = [−1,5 ; −0,5 ; −0,5 ; −0,5 ; 0 ; 0 ; 1 ; 2]
```

Vérification : moyenne de `x̂` = 0, variance = 1. ∎ Le réseau peut ensuite réintroduire une échelle utile via `γ`, mais il *part* d'une distribution standardisée.

*Ce que ça mesure / l'angle mort.* L'hypothèse est que la moyenne et l'échelle absolues des activations ne portent pas d'information à conserver : seule compte leur _forme relative_. Recentrer à chaque couche revient à remettre l'aiguille d'une balance à zéro avant chaque pesée, pour garder l'instrument dans sa plage utile, là où il est précis. On maintient ainsi le relief du coût (l'image du randonneur de l'introduction) bien conditionné — ni falaise, ni plateau, donc des gradients exploitables. L'angle mort : la BatchNorm couple les exemples d'un même batch. En inférence on n'a plus de batch, on utilise des statistiques *glissantes* accumulées à l'entraînement ; si train et test diffèrent (batch de taille 1, distribution décalée), le comportement change. La LayerNorm évite ce couplage — d'où son adoption dans les Transformers.

*Piège d'implémentation.* Le piège numéro un : oublier que la BatchNorm a *deux modes*. `model.train()` calcule les statistiques sur le batch courant ; `model.eval()` utilise les moyennes glissantes. Évaluer sans basculer en `eval()` donne des scores qui dépendent de la composition du batch de test — un bug silencieux et classique.

==== L'attention — a priori « la pertinence est contextuelle »

*Définition.* L'attention pondère un ensemble de valeurs `V` par une similarité entre une requête `Q` et des clés `K`, normalisée par softmax :

```
Attention(Q,K,V) = softmax( Q·Kᵀ / √d ) · V
```

`d` est la dimension des clés. Chaque sortie est une moyenne des `V`, mais une moyenne dont les poids sont *calculés à partir des données* — pas fixés par l'architecture.

*Exemple numérique.* Une requête `q = [1, 0]`, dimension `d = 2`, trois clés et valeurs :

```
K = [[1,0], [0,1], [−1,0]]      V = [[10,0], [0,10], [5,5]]
scores = K·q / √2 = [1, 0, −1] / 1,414 = [0,707 ; 0 ; −0,707]
softmax([0,707 ; 0 ; −0,707]) = [0,576 ; 0,284 ; 0,140]    (somme = 1)
sortie = 0,576·[10,0] + 0,284·[0,10] + 0,140·[5,5] = [6,46 ; 3,54]
```

La sortie penche vers la première valeur, parce que sa clé ressemblait le plus à la requête. ∎ Changez la requête, les poids changent : l'opération *choisit quoi lire* selon le contexte, là où la convolution lit toujours le même voisinage.

*Ce que ça mesure / l'angle mort.* L'attention lit comme on relit un texte une question en tête : on revient sur les passages pertinents, on survole le reste, et ce choix change avec la question posée. Elle abandonne l'a priori de localité de la convolution : n'importe quelle position peut influencer n'importe quelle autre. Puissant pour les dépendances longues, mais le coût est *quadratique* en nombre de positions (`Q·Kᵀ` est une matrice `N×N`) — d'où les variantes éparses ou linéarisées pour les images haute résolution.

*Piège d'implémentation.* Le facteur `1/√d` n'est pas cosmétique. Sans lui, pour `d` grand, les produits scalaires ont une variance ≈ `d` ; le softmax sature (un poids ≈ 1, les autres ≈ 0), son gradient s'annule, et l'entraînement cale — exactement le plateau du randonneur de l'introduction, ici fabriqué par une normalisation oubliée. C'est la même saturation que celle du softmax au §15.1 : un logit trop grand tue le gradient. Pour une attention causale (génération), ne pas oublier le masque qui met à `−∞` les scores des positions futures _avant_ le softmax.

=== Dans VNStudio

Dans votre canvas :
`Image Source` ──> `DINOv2 Classifier` ──> `Attention Map` ──> `Output Display`.

Le nœud `Attention Map` permet de visualiser les zones d'attention du réseau.

*Exercice de dépannage :* L'exercice consiste à entraîner un petit auto-encodeur sur des images contenant du bruit poivre-et-sel (des pixels isolés blancs et noirs aberrants) en utilisant d'abord une perte quadratique *L2 Loss* (erreur au carré). Le lecteur constate que le modèle produit des images floues, lissant les textures nettes pour tenter de minimiser la pénalité gigantesque des pixels aberrants. Remplacer la fonction de coût par une perte robuste de type *L1 Loss* (ou Smooth L1). Le lecteur observe que les images retrouvent leur netteté et que le modèle ignore les pixels aberrants, démontrant l'aversion au risque de la distance L2 par rapport à la stabilité de la L1.

---

// ============================================================

== Entropie croisée et softmax : quand le gradient est l'erreur elle-même

#subtitle[Punir non pas l'erreur en général, mais la confiance mal placée]

#figfull("/figures/fig_ch15_obs1_crossentropy.svg")

=== L'intention
On veut entraîner un classifieur — distinguer des chiffres manuscrits, des diagnostics sur radiographie. La métrique visée est la *justesse* (le taux de bonnes réponses), mais c'est un escalier : elle ne bouge pas quand les sorties du réseau changent un peu, elle saute d'un cran quand la classe prédite bascule. Un escalier n'a pas de pente exploitable. Il faut un substitut lisse.

=== La forme recherchée
On veut une courbe qui punisse la *confiance mal placée* : se tromper avec certitude doit coûter infiniment plus cher que se tromper en hésitant. La forme `−log(ŷ)` réalise exactement cela — quand la probabilité ŷ donnée à la bonne classe tend vers 0, le coût explose vers l'infini ; quand ŷ vaut 1 (confiance parfaite et juste), le coût tombe à zéro. Voir la forme _log_, annexe C. En amont, le *softmax* transforme les sorties brutes du réseau (les _logits_, des nombres quelconques) en une distribution de probabilités valide (tous positifs, de somme 1).

#info-box(title: "La formule")[
```
softmax :           ŷᵢ = exp(zᵢ) / Σⱼ exp(zⱼ)
entropie croisée :  L = −Σᵢ yᵢ · log(ŷᵢ)
```
]

z sont les logits, ŷ la distribution après softmax, y la cible au format _one-hot_ (un 1 sur la bonne classe, des 0 ailleurs). Les deux vont ensemble : softmax fabrique une distribution valide, l'entropie croisée mesure son écart à la cible. ∎

=== Ce qu'elle fait — un gradient qui est l'erreur
Ce couple est célèbre pour son gradient d'une simplicité désarmante : sur les logits, il vaut *exactement la différence entre la prédiction et la cible*.

```
gradient sur les logits = ŷ − y
```

Pas de facteur parasite, pas de saturation cachée : si le réseau prédit 0,7 là où il fallait 1, le logit reçoit une poussée de −0,3 ; s'il a déjà raison, le gradient s'annule de lui-même. (La démonstration de cette simplification figure en annexe maths.) C'est ce qui rend l'entropie croisée si docile à entraîner.

#question-box(title: "Exemple chiffré")[
Un classifieur de chiffres manuscrits sort z = \[2,0 ; 1,0 ; 0,1\] pour {« 3 », « 8 », « 5 »}, la vérité étant « 3 » (y = \[1, 0, 0\]) :

```
exp(z)   = [7,389 ; 2,718 ; 1,105]      somme = 11,212
softmax  = [0,659 ; 0,242 ; 0,099]
L        = −log(0,659) = 0,417
gradient = ŷ − y = [−0,341 ; 0,242 ; 0,099]
```

Le logit de la bonne classe est poussé vers le haut (−0,341), ceux des distracteurs vers le bas. La somme du gradient est nulle : le softmax redistribue la probabilité, il n'en crée pas.
]

=== Son angle mort — le déséquilibre
L'entropie croisée traite chaque exemple à poids égal, quelle que soit sa difficulté ou la fréquence de sa classe. Sur un jeu déséquilibré — 99 % de pixels de fond et 1 % d'objet en segmentation, des milliers d'images saines pour quelques anomalies — la masse des exemples faciles domine le gradient. Le réseau apprend à bien traiter le cas majoritaire et ignore les cas rares. C'est exactement ce que la focal loss (§15.3) et le Dice loss (§15.2) corrigent.

#info-box(title: "Différence d'implémentation — ne jamais enchaîner softmax puis log à la main")[
Calculer le softmax puis le logarithme séparément est numériquement instable : un grand logit fait déborder l'exponentielle, un logit très négatif donne log(0). Les bibliothèques fournissent une entropie croisée stable qui prend directement les *logits bruts* (technique du log-sum-exp). Le bug classique, silencieux, consiste à normaliser d'abord les logits en probabilités, puis à les passer à la fonction d'entropie croisée — une double application du softmax qui écrase les gradients sans planter le programme.
]

#canvas[
Canvas : `Logits` + `Target Class` → `Cross Entropy` → `Inspector`. Le nœud prend les logits bruts et la classe cible, sort le coût et le vecteur de gradient ŷ − y, et affiche le softmax. Pousser un logit à la main montre le gradient s'annuler dès que la prédiction rejoint la cible.

---
]

// ============================================================

== Dice loss : transformer une métrique de segmentation en objectif

#subtitle[Du « présent ou absent » binaire au « présent à 73 % » dérivable]

=== L'intention
Le coefficient de Dice (chapitre 4) mesure le recouvrement de deux masques, idéal contre le déséquilibre objet/fond. On veut s'en servir comme *objectif d'entraînement* d'un réseau de segmentation — mais il opère sur des masques binaires, c'est une fonction en escalier, non dérivable.

=== La forme recherchée
L'image utile est celle d'un thermomètre gradué. Le Dice binaire dit « l'objet est là ou il n'est pas » ; on veut qu'il dise « l'objet est là à 73 % » — cette nuance de gris est exactement ce dont le gradient a besoin pour savoir dans quelle direction pousser. On *relâche* donc la contrainte binaire : l'intersection de pixels devient le produit des probabilités p·g, les cardinaux deviennent des sommes de probabilités. Quand p est binaire, on retrouve le Dice du chapitre 4 ; entre les deux, la version « soft » est continue et dérivable.

#info-box(title: "La formule")[
```
Dice « soft » :  L = 1 − 2·Σ(p·g) / (Σp + Σg + ε)
```
]

p est la carte de probabilités prédite (valeurs continues dans \[0, 1\]), g le masque de vérité binaire, ε un petit terme de stabilité. La propriété décisive est dans son gradient : le dénominateur *normalise par la taille des régions*. Que l'objet occupe 1 % ou 50 % de l'image, l'échelle du gradient reste comparable — là où l'entropie croisée serait noyée par les millions de pixels de fond, le Dice rapporte tout au chevauchement relatif. ∎

#question-box(title: "Exemple chiffré")[
Une coupe IRM montre une petite lésion ; le masque de vérité compte 4 pixels positifs. Le réseau prédit :

```
pixels objet (g=1) :  p = 0,9 ; 0,8 ; 0,6 ; 0,3     → Σ(p·g) = 2,6
pixels fond  (g=0) :  un seul faux positif  p = 0,2 → Σp = 2,8,  Σg = 4

Dice = 2·2,6 / (2,8 + 4) = 0,765      L = 1 − 0,765 = 0,235
```

Le pixel objet à p = 0,3 (mal détecté) reçoit le plus fort gradient vers le haut ; le faux positif à 0,2 une poussée vers le bas. Les milliers de vrais négatifs corrects sont totalement ignorés par le coût — tout l'intérêt face au déséquilibre.
]

#info-box(title: "Subtilité — le terme de stabilité et le multiclasse")[
Sans ε, une image sans objet (g entièrement nul) et une prédiction vide donnent 0/0, un résultat indéfini qui contamine tout le lot d'entraînement. Le ε, placé au numérateur _et_ au dénominateur, rend ce cas bien défini (Dice = 1 : prédire « rien » sur une image sans objet est correct). Le Dice loss s'applique sur des probabilités (après sigmoïde ou softmax), jamais sur les logits bruts. Et en multiclasse, on calcule le Dice par classe puis on moyenne, sinon la grande classe (le fond) masque les petites.
]

#canvas[
Canvas : `Prediction Probs` + `Ground Truth Mask` → `Dice Loss` → `Inspector`. Le nœud sort le Dice soft et le coût ; il colore la carte de gradient par pixel, qui montre où le réseau est tiré vers le haut (objets ratés) ou vers le bas (faux positifs).

---
]

// ============================================================

== Focal loss : déplacer le gradient vers les exemples difficiles

#subtitle[Baisser le son des exemples déjà maîtrisés pour entendre les difficiles]

=== L'intention
Sur un détecteur examinant des dizaines de milliers de zones candidates par image, 99,9 % sont du fond (faciles) et 0,1 % contiennent un objet (difficiles). Chaque exemple facile produit un gradient minuscule, mais ils sont si nombreux qu'ils dominent la mise à jour : le réseau apprend surtout à dire « c'est du fond ». On veut rééquilibrer la pente vers le petit nombre d'exemples qui résistent.

=== La forme recherchée
On ajoute devant l'entropie croisée un *facteur modulateur* qui s'éteint quand l'exemple est bien classé et reste plein quand il est mal classé :

```
exemple BIEN classé : pₜ → 1  ⟹  (1−pₜ)^γ → 0   le coût et son gradient s'effacent
exemple MAL classé  : pₜ → 0  ⟹  (1−pₜ)^γ → 1   le coût reste celui de l'entropie croisée
```

Le facteur éteint progressivement les exemples déjà maîtrisés — comme on baisse le son des voix connues pour entendre celle qui hésite. La force décisive : il pondère par la _difficulté courante_, qui évolue pendant l'entraînement. Un exemple difficile au début devient facile plus tard, et son poids diminue automatiquement.

#info-box(title: "La formule")[
```
L = −α · (1 − pₜ)^γ · log(pₜ)        pₜ = proba prédite de la VRAIE classe
```
]

α équilibre les fréquences de classes, γ ≥ 0 est le facteur de focalisation. À γ = 0, on retrouve l'entropie croisée pondérée. Le parallèle avec Huber (chapitre 16) est instructif par opposition : Huber réduit l'influence des _grandes_ erreurs (les aberrations à ignorer), focal celle des _petites_ erreurs (les exemples faciles, déjà appris). ∎

#question-box(title: "Exemple chiffré (γ = 2)")[
Détection de défauts rares sur des pièces conformes :

```
exemple FACILE  pₜ = 0,9 :  entropie croisée = 0,105
                            focal = (1−0,9)² · 0,105 = 0,00105   → atténué ×100

exemple DIFFICILE pₜ = 0,5 : entropie croisée = 0,693
                            focal = (1−0,5)² · 0,693 = 0,173      → atténué ×4
```

L'exemple facile est divisé par 100, le difficile seulement par 4. Le rapport des poids effectifs entre difficile et facile passe de 6,6 (entropie croisée pure) à 165 : le gradient bascule massivement vers ce qui résiste. C'est ce qui permet d'entraîner un détecteur à une seule étape sans échantillonnage explicite des négatifs.
]

#info-box(title: "Réglage — γ et α ensemble, et le bruit d'étiquettes")[
γ et α s'ajustent conjointement : augmenter γ abaisse l'amplitude globale du coût, qu'on compense souvent par α (les valeurs de référence α = 0,25, γ = 2 ne sont pas universelles). Comme en §15.1, on part des logits bruts pour la stabilité numérique. Et un γ trop élevé peut *mémoriser le bruit d'étiquettes* : un exemple mal étiqueté ressemble à un exemple difficile et capte tout le gradient.
]

#canvas[
Canvas : `Logits` + `Target Class` → `Focal Loss` → `Inspector`. Le nœud expose γ et α en curseurs et affiche, à côté du coût, le facteur de modulation et le rapport d'atténuation facile/difficile. Monter γ montre la contribution des exemples faciles fondre vers zéro.

---
]

// ============================================================

== Smooth L1 (Huber) : le compromis entre stabilité et robustesse

#subtitle[Précis comme L2 près du but, blindé comme L1 contre les aberrations]

=== L'intention
On régresse une grandeur continue — les coordonnées d'une boîte de détection. La L2 (l'erreur au carré) est précise près de la cible mais *explose* sur une annotation aberrante : une seule boîte mal étiquetée fournit un gradient énorme qui pilote toute la mise à jour. La L1 (l'erreur absolue) résiste aux aberrations mais son gradient constant fait vibrer le paramètre près de l'optimum. On veut le meilleur des deux.

=== La forme recherchée
On lit la *forme du gradient* souhaitée : proportionnel à l'erreur près de zéro (précision de la L2), borné au loin (robustesse de la L1).

```
gradient = x/β     si |x| < β     (proportionnel à l'erreur, comme L2)
           sign(x) sinon          (constant et borné, comme L1)
```

La forme quadratique près de zéro donne un gradient doux qui s'annule à l'optimum ; la forme linéaire au loin plafonne le gradient, si bien qu'une erreur énorme ne peut plus écraser le lot. C'est, au facteur d'échelle près, le *M-estimateur de Huber* du chapitre 16 : une parabole près de zéro, une droite au-delà.

#info-box(title: "La formule")[
```
L(x) = 0,5·x²/β      si |x| < β
        |x| − 0,5·β  sinon
```
]

x est l'erreur de régression, β le seuil de transition (souvent 1). Le lien avec le chapitre 8 est direct : l'erreur de reprojection du bundle adjustment est une somme de carrés L2, dominée par une seule correspondance aberrante ; la remplacer par un noyau de Huber est la correction qui rend le recalage robuste aux faux appariements. ∎

#question-box(title: "Exemple chiffré (β = 1)")[
Quatre résidus d'un détecteur embarqué, dont un aberrant dû à une annotation imprécise :

```
erreur x   |  L2 (x²)   gradient (2x)  |  smooth L1   gradient
  0,5       |   0,25         1,0        |   0,125         0,5
  0,8       |   0,64         1,6        |   0,320         0,8
  0,3       |   0,09         0,6        |   0,045         0,3
  6,0 (★)   |  36,0         12,0        |   5,500         1,0
```

En L2, l'aberration (★) pèse 36 sur 37 du coût total et fournit un gradient de 12 — elle dicte seule la mise à jour. En smooth L1, sa contribution tombe à 5,5 et son gradient est plafonné à 1,0, du même ordre que les résidus normaux. L'aberration ne pilote plus l'apprentissage.
]

#info-box(title: "Réglage — le seuil β et les conventions")[
β change radicalement le comportement : trop petit, tout devient L1 (convergence lente près de l'optimum) ; trop grand, tout redevient L2 (sensible aux aberrations). Les bibliothèques divergent sur la convention (`beta` ou `delta`, mise à l'échelle de la branche linéaire) : on vérifie laquelle on emploie avant de comparer des magnitudes de coût. En détection, on régresse en coordonnées normalisées par l'ancre, sinon le bon β dépend de la résolution de l'image.
]

#canvas[
Canvas : `Prediction` + `Target` → `Smooth L1` → `Inspector`. Le nœud expose β et affiche, par résidu, le coût et le gradient en regard de la L2 pure — la branche plafonnée saute aux yeux dès qu'un résidu dépasse β.

---
]

// ============================================================

== IoU loss et GIoU : optimiser la métrique, et combler ses zones plates

#subtitle[Quand deux boîtes ne se touchent pas, la métrique est aveugle — on lui rend la vue]

#figfull("/figures/fig_ch15_obs2_giou.svg")

=== L'intention
Pour entraîner un détecteur, on aimerait optimiser directement l'IoU (chapitre 4), la métrique même qu'on évalue. Mais elle a un défaut fatal comme coût : quand la boîte prédite et la cible *ne se chevauchent pas*, l'IoU vaut 0 partout, quelle que soit la distance entre les deux.

=== La forme recherchée
```
A et B disjointes  ⟹  IoU = 0  ⟹  L_IoU = 1  ⟹  gradient ≈ 0
```

C'est une *zone plate* : le substitut colle si bien à la métrique qu'il en hérite le défaut — impossible de distinguer « boîtes presque adjacentes » de « boîtes aux antipodes ». Le gradient ne sait pas dans quelle direction bouger la boîte. On veut greffer un terme qui reste actif sans chevauchement et décroît quand les boîtes se rapprochent. L'idée de GIoU : mesurer la fraction de la plus petite boîte englobant les deux qui n'est couverte par aucune. Plus les boîtes sont éloignées, plus cette région est vaste — donc plus le coût est grand, et son gradient tire les boîtes l'une vers l'autre.

#info-box(title: "La formule")[
```
L_IoU  = 1 − IoU
L_GIoU = 1 − IoU + |C \ (A ∪ B)| / |C|
```
]

A est la boîte prédite, B la cible, C la plus petite boîte les englobant toutes deux. Le terme correctif sculpte un gradient là où la métrique seule était aveugle — exactement la logique du substitut dérivable. ∎

#question-box(title: "Exemple chiffré")[
Deux boîtes *disjointes*, format (x₁, y₁, x₂, y₂), en imagerie aérienne :

```
A = (0, 0, 2, 2)   B = (3, 3, 5, 5)   aires 4 chacune
intersection = 0   union = 8   IoU = 0   → L_IoU = 1 (zone plate, gradient nul)

C = (0, 0, 5, 5)   aire = 25
|C \ (A∪B)| = 25 − 8 = 17
GIoU = 0 − 17/25 = −0,68     L_GIoU = 1,68
```

Là où l'IoU loss reste bloqué à 1 sans direction, le GIoU vaut 1,68 et *diminue dès que B se déplace vers A* : C rétrécit, l'aire non couverte baisse, le gradient tire activement les boîtes l'une vers l'autre.
]

=== Son angle mort — l'inclusion
GIoU converge lentement quand une boîte en contient une autre : le terme correctif s'annule alors que l'alignement n'est pas optimal. D'où les raffinements ultérieurs (DIoU, CIoU) qui ajoutent la distance des centres et le rapport d'aspect. Aucun ne capture tout — le chapitre 4 résonne encore, et le substitut dérivable hérite toujours d'une part des angles morts de sa métrique.

#info-box(title: "Différence d'implémentation — coordonnées et aires")[
Les conventions de coordonnées sont une source d'erreur permanente : (x, y, w, h) ou (x₁, y₁, x₂, y₂) selon les bibliothèques. On borne largeurs et hauteurs à ≥ 0 avant tout calcul d'aire (des boîtes dégénérées produisent des intersections fantômes), et l'aire de l'union se calcule par |A| + |B| − |A∩B|, jamais par somme naïve. Un ε aux dénominateurs gère les boîtes de taille nulle en début d'entraînement.
]

#canvas[
Canvas : `Predicted Box` + `Target Box` → `IoU Loss` → `Inspector`. Le nœud trace les deux boîtes et la boîte englobante C, affiche IoU, GIoU et le terme correctif ; déplacer la boîte prédite montre le GIoU décroître continûment là où l'IoU reste bloqué à zéro.

---
]

// ============================================================

== Loss contrastive (InfoNCE) : structurer un espace de représentation

#subtitle[Fabriquer un quiz « lequel est le vrai jumeau ? » pour créer une pente à partir de rien]

#figfull("/nvlle illu/A_humorous,_highly_stylized_line-art_202606191405(1).jpeg")

=== L'intention
Ce coût répond à un problème sans cible explicite : pas de bonne classe, pas de masque, pas de boîte. On a seulement la relation « ces deux images montrent le même contenu » ou « des contenus différents ». La métrique visée — la qualité de l'espace de représentation — n'a aucune formule directe. Comment fabriquer une pente à partir de rien ?

=== La forme recherchée
On *invente un problème de classification artificiel* : « parmi tous les candidats, lequel est le vrai positif ? » L'ancre (un vecteur extrait d'une image) doit reconnaître son positif (la même image vue autrement) parmi des négatifs (d'autres images). Les « logits » de ce quiz sont les similarités cosinus (chapitre 3) divisées par une *température* τ. La cible est l'indice du positif — et tout le gradient propre de l'entropie croisée (§15.1) s'applique : il rapproche l'ancre de son positif, éloigne l'ancre des négatifs.

La température règle la dureté de la comparaison, comme le contraste d'un microscope. Une τ basse (fort contraste) amplifie les différences légères : le réseau s'entraîne sur les quasi-confusions, mais le moindre bruit est fatal. Une τ haute (faible contraste) traite tout également : signal doux et stable, mais moins discriminant. C'est le choix de distance du chapitre 3 poussé d'un cran : non plus seulement _ce qui compte_, mais _à quel point les quasi-confusions comptent_.

#info-box(title: "La formule")[
```
L = −log( exp(sim(zᵢ, zⱼ⁺)/τ) / Σₖ exp(sim(zᵢ, zₖ)/τ) )
```
]

zᵢ est l'ancre, zⱼ⁺ le positif, zₖ l'ensemble des candidats (positif + négatifs), `sim` le cosinus, τ la température. Réécrit, c'est exactement l'entropie croisée du §15.1 appliquée au quiz artificiel : le gradient pousse vers le haut la similarité avec le positif, vers le bas celle des négatifs — d'autant plus fort qu'un négatif est, à tort, jugé proche. ∎

#question-box(title: "Exemple chiffré")[
Une ancre microscopique (une cellule), son positif (même cellule, autre contraste, sim = 0,9) et deux négatifs (sim = 0,3 et 0,2). Effet de la température :

```
τ = 0,1 :  logits = [9 ; 3 ; 2]      → p(positif) = 0,997  →  L = 0,003
τ = 1,0 :  logits = [0,9 ; 0,3 ; 0,2] → p(positif) = 0,489  →  L = 0,715
```

Pour des similarités identiques, le coût varie de 0,003 à 0,715 selon τ. À τ basse, le réseau se juge déjà excellent (gradient ténu) ; à τ haute, il voit les négatifs comme des concurrents sérieux et reçoit un gradient fort. La température décide à quel point les quasi-confusions doivent être combattues.
]

#info-box(title: "Subtilité — normaliser, et les faux négatifs")[
Trois points. La similarité cosinus suppose des vecteurs normalisés (de longueur 1) : sans cela, le coût dépend de la norme des vecteurs, pas seulement de leur direction. Une température basse amplifie les *faux négatifs* : deux clichés de nébuleuses différentes du même type peuvent se ressembler, et les traiter comme négatifs avec τ très petite leur inflige à tort un gradient violent. Enfin, le nombre de négatifs gouverne la qualité du signal — trop peu de candidats ne suffit pas à structurer l'espace.
]

#canvas[
Canvas : `Anchor` + `Positive` + `Negatives` → `Contrastive Loss` → `Inspector`. Le nœud normalise les vecteurs, calcule les similarités cosinus, expose τ, et affiche le coût avec la probabilité attribuée au positif. Baisser τ montre la probabilité du positif grimper et le gradient s'éteindre.

---
]

// ============================================================

== Tableau récapitulatif — quel coût pour quel objectif

#table(
  columns: 5,
  table.header(
    [*Coût*], [*Métrique substituée*], [*Forme du gradient*], [*Saturation / explosion*], [*Usage typique*]
  ),
  [Normalisation], [L'échelle absolue est du bruit], [standardisée (moyenne 0, var 1)], [Évaluer sans eval()], [x̂ = (x-μ)/√(σ²+ε)],
  [Attention], [La pertinence est contextuelle], [dynamique, pondérée par softmax], [1/√d oublié -> softmax saturé], [softmax(QKᵀ/√d)·V],
  [---], [---], [---], [---], [---],
  [Entropie croisée + softmax], [justesse de classification (escalier)], [`ŷ − y` (l'erreur elle-même)], [poids égal → noyé par les classes majoritaires], [classification, OCR, détection multiclasse],
  [Dice loss], [coefficient de Dice binaire (non dérivable)], [normalisé par la taille des régions], [instable si objet absent (sans ε) ; ignore les frontières], [segmentation médicale, objets minuscules],
  [Focal loss], [justesse sous déséquilibre extrême], [éteint les exemples faciles `(1−pₜ)^γ`], [sensible au bruit d'étiquettes à γ élevé], [détection dense, défauts rares],
  [Smooth L1 (Huber)], [erreur de localisation sans explosion], [doux près de 0 (L2), borné au loin (±β)], [gradient L2 explose sur les aberrations], [régression de boîtes, reprojection robuste],
  [IoU loss / GIoU], [IoU des boîtes (plate si disjointes)], [nul hors chevauchement → comblé par GIoU], [zone plate complète si A∩B = ∅], [détection, petits objets, aérien],
  [InfoNCE (contrastive)], [qualité de l'espace de représentation], [rapproche positifs, éloigne négatifs], [faux négatifs à τ basse ; signal faible si peu de négatifs], [pré-entraînement auto-supervisé, CLIP],
)

---

// ============================================================

== Le coût n'est pas la cible, c'est la pente vers elle

Le chapitre tient en un principe qui structure tout l'apprentissage profond : on ne minimise jamais ce qu'on veut, mais un substitut dont le gradient y conduit. Et ce substitut n'est pas choisi au hasard — chaque coût répond à une faille précise de la métrique qu'il remplace.

```
classer juste          → la justesse est un escalier ; l'entropie croisée donne ŷ − y, actif partout
segmenter (Dice/IoU)   → la métrique est binaire et plate ; sa relaxation continue redevient dérivable
apprendre malgré le    → l'entropie croisée se noie dans les exemples faciles ;
  déséquilibre           focal et Dice repondèrent pour rendre la pente utile
régresser une boîte    → la L2 explose sur une aberration ; Huber borne le gradient,
                         GIoU comble la zone sans chevauchement
structurer un espace   → « se ressembler » n'a pas de gradient en soi ;
                         InfoNCE en fabrique un par comparaison artificielle
```

Un coût et une opération font le même travail à deux endroits du réseau. Le coût dit _ce que réussir veut dire_ ; l'opération dit _ce qu'il est permis de regarder pour y arriver_. La convolution parie sur la localité, la normalisation tient l'échelle pour négligeable, l'attention laisse les données fixer leur propre pertinence — et chacun de ces paris, comme le choix d'une distance au chapitre 3 ou d'une base au chapitre 10, retire au réseau une liberté pour lui en donner une force. Le gradient reste la seule réalité ; ces opérations décident seulement du relief qu'il descend.

Chaque coût est un arbitrage entre fidélité à la métrique et exploitabilité du gradient : l'IoU est la vraie cible, mais c'est GIoU qu'on optimise parce que lui a une pente partout ; le Dice du chapitre 4 est la mesure, mais c'est sa version soft qu'on dérive. Toute la conception d'un coût tient dans une question — _où le gradient s'annule-t-il, explose-t-il, ou pointe-t-il à côté ?_

Choisir une distance (chapitre 3), c'est déclarer ce qui compte ; choisir une base (chapitre 10), où le problème devient simple ; choisir un coût, c'est déclarer ce qui compte _et fabriquer la pente qui y mène_. La métrique dit si c'est bon, le coût dit dans quelle direction s'améliorer. Le chapitre 16 reprendra la repondération des exemples — déjà à l'œuvre dans Huber et focal — pour en faire le cœur de l'estimation robuste, quand quelques valeurs aberrantes menacent toute une mesure.

---


// ============================================================
// EXERCICES — CHAPITRE 15
// ============================================================

#pagebreak()
== Exercices pratiques




=== Exercice 1 · Détecter des objets rares sans noyer la cible dans le fond

#figtodo("ex_ch15_parking", [Vue aérienne d'un parking quasi vide : des dizaines de places de stationnement v...])


*Ce que vous voyez.* Une scène où la cible (les voitures) est écrasée sous une masse de fond identique. C'est le déséquilibre que la focal loss corrige à l'entraînement : ici on observe ses conséquences sur un détecteur déjà entraîné.

*Pipeline VNStudio*
`Image Source` → `Object Detection (YOLO)` → `Draw Overlay` → `Output Display`

Le nœud affiche les boîtes détectées avec leur score de confiance.




*Questions*


+ Lancez la détection avec un seuil de confiance bas (0,1). Combien de boîtes apparaissent ? Combien sont de vraies voitures, combien sont des fausses alarmes posées sur des places vides ?

+ Montez le seuil progressivement. À quelle valeur les fausses alarmes disparaissent-elles ? Reste-t-il les deux vraies voitures, ou en perdez-vous une au passage ?

+ Un détecteur mal entraîné, écrasé par la masse du fond, devient « paresseux » et rate les objets rares. Sur cette image, le vôtre privilégie-t-il plutôt la prudence (rate des voitures) ou l'excès de zèle (invente des voitures) ? Que faudrait-il rééquilibrer ?

+ *Défi.* Trouvez une scène encore plus déséquilibrée (un seul objet minuscule dans une grande image uniforme) et comptez les fausses détections à seuil bas. Comparez avec une scène équilibrée (autant d'objets que de fond). Sur laquelle le détecteur se trompe-t-il le plus, et pourquoi ?



=== Exercice 2 · Mesurer la qualité d'une segmentation par le recouvrement

#figtodo("ex_ch15_segmentation_overlap", [Vue microscopique d'une cellule : à gauche le contour tracé à la main par un bio...])


*Ce que vous voyez.* Deux masques de la même cellule. La mission : mesurer leur recouvrement, car c'est exactement ce que la Dice loss optimise pendant l'entraînement.

*Pipeline VNStudio*
`Image Source` → `SAM Segmenter` → `Mask Overlap` → `Output Display`

Le nœud `Mask Overlap` compare le masque automatique au masque de référence et affiche le score de recouvrement (IoU et Dice).




*Questions*


+ Segmentez la cellule, puis lisez le score de recouvrement. Le masque automatique colle-t-il bien à la référence, ou déborde-t-il ? Repérez visuellement où ils divergent.

+ Décalez volontairement le masque automatique (déplacez le point de clic SAM). Le score chute-t-il vite ou lentement ? À quel décalage les deux masques ne se touchent plus du tout (recouvrement nul) ?

+ Quand les deux masques ne se chevauchent plus, le score reste bloqué à zéro et ne dit plus dans quelle direction corriger. Pourquoi est-ce un problème quand on démarre un entraînement avec un masque encore très loin de la cible ?

+ *Défi.* Segmentez un amas de plusieurs cellules collées d'un seul clic. Le masque englobe-t-il tout l'amas ou une seule cellule ? Réglez SAM (points positifs et négatifs) pour isoler une seule cellule et faire remonter le score de recouvrement avec son contour de référence.



=== Exercice 3 · Ajuster une boîte englobante malgré des points parasites

#figtodo("ex_ch15_bbox_fit", [Photo d'un panneau routier rectangulaire détecté : la majorité des points de con...])


*Ce que vous voyez.* Une boîte à ajuster autour d'un objet, perturbée par quelques points parasites. C'est le rôle de la Smooth L1 (Huber) en détection : suivre les bons points sans se laisser tirer par les rares aberrants.

*Pipeline VNStudio*
`Image Source` → `Find Contours` → `Robust Box Fit` → `Draw Overlay` → `Output Display`

Le nœud ajuste la boîte avec un mode ordinaire (sensible aux parasites) ou robuste (Huber).




*Questions*


+ Ajustez la boîte en mode ordinaire. Englobe-t-elle juste le panneau, ou s'étire-t-elle pour avaler l'autocollant ? Mesurez de combien elle déborde.

+ Passez en mode robuste. La boîte se resserre-t-elle sur le panneau seul ? Comparez les deux résultats superposés.

+ Réglez le curseur de tolérance du mode robuste. Trouvez la plage où la boîte ignore l'autocollant tout en épousant les quatre coins du panneau. Que se passe-t-il aux réglages extrêmes (trop serré, trop large) ?

+ *Défi.* Ajoutez plusieurs autocollants autour du panneau. Le mode robuste tient-il toujours ? Jusqu'à quelle quantité de points parasites la boîte reste-t-elle correcte avant de décrocher ? Pour un système qui annote des milliers d'images sans supervision, quel mode est le plus sûr ?






#v(2em)
#align(center)[
  #image("/QR Code.png", width: 60pt)
  #v(4pt)
  #text(size: 0.8em, style: "italic", fill: rgb("#64748b"))[Télécharger les images de référence]
]



]
