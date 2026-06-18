#import "@preview/bookly:4.0.0": *

// --- Helpers locaux ---
#let subtitle(t) = block(above: 0.2em, below: 1.2em, sticky: true)[#text(style: "italic", fill: rgb("#64748b"))[#t]]

#let figtodo(id, desc) = figure(
  block(width: 100%, inset: 14pt, radius: 6pt,
    fill: luma(246), stroke: (dash: "dashed", thickness: 0.8pt, paint: luma(170)))[
    #align(center)[#text(fill: luma(110), style: "italic", size: 0.9em)[
      Figure à créer — #raw(id)\
      #desc
    ]]
  ]
)

#let figfull(path) = block(above: 1em, below: 1.4em, width: 100%)[#image(path, width: 100%)]
#let canvas(body) = tip-box(title: "Dans VNStudio")[#body]


#chapter(title: [Couleur et photométrie], toc: false)[

#block(above: 0pt, below: 2em, width: 100%)[#image("/illustrations/chap7.jpeg", width: 100%)]

#pagebreak()
#block(above: 0em, below: 1em)[
  #grid(columns: (auto, 1fr), column-gutter: 0.6em, align: horizon,
    box(width: 3pt, height: 1.2em, fill: rgb("#c1002a"), radius: 1.5pt),
    text(weight: "bold", font: "Roboto", fill: rgb("#1e293b"))[Table des matières])
]
#suboutline(target: heading.where(outlined: true, level: 2))
#pagebreak()

#subtitle[Un même spectre se code de mille façons, et deux spectres distincts peuvent produire la même sensation. La couleur n'est pas une donnée de l'objet : c'est le contrat de l'espace qu'on a choisi pour la décrire.]

La couleur n'est pas une propriété physique des objets : c'est une construction. Un même rayonnement lumineux peut être encodé de dizaines de façons, et deux rayonnements physiquement distincts peuvent produire une sensation visuelle identique. Ce chapitre traite la couleur comme un problème de représentation — quel espace pour quelle tâche — et de mesure — comment quantifier un écart de couleur d'une façon qui corresponde à la perception humaine.

Le fil du chapitre tient en une phrase : *il n'existe pas d'espace colorimétrique « vrai », seulement des espaces adaptés à un usage.* Un *espace colorimétrique* est une manière de coder une couleur par des nombres. RGB code par trois quantités de rouge, vert et bleu (pour les capteurs et les écrans) ; HSV par teinte, saturation et clarté (pour la sélection intuitive) ; CMYK par des quantités d'encre (pour l'impression) ; CIELAB pour la mesure fidèle à l'œil. Convertir entre eux, c'est passer d'une logique à une autre — chaque conversion implique des choix, des approximations, des pièges propres. L'espace n'est pas neutre : il encode une hypothèse sur ce qui compte.

La notion d'espace de représentation est cousine du choix d'une base au chapitre 10 (« changer de base, c'est choisir où le problème devient simple »), et le lien entre espace colorimétrique et mesure de distance prolonge le chapitre 3 : toute distance de couleur suppose implicitement un espace.

=== Un peu de vocabulaire avant de commencer

- *Espace colorimétrique* : Un système mathématique permettant de représenter les couleurs par des coordonnées numériques (ex. : RGB, HSV, CIELAB).
- *Canal (ou composante)* : Une des dimensions de l'espace colorimétrique (comme le canal Rouge, ou le canal Teinte).
- *Gamma (γ)* : Une correction non linéaire appliquée aux intensités des pixels pour correspondre à la sensibilité logarithmique de l'œil humain et optimiser le stockage.

---

// ============================================================

== Luminance : du RGB au niveau de gris

#subtitle[Une recette de mélange où le vert pèse bien plus que sa part]

=== L'intention
On veut réduire une image couleur à un seul canal de clarté — mais une clarté qui corresponde à ce que l'œil perçoit, pas à une moyenne aveugle des trois canaux.

=== La forme recherchée
La conversion n'est pas une simple moyenne (rouge + vert + bleu) / 3, car la rétine n'est pas également sensible à toutes les couleurs. L'œil possède trois types de capteurs (les cônes), sensibles au bleu, au vert et au rouge, et ceux du vert et du rouge sont bien plus nombreux et réactifs que ceux du bleu. L'image utile est celle d'un mélange de peinture où le vert domine massivement la recette : le vert pèse environ 60 à 70 % de la clarté perçue, le rouge 20 à 30 %, le bleu seulement 7 à 11 %. La recette est calibrée sur l'instrument de mesure — l'œil.

#info-box(title: "La formule")[
```
Y = 0.2126·R + 0.7152·G + 0.0722·B   (coefficients haute définition, BT.709)
```
]

Y est la *luminance* (la clarté) ; R, G, B sont les trois canaux. Les coefficients très inégaux traduisent les sensibilités de l'œil. Il existe deux jeux de coefficients selon l'âge des écrans (télévision standard contre haute définition), qui diffèrent de quelques pour-cent — négligeable à l'affichage, détectable en mesure précise. En imagerie médicale, une moyenne simple aplatirait des contrastes tissulaires que les bons coefficients font ressortir comme l'œil les voit. ∎

#question-box(title: "Exemple chiffré")[
Pixel vert-jaune vif R, G, B = (180, 220, 30) :

```
Y = 0.2126×180 + 0.7152×220 + 0.0722×30 ≈ 198
moyenne naïve : (180+220+30)/3 = 143
```

L'écart est de 55 niveaux sur 255 — plus de 20 %. Sur un contrôle qualité de surface peinte, une telle erreur de conversion fausserait la détection de défauts par variation de luminosité.
]

#warning-box(title: "Piège — luma, luminance et le gamma")[
Voici le piège le plus souvent ignoré. Les images stockées (JPEG, PNG) ne contiennent pas la lumière brute : elles sont *encodées en gamma*, c'est-à-dire que les valeurs ont été comprimées par une courbe avant stockage (on y revient au §7.6). La vraie luminance, proportionnelle à l'énergie lumineuse, ne s'obtient qu'après avoir _décompressé_ cette courbe. Ce que calcule un convertisseur ordinaire sur les valeurs telles quelles est une approximation, le _luma_, suffisante pour afficher mais fausse pour une mesure. Pour une luminance physiquement correcte (calcul de contraste pour l'accessibilité, compositing vidéo), on décompresse d'abord le gamma, on applique les coefficients, puis on recompresse si besoin. Traiter des valeurs gamma comme de la lumière, c'est lire un thermomètre dont l'échelle serait étirée : plausible à l'œil, faux à la mesure.
]

#canvas[
Canvas : `Image Source` → `Luminance` → `Output Display`. Le nœud propose les deux jeux de coefficients (TV standard / haute définition) et une option « linéariser le gamma » qui distingue le luma rapide de la luminance physique ; l'écart entre les deux se voit sur un dégradé.

---
]

// ============================================================

== RGB → HSV : séparer la couleur de l'intensité

#subtitle[Un pot de peinture : sa couleur, sa dilution à l'eau, la lampe qui l'éclaire]

=== L'intention
En RGB, teinte et luminosité sont mêlées dans les trois canaux : assombrir un rouge vif change rouge, vert et bleu en même temps. Pour isoler tous les objets rouges d'une scène, quelle que soit leur clarté, on voudrait une représentation où la « couleur pure » est une coordonnée à part.

=== La forme recherchée
HSV (de l'anglais _Hue, Saturation, Value_) découple trois propriétés. Comme un pot de peinture : la *teinte* (H) est la couleur du pot — rouge, bleu, vert… —, repérée par un angle sur la roue des couleurs ; la *saturation* (S) dit si la peinture est diluée à l'eau (délavée, faible S) ou pure (S maximale) ; la *valeur* (V) dit si on peint sous une bonne lampe ou dans l'obscurité. Géométriquement, c'est une réorganisation du cube RGB : on le fait tourner sur sa diagonale des gris et on passe en coordonnées cylindriques — H l'angle autour de l'axe, S la distance à l'axe, V la hauteur.

#info-box(title: "La formule")[
```
V = max(R, G, B)
S = (V − min(R, G, B)) / V
H = angle déduit de la position de R, G, B  (exprimé en degrés sur la roue)
```
]

La valeur est le canal le plus fort, la saturation l'écart relatif entre le plus fort et le plus faible, la teinte l'angle qui repère la couleur dominante. Ce découplage rend HSV idéal pour la segmentation par couleur : isoler les objets rouges revient à garder une plage d'angles autour du rouge, là où la même opération en RGB demanderait de découper un volume 3D peu intuitif. L'espace HSV encode une hypothèse : la teinte est le critère qui compte, l'intensité une nuisance à éliminer. ∎

#question-box(title: "Exemple chiffré")[
Pixel orange vif R, G, B = (255, 128, 0), ramené entre 0 et 1 :

```
V = max = 1.0
S = (1.0 − 0.0) / 1.0 = 1.0        (saturation maximale)
H ≈ 30°  (à mi-chemin du rouge à 0° et du jaune à 60°)
```

Teinte orange, saturation et valeur maximales : une couleur franche et vive, exactement comme on la perçoit.
]

#warning-box(title: "Piège — la teinte est indéfinie sur les gris, et circulaire")[
Quand la saturation tend vers zéro (gris, blanc, noir), la teinte n'a plus de sens : un gris n'a pas de couleur, donc pas d'angle. Numériquement, la teinte devient instable et le moindre bruit la fait sauter de 0° à 180°. Toute segmentation par teinte doit donc d'abord *écarter les pixels peu saturés*, sinon le bruit des zones grises contamine le résultat. De plus, la teinte est *circulaire* : 0° et 360° désignent le même rouge. La moyenne de deux teintes se calcule en angles, pas en nombres bruts — la moyenne de 350° et 10° vaut 0° (rouge), pas 180° (cyan).
]

#canvas[
Canvas : `Image Source` → `Color Convert (HSV)` → `Threshold by Hue` → `Output Display`. Le nœud de seuillage par teinte expose une plage d'angles et un seuil minimal de saturation (pour écarter les gris) ; il sort un masque des objets de la couleur visée.

---
]

// ============================================================

== CIELAB et la mesure perceptuelle

#subtitle[Une carte à équidistance : un même pas paraît un même écart, partout]

#figfull("/figures/fig_ch7_obs2_deltaE.pdf")

=== L'intention
Dans RGB ou HSV, une même différence numérique peut correspondre à des écarts perçus très inégaux : l'œil distingue finement les verts, beaucoup moins les bleus saturés. On veut un espace où *des différences numériques égales correspondent à des différences perçues égales* — pour _mesurer_ un écart de couleur, pas pour l'afficher.

=== La forme recherchée
L'image utile est celle d'une carte de randonnée à équidistance, où des courbes de niveau régulièrement espacées représentent partout la même dénivelée. CIELAB applique cette idée aux couleurs : deux points séparés de la même distance y paraissent « aussi différents » à l'œil, où qu'ils soient. C'est l'*uniformité perceptuelle*. Trois coordonnées :

```
L* : la clarté (0 = noir, 100 = blanc de référence)
a* : l'axe vert (−) ↔ rouge (+)
b* : l'axe bleu (−) ↔ jaune (+)
```

La conversion depuis RGB passe par un espace intermédiaire lié au spectre lumineux, puis applique une courbe qui « étire » les tons sombres pour coller à la sensibilité de l'œil. Le détail importe peu ; ce qui compte est que, une fois dans CIELAB, on peut *mesurer un écart de couleur par une simple distance*, le ΔE (« delta E ») :

#info-box(title: "La formule")[
```
ΔE = √( (ΔL*)² + (Δa*)² + (Δb*)² )
```
]

C'est la distance euclidienne du chapitre 3, appliquée aux trois coordonnées Lab — et elle n'a de sens _que_ parce que l'espace est perceptuellement uniforme. Les seuils, issus d'études sur des observateurs humains :

#info-box(title: "La formule")[
```
ΔE < 1       : différence imperceptible, même pour un œil entraîné
ΔE 1 à 2     : perceptible par un œil exercé, en conditions contrôlées
ΔE 2 à 10    : perceptible au premier coup d'œil
ΔE > 10      : couleurs nettement différentes
```
]

La formule ΔE de base reste imparfaite (elle surestime les écarts dans les bleus saturés) ; une version affinée, ΔE2000, corrige cela et sert de standard industriel pour le contrôle qualité couleur. ∎

#question-box(title: "Exemple chiffré")[
Contrôle qualité textile, fil « bleu marine de référence » Lab = (22, 4, −28), lot de production Lab = (24, 5, −25) :

```
ΔE = √((24−22)² + (5−4)² + (−25+28)²) = √(4 + 1 + 9) = √14 ≈ 3,7
```

Un ΔE de 3,7 est perceptible à l'œil nu — le lot sera refusé si la norme exige ΔE \< 2. Le même calcul en RGB n'aurait aucune signification perceptuelle, validant peut-être un lot visuellement défectueux.
]

#canvas[
Canvas : `Image A` + `Image B` → `Delta E (CIE2000)` → `Output Display`. Le nœud convertit les deux images en Lab, calcule le ΔE en chaque pixel, et affiche une carte des écarts plus une statistique (moyen, maximal, 95ᵉ percentile) — directement exploitable en contrôle qualité.

---
]

// ============================================================

== Gamut et conversion RGB → CMYK

#subtitle[Ajouter de la lumière sur du noir, ou retirer des couleurs au blanc]

#figfull("/illustrations/chap7.4.png")

=== L'intention
On veut imprimer ce qu'on voit à l'écran. Mais l'écran émet de la lumière et l'imprimante dépose de l'encre : passer de l'un à l'autre demande de changer de logique, et toutes les couleurs ne survivent pas au voyage.

=== La forme recherchée
RGB est *additif* : on part du noir (absence de lumière) et on _ajoute_ des lumières colorées — rouge + vert + bleu = blanc. C'est la logique des écrans. CMYK est *soustractif* : on part du blanc (le papier) et les encres _retirent_ des couleurs — le cyan absorbe le rouge, le magenta le vert, le jaune le bleu. Superposer les trois devrait donner du noir, mais donne un brun sale : d'où l'ajout d'un noir séparé (la lettre K). Surtout, les deux ne couvrent pas le même *gamut* — l'ensemble des couleurs reproductibles. Un écran affiche des verts et cyans éclatants impossibles à imprimer. La conversion RGB → CMYK n'est donc pas une simple traduction : c'est une *projection d'un gamut vers un autre*, avec des pertes inévitables pour les couleurs hors d'atteinte de l'encre.

La conversion naïve est directe (le cyan vaut « tout sauf le rouge », etc.), mais elle ignore la physique réelle de l'impression : l'encre s'étale sur le papier, les encres humides interagissent, le papier mat ne rend pas comme le brillant. Une conversion correcte exige un *profil ICC* : un fichier mesuré qui décrit comment une imprimante, une encre et un papier donnés rendent réellement chaque couleur.

Quand une couleur d'écran tombe hors du gamut d'impression, il faut décider comment la « faire entrer ». Plusieurs stratégies (les _intents de rendu_) : comprimer harmonieusement tout le gamut (bon pour les photos), garder exactes les couleurs atteignables et rabattre seulement les autres (bon pour un logo dont le rouge doit rester fidèle), ou privilégier la vivacité sur l'exactitude (graphiques). Le choix est éditorial, pas technique. ∎

#question-box(title: "Exemple chiffré")[
Un vert vif de logo RGB = (0, 210, 90). La simulation avec un profil d'impression standard indique que ce vert est *hors gamut* : le rendu imprimé sera notablement plus terne. L'écart, mesuré en ΔE2000 (§7.3) entre la cible et la valeur imprimée simulée, vaut environ 8,5 — une différence bien visible à l'œil nu.
]

#warning-box(title: "Piège — convertir tôt perd des couleurs irréversiblement")[
Convertir tôt en CMYK fait perdre des couleurs sans retour. La bonne pratique travaille en RGB jusqu'au dernier moment, avec une *épreuve écran* (_soft proof_) qui simule le rendu d'impression à l'écran. Un ΔE2000 entre la couleur visée et son rendu CMYK simulé chiffre la perte à attendre avant d'engager l'impression.
]

#canvas[
Canvas : `Image Source` → `CMYK Soft Proof` → `Output Display`. Le nœud simule le rendu CMYK (profil au choix), signale en surimpression les zones hors gamut, et affiche le ΔE2000 moyen entre l'original et le rendu simulé.

---
]

// ============================================================

== Égalisation d'histogramme et CLAHE

#subtitle[Ouvrir un accordéon comprimé sur quelques notes pour couvrir toute la gamme]

#figfull("/illustrations/chap7.5.png")

=== L'intention
Une image sous-exposée entasse ses intensités sur une petite plage : les structures s'y noient faute de contraste. On veut étaler ces valeurs sur toute la gamme disponible.

=== La forme recherchée
L'image utile est celle d'un accordéon. Un histogramme concentré, c'est un accordéon comprimé sur quelques notes ; l'étaler, c'est l'ouvrir pour couvrir tout le clavier. L'outil est le *cumul* de l'histogramme : la courbe qui donne, pour chaque niveau, la proportion de pixels qui lui sont inférieurs ou égaux. On se sert de cette courbe comme d'une table de correspondance : chaque niveau d'entrée est remplacé par sa proportion cumulée, étalée sur toute la plage. Les niveaux très peuplés (où le cumul grimpe vite) sont écartés les uns des autres, ce qui révèle des détails ; les niveaux rares sont comprimés. L'histogramme final est à peu près plat — toute la dynamique est utilisée.

=== Pourquoi l'égalisation globale échoue — CLAHE
L'égalisation globale applique une seule correction à toute l'image : une zone localement peu contrastée (une ombre dans une radiographie) reste noyée si le reste de l'image domine l'histogramme. Le *CLAHE* (égalisation adaptative à contraste limité) corrige cela par deux idées. D'abord, *adaptatif* : on découpe l'image en tuiles et on égalise chaque tuile séparément, en raccordant les tuiles en douceur pour éviter un effet de damier. Ensuite, *à contraste limité* : avant d'égaliser une tuile, on plafonne son histogramme à une hauteur maximale et on redistribue le surplus. Sans ce plafond, une tuile presque uniforme (un coin de ciel) verrait son minuscule contraste étiré à l'extrême, amplifiant énormément le bruit du capteur. Ce plafond est le réglage clé : trop bas, l'effet est faible ; trop haut, le bruit explose.

#question-box(title: "Exemple chiffré")[
Image de fond d'œil dont les intensités s'entassent entre 0 et 80 sur une plage de 0 à 255. L'égalisation étire \[0, 80\] sur \[0, 255\], révélant les vaisseaux. Mais ce segment contient aussi du bruit de capteur, étiré du même facteur (environ 3,2× = 255/80) : un bruit de 2 niveaux devient 6 niveaux. D'où l'utilité du plafond du CLAHE, qui borne ce gain et empêche le bruit d'exploser.
]

#warning-box(title: "Piège — égaliser sur la luminance, pas sur les couleurs")[
Appliquer CLAHE sur les trois canaux rouge, vert, bleu séparément crée des dominantes de couleur artificielles (les zones sombres virent au vert ou au violet). La bonne pratique convertit d'abord en un espace où la clarté est un canal à part (comme Lab, §7.3), applique CLAHE sur ce seul canal de clarté, puis reconvertit : les couleurs sont préservées, seul le contraste change.
]

#info-box(title: "Paramètres opérationnels (VNStudio / Python)")[
Dans le nœud `CLAHE` (ou via `cv2.createCLAHE` en Python), l'amélioration locale du contraste dépend des deux paramètres suivants :

- *Limite de contraste (`clipLimit`)* :
- Dans VNStudio, ce paramètre correspond au curseur *Contrast Limit* ; en Python (OpenCV), il se nomme `clipLimit` dans `cv2.createCLAHE`.
- Ce paramètre (généralement réglé entre 2.0 et 4.0) définit la hauteur maximale autorisée pour l'histogramme de chaque bloc avant l'égalisation. Si l'histogramme d'une région dépasse cette limite, les valeurs excédentaires sont rabotées et réparties uniformément sur l'ensemble des niveaux. Une valeur de `clipLimit` trop élevée augmente le contraste local au point de faire remonter le bruit de fond de façon spectaculaire (les zones sombres deviennent granuleuses).
- *Taille de la grille locale (`tileGridSize`)* :
- Dans VNStudio, ce paramètre correspond au champ *Grid Size* ; en Python (OpenCV), il correspond à l'argument `tileGridSize` dans `cv2.createCLAHE`.
- Configure la taille des blocs dans lesquels l'image est découpée (ex. : 8×8 ou 16×16 pixels). Une grille trop petite (ex. : 2×2) crée des artefacts de blocs visibles et dégrade la cohérence globale ; une grille trop grande se rapproche d'une égalisation globale et perd l'effet d'adaptation locale.
]

#canvas[
Dans votre canvas :
`Image Source` ──> `CLAHE` ──> `Output Display`.

Le nœud `CLAHE` travaille en interne sur le canal de clarté (préservant les couleurs) et expose les curseurs `Contrast Limit` (plafond de contraste) et `Grid Size` (taille de grille) dans l'inspecteur. En réglant ces paramètres, vous pouvez observer l'équilibre entre la visibilité des détails dans les ombres et l'apparition du bruit de fond.

*Exercice de dépannage (échec contrôlé) :* L'exercice consiste à charger une image couleur représentant un objet rouge sous un éclairage variable (mi-ombre, mi-soleil). Tenter d'isoler cet objet en appliquant un seuillage binaire direct sur le canal R (Rouge) dans le format BGR d'origine. Le lecteur constate que le seuil capture le sol clair ensoleillé mais rate l'objet à l'ombre. Remplacer ce seuil en convertissant d'abord l'image en HSV à l'aide d'un nœud *Color Space Conversion*, puis en appliquant le seuillage sur le canal H (Teinte). Le lecteur observe que l'objet est alors parfaitement isolé, illustrant l'importance de décorréler la couleur de la luminosité pour résister aux variations d'éclairage.

---
]

// ============================================================

== Correction gamma et balance des blancs

#subtitle[Le monde est gris en moyenne — quand il l'est vraiment]

#figfull("/figures/fig_ch7_obs1_gamma.pdf")

#figfull("/figures/fig_ch7_obs3_white_balance.pdf")

=== L'intention
Deux besoins distincts. D'abord comprendre le *gamma*, cette courbe de compression évoquée plusieurs fois. Ensuite corriger une dominante de couleur due à l'éclairage, pour retrouver des teintes neutres.

=== Les deux rôles du gamma
```
I_out = I_in^γ          (sur des valeurs ramenées entre 0 et 1)
```

`γ` (« gamma ») désigne l'exposant de la courbe.

Pour comprendre le rôle du gamma d'un point de vue humain et visuel, faisons une expérience :
+ *L'image mentale des bougies* : Si vous allumez une seule bougie dans une pièce totalement obscure, la hausse de clarté est spectaculaire pour votre œil. Mais si la pièce est déjà brillamment éclairée par cent bougies, allumer une cent-unième bougie passe totalement inaperçu. Notre système visuel est sensible aux *rapports* de lumière (les proportions), pas aux différences absolues. Notre sensibilité est logarithmique.
+ *Le codage malin* : Pour stocker une image en 8 bits (256 niveaux), coder les intensités de façon linéaire (proportionnelle à l'énergie lumineuse physique) serait un gaspillage immense. On allouerait trop de niveaux aux blancs très clairs (où notre œil ne fait plus la différence) et pas assez aux ombres sombres (où notre œil discerne les moindres nuances).
+ *Le gamma d'encodage (γ ≈ 0,45)* : En appliquant cette courbe de puissance avant le stockage, on comprime l'image. Cela a pour effet d'allouer une grande partie des 256 niveaux disponibles pour décrire finement les tons sombres, imitant la sensibilité naturelle de l'œil. C'est le fondement du codage standard sRGB.
+ *Le gamma d'ajustement* : Utilisé en retouche d'image, régler un `γ < 1` (ex. 0,5) redresse la courbe et éclaircit les tons moyens sans saturer les blancs. Régler un `γ > 1` (ex. 2,0) creuse la courbe et assombrit l'image tout en augmentant le contraste perçu.

Le lien avec le §7.1 est direct : les images stockées sont déjà encodées en gamma. Toute opération qui suppose une proportionnalité avec la lumière physique (lissage, redimensionnement, ou calcul de luminance) n'est rigoureusement exacte qu'après avoir *décompressé* cette courbe (en appliquant un exposant inverse de 2,2 pour retrouver l'espace linéaire). Flouter ou redimensionner sans décompresser assombrit subtilement les transitions de l'image, un biais cumulatif dans un pipeline de traitement.

=== La balance des blancs : l'hypothèse « monde gris »
L'intention : sous un éclairage teinté (une lampe jaune), retrouver des couleurs neutres. La forme repose sur une hypothèse simple — dans une scène variée, les couleurs se compensent en moyenne, donc la moyenne de l'image devrait être grise sous un éclairage neutre. Si elle ne l'est pas (l'éclairage jaunit, donc le rouge et le vert dominent le bleu en moyenne), on rééquilibre chaque canal pour ramener les trois moyennes à égalité :

```
nouveau R = R × (moyenne du vert / moyenne du rouge)
nouveau B = B × (moyenne du vert / moyenne du bleu)
```

(on prend le vert comme référence, le canal le plus stable.) Cette hypothèse est raisonnable pour des scènes générales (un bureau, une salle d'opération) mais *fausse* dès qu'une couleur domine la scène : un champ de colza, une radiographie, une forêt vue du ciel. La correction y introduit alors une distorsion inverse. Les méthodes modernes (estimation de l'éclairage par réseau de neurones) sont plus robustes, mais reposent toutes sur une hypothèse — explicite ou apprise — sur la scène.

#question-box(title: "Exemple chiffré")[
Image à dominante jaune (lampe halogène) : moyennes rouge = 180, vert = 170, bleu = 120.

```
gain rouge = 170 / 180 ≈ 0,94    (légère atténuation)
gain bleu  = 170 / 120 ≈ 1,42    (forte amplification)
```

Après correction, les trois moyennes valent 170, la dominante jaune disparaît. Mais le gain bleu de 1,42 appliqué à un pixel bleu de 200 donne 284, écrêté à 255 — une saturation qui crée des taches blanches dans les zones claires. Amplifier le bleu amplifie aussi le bruit du capteur sur ce canal, le plus bruité en faible lumière.
]

#canvas[
Canvas : `Image Source` → `White Balance (Gray World)` → `Output Display`. Le nœud calcule les gains par canal et corrige la dominante ; un nœud `Gamma Correct` placé en amont permet de travailler en espace linéarisé quand les opérations suivantes l'exigent.

---
]

// ============================================================

== Tableau récapitulatif — quel espace pour quelle tâche ?

#table(
  columns: 4,
  table.header(
    [*Espace / outil*], [*Ce qu'il encode*], [*Angle mort*], [*Usage typique*]
  ),
  [RGB (linéaire)], [énergie lumineuse physique des trois primaires], [aucun lien direct avec la perception], [calculs physiques : flou, mélange, rendu 3D],
  [RGB (gamma sRGB)], [valeurs compressées pour affichage/stockage], [faux pour tout calcul supposant de la lumière], [capture, stockage, affichage écran],
  [Niveaux de gris (luma)], [clarté pondérée selon l'œil], [perd toute l'information de couleur], [traitement structurel, gradients, seuillage],
  [HSV], [teinte, saturation, valeur découplées], [teinte instable pour les pixels peu saturés], [segmentation couleur, sélection intuitive],
  [CIELAB], [couleur perceptuellement uniforme (L_, a_, b\*)], [conversion coûteuse, pas pour le stockage], [mesure ΔE, contrôle qualité, comparaison],
  [CMYK], [quatre encres soustractives], [gamut restreint, conversion à perte], [impression, prépresse],
)

---

// ============================================================

== savoir, à chaque étape, dans quel espace on se trouve

Chaque espace colorimétrique n'est pas une vérité mais un *contrat* : il définit ce qui compte et ce qui est ignoré. RGB linéaire suppose que ce qui compte est la physique de la lumière. HSV suppose que c'est la teinte, séparée de la luminosité. CIELAB suppose que c'est la différence telle que l'œil la perçoit, non telle que le capteur la mesure. CMYK suppose que le support est de l'encre sur du papier, pas de la lumière sur un écran.

Choisir un espace pour une opération, c'est donc formuler une hypothèse sur la tâche. Mesurer un écart de couleur en RGB revient à mesurer une distance sur une carte à l'échelle variable. Segmenter par teinte sans écarter les gris revient à croire que les gris ont une couleur. Flouter sans décompresser le gamma revient à croire que les valeurs stockées sont de la lumière.

Le chapitre 3 posait la même question pour les distances, le chapitre 10 la reprendra en termes de bases — où changer de base, c'est choisir où le problème devient simple. La couleur en est l'exemple le plus quotidien : le même pixel, dans deux espaces différents, est un objet de nature entièrement différente. La rigueur photométrique ne consiste pas à connaître toutes les formules de conversion, mais à savoir, à chaque étape d'un pipeline, dans quel espace l'on se trouve et ce qu'il suppose.

---

]
