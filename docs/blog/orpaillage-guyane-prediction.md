# Prédire l'orpaillage : enquête sur un signal qui se dérobe

*Suite du [carnet d'exploration](orpaillage-guyane.md). On ne cherche plus à **voir** les chantiers — on cherche à **deviner où les prochains vont naître**. C'est une enquête : une série de verrous, quelques murs, deux ou trois fausses joies, et au bout, un résultat modeste mais que je peux défendre ligne par ligne.*

---

> **Note de méthode.** Ce texte raconte une investigation réelle, avec ses
> impasses laissées en place — parce que les impasses sont la moitié du travail.
> J'y suis tombé dans deux pièges méthodologiques classiques ; chacun donnait un
> résultat flatteur et faux. Les démonter, l'un après l'autre, c'est ce qui a fait
> passer le modèle du joli-mais-bidon au modeste-mais-vrai. C'est cette
> trajectoire-là qui m'intéresse.

---

## 1. Le point de départ : une vérité terrain, enfin

Le carnet précédent butait sur un manque : toute la chaîne de variables était
prête, mais sans **vérité terrain spécifique à l'orpaillage**, impossible
d'entraîner quoi que ce soit.

Cette pièce existe. La Guyane publie, via GéoGuyane, les données de l'**OAM**
(Observatoire de l'Activité Minière) : les polygones des surfaces réellement
exploitées, datés, typés (alluvionnaire, primaire, campement…), avec leur statut
légal. Plus de 22 000 entités. Filtré sur *illégal × alluvionnaire* :
**15 186 sites confirmés**.

La question se pose alors nettement, et elle est tranchante : **à partir des sites
connus fin 2022, peut-on prédire où de nouveaux sites apparaîtront en 2023 ?**

Tout l'enjeu de l'enquête tient dans ce mot — *prédire*. On verra qu'il est bien
plus exigeant qu'il n'en a l'air.

---

## 2. Fausse piste n°1 : la propagation

Première hypothèse, la plus naturelle : un chantier en attire d'autres autour de
lui. Je monte un nœud de **propagation Monte Carlo** — on part des sites actifs,
on simule des centaines de fois une expansion stochastique modulée par
l'attractivité du terrain, on accumule une carte de probabilité.

Le résultat est séduisant : des halos nets autour de chaque site. Et c'est
exactement le piège. **Un halo n'est pas une prédiction** : le modèle dilate ce
qui existe déjà. Il répond à « jusqu'où s'étend ce site ? », jamais à « où un
*nouveau* site va surgir ? ». Pour l'expansion locale, c'est juste. Pour
l'émergence, c'est une tautologie peinte en carte de chaleur.

Premier verrou identifié : *propagation ≠ prédiction*. Il faut changer de
paradigme — passer à un modèle de **susceptibilité**, un profil du « site idéal »
appris sur les données puis projeté sur tout le territoire.

---

## 3. Deux modèles pour traquer le profil

Je monte **deux modèles en parallèle**, par méthode :

- **Random Forest** — exemples positifs : les sites OAM ; négatifs : des pixels
  tirés au hasard ailleurs. Il apprend la combinaison de critères qui signe un
  site, et il livre l'**importance** de chaque variable. C'est mon détecteur de
  mensonge : si une intuition de terrain est fausse, l'importance le dira.
- **MCDA** — somme pondérée de critères normalisés, poids choisis à la main.
  Transparent, défendable, lisible.

Le RF découvre les poids ; le MCDA les expose. Deux angles sur la même cible.

---

## 4. L'indice de terrain : remonter le fleuve

Un détail rapporté par les acteurs de terrain accroche : une équipe délogée
**remonte le fleuve d'une quarantaine de kilomètres** avant de se réinstaller. Le
réseau hydrographique est leur autoroute ; l'accès se fait en pirogue.

La distance euclidienne classique passe complètement à côté de ça. Il me faut une
**distance le long du réseau de drainage, vers l'amont**. J'écris le nœud
`geo_upstream_distance` : depuis les directions d'écoulement du DEM (D8), il
remonte le réseau depuis chaque site connu, en accumulant la distance, plafonnée à
40 km.

La construction est propre — le bassin amont d'un point forme un arbre, donc
chaque cellule atteinte a un chemin unique ; un parcours en largeur suffit, exact
au pixel près sur mes rivières-tests. Le nœud marche. Je tiens, je crois, ma
variable maîtresse.

---

## 5. Premier mur : la fuite de cible

Je branche, je lance le Random Forest, je regarde l'importance :

```
upstream_dist   0.88   ← écrase tout le reste
flow_acc        0.059
ndvi            0.040
slope           0.011
hand            0.009
```

Fausse joie. Une variable à 0.88, ce n'est pas une victoire, c'est un signal
d'alarme. La distance amont est **calculée à partir des sites OAM** — qui sont
aussi mes étiquettes. Elle vaut zéro exactement là où il y a un site. Le modèle
n'apprend rien : il recopie la réponse. *« Proche d'un site connu = un site. »*

C'est une **fuite de cible** : la réponse s'est infiltrée dans les entrées. Le
piège canonique du machine learning supervisé, et j'y suis allé tout droit.

Le déverrouillage est conceptuel : `upstream_distance` n'est pas une variable
d'apprentissage, c'est une **contrainte spatiale** à appliquer *après* le modèle.
Le RF apprend le profil intrinsèque ; la distance amont filtre ensuite les zones
atteignables. Deux étages, étanches l'un à l'autre.

Importance après nettoyage — équilibrée, donc enfin crédible :

```
ndvi      ~0.35      slope   ~0.30
flow_acc  ~0.26      hand    ~0.09
```

Premier verrou sauté. Le modèle apprend désormais un vrai profil
géomorpho-spectral. Mais apprendre le passé ne prouve rien — reste à le mettre à
l'épreuve du futur.

---

## 6. Le juge de paix : la validation temporelle

Un modèle qui « explique » l'existant ne vaut rien tant qu'il n'a pas prédit du
**neuf**. Le seul test qui tienne est temporel : entraîner sur ce qu'on savait fin
2022, confronter aux sites réellement apparus en 2023.

La règle, gravée :

```
Tout ce qui nourrit le modèle  → ≤ 2022
La vérité de contrôle          → 2023
Du 2023 dans les entrées       → on triche
```

Mon nœud de validation calcule, pour les nouveaux sites 2023, le **recall**
(combien on en attrape) et surtout l'**enrichissement** : la densité de nouveaux
sites dans la zone prédite, rapportée au hasard. Enrichissement de 1 = tirage au
sort. De 5 = le modèle concentre le risque cinq fois mieux que l'aléatoire.

C'est ce chiffre-là qui va arbitrer toute la suite.

---

## 7. Le grand mur : l'hypothèse de la remontée s'effondre

Verdict du modèle à deux étages :

```
enrichissement     5.2×    ← le signal existe, indéniablement
recall             1.1%    ← 2 sites sur 182 capturés
surface candidate  0.21%
```

Apparente contradiction : le modèle vise juste (5×) mais ne capture quasi rien. Un
diagnostic que j'avais ajouté tranche d'un coup :

```
FN_beyond_40km = 180 / 182
```

**180 des 182 nouveaux sites de 2023 ne sont reliés en amont à aucun site connu de
2022.** La zone fait 22 km de large — 40 km de portée couvrent tout le réseau en
distance. Le frein n'est donc pas la distance : c'est la **connectivité**. Les
nouveaux sites naissent sur d'autres sous-bassins, en aval, sur des criques non
raccordées.

Je refuse d'en rester à une intuition. Je pousse le test à l'extrême : seed sur
**tous les sites, toutes années, tous types** (1990-2022). Si la remontée comptait,
le mur devrait reculer.

```
FN_beyond_40km = 175 / 182
```

Il ne bouge pas. **L'hypothèse de la remontée, si convaincante sur le terrain,
n'explique qu'environ 1 % de l'émergence.** Le modèle est *parfait* sur son
hypothèse — 100 % de recall sur les rares sites atteignables — mais l'hypothèse
elle-même est marginale.

Ce n'est pas un échec : c'est un **résultat**. Établi, reproductible, défendable :
à Dorlin, l'orpaillage ne se propage pas principalement par remontée depuis
l'existant. Il émerge en fronts indépendants. Un verrou de plus saute — celui
d'une idée reçue.

---

## 8. Forcer le profil : nouvelles variables

Si la contrainte spatiale ne sauve rien, tout repose sur la **qualité du profil**.
Quatre variables, c'est maigre. Deux fronts d'attaque.

**Les signatures de chantier (Sentinel-2)** — j'ajoute BSI (sol nu), MNDWI et NDWI
(eau turbide), les marqueurs directs d'un site minier.

**La géologie** — sur les flux de [guyane-sig.fr](https://www.guyane-sig.fr), je
tombe sur **652 couches** servies en WFS. Et le graal :
`FAVORABILITE_AURIFERE_FORMATIONS_GEOLOGIQUES_BRGM_2001`. La favorabilité aurifère
des formations, par le BRGM.

J'en fais un nœud générique, `geo_wfs_loader` : il tire n'importe quelle couche
WFS, la reprojette, la rasterise, avec une table catégorie → valeur. Je range les
dix lithologies selon la métallogénie du bouclier guyanais : 3 pour les unités
volcaniques/mafiques (l'hôte classique de l'or orogénique), 2 pour pélites et
gabbros, 1 pour les grès. Sur le papier, c'est exactement la variable qui me
manquait.

---

## 9. Double mur : la géologie muette et le futur dans les entrées

Test grandeur nature sur Dorlin :

```
Bbox Dorlin (22 km) → un seul polygone volcanique → favorabilité 3 partout
```

Dorlin est **entièrement** dans la ceinture volcanique Paramaca. Une seule
formation. À cette échelle, la géologie est **uniforme** : elle ne discrimine
rien. Elle vaudrait sur un bassin entier, à cheval sur plusieurs formations — pas
ici. Variable réelle, nœud propre, **apport local nul**. Deuxième fausse joie.

Et en cherchant pourquoi les indices Sentinel-2 ne bougeaient pas davantage le
résultat, le second mur se révèle, plus grave. Mon imagerie S2 datait de **2023**.
Or utiliser le sol nu de 2023 pour « prédire » les sites de 2023, ce n'est pas
prédire — **c'est lire la cicatrice**. Le sol nu *est* le chantier.

```
DÉTECTION   : S2 de l'année courante → trouver les chantiers actifs   (fort, facile)
PRÉDICTION  : variables ANTÉRIEURES à l'émergence → où ça va surgir     (faible, dur)
```

Seconde fuite, temporelle cette fois. Pour une prédiction propre, l'imagerie doit
précéder l'année cible. Je recule le S2 à 2021-2022 — forêt encore intacte. Mais
alors le sol nu est quasi nul partout : pas encore de chantier. **L'optique ne
prédit pas, elle constate après coup.** Limite physique, non négociable.

---

## 10. Ce qui reste debout — et tient

Les deux fuites colmatées, voici la vraie courbe du modèle prédictif
(susceptibilité de terrain, variables strictement antérieures à 2023) :

| seuil | recall | surface | enrichissement |
|------:|-------:|--------:|---------------:|
| 0.72  | 36 %   | 20 %    | 1.8×           |
| 0.76  | 22 %   | 9 %     | 2.5×           |
| 0.80  | 18 %   | 4.4 %   | **4.0×**       |
| 0.85  | 11 %   | 1.7 %   | 6.5×           |

Pas de coude miraculeux : un compromis pur. Plus on resserre, plus on concentre le
risque, moins on capture. Le signal est **réel mais faible** — il ne vit que dans
le dernier décile du score.

Le chiffre que je peux défendre, sans astérisque : prédire *où* un nouveau site va
naître à partir de la seule géomorphologie plafonne autour de **4× le hasard, pour
18 % de recall sur 4 % du territoire**. Traduit en opérations : une brigade qui ne
peut couvrir que 4 % de la zone multiplie par quatre ses chances de tomber sur un
front neuf. C'est un **outil de ciblage**, pas un pointeur de sites — et la
distinction est honnête, pas timide.

La raison de fond se tient debout toute seule : *l'endroit exact* d'un front
d'orpaillage dépend de facteurs absents de ma grille — filons, logistique des
réseaux, déplacement des pressions policières, décisions humaines. La
géomorphologie pose les **conditions de possibilité** ; elle ne fixe pas le point.
Ça, c'est démontré, pas supposé.

---

## 11. Le bilan d'enquête

Trois acquis, plus solides que la carte finale :

1. **La fuite est la règle, pas l'exception.** Deux trouvées : une fuite de cible
   (variable dérivée des étiquettes), une fuite temporelle (le futur dans les
   entrées). Les deux produisaient des scores flatteurs et faux. Le réflexe « c'est
   trop beau » est le meilleur garde-fou de la discipline.

2. **Un bel outil n'est pas un outil utile.** `upstream_distance` et la géologie
   BRGM sont bien construits, testés, réutilisables — et tous deux quasi sans effet
   à Dorlin. Construire l'instrument et mesurer son apport réel sont deux gestes
   distincts ; ne jamais confondre l'un avec l'autre.

3. **Détecter et prédire sont deux métiers.** Trouver les chantiers actifs marche
   très bien (détection optique, c'est le carnet précédent). Deviner les prochains
   est d'un autre ordre de difficulté — et toute la rigueur consiste à ne pas
   maquiller l'un en l'autre.

L'enquête s'est menée **dans le graphe**, à coups de nœuds rebranchés et de
paramètres glissés en direct. C'est ce qui a rendu les deux fuites *visibles* —
l'une dans un histogramme d'importance, l'autre en confrontant deux dates
d'imagerie côte à côte. L'outil n'a pas fait la science ; il a rendu les erreurs
détectables assez vite pour qu'on les corrige. Une erreur qu'on voit est une
erreur déjà à demi résolue.

---

## 12. Pistes ouvertes

- **Assumer la détection.** Le signal fort est là, sur l'imagerie courante. Un
  détecteur Sentinel-1 (radar, qui perce les nuages guyanais) couplé au
  Sentinel-2, validé sur l'OAM, serait opérationnel tout de suite.
- **Changer d'échelle pour la géologie.** Sur un bassin entier, à cheval sur
  plusieurs formations, la favorabilité aurifère redevient discriminante. Le
  `geo_wfs_loader` est prêt.
- **Hybrider.** Détecter les fronts frais, puis simuler leur propagation locale à
  court terme. Là, le Monte Carlo retrouve un sens — non plus prédire l'émergence,
  mais l'expansion d'un foyer déjà allumé.

Je referme ce chapitre sur un modèle modeste et un cap tenu. Je ne sais toujours
pas prédire l'orpaillage — mais je sais désormais *pourquoi* c'est dur, je l'ai
**mesuré**, et j'ai deux fuites de moins dans mes réflexes. Ce ne sont pas des
conclusions spectaculaires ; ce sont des conclusions qui tiennent.

---

*Tous les nœuds évoqués (`geo_upstream_distance`, `geo_wfs_loader`,
`util_monte_carlo_propagation`, le pipeline de susceptibilité et sa validation
temporelle) sont des plugins Python de VNStudio, testés unitairement. Le modèle,
ses deux étages et sa validation tiennent dans un seul graphe rechargeable.*
