# Reconstruction de l'origine du sang par analyse de patterns : une exploration avec VNStudio

**Mots-clés :** analyse de patterns de sang, forensique computationnelle, logiciel nodal, stringing, reconstruction 3D, dataset Attinger

---

## Introduction

Je ne suis pas expert en sciences forensiques. Mes domaines de prédilection tournent autour de la vision par ordinateur, du traitement d'image et, plus récemment, du développement de VNStudio — un logiciel nodal de vision computationnelle que j'ai construit pour explorer et connecter visuellement des algorithmes de traitement d'image. L'idée de base est simple : plutôt que d'écrire des scripts Python chaque fois qu'on veut tester une nouvelle pipeline de traitement, on assemble des blocs fonctionnels (les *nodes*) en les connectant par des ports colorés, comme on brancherait des câbles dans un studio de synthèse. L'exécution est temps-réel, le retour visuel est immédiat.

C'est précisément cette flexibilité qui m'a conduit, presque par curiosité, à m'intéresser à l'analyse de patterns de sang (*Bloodstain Pattern Analysis*, BPA). Il existe un jeu de données publié et documenté — le dataset Attinger, du nom du professeur Daniel Attinger de l'Iowa State University — qui contient des images à haute résolution de projections sanguines dans des conditions contrôlées. 30 expériences, des métadonnées précises, des coordonnées 3D mesurées. Un terrain de jeu idéal pour tester ce que VNStudio peut faire dans un domaine que je ne maîtrise pas.

Cet article raconte cette exploration : les choix algorithmiques, l'intérêt de l'approche nodale pour ce type de travail, les mathématiques que j'ai implémentées, et surtout, une évaluation honnête de ce qui fonctionne et de ce qui ne fonctionne pas encore.

---

## La BPA : quelques mots sur la discipline

L'analyse de patterns de sang est une branche des sciences forensiques qui cherche à reconstruire les circonstances d'un événement violent à partir des traces de sang laissées sur une scène de crime. Parmi les questions centrales figure la détermination de l'*origine* du sang : d'où provenait-il dans l'espace ? À quelle hauteur ? À quelle distance de la surface touchée ?

La méthode classique, dite du *stringing*, consiste à tendre physiquement des fils à travers les taches allongées présentes sur les surfaces. Chaque tache fournit une direction dans l'espace (son axe majeur indique la trajectoire du projectile sanguin), et l'accumulation de ces fils converge visuellement vers une zone de l'espace — l'origine. C'est une méthode fondamentalement visuelle et manuelle, développée dans les années 1970-1980, qui demeure l'outil de référence sur le terrain malgré ses limitations évidentes en termes de précision et de reproductibilité.

La version computationnelle de ce problème existe depuis une vingtaine d'années. Elle consiste à détecter automatiquement les taches dans une image numérique, à modéliser chaque tache comme une ellipse dont le rapport d'axes encode l'angle d'impact, puis à reconstruire l'origine par intersection de rayons 3D. C'est cette pipeline que j'ai cherché à implémenter dans VNStudio.

---

## Pourquoi un logiciel nodal ?

La question mérite d'être posée. Pourquoi ne pas simplement écrire un script Python de bout en bout ?

La réponse courte : l'exploration interactive est fondamentalement différente de l'exécution séquentielle d'un script. Lorsqu'on travaille sur des données inconnues — ici, des images de taches de sang sur du carton blanc — on ajuste constamment les paramètres. Quel seuil pour la segmentation ? Quelle taille minimale pour considérer une tache comme valide ? Quel niveau de flou avant la détection des contours ? Un script exige de relancer l'exécution à chaque modification. Un éditeur nodal permet de tweaker un paramètre et d'observer le résultat en temps réel, au niveau de chaque étape de la pipeline.

Dans VNStudio, chaque *node* est un bloc Python autonome (un plugin) qui déclare ses ports d'entrée, de sortie, et ses paramètres. Un node `BPA Stain Detector` reçoit une image et un facteur de calibration, et produit en sortie l'image annotée, le masque de segmentation, les données des taches (liste d'ellipses), et des scalaires comme le nombre de taches ou l'angle d'impact moyen. On branche visuellement ces sorties vers les entrées d'un node `BPA Origin Reconstructor`, qui reçoit également les coordonnées de la cible depuis un `BPA Metadata Reader`. Tout se recalcule instantanément à chaque modification de paramètre.

Cette approche favorise quelque chose que j'appelle la *science exploratoire composable* : on peut insérer un node de visualisation intermédiaire n'importe où dans la pipeline, isoler une étape, la remplacer par une alternative, ou brancher les mêmes données vers plusieurs algorithmes en parallèle. Pour un domaine que je découvre, c'est un avantage décisif. Je ne construis pas un outil figé : je construis un espace de raisonnement visuel.

La pipeline BPA finale dans VNStudio comprend neuf nodes spécialisés : lecteur de métadonnées, chargeur d'image, détecteur de taches, reconstructeur 3D, et quatre nodes de visualisation (stringing overlay, heatmap de convergence, vue top-down, scène 3D). Ces nodes sont réutilisables et combinables avec les 70+ autres nodes du logiciel — un histogramme ou un scatter plot du jeu de données ML s'agrège naturellement aux résultats numériques du reconstructeur.

---

## Le jeu de données Attinger

Le dataset utilisé pour cette étude est décrit dans la publication *Controlled experiments of bloodstain formation* (Attinger et al., *Data in Brief*, 2018). Il comprend 30 expériences réalisées avec un dispositif mécanique reproductible : une rondelle de hockey propulse un cylindre imprégné de sang de porc (avec anticoagulant héparine) contre une cible — un carton blanc positionné verticalement dans une pièce contrôlée.

Chaque expérience est documentée par :
- **Une image JPEG à 600 dpi** de la cible, capturée par scanner à plat haute résolution. Les images HP_19–HP_34 atteignent 32 600 × 26 000 pixels (138 × 110 cm), les expériences HP_50–HP_63 sont plus compactes (environ 73 × 56 cm).
- **Un fichier texte de métadonnées** contenant les coordonnées 3D de l'origine du sang (`x_o`, `y_o`, `z_o`) et du coin inférieur gauche de la cible (`x_t`, `y_t`, `z_t`), mesurées à partir du coin inférieur gauche de la pièce, ainsi que les propriétés biologiques du sang (hématocrite, volume), les conditions ambiantes (température, humidité), et les paramètres mécaniques du dispositif (angle du cylindre, bras de levier).

Les expériences se divisent en deux séries :
- **HP_19–HP_34** : volume = 1 ml, angle = 21°, origine à environ **190 cm** de la cible.
- **HP_50–HP_63** : volumes = 1 ml ou 5 ml, angle = 21° ou 25°, origine à environ **60 cm** de la cible.

Deux expériences (HP_62, HP_63) présentent une *double origine* — le sang provenait simultanément de deux points distincts, cas particulièrement complexe.

---

## Pipeline de traitement : les étapes et les mathématiques

### 1. Chargement et calibration

Les images sont trop grandes pour être traitées en pleine résolution (une image HP_19 fait 850 mégapixels). Le node `BPA Image Loader` implémente un facteur d'échelle configurable et maintient la cohérence métrologique : si le scanner capture à 600 dpi (236,2 px/cm) et qu'on charge à 20 % de la résolution, le facteur de calibration est 236,2 × 0,2 = 47,24 px/cm. Ce facteur est propagé dans toute la pipeline via un port scalaire, ce qui garantit que tous les calculs métriques restent cohérents indépendamment de l'échelle choisie.

### 2. Détection des taches : segmentation LAB-A + HSV-V

Le sang séché sur papier blanc présente une signature colorimétrique caractéristique : des teintes brun-rouge à rosées, nettement distinctes du fond blanc. La segmentation exploite deux canaux complémentaires dans des espaces colorimétriques différents :

**Canal A de l'espace LAB** : l'axe A représente l'opposition rouge–vert. Le sang séché présente des valeurs A positives (rougeur). Un seuil `a > a_thresh` (défaut : 5, après centrage à 0) isole les pixels rougeâtres.

**Canal V de l'espace HSV** : la valeur V mesure la luminosité. Le fond blanc a V ≈ 255. Un masque `V < val_max` (défaut : 230) exclut le fond sans rejeter les taches légères.

La combinaison logique (`AND`) des deux masques produit une segmentation robuste qui rejette à la fois le fond blanc (V trop élevé) et les teintes non-sanguines (A insuffisant). Une ouverture morphologique (noyau elliptique 3×3) supprime les artefacts de compression JPEG isolés.

Les paramètres de taille des taches sont exprimés en millimètres (diamètre minimum et maximum), convertis dynamiquement en pixels carrés en utilisant le facteur `px_per_cm` :

```
min_area_px = π × (min_mm × px_per_cm / 20)²
```

Cette approche rend le détecteur indépendant de l'échelle de chargement.

### 3. Ajustement d'ellipses et angle d'impact

Pour chaque contour valide, la fonction `cv2.fitEllipse` ajuste une ellipse minimale englobante. Les paramètres extraits sont : le centre `(cx, cy)`, les axes `(minor, major)`, et l'angle de rotation `rot`.

L'angle d'impact `α` — l'angle que forme la trajectoire du projectile avec le plan de la cible — est calculé par la relation géométrique classique de la BPA :

```
sin(α) = minor / major
```

Un projectile sphérique impactant une surface à angle `α` produit une empreinte elliptique dont le rapport d'axes encode directement cet angle : incidence normale (α = 90°) → tache circulaire (minor = major) ; incidence rasante (α → 0°) → tache très allongée (minor << major).

### 4. Reconstruction 3D par stringing aux moindres carrés

Chaque tache définit un rayon 3D dans l'espace pièce. Ce rayon part de la position de la tache sur le plan de la cible et pointe vers l'origine du sang. La direction du rayon est construite à partir de deux informations :
- **Direction YZ** (dans le plan de la cible) : donnée par l'angle de rotation de l'ellipse dans l'image, convertie en coordonnées monde.
- **Composante X** (perpendiculaire à la cible) : `dX = tan(α)`, où α est l'angle d'impact.

La reconstruction cherche le point de l'espace qui minimise la somme des distances au carré aux N rayons — le problème d'intersection de droites aux moindres carrés. Pour chaque rayon de direction unitaire **d**_i passant par le point **P**_i (position de la tache en coordonnées monde), on pose :

```
A_i = I - d_i ⊗ d_i
Σ A_i · x = Σ A_i · P_i
```

Ce système linéaire 3×3 est résolu par `numpy.linalg.solve`. Une deuxième passe élimine les rayons dont le résidu (distance au point estimé) dépasse un seuil configurable, améliorant la robustesse aux taches aberrantes.

---

## Résultats et évaluation

### Performance sur la série HP_50–HP_63 (origine à ~60 cm)

Pour les 30 échantillons du dataset, la reconstruction donne une erreur Euclidienne 3D moyenne de **86 cm** (médiane : 75 cm, min : 28 cm, max : 189 cm). Ces chiffres bruts nécessitent une décomposition par axe pour être interprétés correctement.

La décomposition révèle une asymétrie significative entre les axes :
- **Axe Y** (horizontal le long de la cible) : erreur typique de **10 à 25 cm** — raisonnable.
- **Axe Z** (vertical) : erreur de **5 à 60 cm** selon l'échantillon.
- **Axe X** (profondeur, perpendiculaire à la cible) : erreur **systématique de ~50 cm**, soit une sous-estimation d'environ 80 % de la distance réelle pour la série HP_50 (GT : 60 cm, estimé : ~15 cm).

La reconstruction YZ est donc exploitable pour localiser la projection de l'origine sur la cible. La reconstruction en profondeur (axe X) est systématiquement défaillante.

### Analyse de la limitation centrale

L'origine de cette défaillance est identifiable mathématiquement. Pour la série HP_50, l'origine est à 60 cm de la cible, ce qui implique des angles d'impact attendus entre 55° et 75° selon la position des taches. Or, la mesure par rapport d'axes donne des angles centrés autour de 53° — ce qui semble cohérent à première vue.

Mais pour la série HP_19 (distance = 190 cm), les angles attendus sont de l'ordre de 80–85° — des taches quasi-circulaires — alors que la mesure donne des angles de 25–35°. L'écart est massif.

La cause : le rapport `minor/major` mesuré par `fitEllipse` ne correspond pas au rapport théorique d'une projection géométrique parfaite. Les taches de sang ne sont pas des ellipses pures — elles présentent des queues de traînée, des satellites secondaires, une rugosité de surface. Le contour de la tache est morphologiquement plus allongé que ce que prédirait la géométrie pure, conduisant à une *surestimation de l'élongation* et donc à une *sous-estimation de l'angle d'impact*. Puisque `dX = tan(α)`, une sous-estimation de α produit une sous-estimation drastique de la composante de profondeur du rayon — et donc de la coordonnée X de l'origine.

Ce biais est structurel : il ne disparaîtra pas en augmentant la résolution ou en améliorant les paramètres de détection. Il appelle soit une calibration empirique de la relation entre aspect ratio mesuré et angle réel (spécifique au substrat et aux conditions), soit une méthode alternative pour estimer la composante de profondeur.

### Ce que les visualisations apportent

Les quatre nodes de visualisation produits pour ce projet révèlent des informations que les seuls chiffres ne capturent pas.

Le **stringing overlay** — lignes tracées à travers chaque tache selon son axe majeur, colorées par angle d'impact — montre visuellement la convergence du pattern. Même quand la reconstruction numérique échoue sur la coordonnée X, la convergence des lignes sur l'image 2D pointe correctement vers la projection de l'origine sur la cible. C'est, en un sens, ce que l'expert forensique voit d'instinct sur le terrain.

La **heatmap de convergence** accumule les densités de lignes de stringing dans un buffer flottant, puis applique un colormap thermique (noir → rouge → jaune → blanc). La zone la plus chaude identifie la région de convergence maximale sans aucun calcul matriciel. Cette approche est particulièrement robuste face aux taches aberrantes, qui déplacent peu le maximum de densité.

La **vue top-down** en coordonnées pièce (plan XY) et la **scène 3D** permettent de placer la reconstruction dans son contexte géométrique : on visualise simultanément la cible, les projections des taches, l'origine estimée, l'origine réelle, et la flèche d'erreur. Pour un rapport forensique, ces représentations sont immédiatement lisibles.

---

## Discussion : intérêt et limites de la démarche

Ce travail d'exploration soulève une question de fond sur le rôle d'un outil comme VNStudio dans un contexte de recherche appliquée.

D'un côté, la rapidité d'implémentation est remarquable. En quelques sessions, j'ai construit une pipeline complète depuis le chargement des images brutes jusqu'à quatre modes de visualisation, incluant un évaluateur batch qui tourne les 30 échantillons automatiquement et produit un DataFrame analysable avec les nodes DataFrame et ML déjà présents dans le logiciel. Ce qui aurait nécessité plusieurs jours de développement en mode script-seul a pris quelques heures en mode nodal.

D'un autre côté, cette facilité de mise en œuvre peut masquer des lacunes conceptuelles. J'ai implémenté le modèle `sin(α) = b/a` parce qu'il est omniprésent dans la littérature BPA, sans m'interroger suffisamment sur ses hypothèses. C'est l'évaluation quantitative — permise par le batch evaluator — qui a révélé le biais systématique sur l'axe X. Un outil nodal n'est pas une garantie de rigueur scientifique : il réduit la friction entre l'idée et son implémentation, mais l'interprétation des résultats reste entièrement à la charge du chercheur.

Sur le plan des perspectives, plusieurs pistes amélioreraient significativement la précision :

**Calibration empirique de l'angle d'impact.** Sur un substrat donné, mesurer la relation réelle entre aspect ratio et angle connu (en utilisant des expériences avec incidence contrôlée) permettrait d'introduire une fonction de correction `α_corrected = f(b/a, substrate)`.

**Méthode de convergence directe en 2D.** La reconstruction de la projection YZ de l'origine (sans estimer X) est nettement plus fiable. On pourrait combiner cette information 2D avec une contrainte de hauteur issue d'autres indices (par exemple, la hauteur typique d'impact pour un scénario donné) pour estimer X indépendamment.

**Exploitation de la queue des taches.** Dans les images haute résolution, la direction de la queue (et non l'axe de l'ellipse entière) pointe plus directement vers l'origine. Un détecteur de queue de tache, exploitant la morphologie asymétrique, pourrait remplacer avantageusement le rapport d'axes.

---

## Conclusion

Cette exploration de la BPA computationnelle à travers VNStudio illustre quelque chose qui me tient à cœur : la valeur d'un logiciel d'exploration visuelle pour aborder des domaines hors de sa zone de confort. Je n'étais pas forensicien au début de ce projet. Je ne le suis toujours pas. Mais je dispose maintenant d'une pipeline documentée, d'un évaluateur quantitatif sur 30 expériences réelles, et d'une compréhension précise de pourquoi l'algorithme classique de stringing échoue en profondeur sur ce jeu de données.

La BPA computationnelle n'est pas un problème résolu. La transition du stringing manuel vers une reconstruction 3D automatisée et précise reste un sujet actif de recherche, notamment face à la variabilité des substrats, des conditions d'éclairage et des propriétés rhéologiques du sang. Ce que VNStudio apporte à cette problématique, c'est un environnement où l'on peut tester des hypothèses rapidement, visualiser les résultats à chaque étape, et partager des pipelines reproductibles — des atouts qui pourraient s'avérer utiles aussi bien pour la formation des experts que pour le prototypage de nouvelles méthodes.

Le code est open-source, les nodes sont documentés, le jeu de données est public. Il n'y a aucune raison que ce travail reste confiné à quelques sessions de développement exploratoire.

---

*Pipeline disponible dans VNStudio : templates `bpa_forensics.vn` (analyse mono-échantillon, 4 visualisations) et `bpa_batch_analysis.vn` (évaluation des 30 échantillons Attinger). Dataset : Attinger et al., Data in Brief 18 (2018) 1676–1691.*
