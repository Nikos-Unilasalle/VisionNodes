# Patch de contenu — Chapitre 15 : titre, cadrage, et les opérations comme formules
## Réponse à « le chapitre n'a que des coûts ; les opérations ne sont qu'invoquées »

> **Mode d'emploi.** Patch de **contenu**. Trois actions :
> 1. **Renommer le chapitre** pour que le titre tienne ce que le chapitre livre.
> 2. **Ajouter un encadré de cadrage** en tête, qui dit honnêtement ce que le chapitre couvre et pourquoi.
> 3. **Ajouter une section 15.0** qui traite trois opérations (convolution-couche, normalisation, attention) comme de vraies formules — pour qu'elles ne soient plus seulement nommées.

---

## Action 1 — Nouveau titre

Remplacer :

```
# Chapitre — Apprentissage profond : dérivations et exemples
```

par :

```
# Chapitre — Apprentissage profond : les fonctions de coût comme sources de gradient
```

Le sous-titre devient une promesse exacte. Un acheteur qui feuillette sait qu'il achète un chapitre sur les **coûts** (et les opérations qui les rendent dérivables), pas un cours d'architectures.

## Action 2 — Encadré de cadrage (à placer juste après le paragraphe d'introduction)

> **Ce que ce chapitre couvre — et ce qu'il ne couvre pas.** Un réseau profond n'apprend rien par lui-même : il descend une pente. Ce chapitre traite la quantité qui *crée* cette pente — la fonction de coût — parce que c'est elle qui encode ce que « réussir » veut dire, et c'est là que se prennent les décisions de vision (quelle erreur punir, quel déséquilibre corriger, quelle géométrie récompenser). Les **architectures** — combien de couches, lesquelles, dans quel ordre — relèvent d'un autre ouvrage ; on n'en donne ici que le strict nécessaire pour comprendre d'où vient le gradient. La section 15.0 pose les trois opérations qui reviennent dans presque tout réseau de vision, non pour les cataloguer, mais parce que chacune, comme un coût, encode un a priori sur ce qui compte. Le reste du chapitre est consacré aux coûts.

## Action 3 — Nouvelle section 15.0

**Placement : avant 15.1 (entropie croisée).** Elle prépare le terrain : les opérations façonnent le relief que les coûts feront ensuite descendre.

---

### Section 15.0 — Trois opérations, trois a priori

On présente souvent ces opérations comme des « briques » d'architecture, neutres et interchangeables. Elles ne le sont pas. Chacune impose une hypothèse forte sur la structure du signal — et c'est précisément cette hypothèse qui réduit le nombre de paramètres à apprendre et oriente ce que le réseau *peut* voir. Trois suffisent à porter presque toute la vision profonde.

#### 15.0.1 La convolution comme couche — a priori de localité et d'équivariance

**Définition.** Une couche convolutive produit le canal de sortie `o` à partir des canaux d'entrée `I_c` par :

```
O_o(x,y) = b_o + Σ_c Σ_{i,j} I_c(x+i, y+j) · K_{o,c}(i,j)        puis  σ(·)  (non-linéarité)
```

C'est la convolution du chapitre 5, à une différence décisive : le noyau `K` n'est plus posé par le concepteur, il est **appris** par descente de gradient.

**Dérivation — l'économie de paramètres.** Relier une carte `H×W` à une autre par une couche dense coûte `(H·W)²` poids. Une couche convolutive de noyau `k×k` impose deux contraintes : **localité** (un pixel de sortie ne dépend que d'un voisinage `k×k`) et **partage des poids** (le même `K` sur toute l'image). Le coût tombe à `k²` poids par paire de canaux, indépendant de la taille de l'image. ∎ Ce partage *est* l'hypothèse : un motif utile en un point l'est partout — c'est l'**équivariance par translation**. Déplacez l'entrée, la sortie se déplace d'autant.

**Angle mort.** L'équivariance par translation est exactement ce qu'on veut pour détecter un même motif n'importe où ; c'est exactement ce qu'on ne veut pas quand la position absolue compte (un ciel est en haut, une route en bas). D'où les correctifs : *coordconv*, plongements de position, ou simplement des couches denses en fin de réseau.

**Piège d'implémentation.** Les frameworks (PyTorch, TensorFlow) appellent « convolution » ce qui est en réalité une **corrélation croisée** — le noyau n'est pas retourné (rappel du piège du §5.1). Sans conséquence puisque `K` est appris (le réseau apprend le noyau déjà retourné), mais fatal si vous *initialisez* une couche avec un noyau de référence (Sobel, gaussien) en attendant le comportement de `cv2.filter2D` : il faut le retourner, ou utiliser `scipy.signal.correlate`. Vérifier aussi `padding` et `stride`, qui changent la taille de sortie.

#### 15.0.2 La normalisation — a priori « l'échelle est du bruit »

**Définition.** Une couche de normalisation recentre et remet à l'échelle un vecteur d'activations, puis lui rend deux degrés de liberté appris (`γ`, `β`) :

```
x̂_i = (x_i − μ) / √(σ² + ε)        y_i = γ·x̂_i + β
```

`μ` et `σ²` sont la moyenne et la variance calculées sur un axe choisi : sur le **batch** (BatchNorm), sur les **features** d'un même exemple (LayerNorm, base des Transformers).

**Dérivation / exemple numérique (calculable à la main).** Soit le vecteur d'activations `x = [2, 4, 4, 4, 5, 5, 7, 9]` (ε ≈ 0).

```
μ = (2+4+4+4+5+5+7+9)/8 = 40/8 = 5
σ² = [(−3)²+(−1)²+(−1)²+(−1)²+0²+0²+2²+4²]/8 = (9+1+1+1+0+0+4+16)/8 = 32/8 = 4   ⟹  σ = 2
x̂ = [(2−5)/2, (4−5)/2, …] = [−1,5 ; −0,5 ; −0,5 ; −0,5 ; 0 ; 0 ; 1 ; 2]
```

Vérification : moyenne de `x̂` = 0, variance = 1. ∎ Le réseau peut ensuite réintroduire une échelle utile via `γ`, mais il **part** d'une distribution standardisée.

**Ce que ça mesure / l'angle mort.** L'hypothèse est que la moyenne et l'échelle absolues des activations ne portent pas d'information à conserver : seule compte leur *forme relative*. Recentrer à chaque couche revient à remettre l'aiguille d'une balance à zéro avant chaque pesée, pour garder l'instrument dans sa plage utile, là où il est précis. On maintient ainsi le relief du coût (l'image du randonneur de l'introduction) bien conditionné — ni falaise, ni plateau, donc des gradients exploitables. L'angle mort : la BatchNorm couple les exemples d'un même batch. En inférence on n'a plus de batch, on utilise des statistiques **glissantes** accumulées à l'entraînement ; si train et test diffèrent (batch de taille 1, distribution décalée), le comportement change. La LayerNorm évite ce couplage — d'où son adoption dans les Transformers.

**Piège d'implémentation.** Le piège numéro un : oublier que la BatchNorm a **deux modes**. `model.train()` calcule les statistiques sur le batch courant ; `model.eval()` utilise les moyennes glissantes. Évaluer sans basculer en `eval()` donne des scores qui dépendent de la composition du batch de test — un bug silencieux et classique.

#### 15.0.3 L'attention — a priori « la pertinence est contextuelle »

**Définition.** L'attention pondère un ensemble de valeurs `V` par une similarité entre une requête `Q` et des clés `K`, normalisée par softmax :

```
Attention(Q,K,V) = softmax( Q·Kᵀ / √d ) · V
```

`d` est la dimension des clés. Chaque sortie est une moyenne des `V`, mais une moyenne dont les poids sont **calculés à partir des données** — pas fixés par l'architecture.

**Dérivation / exemple numérique (vérifié).** Une requête `q = [1, 0]`, dimension `d = 2`, trois clés et valeurs :

```
K = [[1,0], [0,1], [−1,0]]      V = [[10,0], [0,10], [5,5]]
scores = K·q / √2 = [1, 0, −1] / 1,414 = [0,707 ; 0 ; −0,707]
softmax([0,707 ; 0 ; −0,707]) = [0,576 ; 0,284 ; 0,140]    (somme = 1)
sortie = 0,576·[10,0] + 0,284·[0,10] + 0,140·[5,5] = [6,46 ; 3,54]
```

La sortie penche vers la première valeur, parce que sa clé ressemblait le plus à la requête. ∎ Changez la requête, les poids changent : l'opération **choisit quoi lire** selon le contexte, là où la convolution lit toujours le même voisinage.

**Ce que ça mesure / l'angle mort.** L'attention lit comme on relit un texte une question en tête : on revient sur les passages pertinents, on survole le reste, et ce choix change avec la question posée. Elle abandonne l'a priori de localité de la convolution : n'importe quelle position peut influencer n'importe quelle autre. Puissant pour les dépendances longues, mais le coût est **quadratique** en nombre de positions (`Q·Kᵀ` est une matrice `N×N`) — d'où les variantes éparses ou linéarisées pour les images haute résolution.

**Piège d'implémentation.** Le facteur `1/√d` n'est pas cosmétique. Sans lui, pour `d` grand, les produits scalaires ont une variance ≈ `d` ; le softmax sature (un poids ≈ 1, les autres ≈ 0), son gradient s'annule, et l'entraînement cale — exactement le plateau du randonneur de l'introduction, ici fabriqué par une normalisation oubliée. C'est la même saturation que celle du softmax au §15.1 : un logit trop grand tue le gradient. Pour une attention causale (génération), ne pas oublier le masque qui met à `−∞` les scores des positions futures *avant* le softmax.

---

## Lignes à ajouter au tableau récapitulatif du chapitre 15

| Opération | A priori encodé | Angle mort | Piège | Formule clé |
|---|---|---|---|---|
| Convolution-couche | Localité + équivariance par translation | Aveugle à la position absolue | Corrélation, pas convolution (noyau non retourné) | `O = b + Σ I⋆K` |
| Normalisation | L'échelle absolue est du bruit | BN couple le batch ; mode train/eval | Évaluer sans `eval()` | `x̂ = (x−μ)/√(σ²+ε)` |
| Attention | La pertinence est contextuelle | Coût quadratique en positions | `1/√d` oublié → softmax saturé | `softmax(QKᵀ/√d)·V` |

## Raccord à l'encadré final du chapitre

> Un coût et une opération font le même travail à deux endroits du réseau. Le coût dit *ce que réussir veut dire* ; l'opération dit *ce qu'il est permis de regarder pour y arriver*. La convolution parie sur la localité, la normalisation tient l'échelle pour négligeable, l'attention laisse les données fixer leur propre pertinence — et chacun de ces paris, comme le choix d'une distance au chapitre 3 ou d'une base au chapitre 10, retire au réseau une liberté pour lui en donner une force. Le gradient reste la seule réalité ; ces opérations décident seulement du relief qu'il descend.
