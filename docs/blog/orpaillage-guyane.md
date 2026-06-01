# Sur les traces de l'orpaillage illégal en Guyane : un carnet d'exploration par télédétection

*Comment j'ai détourné un studio de vision par nœuds pour partir à la recherche des chantiers clandestins, en deux temps : explorer le terrain, puis modéliser.*

---

> **Disclaimer.** Je ne suis pas géographe, ni télédétecteur, ni spécialiste de la
> Guyane. Je teste **VNStudio**, un outil que je construis, sur un cas réel et
> concret — parce qu'un vrai problème est le meilleur banc d'essai qui soit. Je
> tâtonne, je me trompe, j'apprends en regardant. Je m'amuse, surtout. Et
> j'espère qu'au bout du compte il en sortira quelque chose d'utile. Ce texte est
> un carnet de bord honnête, pas une publication scientifique : prenez mes
> conclusions pour ce qu'elles sont — celles d'un curieux qui bricole.

---

## 1. Le contexte : un fléau humain, social et écologique

Au cœur de l'Amazonie française, la Guyane abrite l'une des forêts primaires les
mieux conservées de la planète. Elle est aussi le théâtre d'une activité
clandestine massive : **l'orpaillage illégal**, l'extraction sauvage d'or dans le
lit et les berges des rivières.

Les conséquences se cumulent sur trois plans :

- **Écologique.** Le dragage des cours d'eau détruit les berges, met en suspension
  d'énormes quantités de sédiments (rivières « café au lait ») et anéantit les
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

La difficulté centrale, celle qui m'a accroché, c'est **la détection**. Les sites
(les *« chantiers »*) sont petits, mobiles, dispersés sur un territoire grand comme
le Portugal, souvent inaccessibles par voie terrestre et masqués par une couverture
nuageuse quasi permanente.

## 2. L'opération Harpie

Lancée en 2008 et pérennisée depuis, **l'opération Harpie** mobilise les Forces
armées en Guyane (FAG) et la gendarmerie pour lutter contre l'orpaillage illégal :
destruction des chantiers, interception des flux logistiques (carburant, mercure,
vivres) qui remontent les fleuves, et démantèlement des filières.

L'efficacité de ces opérations repose en grande partie sur le **renseignement
géographique** : savoir *où* chercher avant d'engager des moyens héliportés
coûteux. C'est précisément là que la **télédétection satellitaire** m'a semblé
pouvoir apporter quelque chose — repérer à distance, et de façon répétée dans le
temps, les signatures d'un chantier actif. C'est mon terrain de jeu pour ce projet.

## 3. Ma démarche, en deux temps

Je n'ai pas cherché à produire d'emblée une carte opérationnelle. J'ai procédé en
deux phases, comme on apprivoise un sujet qu'on ne connaît pas :

1. **Phase 1 — Explorer et comprendre.** Apprendre à quoi *ressemble* un site
   d'orpaillage vu du ciel, me familiariser avec le terrain guyanais, repérer des
   sites potentiels et observer comment la turbidité des rivières évolue dans le
   temps.

2. **Phase 2 — Caractériser et modéliser.** Ajouter la dimension du relief (à
   partir du modèle numérique de terrain) pour mieux cerner les conditions
   topographiques d'un chantier, puis construire un premier modèle de
   classification automatique.

Le tout entièrement avec des **données ouvertes et gratuites** (Copernicus,
Microsoft Planetary Computer), assemblées visuellement dans VNStudio.

## 4. Phase 1 — Explorer : apprendre à voir un chantier

### 4.1 Comparer deux dates

Mon point de départ : un site d'orpaillage **transforme** le paysage. Là où il y
avait de la forêt, apparaissent du sol nu et de l'eau boueuse. Plutôt que de
chercher une signature absolue, j'ai donc comparé **deux dates** d'images
Sentinel-2 (une image ancienne de référence, une image récente) sur la même zone.

Pour chaque date, je calcule deux indices :

- **NDVI** — la vigueur de la végétation. Une forêt intacte est très verte ; un
  chantier, presque nu.
- **MNDWI** — la présence d'eau. Il révèle le réseau hydrographique et les plans
  d'eau, là où se concentre l'activité.

### 4.2 Cartographier le changement

En croisant les deux dates, je construis une **carte de changement en quatre
couleurs** (un petit nœud Python dans le graphe) :

- **forêt stable** (NDVI élevé aux deux dates) ;
- **repousse** (végétation regagnée) ;
- **déforestation** (NDVI qui s'effondre) ;
- **eau** (et son intensité, qui trahit la turbidité).

Cette lecture met immédiatement en évidence les zones qui *bougent* — et l'œil est
attiré, naturellement, vers les pertes de forêt accolées à des rivières : la
signature géographique typique d'un chantier.

### 4.3 Découvrir des sites et suivre la turbidité

À partir de là, deux outils m'ont permis de passer de l'image à des *objets* :

- l'**extraction de centroïdes** des zones détectées — chaque tache de changement
  devient un point géolocalisé, une liste de **sites candidats** à inspecter ;
- l'**échantillonnage interactif** — je clique sur un pixel suspect et je lis ses
  valeurs spectrales, ce qui m'apprend petit à petit la « signature » d'un site.

Et surtout, en rejouant la comparaison sur plusieurs années, j'**observe
l'évolution de la turbidité** : une rivière qui passe du bleu sombre (eau claire)
au jaune-rouge (chargée de sédiments) raconte une activité d'orpaillage qui
s'installe en amont. Cette phase ne « détecte » rien automatiquement — elle me fait
**connaître le terrain** et formuler des hypothèses.

## 5. Phase 2 — Caractériser le terrain et modéliser

Forte des intuitions de la phase 1, la phase 2 (le graphe sur lequel je travaille
actuellement) ajoute deux choses : la **dimension du relief**, et un **modèle
automatique**.

### 5.1 Sources

| Source | Produit | Rôle |
|--------|---------|------|
| Sentinel-2 L2A | Optique 5 bandes (R, V, B, NIR, SWIR) @ 20 m | Indices spectraux |
| Sentinel-1 GRD | Radar SAR (VV, VH) @ 20 m | Eau turbide, sol nu sous les nuages |
| Copernicus DEM GLO-30 | Modèle numérique de terrain @ 30 m | Dérivés morphologiques et hydrologiques |
| ESA WorldCover | Carte d'occupation du sol 10 m | Labels d'entraînement |

L'image optique de Guyane est constamment voilée par les nuages. Le **radar
Sentinel-1**, qui les traverse, est donc un complément essentiel : l'eau chargée de
sédiments d'un chantier présente une rétrodiffusion caractéristique.

### 5.2 Onze variables par pixel

À partir des sources brutes, je dérive **onze variables**, regroupées en quatre
familles :

**Spectral (Sentinel-2)**
- **NDVI** — vigueur de la végétation `(NIR − Rouge) / (NIR + Rouge)`
- **BSI** — indice de sol nu (*Bare Soil Index*)

**Terrain (DEM)** — tous calculés par mes propres nœuds
- **Pente** (slope, Horn 1981)
- **TRI** — *Terrain Ruggedness Index* (Riley et al. 1999)
- **TWI** — *Topographic Wetness Index*, `ln(a / tan β)` (Beven & Kirkby 1979)
- **HAND** — *Height Above Nearest Drainage* (Rennó et al. 2008)
- **flow_log** — accumulation de flux D8 en échelle logarithmique

**Radar (Sentinel-1)**
- **VV** et **VH** — rétrodiffusion en dB selon les deux polarisations

**Bi-temporel (Sentinel-2 2021 → 2024)**
- **ΔNDVI** et **ΔBSI** — variation spectrale entre deux dates. La signature d'un
  chantier récent : une **chute de NDVI** (perte de couvert) couplée à une **hausse
  de BSI** (apparition de sol nu) — exactement ce que la phase 1 m'avait appris à
  reconnaître.

### 5.3 Assemblage et classification

Les onze bandes sont fusionnées par empilements successifs (`Band Stack`) sur une
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

### 5.4 Résultats

Je compare deux versions : une première à 7 variables (spectral + terrain
seulement) et la version à 11 variables (+ radar + bi-temporel).

| Classe (WorldCover) | v1 — 7 var. | v2 — 11 var. | Évolution |
|---------------------|:-----------:|:------------:|:---------:|
| 10 — Forêt          | 0,90        | **0,93**     | =         |
| 30 — Prairie        | 0,64        | **0,69**     | ▲ +0,10   |
| 60 — Sol nu         | 0,44        | 0,33         | ▼ −0,11   |
| 80 — Eau            | 0,57        | **0,71**     | ▲ +0,14   |
| 90 — Zone humide    | 0,68        | 0,58         | ▼ −0,08   |

*(valeurs = rappel sur la diagonale de la matrice de confusion normalisée)*

L'apport du **radar** est net sur la classe **Eau** (+0,14) : sa rétrodiffusion
spéculaire rend les surfaces en eau très contrastées. Le **bi-temporel** et le
**SAR** apparaissent tous deux dans le haut du classement d'importance des
variables — la preuve qu'ils portent un signal réel.

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

## 6. La turbidité, mon meilleur appui visuel

S'il y a une chose que ce projet m'a apprise, c'est l'importance de **voir** la
donnée. Et la **carte de turbidité** est devenue mon repère le plus parlant.

Le principe est physique : l'orpaillage **draine le lit des rivières et remet les
sédiments en suspension**. Cette charge particulaire augmente la réflectance dans
le rouge. Une rivière forestière intacte apparaît en bleu sombre ; un cours d'eau
perturbé par un chantier ressort en **jaune-rouge vif**.

Mais cette image ne m'a pas été donnée facilement. Mes premiers essais sortaient
**uniformément plats** — un bleu monotone, décevant. J'ai failli conclure que la
donnée était pauvre. Le déclic : au lieu de croire le rendu, **sonder la donnée**
en branchant la sortie brute sur l'outil d'échantillonnage. Surprise — les valeurs
étaient en réalité **richement nuancées**. Le problème n'était pas la donnée mais
mon affichage : un intervalle de couleurs figé écrasait une dynamique pourtant bien
réelle. En **étirant les couleurs sur les seuls pixels d'eau** (un étirement par
percentiles), le réseau hydrographique a soudain révélé tout son dégradé — du bleu
limpide au rouge chargé, avec des **points chauds** trahissant les zones les plus
turbides.

Cette carte ne remplace pas une vérité terrain — la turbidité a d'autres causes
naturelles (crues, estuaires). Mais elle **matérialise** ce que les classes
génériques ignorent, et elle guide l'œil vers les bons endroits. C'est, à ce stade,
mon meilleur outil de découverte.

## 7. Les limites (que j'assume)

1. **Le verrou n'est pas technique, mais celui des labels.** ESA WorldCover ne
   possède **aucune classe « orpaillage »**. Sa classe « sol nu » (60), seule
   approximation, est trop hétérogène : son rappel chute à 0,33, confondue avec la
   prairie. Mon modèle ne peut pas apprendre une classe qu'on ne lui montre jamais.

2. **J'entraîne sur 2021 et je prédis sur 2024.** Tout chantier apparu après la
   date des labels est, par construction, invisible pour le modèle supervisé.

3. **HAND inopérant ici (0,004).** Le littoral guyanais est trop plat pour que la
   hauteur au-dessus du drainage discrimine quoi que ce soit ; cette variable
   brillerait en relief d'intérieur.

En clair : j'ai **saturé ce que les variables peuvent apporter**. Aucune feature
supplémentaire ne corrigera l'absence d'une vérité terrain adéquate.

## 8. La prochaine étape

La suite est limpide : **construire un jeu de vérité terrain spécifique à
l'orpaillage.**

- **Collecter des sites confirmés** auprès des acteurs de terrain (le suivi de type
  Harpie).
- **Annoter** ces sites sur mes images, via l'outil d'échantillonnage déjà en place.
- Entraîner un **Random Forest binaire** *forêt saine vs. chantier* sur ces
  annotations, plutôt que sur une carte d'occupation générique.

Toute la chaîne de variables (spectral + terrain + radar + bi-temporel) est déjà
construite et **prête à accueillir ces labels** dès que je les aurai.

## 9. Note de méthode : concevoir une pipeline par le regard

Au-delà du résultat, la manière dont j'ai *construit* ces graphes mérite un mot —
car c'est, je crois, ce qui a rendu l'exploration possible.

### 9.1 Le feedback visuel comme moteur d'intuition

Dans VNStudio, chaque étape — chaque indice, chaque dérivé de terrain, chaque
composite radar — **affiche son propre aperçu en direct**, sur le nœud lui-même. Je
ne lis pas une statistique après coup : je *vois* immédiatement ce que produit
chaque opération.

Cette boucle de retour courte change tout. Quand le MNDWI dessine mal les berges,
je le vois. Quand l'ombrage révèle un relief plat, je comprends sur-le-champ
pourquoi le HAND sera inutile (cf. §7). Et l'épisode de la turbidité (§6) résume
tout : c'est en *regardant la donnée par une autre fenêtre* que j'ai compris que le
signal était là, et qu'il fallait corriger l'affichage, pas la donnée. Aucune
statistique agrégée ne m'aurait soufflé cette correction. Mes meilleures décisions
(fusionner le radar, ajouter le bi-temporel, abandonner HAND) sont toutes nées de
l'observation, pas du calcul.

### 9.2 Graphe de nœuds vs. empilement de couches

L'approche classique en SIG (ArcGIS, QGIS) raisonne en **couches** et en **boîtes à
outils** : on empile des rasters, on lance un outil qui écrit un fichier, qu'un
autre relit. Le flux de données est implicite, éclaté entre des étapes et des
fichiers intermédiaires.

Le **graphe de nœuds** inverse la logique : le flux de données *est* le document.
Sur ce projet, j'y ai gagné :

- **Traçabilité totale.** Le trajet d'un pixel — du téléchargement à la prédiction
  — se lit d'un coup d'œil. Aucune étape cachée, aucun fichier temporaire oublié.
- **Inspectabilité à chaud.** N'importe quel nœud intermédiaire est visualisable
  instantanément, sans ré-exécuter ni exporter. Je « sonde » la pipeline comme on
  pose une sonde sur un circuit — c'est exactement ce qui a sauvé la turbidité.
- **Modularité.** Le bloc de dérivés DEM, la fusion de bandes, le classifieur sont
  des briques recombinables. Greffer la branche turbidité m'a pris quelques nœuds.
- **Itération non destructive.** Brancher/débrancher une variable pour tester son
  apport est l'affaire d'un lien — là où le paradigme par couches impose souvent de
  reconstruire toute une chaîne de géotraitement.
- **Parallélisme lisible.** Optique, radar, terrain, bi-temporel cohabitent
  visuellement et convergent explicitement vers la fusion.

Le graphe ne fait pas qu'exécuter un traitement : il **expose la pensée** derrière
ce traitement. Pour un travail exploratoire comme le mien — où je ne savais pas
d'avance quelles variables porteraient le signal — cette transparence a été un
accélérateur d'intuition bien plus qu'un simple confort d'interface. C'est aussi,
au passage, ce que j'essaie de mettre dans VNStudio.

---

## Annexe — Repères bibliographiques sur les algorithmes

**Dérivés du modèle numérique de terrain (DEM)**

- **Horn, B. K. P. (1981).** *Hill shading and the reflectance map.* Proceedings of
  the IEEE, 69(1), 14–47. — Gradient 3×3 pondéré utilisé pour la pente, l'exposition
  et l'ombrage (référence GDAL/ArcGIS).
- **Riley, S. J., DeGloria, S. D., & Elliot, R. (1999).** *A terrain ruggedness
  index that quantifies topographic heterogeneity.* Intermountain Journal of
  Sciences, 5(1–4), 23–27. — Définition du TRI.
- **O'Callaghan, J. F., & Mark, D. M. (1984).** *The extraction of drainage networks
  from digital elevation data.* Computer Vision, Graphics, and Image Processing,
  28(3), 323–344. — Algorithme D8 de direction et d'accumulation de flux.
- **Beven, K. J., & Kirkby, M. J. (1979).** *A physically based, variable
  contributing area model of basin hydrology.* Hydrological Sciences Bulletin,
  24(1), 43–69. — Indice topographique d'humidité (TWI).
- **Rennó, C. D., Nobre, A. D., et al. (2008).** *HAND, a new terrain descriptor
  using SRTM-DEM.* Remote Sensing of Environment, 112(9), 3469–3481. — Descripteur
  HAND.

**Classification**

- **Breiman, L. (2001).** *Random Forests.* Machine Learning, 45(1), 5–32. —
  Forêt aléatoire ; classifieur pixel à pixel et importance des variables (Gini).

**Données, indices spectraux et turbidité**

- **Rouse, J. W., et al. (1974).** *Monitoring vegetation systems in the Great
  Plains with ERTS.* — NDVI.
- **Xu, H. (2006).** *Modification of normalised difference water index (NDWI).*
  International Journal of Remote Sensing, 27(14), 3025–3033. — MNDWI (eau, SWIR).
- **Rikimaru, A., Roy, P. S., & Miyatake, S. (2002).** *Tropical forest cover
  density mapping.* Tropical Ecology, 43(1). — Indices de sol nu (BSI).
- **Nechad, B., Ruddick, K. G., & Park, Y. (2010).** *Calibration and validation of
  a generic multisensor algorithm for mapping of total suspended matter in turbid
  waters.* Remote Sensing of Environment, 114(4), 854–866. — Modèle de turbidité.
- **Zanaga, D., et al. (2021).** *ESA WorldCover 10 m 2020 v100.* — Occupation du
  sol utilisée comme source de labels.
- **Programme Copernicus / ESA** — Sentinel-1 (SAR), Sentinel-2 (optique),
  Copernicus DEM GLO-30 ; accès via le Copernicus Data Space Ecosystem et Microsoft
  Planetary Computer.
