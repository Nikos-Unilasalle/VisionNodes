# Patch pédagogique — Chapitre 17 : Descripteurs locaux et appariement
## Enrichissements pour rendre le chapitre opérationnel

> **Mode d'emploi.** Patch chirurgical — chaque bloc indique où il s'insère dans le chapitre existant. Le texte du chapitre n'est pas modifié ; ces blocs s'ajoutent.
>
> **Trois types d'ajouts :**
> - `💡 Image mentale` — analogie ou description visuelle à insérer dans le corps de la section.
> - `🔎 Ce que vous verriez` — description de l'effet observable, sans pipeline.
> - `📷 Observation` — exercice VNStudio au format du cahier.
>
> **Nœuds utilisés.** Beaucoup existent en standard : **Features (ORB/SIFT/AKAZE)** (`cv_features`), **RANSAC homographie** (`cv_ransac`), **Resize**, **Rotate**, **Brightness/Contrast**, **Warp Perspective**, **Noise (Gaussian)**, **Draw Overlay**, **Draw Point/Line**, **Grid Compare**, **Split Half**, **Color Space**, **Output Display**. Là où un calcul fin est demandé (ratio test réglable, espace d'échelle, HOG), on passe par un **Python Node** ; les scripts correspondants vont à l'annexe d'observation.

---

## Diagnostic général du chapitre 17

Le chapitre est complet et juste, mais il décrit une **chaîne de traitement** qu'un opérateur doit avant tout *voir tourner*. Quatre choses restent abstraites à la lecture seule :

1. **Pourquoi** un descripteur survit à une transformation alors qu'un patch de pixels échoue — il faut le voir échouer puis réussir sur la même paire d'images.
2. **Ce qu'est** une échelle caractéristique — un cercle dessiné autour d'un point, dont le rayon suit le zoom.
3. **Ce que fait** le ratio test — des lignes d'appariement qui se croisent en désordre, puis qui se rangent quand on serre le seuil.
4. **Ce que gagne** RANSAC — des correspondances triées en vert/rouge, et deux images qui s'alignent enfin.

L'objectif de ce patch : que l'opérateur reparte avec des **réflexes** — « mes appariements sont mauvais → je serre le ratio », « ma scène est répétitive → je m'appuie sur la géométrie », « peu d'inliers → je ne fais pas confiance à l'homographie ».

---

## 1. Section 17.1 — Le problème de l'appariement

### Ce qui est déjà bon

L'exemple chiffré du SSD qui explose pour un simple gain/offset est convaincant, et le cahier des charges des invariances est clair.

### Ce qui accroche

L'opérateur lit que « les pixels bruts échouent » mais ne l'a pas vu échouer. Tant qu'il n'a pas constaté qu'un descripteur retrouve un point que le SSD perd, l'intérêt de toute la machinerie reste théorique.

---

### 💡 Image mentale à insérer — après « Le descripteur doit donc être invariant à un ensemble explicite de transformations »

> **Image mentale : reconnaître un visage, pas mémoriser des pixels.**
> Vous reconnaissez un ami dans la rue sans avoir mémorisé la valeur de chaque pixel de son visage sous l'éclairage d'un jour précis. Ce que vous gardez, c'est ce qui ne change pas : les proportions, l'écart des yeux, la forme du nez — pas la teinte exacte de la peau à midi ou à l'ombre. Un bon descripteur fait le même tri. Il enregistre la structure stable du voisinage d'un point et jette ce que la lumière, la distance et l'angle font varier. C'est ce tri, et non une mémoire photographique, qui permet de retrouver le même point d'une vue à l'autre.

---

### 🔎 Ce que vous verriez

Sur une image et sa copie tournée de 30°, agrandie de 20 % et éclaircie :

- En comparant les **patchs bruts** (SSD), le meilleur « appariement » d'un coin part vers un point sans rapport : la mesure est dominée par la rotation et le gain, pas par le contenu.
- En comparant les **descripteurs ORB** des mêmes points, le coin retrouve son homologue : la ligne d'appariement relie bien les deux mêmes angles de fenêtre.

La même paire d'images, deux verdicts opposés selon ce qu'on compare. C'est la démonstration que l'invariance se construit dans le descripteur.

---

### 📷 Observation 17.A — Pixels bruts contre descripteurs : qui survit à la transformation ?

**Images fournies :** une photo de façade, et un cas applicatif au choix (étiquette de produit, page scannée, vue de drone).

**Pipeline :**
```
Image Loader → Rotate (30°) → Resize (×1.2) → Brightness/Contrast (+40)  [= la vue B transformée]
Image Loader ─┬→ Features (ORB) ─┐
Vue B  ───────┴→ Features (ORB) ─┴→ Python Node (appariement + ratio) → Draw Lines → Output Display
```

**Ce que vous allez vérifier :** qu'ORB retrouve les points homologues malgré rotation, échelle et éclairage, là où une comparaison de patchs bruts les perdrait.

**Missions**
1. Lancez l'appariement ORB entre la vue d'origine et la vue transformée. Combien d'appariements corrects (lignes parallèles, sans croisement) obtenez-vous ?
2. Dans le **Python Node**, remplacez la distance entre descripteurs par un SSD sur des patchs 16×16 bruts autour des mêmes points. Les lignes deviennent-elles incohérentes (croisements, directions aléatoires) ?
3. Augmentez progressivement l'angle de **Rotate** (10°, 30°, 60°, 90°). À partir de quel angle ORB commence-t-il à perdre des appariements ? Le constat : l'invariance n'est jamais parfaite, elle se dégrade.

---

## 2. Section 17.2 — Échelle caractéristique

### Ce qui est déjà bon

La dérivation du facteur `σ²` et l'exemple `σ₀ = s = 6` sont rigoureux ; l'analogie du diapason donne l'intuition de la résonance.

### Ce qui accroche

« Échelle caractéristique » reste un mot tant qu'on ne l'a pas vue : un point-clé n'est pas qu'une position, c'est une position **et** une taille. Et la propriété qui compte en pratique — la même structure est détectée à la bonne taille quand on zoome — doit être manipulée pour devenir un réflexe.

---

### 💡 Image mentale à insérer — après « Un extremum en (x₀, y₀, σ₀) donne la position du blob et son échelle caractéristique »

> **Image mentale : le bon recul pour lire un mot.**
> Un mot imprimé a une distance de lecture naturelle. Le nez collé à la page, vous ne voyez que le grain du papier ; à dix mètres, le mot a disparu ; entre les deux, il existe un recul où il se lit le mieux. L'espace d'échelle cherche exactement ce recul pour chaque structure de l'image. Le `σ` caractéristique d'un point-clé, c'est la distance de lecture de la tache à laquelle il appartient — la taille à laquelle cette tache « ressort » le plus du fond. Extraire le descripteur à cette taille-là, et non à une taille fixe, est ce qui le rend insensible au zoom.

---

### 🔎 Ce que vous verriez

Sur une image où le détecteur dessine un cercle par point-clé, de rayon proportionnel à `σ` :

- Les petits détails (coins de texte, grains) portent de **petits cercles** ; les grandes taches (un panneau, une lune) portent de **grands cercles**.
- En agrandissant l'image d'un facteur 2 (**Resize ×2**), les mêmes points sont redétectés avec des **cercles deux fois plus grands**. La position relative et l'identité des points tiennent ; seule l'échelle suit le zoom.

Cette mise à l'échelle automatique des cercles est l'invariance d'échelle, rendue visible.

---

### 📷 Observation 17.B — Le cercle qui suit le zoom

**Images fournies :** une scène à structures de tailles variées (par exemple un ciel étoilé, des cellules de tailles diverses, ou une plaque de circuit imprimé).

**Pipeline :**
```
Image Loader ─┬────────────────────────→ Features (SIFT, dessine échelle) → Draw Overlay → Output Display
              └→ Resize (×2) ───────────→ Features (SIFT, dessine échelle) → Draw Overlay → Output Display
                                                                      (comparer via Split Half)
```

**Ce que vous allez vérifier :** que l'échelle détectée d'un point suit proportionnellement l'agrandissement de l'image.

**Missions**
1. Repérez trois points-clés sur des structures de tailles nettement différentes. Le rayon du cercle est-il bien plus grand pour la grande structure ?
2. Comparez l'image d'origine et la version **Resize ×2** via **Split Half**. Un point-clé donné a-t-il un cercle environ deux fois plus grand dans la version agrandie ?
3. Cas d'opérateur : vos objets d'intérêt apparaissent à des distances très variables (caméra mobile, zoom optique). Pourquoi un détecteur **sans** espace d'échelle (Harris nu, §6.5) échouerait-il à les apparier d'une prise à l'autre ?

---

## 3. Section 17.3 — HOG

### Ce qui est déjà bon

L'exemple jouet de la rampe à 45° (tout le vote dans un seul bin) montre nettement le mécanisme du vote orienté.

### Ce qui accroche

Deux propriétés s'affirment sans se voir : HOG **résiste à l'éclairage** (donc le glyphe ne bouge pas quand on change la lumière) mais **n'est pas invariant en rotation** (donc le glyphe tourne avec l'image). Un opérateur qui ne l'a pas constaté appliquera HOG à un cas tourné et s'étonnera de l'échec.

---

### 💡 Image mentale à insérer — après « HOG décrit la distribution locale des orientations de bord »

> **Image mentale : la rose des vents des bords.**
> Chaque cellule HOG est une petite rose des vents : au lieu d'indiquer d'où vient le vent, elle indique dans quelles directions pointent les bords du voisinage, et avec quelle force. Une zone rayée verticalement donne une rose qui pointe fort vers l'horizontale (les bords sont verticaux, leurs gradients horizontaux) ; une zone lisse donne une rose plate, sans direction dominante. Décrire une image par HOG, c'est la couvrir d'un quadrillage de ces petites roses. Tourner l'image fait tourner toutes les roses d'un bloc — ce qui explique d'un coup pourquoi HOG ne résiste pas à la rotation.

---

### 🔎 Ce que vous verriez

Sur la visualisation HOG (le glyphe en étoile par cellule) d'une silhouette ou d'un objet manufacturé :

- En montant la **luminosité** de +60 et le **contraste** modérément, les étoiles HOG **ne bougent quasiment pas** : les orientations des bords sont conservées, c'est l'invariance d'éclairage.
- En appliquant une **rotation** de 20°, les étoiles **tournent toutes** : le descripteur global change, deux HOG du même objet à deux orientations ne se ressemblent plus.

---

### 📷 Observation 17.C — HOG : insensible à la lumière, sensible à la rotation

**Images fournies :** une silhouette de piéton (ou une pièce mécanique sur fond uni), cas typiques où HOG est employé.

**Pipeline :**
```
Image Loader → Brightness/Contrast (réglable) → Python Node (HOG, visualize) → Output Display
            ↘ Rotate (réglable) ─────────────→ Python Node (HOG, visualize) → Output Display
                                                                 (comparer via Grid Compare)
```

**Ce que vous allez vérifier :** que le descripteur HOG est stable sous changement d'éclairage et instable sous rotation.

**Missions**
1. Faites varier **Brightness/Contrast** sur une large plage. Le glyphe HOG change-t-il visiblement ? Pourquoi le passage au gradient puis la normalisation par bloc rendent-ils HOG aveugle à ce changement ?
2. Faites tourner l'image de 0° à 45°. À quel angle le glyphe devient-il méconnaissable par rapport à l'original ?
3. Réflexe à acquérir : pour quels cas HOG est-il le bon choix (détection de piétons, lecture de caractères à orientation connue) et pour lesquels faut-il lui préférer SIFT (objets d'orientation quelconque) ?

---

## 4. Section 17.4 — SIFT

### Ce qui est déjà bon

L'exemple de l'orientation dominante qui « tourne avec l'image » (gradient à 85° enregistré à 45° relatif, identique après rotation de 30°) explique précisément l'invariance de rotation.

### Ce qui accroche

Cette compensation d'orientation est le cœur de SIFT, et c'est exactement ce qu'on peut **montrer** : les flèches d'orientation des points-clés tournent avec la structure, si bien que les appariements survivent à une rotation qui mettrait HOG en échec.

---

### 💡 Image mentale à insérer — après « Décrire un point dans son référentiel propre revient à décrire un bâtiment depuis sa façade »

> **Image mentale : orienter la carte avant de la lire.**
> Avant de lire une carte en marchant, on la tourne pour que le « haut » corresponde à la direction où l'on va. La carte n'a pas changé, mais on la lit toujours dans le même repère, quel que soit le cap. SIFT fait cela pour chaque point-clé : il détecte d'abord l'orientation dominante du voisinage, puis tourne mentalement le patch pour décrire tous ses gradients dans ce repère. Deux vues du même point, prises avec l'appareil incliné différemment, produisent alors le même descripteur — parce que chacune a été « remise droite » avant d'être lue.

---

### 🔎 Ce que vous verriez

Sur deux vues d'une même scène, l'une tournée de 45° :

- Les **flèches d'orientation** des points-clés pointent, sur chaque vue, dans la direction propre de la structure locale ; entre les deux vues, ces flèches sont tournées de 45°, comme la scène.
- Les **lignes d'appariement** SIFT restent correctes après cette rotation : le nombre de bons appariements chute à peine, là où une comparaison HOG s'effondrerait.

---

### 📷 Observation 17.D — Les flèches qui tournent avec la scène

**Images fournies :** une couverture de livre ou une affiche (riche en coins), photographiée droite puis inclinée.

**Pipeline :**
```
Image Loader (vue droite)  → Features (SIFT, dessine orientation) ─┐
Image Loader (vue inclinée) → Features (SIFT, dessine orientation) ─┴→ Python Node (match + ratio) → Draw Lines → Output Display
```

**Ce que vous allez vérifier :** que l'orientation dominante absorbe la rotation, donc que les appariements y survivent.

**Missions**
1. Observez les flèches d'orientation sur les deux vues. Pour un même coin, l'écart angulaire entre les deux flèches correspond-il à l'inclinaison appliquée ?
2. Comptez les bons appariements à 0°, 45°, 90°. La chute est-elle douce (SIFT robuste) ou brutale ?
3. Refaites l'**Observation 17.C** (HOG) sur la même paire tournée : combien d'appariements HOG survivent à 45° ? La comparaison directe SIFT vs HOG ancre le rôle de l'étape d'orientation.

---

## 5. Section 17.5 — ORB et BRIEF

### Ce qui est déjà bon

L'exemple de la distance de Hamming (3 bits sur 8) et l'arbitrage vitesse/robustesse sont clairs.

### Ce qui accroche

L'arbitrage est un mot tant qu'on ne l'a pas chiffré sur ses propres images : ORB est-il *assez* bon pour mon cas, et *combien* plus rapide ? C'est une décision d'opérateur, pas un théorème.

---

### 🔎 Ce que vous verriez

Sur la même paire d'images, en comparant ORB et SIFT côte à côte :

- **ORB** produit ses appariements quasi instantanément ; **SIFT** prend sensiblement plus de temps (souvent un ordre de grandeur).
- Sous transformation modérée (rotation, léger changement de vue), les deux donnent des appariements corrects. Sous transformation **sévère** (fort changement de point de vue, flou), SIFT conserve plus d'appariements valides qu'ORB.

Le compromis devient une observation chiffrée : nombre d'appariements corrects d'un côté, temps de calcul de l'autre.

---

### 📷 Observation 17.E — ORB ou SIFT : mesurer le compromis sur son cas

**Images fournies :** une paire issue de votre cas réel (deux prises d'un même objet, deux images d'un panorama, deux scans à recaler).

**Pipeline :**
```
Paire d'images → Features (ORB) → Python Node (match + ratio + chrono) → Draw Lines → Grid Compare
              ↘ Features (SIFT) → Python Node (match + ratio + chrono) → Draw Lines ↗
```

**Ce que vous allez vérifier :** que le choix ORB/SIFT est un compromis mesurable, pas une préférence.

**Missions**
1. Relevez, pour ORB et pour SIFT, le **nombre d'appariements retenus** (après ratio test) et le **temps de calcul** (renvoyé par le **Python Node**). Quel rapport de vitesse observez-vous ?
2. Dégradez la paire (ajoutez **Noise (Gaussian)**, ou un fort changement de point de vue via **Warp Perspective**). Lequel des deux résiste le mieux ?
3. Décision : pour un traitement **temps réel** (30 fps) sur cette paire, ORB tient-il le budget de temps ? Pour un recalage **hors ligne** où seule la qualité compte, SIFT apporte-t-il assez d'appariements supplémentaires pour justifier son coût ?

---

## 6. Section 17.6 — Appariement et ratio test de Lowe

### Ce qui est déjà bon

L'exemple `0,63` accepté / `0,92` rejeté et l'analogie clé/serrure rendent le principe limpide.

### Ce qui accroche

Le ratio test est **le** geste d'opérateur du chapitre, et c'est précisément celui qu'il faut tenir entre les mains : un curseur qui, à mesure qu'on le serre, fait disparaître les lignes d'appariement qui se croisent en désordre.

---

### 💡 Image mentale à insérer — après « Le seuil 0,8 vient de l'analyse de Lowe »

> **Image mentale : la séance d'identification.**
> Un témoin passe devant une rangée de suspects. S'il en désigne un avec beaucoup plus d'assurance que tous les autres, son identification vaut quelque chose. S'il hésite entre deux personnes presque autant l'une que l'autre, son témoignage ne vaut rien — non parce qu'il a tort, mais parce qu'il n'est pas distinctif. Le ratio test applique cette règle à chaque point : il ne demande pas « ce candidat est-il proche ? » mais « est-il nettement plus proche que le suivant ? ». Un point qui a un quasi-jumeau ailleurs dans l'image est écarté, même si son meilleur candidat semble bon.

---

### 🔎 Ce que vous verriez

En faisant glisser le seuil `τ` du ratio test sur une paire d'images :

- **τ = 0,95** : presque tous les appariements passent. Beaucoup de lignes se croisent en éventail désordonné — des faux appariements.
- **τ = 0,8** (valeur de Lowe) : la plupart des croisements disparaissent ; restent des lignes majoritairement parallèles.
- **τ = 0,6** : très peu d'appariements, mais quasiment tous corrects.

Sur une image à **texture répétée** (mur de briques, rangée de fenêtres, damier), même à `τ = 0,8`, presque tout est rejeté : chaque point a des jumeaux, aucun n'est distinctif.

---

### 📷 Observation 17.F — Le curseur du ratio test : du désordre aux lignes parallèles

**Images fournies :** une paire « facile » (objet texturé unique) et une paire « piège » à texture répétée (façade à fenêtres identiques, carrelage).

**Pipeline :**
```
Paire d'images → Features (ORB) → Python Node (match, ratio τ réglable) → Draw Lines → Output Display
```

**Ce que vous allez vérifier :** que serrer `τ` élimine les appariements ambigus, et que la texture répétée les rend de toute façon non distinctifs.

**Missions**
1. Sur la paire facile, faites varier `τ` de 0,95 à 0,6. À quelle valeur les lignes qui se croisent disparaissent-elles ? Combien d'appariements reste-t-il à `τ = 0,8` ?
2. Sur la paire à texture répétée, même balayage. Pourquoi le ratio test « affame »-t-il l'appariement ici ? Que faudrait-il faire à la place (indice : §17.7, s'appuyer sur la cohérence géométrique plutôt que sur la distinctivité individuelle) ?
3. Réflexe à acquérir : devant un nuage de lignes incohérentes, le premier geste est de **serrer le ratio**. Devant une scène répétitive, le ratio ne suffira pas — il faut un modèle géométrique.

---

## 7. Section 17.7 — RANSAC et homographie

### Ce qui est déjà bon

La sensibilité chiffrée du nombre d'itérations à `w` (72 contre 567) et l'analogie des cartes montrent pourquoi le pré-filtrage compte.

### Ce qui accroche

Le bénéfice de RANSAC est spectaculaire mais invisible dans le texte : trier les correspondances en inliers/outliers, et **aligner** deux images qui, sans lui, se superposeraient n'importe comment. C'est l'aboutissement du pipeline, et le moment où l'opérateur voit le panorama se former.

---

### 💡 Image mentale à insérer — après « RANSAC trouve le modèle dominant »

> **Image mentale : tracer la droite à travers une foule de farceurs.**
> On vous demande de tracer la droite que « suit » un groupe de personnes, mais la moitié d'entre elles se sont placées au hasard pour vous tromper. Faire la moyenne de tout le monde donne une droite absurde, tirée vers les farceurs. La bonne stratégie : tirer deux personnes au hasard, tracer la droite qui les joint, compter combien d'autres tombent dessus, et recommencer. La droite qui rassemble le plus grand groupe d'accord est la vraie. RANSAC procède ainsi sur les correspondances : il ne moyenne pas les appariements, il cherche le plus grand sous-ensemble qui s'accorde sur une même transformation, et déclare le reste aberrant.

---

### 🔎 Ce que vous verriez

Sur deux photos qui se chevauchent (un début de panorama), après appariement et ratio test :

- En coloriant les appariements selon le **masque d'inliers** de RANSAC : les lignes **vertes** (inliers) sont cohérentes et parallèles, les **rouges** (outliers) partent dans tous les sens.
- En appliquant l'homographie estimée via **Warp Perspective** puis en superposant les deux images (**Draw Overlay**), elles **s'alignent** : les bords communs se recouvrent. En désactivant RANSAC (homographie estimée sur **tous** les appariements, aberrants compris), l'image déformée part en vrille.

Le nombre d'inliers affiché est votre jauge de confiance : beaucoup d'inliers, alignement fiable ; une poignée, méfiance.

---

### 📷 Observation 17.G — Voir le panorama se former (et l'inverse sans RANSAC)

**Images fournies :** deux photos qui se chevauchent partiellement (paysage, document en deux prises, vue aérienne).

**Pipeline :**
```
Image A → Features (SIFT) ─┐
Image B → Features (SIFT) ─┴→ Python Node (match + ratio) → RANSAC homographie
    → [inliers/outliers en vert/rouge] → Draw Lines → Output Display
    → [H] → Warp Perspective (A) → Draw Overlay ← B → Output Display
```

**Ce que vous allez vérifier :** que RANSAC sépare inliers et outliers, et que l'homographie qui en résulte aligne les deux images.

**Missions**
1. Affichez les appariements coloriés par le masque d'inliers. Combien d'inliers sur le total après ratio test ? Les lignes vertes sont-elles bien parallèles ?
2. Superposez l'image A déformée sur B via **Warp Perspective** + **Draw Overlay**. Les zones communes se recouvrent-elles proprement ?
3. Estimez l'homographie sur **tous** les appariements (sans RANSAC, en mettant le seuil de reprojection très grand). L'alignement se dégrade-t-il ? De combien le nombre d'inliers réels chute-t-il ?
4. Cas d'opérateur : sur une scène à **deux plans** (un mur et le sol), une seule homographie ne peut pas tout aligner. Quels appariements RANSAC déclare-t-il inliers, et lesquels rejette-t-il ? Pourquoi faut-il alors appliquer RANSAC en séquence (un plan à la fois) ?

---

## 8. Section 17.8 — État de l'art

### 🔎 Ce que vous verriez

Sur une paire **difficile** — faible texture (mur uni, surface métallique), ou très fort changement de point de vue — où SIFT et ORB ne trouvent presque aucun appariement :

- Un appariem **sans détecteur** appris (par exemple LoFTR, si un nœud ML l'expose) produit des correspondances **denses** là où les méthodes classiques restaient muettes.
- Sur une paire **facile** et bien texturée, l'écart se réduit : SIFT suffit, plus vite et sans GPU.

La leçon opérationnelle : on n'abandonne pas SIFT/ORB, on sait reconnaître les cas (faible texture, point de vue extrême) où une méthode apprise vaut son coût.

---

## Récapitulatif des ajouts pour le chapitre 17

| Ajout | Type | Rattaché à | Concept rendu visible |
|---|---|---|---|
| Image mentale « reconnaître un visage » | 💡 | §17.1 | Le descripteur garde le stable, jette le variable |
| Ce que vous verriez (SSD vs ORB) | 🔎 | §17.1 | Même paire, deux verdicts selon ce qu'on compare |
| Observation 17.A — Pixels bruts contre descripteurs | 📷 | §17.1 | ORB survit à la transformation, le SSD non |
| Image mentale « le bon recul pour lire un mot » | 💡 | §17.2 | L'échelle caractéristique = distance de lecture |
| Ce que vous verriez (cercles qui suivent le zoom) | 🔎 | §17.2 | Rayon ∝ σ, et σ suit l'agrandissement |
| Observation 17.B — Le cercle qui suit le zoom | 📷 | §17.2 | L'invariance d'échelle, rendue visible |
| Image mentale « la rose des vents des bords » | 💡 | §17.3 | HOG = quadrillage de roses d'orientation |
| Ce que vous verriez (HOG sous lumière / rotation) | 🔎 | §17.3 | Stable en éclairage, instable en rotation |
| Observation 17.C — HOG : lumière vs rotation | 📷 | §17.3 | Le glyphe ne bouge pas / tourne |
| Image mentale « orienter la carte avant de la lire » | 💡 | §17.4 | L'orientation dominante remet le patch droit |
| Ce que vous verriez (flèches qui tournent) | 🔎 | §17.4 | Les appariements SIFT survivent à la rotation |
| Observation 17.D — Les flèches qui tournent | 📷 | §17.4 | L'étape d'orientation absorbe la rotation |
| Ce que vous verriez (ORB vs SIFT) | 🔎 | §17.5 | Vitesse contre robustesse, chiffrées |
| Observation 17.E — Mesurer le compromis ORB/SIFT | 📷 | §17.5 | Le choix est un compromis mesurable |
| Image mentale « la séance d'identification » | 💡 | §17.6 | Distinctif = nettement plus proche que le suivant |
| Ce que vous verriez (curseur τ) | 🔎 | §17.6 | Du désordre aux lignes parallèles |
| Observation 17.F — Le curseur du ratio test | 📷 | §17.6 | Serrer τ élimine les ambigus ; texture répétée |
| Image mentale « la droite à travers les farceurs » | 💡 | §17.7 | RANSAC cherche le plus grand groupe d'accord |
| Ce que vous verriez (inliers verts / panorama) | 🔎 | §17.7 | Le tri inliers/outliers et l'alignement |
| Observation 17.G — Voir le panorama se former | 📷 | §17.7 | L'homographie robuste aligne les images |
| Ce que vous verriez (classique vs appris) | 🔎 | §17.8 | Le créneau des méthodes apprises (faible texture) |

**Total chapitre 17 : 6 images mentales + 7 blocs « ce que vous verriez » + 7 exercices d'observation.**

> **Note scripts.** Les **Python Node** de ces observations (appariement + ratio test réglable, HOG `visualize`, chronométrage, coloriage du masque d'inliers) utilisent `cv2` et `skimage` (`feature.match_descriptors`, `feature.hog`, `measure.ransac`). Leurs scripts vont à l'annexe d'observation, numérotés `OBS‑17.A` à `OBS‑17.G`, suivant la convention des chapitres précédents.
