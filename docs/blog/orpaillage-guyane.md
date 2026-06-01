# Détecter l'orpaillage illégal en Guyane par télédétection : première pipeline

*Un atelier de cartographie par nœuds appliqué à un enjeu de souveraineté et d'écologie tropicale.*

---

## 1. Contexte : un fléau humain, social et écologique

Au cœur de l'Amazonie française, la Guyane abrite l'une des forêts primaires les
mieux conservées de la planète. Elle est aussi le théâtre d'une activité
clandestine massive : **l'orpaillage illégal**, l'extraction sauvage d'or dans le
lit et les berges des rivières.

Les conséquences se cumulent sur trois plans :

- **Écologique.** Le dragage des cours d'eau détruit les berges, met en suspension
  d'énormes quantités de sédiments (rivières « cafés au lait ») et anéantit les
  habitats aquatiques. Surtout, l'extraction recourt au **mercure** pour amalgamer
  l'or : ce métal lourd contamine durablement l'eau, se bioaccumule dans la chaîne
  alimentaire et empoisonne les poissons.

- **Sanitaire et humain.** Les populations amérindiennes du Haut-Maroni et du
  Haut-Oyapock, dont l'alimentation dépend de la pêche, présentent des taux
  d'imprégnation au mercure parmi les plus élevés au monde, avec des atteintes
  neurologiques documentées, notamment chez les nouveau-nés. Les sites
  d'orpaillage sont par ailleurs des zones de non-droit : travail forcé,
  prostitution, violences armées, trafics.

- **Économique et régalien.** Des dizaines de tonnes d'or quittent le territoire
  chaque année hors de tout cadre légal, alimentant des réseaux criminels
  transfrontaliers.

La difficulté centrale est **la détection**. Les sites (les *« chantiers »*) sont
petits, mobiles, dispersés sur un territoire grand comme le Portugal, souvent
inaccessibles par voie terrestre et masqués par une couverture nuageuse quasi
permanente.

## 2. L'opération Harpie

Lancée en 2008 et pérennisée depuis, **l'opération Harpie** mobilise les Forces
armées en Guyane (FAG) et la gendarmerie pour lutter contre l'orpaillage illégal :
destruction des chantiers, interception des flux logistiques (carburant, mercure,
vivres) qui remontent les fleuves, et démantèlement des filières.

L'efficacité de ces opérations repose en grande partie sur le **renseignement
géographique** : savoir *où* chercher avant d'engager des moyens héliportés
coûteux. C'est précisément là que la **télédétection satellitaire** apporte une
valeur décisive — repérer à distance, et de façon répétée dans le temps, les
signatures d'un chantier actif.

## 3. Notre première ébauche et ce que nous visons

Nous avons construit, dans notre studio de vision par nœuds, une **première
pipeline de classification** entièrement à partir de données ouvertes et gratuites
(Copernicus, Microsoft Planetary Computer). L'objectif de cette première étape
n'était **pas** de produire une carte opérationnelle d'orpaillage, mais de :

1. **valider la chaîne technique** de bout en bout (téléchargement → features →
   classification → visualisation) ;
2. **mesurer le pouvoir discriminant** des différentes sources de données
   (optique, radar, modèle de terrain, temporel) ;
3. **identifier le véritable goulot d'étranglement** avant d'investir dans une
   collecte de vérité terrain coûteuse.

La cible à terme est un classifieur **forêt saine vs. chantier d'orpaillage**,
entraîné sur des sites confirmés.

## 4. La pipeline en détail

### 4.1 Sources

| Source | Produit | Rôle |
|--------|---------|------|
| Sentinel-2 L2A | Optique 5 bandes (R, V, B, NIR, SWIR) @ 20 m | Indices spectraux |
| Sentinel-1 GRD | Radar SAR (VV, VH) @ 20 m | Eau turbide, sol nu sous nuages |
| Copernicus DEM GLO-30 | Modèle numérique de terrain @ 30 m | Dérivés morphologiques et hydrologiques |
| ESA WorldCover | Carte d'occupation du sol 10 m | Labels d'entraînement |

L'image optique de Guyane est constamment voilée par les nuages. Le **radar
Sentinel-1**, qui traverse les nuages, est donc un complément essentiel : l'eau
chargée de sédiments d'un chantier présente une rétrodiffusion caractéristique.

### 4.2 Ingénierie des features (11 bandes)

À partir des sources brutes, nous dérivons **onze variables** par pixel, regroupées
en quatre familles :

**Spectral (Sentinel-2)**
- **NDVI** — vigueur de la végétation `(NIR − Rouge) / (NIR + Rouge)`
- **BSI** — indice de sol nu (*Bare Soil Index*)

**Terrain (DEM)** — tous calculés par nos propres nœuds
- **Pente** (slope, Horn 1981)
- **TRI** — *Terrain Ruggedness Index* (Riley et al. 1999)
- **TWI** — *Topographic Wetness Index*, `ln(a / tan β)` (Beven & Kirkby 1979)
- **HAND** — *Height Above Nearest Drainage* (Rennó et al. 2008)
- **flow_log** — accumulation de flux D8 en échelle logarithmique

**Radar (Sentinel-1)**
- **VV** et **VH** — rétrodiffusion en dB selon les deux polarisations

**Bi-temporel (Sentinel-2 2021 → 2024)**
- **ΔNDVI** et **ΔBSI** — variation spectrale entre deux dates. La signature d'un
  chantier nouveau est une **chute de NDVI** (perte de couvert) couplée à une
  **hausse de BSI** (apparition de sol nu).

### 4.3 Assemblage et classification

Les onze bandes sont fusionnées par empilement successif (`Band Stack`) sur une
grille de référence commune, puis fournies à un **classifieur Random Forest**
(150 arbres, profondeur 15) entraîné sur les labels ESA WorldCover.

```
        ┌── Sentinel-2 (2024) ── NDVI, BSI
        │
        ├── Sentinel-2 (2021) ─┐
        │                       ├── Δ Spectral ── ΔNDVI, ΔBSI
BBox ───┤── Sentinel-2 (2024) ─┘
        │
        ├── DEM ── Flow ── Slope / TRI / TWI / HAND / flow_log
        │
        └── Sentinel-1 ── VV, VH
                          │
        11 bandes ────────┴──► Random Forest ──► Carte classée
        WorldCover ──────────► (labels)
```

## 5. Résultats

### 5.1 Évolution des performances

Nous comparons deux versions : une première pipeline à 7 features
(spectral + terrain seulement) et la version finale à 11 features
(+ radar + bi-temporel).

| Classe (WorldCover) | v1 — 7 bandes | v2 — 11 bandes | Évolution |
|---------------------|:-------------:|:--------------:|:---------:|
| 10 — Forêt          | 0,90          | **0,93**       | =         |
| 30 — Prairie        | 0,64          | **0,69**       | ▲ +0,10   |
| 60 — Sol nu         | 0,44          | 0,33           | ▼ −0,11   |
| 80 — Eau            | 0,57          | **0,71**       | ▲ +0,14   |
| 90 — Zone humide    | 0,68          | 0,58           | ▼ −0,08   |

*(valeurs = rappel sur la diagonale de la matrice de confusion normalisée)*

L'apport du **radar** est net sur la classe **Eau** (+0,14) : la rétrodiffusion
spéculaire rend les surfaces en eau très contrastées. Le **bi-temporel** et le
**SAR** apparaissent tous deux dans le haut du classement d'importance des
variables, preuve qu'ils portent un signal réel.

### 5.2 Importance des variables (Gini)

```
BSI        ████████████████████  0,16
NDVI       ███████████████████   0,158
slope      ██████████████        0,115
TRI        █████████████         0,101
ΔNDVI      ███████████           0,089   ← bi-temporel
ΔBSI       ██████████            0,079   ← bi-temporel
VH         ██████████            0,079   ← radar
TWI        █████████             0,076
VV         █████████             0,070   ← radar
flow_log   ███████               0,054
HAND       █                     0,004
```

Les quatre variables ajoutées (ΔNDVI, ΔBSI, VV, VH) totalisent **≈ 32 %** de
l'importance : l'intuition de fusionner optique, radar et temporel est confirmée.

### 5.3 Limites identifiées

1. **Le verrou n'est plus technique, mais celui des labels.** ESA WorldCover ne
   possède **aucune classe « orpaillage »**. Sa classe « sol nu » (60), seule
   approximation disponible, est trop hétérogène : son rappel chute même à 0,33,
   confondue avec la prairie.

2. **Entraînement 2021, prédiction 2024.** Tout chantier apparu après la date des
   labels est, par construction, invisible pour le modèle supervisé.

3. **HAND inopérant ici (0,004).** Le littoral guyanais est trop plat pour que la
   hauteur au-dessus du drainage discrimine quoi que ce soit ; cette variable
   serait pertinente en relief d'intérieur.

En résumé : **nous avons saturé ce que les features peuvent apporter.** Aucune
variable supplémentaire ne corrigera l'absence de vérité terrain adéquate.

### 5.4 La turbidité, révélateur de ce que les labels ignorent

Pour rendre cette limite **tangible**, nous avons ajouté à la pipeline une branche
de visualisation dédiée : une **carte de turbidité** de l'eau en 2024, calculée par
le modèle de Nechad et al. (2010) à partir de la bande rouge de Sentinel-2 et
restreinte aux surfaces en eau (masque MNDWI).

Le principe physique est direct : l'orpaillage **draine le lit des rivières et
remet les sédiments en suspension**. Cette charge particulaire augmente fortement la
réflectance dans le rouge, donc la turbidité mesurée (en NTU). Une rivière
forestière intacte apparaît en bleu sombre (eau claire, peu réfléchissante) ; un
cours d'eau perturbé par un chantier ressort en **jaune-rouge vif**.

Or c'est précisément cette distinction que ESA WorldCover **efface** : sa classe
« eau » (80) regroupe indistinctement l'eau claire et l'eau chargée. La carte de
turbidité montre, à l'œil nu, le **sous-ensemble suspect** que le classifieur ne
peut pas isoler faute de label dédié. Elle ne remplace pas la vérité terrain — la
turbidité a d'autres causes naturelles (crues, estuaires) — mais elle **matérialise
la frontière manquante** et guide l'intuition : *voilà ce qu'il faudra apprendre au
modèle à reconnaître.*

C'est aussi une piste de feature future : un seuil de turbidité, ou son évolution
bi-temporelle le long du réseau hydrographique (croisé avec l'accumulation de flux
déjà calculée), constituerait un indicateur d'orpaillage bien plus spécifique que
le « sol nu » générique.

## 6. La prochaine étape

La conclusion oriente clairement la suite : **construire un jeu de vérité terrain
spécifique à l'orpaillage.**

- **Collecte de sites confirmés** auprès des acteurs de terrain (données issues du
  suivi de type Harpie).
- **Annotation interactive** des sites sur nos images, via l'outil
  d'échantillonnage déjà intégré à la pipeline.
- **Random Forest binaire** *forêt saine vs. chantier*, entraîné sur ces
  annotations plutôt que sur une carte d'occupation générique.

La chaîne de features (spectral + terrain + radar + bi-temporel) est déjà en place
et **prête à accueillir ces nouveaux labels** dès qu'ils seront disponibles.

## 7. Note de méthode : concevoir une pipeline par le regard

Au-delà du résultat, la manière dont cette pipeline a été *construite* mérite un
mot — car elle illustre un parti pris d'outillage.

### 7.1 Le feedback visuel comme moteur d'intuition

Chaque étape de notre traitement — chaque indice, chaque dérivé de terrain, chaque
composite radar — **affiche son propre aperçu en direct**, sur le nœud lui-même.
Nous ne lisons pas une statistique après coup : nous *voyons* immédiatement ce que
produit chaque opération.

Cette boucle de retour courte change la nature du travail. Quand le MNDWI dessine
mal les berges, on le voit. Quand le hillshade révèle un relief plat, on comprend
sur-le-champ pourquoi le HAND sera inutile (cf. §5.3). Quand la carte de turbidité
fait surgir une rivière en rouge, une hypothèse naît — *et si c'était un chantier ?*
L'analyse cesse d'être une exécution aveugle de scripts pour devenir un **dialogue
visuel** avec la donnée. L'ajout de la branche turbidité (§5.4) est né exactement de
ce réflexe : « il manque une image qui rende la limite visible. »

L'intuition du concepteur — savoir quelle variable ajouter, laquelle abandonner —
se nourrit de ce regard permanent. Les meilleures décisions de cette pipeline (fusionner
le radar, ajouter le bi-temporel, abandonner HAND) sont venues de l'observation, pas
du calcul.

Un épisode illustre ce point à lui seul. La première carte de turbidité produite
semblait **uniformément plate** : un bleu monotone, décevant. Le réflexe a été non
pas de croire le rendu, mais de **sonder la donnée elle-même** — en branchant la
sortie brute sur l'outil d'échantillonnage interactif. Surprise : les valeurs
étaient en réalité **richement nuancées**. Le rendu par défaut, en masquant les
terres et en étalant une eau de réservoir homogène, *écrasait* un signal pourtant
bien présent. Mieux : les valeurs élevées se concentraient sur des **taches de sol
nu** — clairières, pistes, chantiers potentiels — exactement la signature
recherchée. C'est en *regardant la donnée par une autre fenêtre* qu'on a compris
qu'il fallait changer la colormap et le masque, transformant une visualisation
muette en révélateur de zones perturbées. Aucune statistique agrégée n'aurait
soufflé cette correction ; le contact visuel direct, si.

### 7.2 Graphe de nœuds vs. empilement de couches

L'approche dominante en SIG (ArcGIS, QGIS) raisonne en **couches** et en **boîtes à
outils** : on empile des rasters, on lance un outil qui écrit un fichier de sortie,
puis un autre qui le relit. Le flux de données est implicite, dispersé dans une
succession d'étapes et de fichiers intermédiaires.

Une conception **par graphe de nœuds** inverse la logique : le flux de données *est*
le document. Les avantages observés sur ce projet :

- **Traçabilité totale.** Le chemin d'un pixel — du téléchargement Copernicus
  jusqu'à la prédiction RF — se lit d'un coup d'œil sur le graphe. Aucune étape
  cachée, aucun fichier temporaire oublié.
- **Inspectabilité à chaud.** N'importe quel nœud intermédiaire est visualisable
  instantanément, sans avoir à ré-exécuter ou exporter. On « sonde » la pipeline
  comme on poserait une sonde sur un circuit.
- **Réutilisation et modularité.** Le bloc de dérivés DEM, la fusion de bandes, le
  classifieur sont des briques génériques recombinables. La branche turbidité a été
  greffée en quelques nœuds sans toucher au reste.
- **Itération non destructive.** Brancher/débrancher une feature pour tester son
  apport est l'affaire d'un lien — là où le paradigme par couches impose souvent de
  reconstruire une chaîne de géotraitement entière.
- **Parallélisme lisible.** Les branches indépendantes (optique, radar, terrain,
  bi-temporel) cohabitent visuellement et convergent explicitement vers la fusion.

En somme, le graphe de nœuds ne fait pas qu'exécuter un traitement : il **expose la
pensée** derrière ce traitement. Pour un travail exploratoire comme la recherche
d'une signature d'orpaillage — où l'on ne sait pas d'avance quelles variables
porteront le signal — cette transparence est un accélérateur d'intuition plus qu'un
simple confort d'interface.

---

## Annexe — Repères bibliographiques sur les algorithmes

**Dérivés du modèle numérique de terrain (DEM)**

- **Horn, B. K. P. (1981).** *Hill shading and the reflectance map.* Proceedings of
  the IEEE, 69(1), 14–47. — Méthode de gradient 3×3 pondéré utilisée pour la pente,
  l'exposition et l'ombrage (référence GDAL/ArcGIS).
- **Riley, S. J., DeGloria, S. D., & Elliot, R. (1999).** *A terrain ruggedness
  index that quantifies topographic heterogeneity.* Intermountain Journal of
  Sciences, 5(1–4), 23–27. — Définition du TRI.
- **O'Callaghan, J. F., & Mark, D. M. (1984).** *The extraction of drainage networks
  from digital elevation data.* Computer Vision, Graphics, and Image Processing,
  28(3), 323–344. — Algorithme D8 de direction et d'accumulation de flux.
- **Beven, K. J., & Kirkby, M. J. (1979).** *A physically based, variable
  contributing area model of basin hydrology.* Hydrological Sciences Bulletin,
  24(1), 43–69. — Introduction de l'indice topographique d'humidité (TWI).
- **Rennó, C. D., Nobre, A. D., et al. (2008).** *HAND, a new terrain descriptor
  using SRTM-DEM.* Remote Sensing of Environment, 112(9), 3469–3481. — Définition
  du descripteur HAND (hauteur au-dessus du drainage le plus proche).

**Classification**

- **Breiman, L. (2001).** *Random Forests.* Machine Learning, 45(1), 5–32. —
  Algorithme de forêt aléatoire, fondement du classifieur pixel à pixel et de
  l'importance des variables par indice de Gini.

**Données et indices spectraux**

- **Rouse, J. W., et al. (1974).** *Monitoring vegetation systems in the Great
  Plains with ERTS.* — Définition originelle du NDVI.
- **Rikimaru, A., Roy, P. S., & Miyatake, S. (2002).** *Tropical forest cover
  density mapping.* Tropical Ecology, 43(1). — Famille des indices de sol nu (BSI).
- **Nechad, B., Ruddick, K. G., & Park, Y. (2010).** *Calibration and validation of
  a generic multisensor algorithm for mapping of total suspended matter in turbid
  waters.* Remote Sensing of Environment, 114(4), 854–866. — Modèle de turbidité /
  matière en suspension utilisé pour la carte de turbidité (§5.4).
- **Zanaga, D., et al. (2021).** *ESA WorldCover 10 m 2020 v100.* — Produit
  d'occupation du sol utilisé comme source de labels.
- **Programme Copernicus / ESA** — Sentinel-1 (SAR) et Sentinel-2 (optique),
  Copernicus DEM GLO-30 ; accès via le Copernicus Data Space Ecosystem et
  Microsoft Planetary Computer.
