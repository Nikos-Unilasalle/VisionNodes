# Annexe — Corrigés des exercices de concrétisation

Les exercices de concrétisation de ce cahier sont des **observations expérimentales** : la réponse n'est pas un calcul à vérifier mais un phénomène à interpréter. Chaque corrigé ci-dessous décrit ce qu'on doit voir, les valeurs ou comportements attendus, et — surtout — pourquoi l'observation confirme (ou infirme) la formule du chapitre correspondant.

Les corrigés suivent la numérotation du cahier. Lorsqu'une observation peut varier selon les images utilisées, des ordres de grandeur typiques sont donnés ; l'essentiel est la direction du phénomène, pas le chiffre exact.

---

## Chapitre 1 — Descripteurs de forme

### Obs. 1.1 — Circularité vs. rondeur : deux façons de voir le contour 🔴

**Ce qu'on doit voir.** Sur un engrenage (dentelure fine, contour très long) : la circularité est basse (valeur typique : 0,2–0,4) parce que P² augmente vite avec les dents, tandis que la rondeur reste élevée (0,8–1,0) parce que la boîte englobante est toujours quasi carrée. Sur un ellipsoïde lisse allongé : à l'inverse, le contour est régulier donc la circularité est proche de 1, mais la rondeur chute (elle vaut 4A / (π · max\_diam²), qui tend vers le rapport des axes).

**Pourquoi.** La circularité C = 4πA/P² pénalise toute irrégularité du bord — même un léger dentelé fait exploser P. La rondeur R = 4A/(π · a²) avec a le grand axe ne « voit » pas le contour, seulement la boîte orientée. Les deux descripteurs encodent des points de vue orthogonaux sur la même forme, ce que leur co-présence dans la sortie dictionnaire rend immédiatement lisible.

**Valeurs de référence.**

| Forme | Circularité | Rondeur |
|---|---|---|
| Disque parfait | 1,00 | 1,00 |
| Engrenage (12 dents) | 0,25–0,40 | 0,85–0,95 |
| Ellipse (rapport 1:3) | 0,80–0,90 | 0,33 |

---

### Obs. 1.2 — Solidité vs. convexité : surface vs. périmètre de l'enveloppe 🟠

**Ce qu'on doit voir.** Un croissant lunaire présente une solidité faible (aire du croissant / aire de l'enveloppe convexe ≈ 0,4–0,5 ; l'enveloppe est un disque plein) mais une convexité élevée (périmètre du croissant ≈ périmètre de l'enveloppe car les deux courbes sont lisses). Un disque très dentelé présente la relation inverse : les dents n'affectent pas beaucoup l'aire relative mais font exploser le périmètre réel par rapport au périmètre convexe.

**Pourquoi.** La solidité = A/A_ch compare des surfaces ; la convexité = P_ch/P compare des périmètres. Une concavité profonde creuse l'aire mais n'allonge pas forcément le bord (croissant). Des dentelures superficielles allongent le bord sans rogner beaucoup l'aire.

---

### Obs. 1.3 — L'étendue change avec la rotation, pas la rectangularité 🟠

**Ce qu'on doit voir.** Un rectangle de 100 × 20 pixels placé à 0° a une étendue ≈ 100×20 / (100×20) = 1,00 (la boîte droite coïncide avec l'objet). Tourné à 45°, la boîte droite englobante mesure environ 85 × 85 : l'étendue tombe à 2000 / 7225 ≈ 0,28. La rectangularité (= A / A_ch_oriented, calculée sur la boîte minimale orientée) reste ≈ 1,00 dans les deux cas.

**Pourquoi.** La boîte droite (*axis-aligned bounding box*) dépend de l'orientation de l'objet par rapport aux axes de l'image : en diagonale, elle « gaspille » des coins. La boîte minimale orientée s'adapte à l'objet, ce qui rend la rectangularité invariante à la rotation.

---

## Chapitre 2 — Moments d'image

### Obs. 2.1 — L'ellipse équivalente ne mesure pas la taille de l'objet 🔴

**Ce qu'on doit voir.** Pour une forme en étoile ou en croix, l'ellipse équivalente (axes déterminés par μ₂₀, μ₀₂, μ₁₁) déborde largement hors des pixels de l'objet. Sur un fond blanc, la superposition via `Draw Overlay` montre que l'ellipse « occupe » l'espace entre les branches de la croix, pourtant vides. Le rapport A_ellipse / A_objet peut atteindre 3–5 pour une étoile à 6 branches.

**Pourquoi.** L'ellipse des moments d'inertie est l'ellipse d'une distribution gaussienne de même moyenne et même matrice de covariance que les pixels de l'objet. Elle caractérise la *dispersion* des pixels, pas leur *support*. Une croix a des pixels très éloignés du centroïde dans les deux directions, donc une grande inertie dans les deux axes — même si le centre géométrique est vide.

---

### Obs. 2.2 — Les moments d'ordre 3 mesurent l'asymétrie 🔴

**Ce qu'on doit voir.** Pour un triangle isocèle pointe vers le haut : μ₃₀ prend une valeur positive (la masse est concentrée vers la gauche de la pointe si le triangle n'est pas centré, ou la distribution y-cube est asymétrique). Retourner le triangle (pointe vers le bas) donne un μ₃₀ de signe opposé, amplitude identique. Pour une forme parfaitement symétrique par rapport à l'axe vertical (rectangle), μ₃₀ ≈ 0.

**Pourquoi.** μ₃₀ = Σ (x − x̄)³ · I(x,y) / m₀₀ pèse les pixels par le cube de leur écart au centroïde. Si la forme a plus de masse à gauche du centroïde qu'à droite, les termes négatifs (x − x̄ < 0) dominent : μ₃₀ < 0. Inverser la forme échange les deux côtés, changeant le signe. L'invariant de Hu qui en dérive combine μ₃₀ et μ₀₃ précisément pour obtenir l'invariance à la rotation sans perdre ce signal d'asymétrie.

---

### Obs. 2.3 — L'orientation est instable sur les formes isotropes 🟠

**Ce qu'on doit voir.** Sur un disque parfait ou presque parfait, relancer le pipeline deux fois avec un bruit gaussien léger (σ = 2–5 niveaux) produit des valeurs d'orientation qui varient de 10° à 90° d'un run à l'autre. Sur un ellipsoïde allongé (rapport ≥ 1:2), l'orientation fluctue de moins de 2°.

**Pourquoi.** L'orientation est calculée comme ½ arctan(2μ₁₁ / (μ₂₀ − μ₀₂)). Quand λ₁ ≈ λ₂ (objet circulaire), le dénominateur μ₂₀ − μ₀₂ est proche de zéro : la fraction est numériquement instable, et un bruit infime fait basculer l'angle de plusieurs dizaines de degrés. Le chapitre 2 qualifie ce comportement de « dégénérescence isotrope ».

---

## Chapitre 3 — Distances et similarités

### Obs. 3.1 — Mahalanobis : l'ellipse d'iso-distance épouse le nuage 🔴

**Ce qu'on doit voir.** La carte de distance de Mahalanobis (colorisée via LUT chaud-froid) fait ressortir en rouge les pixels dont la teinte ou la saturation est inhabituelles *relativement à la distribution du fond*. Un pixel légèrement décalé dans une direction de faible variance du nuage (H,S) apparaît anormalement rouge, alors que la même distance euclidienne dans une direction de grande variance reste bleue (normal).

**Pourquoi.** D_M(x) = √[(x−μ)ᵀ Σ⁻¹ (x−μ)]. L'inverse de la covariance Σ⁻¹ rechange l'échelle de chaque axe : il *comprime* les directions de grande variance (fréquentes) et *étire* les directions de faible variance (rares). Une anomalie « étroite » (hors de l'axe principal du nuage) est donc fortement amplifiée — ce que la distance euclidienne n'aurait pas vu.

---

### Obs. 3.2 — Wasserstein vs. χ² : transport vs. comparaison case à case 🔴

**Ce qu'on doit voir.** Pour deux histogrammes identiques décalés de 10 niveaux de gris : χ² est très élevée (toutes les cases diffèrent, même si chaque case a « glissé » vers sa voisine). La distance de Wasserstein est faible — quelques dizaines de niveaux au plus, proportionnelle au décalage. Pour deux histogrammes de formes différentes mais centrés sur la même valeur moyenne : Wasserstein peut être faible (les masses sont proches) alors que χ² reste élevée (les cases locales diffèrent).

**Pourquoi.** χ²(P,Q) = Σ (P_i − Q_i)² / Q_i compare case à case sans tenir compte de la structure ordinale de l'histogramme. W₁(P,Q) = inf_γ E[|x−y|] sous le plan de transport γ — c'est le coût de déplacement minimal de toute la masse d'un histogramme vers l'autre. Un simple décalage est un transport de coût faible ; χ² le traite comme une catastrophe.

---

### Obs. 3.3 — La boule unité change de forme avec p 🟠

**Ce qu'on doit voir.** Trois images (ou une image à trois canaux colorisés) montrent :
- **p = 1** : un carré orienté à 45° (losange). Les points à distance L₁ = 1 satisfont |x| + |y| = 1.
- **p = 2** : un cercle parfait.
- **p = ∞** : un carré aligné sur les axes. Les points à distance L∞ = 1 satisfont max(|x|, |y|) = 1.

**Pourquoi.** La norme Lp est définie par ‖v‖_p = (Σ|v_i|^p)^(1/p). À p → 1, les axes dominent ; à p → ∞, le maximum prend tout le poids. La forme de la boule unité visualise littéralement « ce que la distance considère équivalent » — le fil conducteur du chapitre.

---

## Chapitre 4 — Métriques de segmentation et détection

### Obs. 4.1 — La courbe précision-rappel et l'effet du seuil de confiance 🔴

**Ce qu'on doit voir.** En faisant varier le seuil de confiance de 0,1 à 0,9 et en traçant précision vs. rappel :
- Seuil bas (0,1) : beaucoup de détections, donc rappel élevé (≥ 0,9) mais précision faible (nombreux faux positifs).
- Seuil élevé (0,9) : peu de détections, précision élevée mais rappel bas.
- La courbe trace une hyperbole décroissante dans l'espace (rappel, précision). L'AP est l'aire sous cette courbe.

**Pourquoi.** La précision = VP / (VP + FP) et le rappel = VP / (VP + FN) sont antagonistes : baisser le seuil récupère plus de vrais positifs (rappel ↑) mais accepte plus de faux positifs (précision ↓). Aucune valeur de seuil n'est universellement optimale — rappel du fil conducteur du chapitre 4.

---

### Obs. 4.2 — AP comme aire sous la courbe PR 🟠

**Ce qu'on doit voir.** `np.trapz(precisions, recalls)` donne un nombre entre 0 et 1. Une courbe PR qui reste haute (précision ≥ 0,8 pour tout le rappel) donne AP ≥ 0,8. Une courbe qui s'effondre tôt donne AP ≈ 0,4–0,5. Visuellement, la valeur AP est proportionnelle à l'aire colorée sous la courbe affichée dans DF Editor.

**Pourquoi.** L'AP (Average Precision) est une intégrale discrète : elle résume la performance sur *tous* les seuils en un seul nombre. Un modèle qui maintient une bonne précision même à haut rappel a une grande AP — c'est la définition d'un bon détecteur sur l'ensemble du spectre de confiance.

---

### Obs. 4.3 — IoU loss vs. cross-entropie : zone plate au début 🟠

**Ce qu'on doit voir.** Pour deux masques qui ne se chevauchent pas (intersection = 0) :
- **IoU loss** = 1 − 0/(A + B − 0) = 1,0. La valeur est constante quel que soit le degré de non-chevauchement : le gradient est nul.
- **Cross-entropie** = −Σ [y log ŷ + (1−y) log(1−ŷ)], qui reste non nulle et différente selon les probabilités prédites.

**Pourquoi.** L'IoU est définie sur l'intersection : si les masques sont complètement disjoints, l'intersection est 0 et toute variation de position ne change pas la perte. Le réseau reçoit donc un gradient nul et ne peut pas apprendre à déplacer le masque prédit vers la cible. La cross-entropie, calculée pixel par pixel, fournit un signal même quand les masques ne se touchent pas — au prix d'ignorer la cohérence spatiale.

---

## Chapitre 5 — Filtrage et convolution

### Obs. 5.1 — La DoG comme filtre passe-bande 🔴

**Ce qu'on doit voir.** L'image DoG = G(σ=1) − G(σ=3) fait ressortir les structures dont l'échelle spatiale est entre 1 et 3 pixels. Les très fines textures (sous 1 px) et les larges gradients (au-dessus de 3 px) sont éliminés. Sur une image contenant simultanément du grain fin, des bords moyens et de grandes zones uniformes, seuls les bords moyens s'allument. L'image résultante a une moyenne proche de zéro (histogram centré sur 128 après normalisation).

**Pourquoi.** G(σ=1) laisse passer tout ce qui est au-dessus de 1/σ₁ en fréquence. G(σ=3) laisse passer tout ce qui est au-dessus de 1/σ₂. La différence annule les fréquences communes aux deux (très basses et très hautes) et conserve la bande intermédiaire. La DoG est une approximation du Laplacien de Gaussienne (LoG), qui est lui-même le filtre optimal pour la détection de blobs.

---

### Obs. 5.2 — Le filtre de Gabor : fréquence ET orientation 🔴

**Ce qu'on doit voir.** Sur une image d'empreinte digitale :
- Gabor à θ = 0° (horizontal) : les crêtes horizontales s'allument, les crêtes verticales restent sombres.
- Gabor à θ = 90° (vertical) : situation inverse.
- La carte de réponse totale (max sur 4 orientations) révèle l'ensemble des crêtes.

La réponse d'un filtre de Gabor à θ = 0° sur une crête perpendiculaire (verticale) est quasi nulle. La séparation est nette, visible dans la LUT colorisée.

**Pourquoi.** Le filtre de Gabor est le produit d'une gaussienne (qui localise) et d'une sinusoïde à fréquence λ orientée à angle θ. Il ne répond qu'aux structures qui oscillent à la fréquence λ dans la direction θ — les deux paramètres sont indépendants et cumulatifs. Le chapitre 5 montre que c'est l'analogue fréquentiel d'un filtre sélectif en orientation, lié à la théorie des ondelettes (cf. chapitre 10).

---

### Obs. 5.3 — La convolution n'est pas une corrélation 🟠

**Ce qu'on doit voir.** Un noyau asymétrique (par exemple un triangle ou une flèche orientée à droite) appliqué via `cv2.filter2D` et via `scipy.signal.convolve2d` (qui retourne le noyau) donne deux images différentes : la flèche semble pointer dans le sens inverse dans l'un des cas. Sur un noyau symétrique (Gaussienne, Laplacien), les deux résultats sont identiques.

**Pourquoi.** La convolution mathématique de f par g est (f ★ g)(x) = Σ f(τ) g(x−τ) : le noyau g est retourné (flip horizontal et vertical) avant d'être glissé. `cv2.filter2D` calcule la corrélation : il applique le noyau tel quel, sans retournement. Pour un noyau symétrique (g(−x) = g(x)), l'opération est identique — c'est pourquoi le piège est invisible dans 90 % des cas pratiques et mord précisément quand le noyau code une direction.

---

## Chapitre 6 — Gradients et contours

### Obs. 6.1 — Le tenseur de structure : coin / bord / plat 🔴

**Ce qu'on doit voir.** La carte colorisée des trois régimes (calculée depuis λ₁ et λ₂ du tenseur de structure) montre trois couleurs distinctes :
- **Zone plate** (fond uni) : λ₁ ≈ λ₂ ≈ 0 → couleur A (ex. bleu).
- **Bord droit** : λ₁ grand, λ₂ ≈ 0 → couleur B (ex. vert).
- **Coin** (jonction de deux bords) : λ₁ grand, λ₂ grand → couleur C (ex. rouge).

Le critère de Harris R = λ₁λ₂ − k(λ₁+λ₂)² sépare ces trois régimes par des seuils sur R.

**Pourquoi.** Le tenseur de structure J = Σ [∇I(∇I)ᵀ] dans un voisinage gaussien encode la distribution des directions de gradient locales. Si les gradients pointent tous dans la même direction : un seul vecteur propre fort (bord). Si les gradients pointent dans toutes les directions : deux vecteurs propres forts (coin). Si les gradients sont nuls : aucun (fond).

---

### Obs. 6.2 — Le problème d'ouverture 🔴

**Ce qu'on doit voir.** Sur une barre verticale se déplaçant horizontalement, les vecteurs de flot sur les bords latéraux (verticaux) pointent correctement vers la droite. Les vecteurs sur le bord supérieur ou inférieur (horizontal) pointent dans des directions aléatoires ou nulles — la composante parallèle au bord n'est pas observable. Relancer sur une frame légèrement différente change les vecteurs horizontaux sans les stabiliser.

**Pourquoi.** L'équation du flot Ix·u + Iy·v + It = 0 contraint le flot sur une droite dans l'espace (u,v) — la droite normale au vecteur gradient (Ix, Iy). Le long d'un bord horizontal, Ix ≈ 0 : la contrainte devient Iy·v + It = 0, qui fixe v mais laisse u totalement libre. Seul un a priori additionnel (régularisation comme dans Horn-Schunck) peut résoudre l'ambiguïté.

---

### Obs. 6.3 — Suppression des non-maxima dans Canny 🟠

**Ce qu'on doit voir.** La carte de gradient Sobel produit des bords larges de 3–7 pixels. Après suppression des non-maxima (étape interne à Canny), les bords sont réduits à 1 pixel de large, précisément alignés sur le maximum local dans la direction du gradient. La comparaison Split Half rend le contraste entre les deux immédiatement lisible.

**Pourquoi.** Pour chaque pixel, Canny regarde ses deux voisins dans la direction du gradient. Si le pixel n'est pas un maximum local (l'un de ses voisins a un gradient plus fort), il est supprimé. Ce filtre morphologique d'amincissement n'affecte pas la position du bord mais garantit sa finesse — condition nécessaire pour mesurer des distances ou ajuster des contours.

---

## Chapitre 7 — Couleur et photométrie

### Obs. 7.1 — La correction gamma : espace linéaire vs. perceptuel 🔴

**Ce qu'on doit voir.** Un dégradé de gris *linéaire* (valeurs 0, 32, 64, 96, … 255 dans l'image) paraît non uniforme à l'œil : les tons sombres semblent trop proches les uns des autres. Après décodage gamma (division des valeurs par 255, élévation à la puissance 2.2, remultiplication) : le profil de ligne (*Line Profile*) devient croissant régulièrement, et le dégradé paraît perceptuellement uniforme.

**Pourquoi.** Les images JPEG stockent des valeurs sRGB *gamma-encodées* : V_stocké = V_linéaire^(1/2.2). La courbe gamma compresse les hautes luminances et étire les basses — car l'œil humain est plus sensible aux variations dans les ombres. Travailler en espace linéaire (après décodage) est indispensable pour toute opération photométrique correcte (floutage, interpolation, fusion). Le chapitre 7 souligne que confondre les deux espaces introduit des erreurs invisibles mais systématiques.

---

### Obs. 7.2 — ΔE en espace Lab 🔴

**Ce qu'on doit voir.** Deux paires de couleurs soigneusement choisies :
- Paire A : un rouge orangé et un rouge légèrement plus saturé. Distance RGB : faible (≈ 15). ΔE Lab : élevé (≈ 8–12, perceptible à l'œil).
- Paire B : un bleu foncé et un noir. Distance RGB : faible (≈ 15). ΔE Lab : très faible (≈ 2–3, imperceptible).

Le Python Node calcule les deux ΔE et les affiche dans le dictionnaire : la valeur Lab prédit exactement la perception.

**Pourquoi.** L'espace CIE L*a*b* est construit pour que ΔE = ‖Lab₁ − Lab₂‖₂ corresponde à la différence perçue par un observateur standard. La métrique euclidienne en RGB n'a aucune propriété perceptuelle : les couleurs n'y sont pas réparties uniformément selon la sensibilité de l'œil.

---

### Obs. 7.3 — La balance des blancs comme hypothèse sur l'illuminant 🟠

**Ce qu'on doit voir.** Une image sous lumière tungstène a une dominante orange (canal R très supérieur à B). Cibler une zone supposée blanche (une feuille de papier) comme référence neutralise la dominante : la feuille devient blanche, toute la scène est corrigée. Changer la zone cible (pointer un mur beige comme « blanc ») produit une correction différente — voire une dominante bleue si la zone choisie est réellement orangée.

**Pourquoi.** La balance des blancs est une normalisation par canal : R' = R / R_ref, G' = G / G_ref, B' = B / B_ref. On *déclare* que R_ref, G_ref, B_ref sont les valeurs d'un objet « blanc » dans la scène. C'est une hypothèse sur l'illuminant : si l'hypothèse est fausse (la zone cible n'est pas blanche dans la réalité), la correction est incorrecte. L'algorithme ne peut pas distinguer « blanc sous lumière colorée » de « couleur sous lumière blanche ».

---

## Chapitre 8 — Géométrie projective et caméra

### Obs. 8.1 — Les coordonnées homogènes 🔴

**Ce qu'on doit voir.** Appliquer translation (Δx = 50, Δy = 30) puis rotation (θ = 15°) via deux matrices séquentielles donne exactement le même résultat qu'une unique matrice H = T · R. Le Split Half montre deux images pixel-identiques. Ce qui est nouveau : la matrice H est lisible — les deux premières colonnes encodent la rotation, la troisième la translation.

**Pourquoi.** En coordonnées homogènes, un point (x, y) devient (x, y, 1) et la translation [Δx, Δy] s'écrit comme une troisième colonne de la matrice 3×3. Cela transforme la composition de transformations affines en simple multiplication matricielle — ce qui autorise notamment l'interpolation entre transformations et la décomposition SVD pour l'estimation robuste (RANSAC).

---

### Obs. 8.2 — La distorsion radiale : les droites qui courbent 🔴

**Ce qu'on doit voir.** Sur une image brute de damier grand-angle : les bords du damier sont courbes (distorsion en barillet pour un objectif fisheye, avec les bords qui s'incurvent vers l'intérieur). Après `cv2.undistort` avec les coefficients k1, k2 calibrés : les lignes du damier sont parfaitement droites, vérifiable en superposant une grille.

**Pourquoi.** Le modèle de distorsion radiale corrige r_corr = r_dist · (1 + k1·r² + k2·r⁴ + …). À faible r (centre), la correction est négligeable. À grand r (bords), elle peut déplacer un pixel de plusieurs dizaines de pixels. La calibration (via des images de damier) estime k1, k2 — sans cette étape, toute mesure géométrique à partir d'une image grand-angle est biaisée.

---

### Obs. 8.3 — Géométrie épipolaire et droites épipolaires 🟠

**Ce qu'on doit voir.** En cliquant sur un point dans la vue gauche et en traçant la droite épipolaire correspondante dans la vue droite : le point correspondant réel (visible à l'œil) se trouve systématiquement *sur* cette droite, à moins d'un pixel près (erreur de reprojection typique après bonne calibration : < 1,5 px). Changer le point cliqué déplace la droite, et le correspondant reste dessus.

**Pourquoi.** La matrice fondamentale F encode la contrainte épipolaire : pour tout point x dans la vue gauche, son correspondant x' dans la vue droite satisfait x'ᵀ F x = 0. La droite épipolaire F·x est donc une contrainte exacte (modulo le bruit de calibration) — elle réduit la recherche de correspondance de 2D à 1D, ce qui est le fondement de la vision stéréo.

---

## Chapitre 9 — Flot optique et mouvement

### Obs. 9.1 — La contrainte du flot : une équation, deux inconnues 🔴

**Ce qu'on doit voir.** Sur une barre verticale se déplaçant horizontalement, les flèches de flot sur les bords latéraux (verticaux de la barre) pointent horizontalement et sont cohérentes d'un run à l'autre. Sur le bord supérieur de la barre (horizontal), les flèches ont des composantes verticales aléatoires — elles varient entre exécutions même pour le même mouvement.

**Pourquoi.** L'équation Ix·u + Iy·v + It = 0 contraint (u, v) à une droite. Sur un bord vertical, Iy ≈ 0 : la contrainte devient Ix·u + It = 0, qui fixe u (la composante horizontale, correcte) mais laisse v libre. Chaque algorithme résout cette ambiguïté différemment (Lucas-Kanade suppose un flot constant dans une fenêtre ; Horn-Schunck ajoute un terme de régularisation globale), mais le problème sous-déterminé au niveau du pixel isolé reste entier.

---

### Obs. 9.2 — Horn-Schunck : α règle le curseur données/régularisation 🟠

**Ce qu'on doit voir.**
- **α = 0.05** (colle aux données) : la carte de flot est détaillée mais bruitée. Les zones homogènes montrent des vecteurs erratiques (gradient nul → contrainte presque nulle → flot arbitraire).
- **α = 2.0** (lisse fortement) : la carte est régulière mais les bords des objets en mouvement sont « dilués » — le flot d'un objet se propage aux pixels du fond voisin.

La comparaison Split Half + LUT (codage couleur de la direction et magnitude du flot) rend le compromis immédiatement visible.

**Pourquoi.** Horn-Schunck minimise E = ∬ [(Ix·u + Iy·v + It)² + α² (‖∇u‖² + ‖∇v‖²)] dx dy. Le premier terme colle aux données ; le second lisse le champ. α est le paramètre de régularisation — exactement le λ du chapitre 9, ici mis en scène.

---

### Obs. 9.3 — Flot épars vs. flot dense 🟠

**Ce qu'on doit voir.** Dans la Grid Compare Dashboard :
- **Flot épars** (Shi-Tomasi + Lucas-Kanade) : des flèches apparaissent uniquement sur les coins et textures fortes. Les zones de fond uni, les ciels, les murs homogènes n'ont aucun vecteur.
- **Flot dense** (Farneback) : chaque pixel a un vecteur, y compris dans les zones homogènes — mais ces vecteurs sont souvent bruités ou arbitraires dans les zones sans gradient.

**Pourquoi.** Le flot épars ne calcule que là où le tenseur de structure a deux valeurs propres significatives (coins), ce qui garantit la fiabilité locale. Le flot dense extrapole partout, au risque d'inventer un mouvement là où le signal est insuffisant. Aucun des deux n'est supérieur : leur choix dépend de l'application (suivi de points vs. estimation globale du mouvement).

---

## Chapitre 10 — Transformées

### Obs. 10.1 — La transformée de distance 🔴

**Ce qu'on doit voir.** La carte de distance (colorisée en LUT chaud, valeurs hautes = rouge) montre un pic rouge en forme de dôme au centre de chaque objet — les pixels les plus éloignés du bord. Pour une cellule circulaire, le pic est centré et symétrique ; pour une cellule allongée, le pic est une crête le long de l'axe principal. Ce sommet est directement utilisable comme germe pour l'algorithme watershed.

**Pourquoi.** `cv2.distanceTransform(mask, DIST_L2, 5)` attribue à chaque pixel de premier plan sa distance euclidienne au pixel de fond le plus proche. La transformée inverse la notion de bord : les pixels « éloignés du bord » sont les candidats naturels aux centres d'objets. C'est le dual morphologique de l'érosion — éroder une forme jusqu'à son squelette fait apparaître les mêmes points.

---

### Obs. 10.2 — Le théorème de convolution 🔴

**Ce qu'on doit voir.** Les deux résultats (flou via `Gaussian Blur` direct, et flou via FFT → multiplication → IFFT) sont pixel-identiques à la précision numérique près (différence max ≈ 1 niveau de gris). Le Split Half ne montre aucune différence visible. En revanche, le chemin FFT permet de *visualiser* le spectre du noyau gaussien avant multiplication : un dôme centré en (0,0) à décroissance rapide.

**Pourquoi.** Si F désigne la transformée de Fourier, le théorème de convolution dit que F[f ★ g] = F[f] · F[g]. Appliquer le flou dans l'espace fréquentiel consiste à multiplier terme à terme les spectres — une opération triviale — puis à repasser dans l'espace image par FFT inverse. L'intérêt pratique : pour un grand noyau (σ grand), cette voie est plus rapide que la convolution directe (O(N log N) vs. O(N²)).

---

### Obs. 10.3 — La transformée de Hough : l'espace accumulateur 🟠

**Ce qu'on doit voir.** L'accumulateur H(ρ, θ) colorisé par LUT montre des pics brillants en rouge pour les couples (ρ, θ) correspondant aux droites dominantes de l'image. Sur une image d'un damier, on voit des séries de pics horizontaux (θ ≈ 0°) et verticaux (θ ≈ 90°), régulièrement espacés en ρ selon le pas du damier.

**Pourquoi.** Chaque pixel de contour (x₀, y₀) vote pour toutes les droites qui le traversent : ρ = x₀ cos θ + y₀ sin θ pour θ ∈ [0°, 180°]. Dans l'accumulateur, ce vote dessine une courbe sinusoïdale. Quand plusieurs pixels colinéaires votent, leurs courbes sinusoïdales s'intersectent au même point (ρ, θ) : le pic est le seul endroit où toutes les contraintes sont simultanément satisfaites — exactement le principe des méthodes à vote généralisé.

---

## Chapitre 11 — Morphologie mathématique

### Obs. 11.1 — L'élément structurant est une hypothèse sur la forme 🔴

**Ce qu'on doit voir.** Sur une image contenant des grains circulaires et des fibres fines allongées :
- **Érosion par SE circulaire (rayon 5)** : les fibres fines (largeur < 5 px) disparaissent, les grains ronds (diamètre > 10 px) sont réduits mais survivent.
- **Érosion par SE rectangulaire horizontal (1 × 11)** : les objets verticaux fins disparaissent, les fibres horizontales survivent.

La Grid Compare Dashboard montre deux résultats très différents sur la même image d'entrée.

**Pourquoi.** L'érosion de A par B = {x : B_x ⊆ A} ne conserve que les pixels autour desquels l'élément structurant tient entièrement dans A. Le SE est donc une hypothèse explicite sur la forme qu'on cherche à préserver : choisir le SE, c'est déclarer quelle géométrie mérite d'exister — fil conducteur du chapitre 11.

---

### Obs. 11.2 — Le gradient morphologique révèle les bords sans dériver 🔴

**Ce qu'on doit voir.** Sur une image bruitée (bruit gaussien σ = 10–15) :
- **Sobel** : les bords sont visibles mais accompagnés d'un bruit de fond significatif dans les zones homogènes (le bruit crée des gradients parasites).
- **Gradient morphologique** (dilate − erode avec SE 3×3) : les bords principaux ressortent, les zones homogènes sont quasi silencieuses (le max et le min locaux sont proches pour un bruit modéré).

**Pourquoi.** Le gradient morphologique Δ(A) = δ(A) − ε(A) est la différence entre dilatation et érosion. Il mesure l'écart entre le maximum et le minimum de A dans le SE — une mesure de contraste local purement basée sur l'ordre, non sur la dérivée. Le bruit gaussien ajoute des fluctuations de quelques niveaux, que le max−min atténue naturellement sur une fenêtre 3×3.

---

### Obs. 11.3 — Le squelette : axe médian topologique 🟠

**Ce qu'on doit voir.**
- **Forme en T** : squelette avec une jonction à trois branches, chaque branche correspondant à un bras du T.
- **Forme en L** : squelette à deux branches avec un coude.
- **Anneau (tore 2D)** : squelette circulaire — un cercle, pas un point.

La superposition via Draw Overlay montre que chaque branche du squelette est l'axe des cercles maximaux inscrits dans la forme.

**Pourquoi.** Le squelette est l'ensemble des centres des boules maximales inscrites dans A : {x : ∃r, B(x,r) ⊆ A, et il n'existe pas de boule plus grande contenant B(x,r) dans A}. Topologiquement, il préserve les connexités et les trous de la forme originale (le squelette d'un anneau est connexe, celui d'un disque est un point). C'est une représentation structurelle, pas géométrique — elle dit comment la forme est connectée, pas quelle est sa taille exacte.

---

## Chapitre 12 — Seuillage et segmentation classique

### Obs. 12.1 — K-means : sensibilité à l'initialisation 🔴

**Ce qu'on doit voir.** Sur la même image relancée deux fois avec `KMEANS_RANDOM_CENTERS` :
- Les étiquettes de cluster peuvent être permutées (le « cluster 1 » d'un run est le « cluster 2 » de l'autre — permutation d'étiquette, inévitable).
- Mais plus significativement : la frontière entre clusters peut être tracée différemment, surtout dans les zones de l'histogramme où les modes sont proches ou chevauchants. La Grid Compare Dashboard révèle des différences dans ces zones ambiguës.

**Pourquoi.** K-means converge vers un minimum *local* de l'inertie intra-cluster. Deux initialisations aléatoires différentes peuvent tomber dans des bassins d'attraction différents. Sur une image multimodale bien séparée, les résultats convergent vers le même minimum ; sur une image avec des modes proches, les minima locaux diffèrent significativement. K-means++ (initialisation intelligente) réduit mais n'élimine pas ce problème.

---

### Obs. 12.2 — Mean-shift : les pixels remontent vers les modes de densité 🔴

**Ce qu'on doit voir.** La segmentation mean-shift produit automatiquement un nombre de régions qui n'a pas besoin d'être spécifié à l'avance. Sur une image de fleurs, K-means avec K = 4 peut fusionner deux fleurs de couleurs proches en un seul cluster ; mean-shift les sépare naturellement si leurs modes dans l'espace couleur sont distincts. Le nombre de régions varie avec les paramètres `spatialRadius` et `colorRadius`.

**Pourquoi.** Mean-shift est un algorithme de recherche de modes : chaque pixel remonte itérativement vers la moyenne de son voisinage (dans l'espace couleur-position joint), jusqu'à convergence vers un mode local de la densité. Les pixels convergent vers le même mode sont dans la même région. Le nombre de modes — donc de régions — est une propriété émergente de la densité, pas un paramètre.

---

### Obs. 12.3 — La coupe de graphe : l'a priori de cohérence spatiale 🟠

**Ce qu'on doit voir.** Sur une image de deux régions séparées avec du bruit :
- **K-means** : de nombreux pixels isolés sont mal classés (le cluster est décidé par couleur seule, sans tenir compte des voisins).
- **AI Segmenter (SAM)** : les frontières sont cohérentes, les régions sont connexes, les pixels isolés ont été « corrigés » par leur contexte spatial.

**Pourquoi.** La coupe de graphe minimise E = Σ_pixel [terme_donnée] + λ · Σ_voisins [terme_régularisation]. Le terme de régularisation pénalise les couples de pixels voisins ayant des étiquettes différentes — il est l'analogue du λ ‖∇u‖² du chapitre 9. K-means minimise uniquement le terme données ; la coupe de graphe intègre les deux. Le paramètre λ est le même curseur données/régularisation que celui du chapitre 9 (Horn-Schunck), du chapitre 15 (loss terms) et du chapitre 16 (IRLS).

---

## Chapitre 13 — Texture

### Obs. 13.1 — La GLCM : la texture comme relation entre paires de pixels 🔴

**Ce qu'on doit voir.**
- **Tissu croisé** (trame régulière) : la GLCM montre des pics hors-diagonale concentrés en positions symétriques — les niveaux de gris alternent régulièrement entre voisins, ce que la GLCM encode comme des cooccurrences denses à distance fixe de la diagonale.
- **Sable ou texture aléatoire** : la GLCM est diffuse, concentrée sur la diagonale (les voisins ont souvent des niveaux proches) sans pic hors-diagonale.

**Pourquoi.** GLCM(i,j) = nombre de paires (p,q) voisines avec I(p) = i et I(q) = j. Une texture périodique crée des cooccurrences très prévisibles : le niveau i est systématiquement suivi du niveau j. Une texture aléatoire répartit les cooccurrences uniformément. L'énergie (somme des carrés) mesure la concentration, la corrélation mesure la régularité — deux descripteurs extraits de la même matrice pour des tâches différentes.

---

### Obs. 13.2 — LBP : l'histogramme change avec la rotation 🔴

**Ce qu'on doit voir.**
- **LBP classique** sur un tissu à 0° et à 45° : les histogrammes LBP sont clairement différents. Les bins correspondant aux motifs binaires « bord gauche », « bord droit » etc. changent d'importance avec la rotation.
- **LBP rotation-invariant** (variante `uniform`) : les deux histogrammes sont quasi identiques — la distance χ² entre eux est divisée par 5–10.

**Pourquoi.** Le LBP classique encode le patron de bits brut (ex. 00011111) ; tourner l'image fait tourner le patron de bits (→ 00000111), changeant le bin. Le LBP rotation-invariant classe tous les rotations d'un même patron dans le même bin (la rotation circulaire minimale) — au prix d'un histogramme moins discriminant (moins de bins distincts).

---

### Obs. 13.3 — L'énergie de Gabor 🟠

**Ce qu'on doit voir.** La Grid Compare Dashboard à 8 cases (4 orientations × 2 fréquences) montre :
- Les cases correspondant à l'orientation dominante de la texture s'allument (réponse forte).
- Les cases perpendiculaires restent sombres.
- Les cases à haute fréquence captent les textures fines ; les basses fréquences captent les structures larges.

Pour une image de bois (veines parallèles à 30°), seules les cases proches de θ = 30° montrent une réponse forte.

**Pourquoi.** Le banc de filtres de Gabor constitue un dictionnaire de détecteurs, chacun accordé à une fréquence et une orientation précises. La réponse de chaque filtre mesure la puissance du signal texturé à cette fréquence et cette orientation localement. L'ensemble des réponses forme une représentation temps-fréquence-orientation — le pendant orienté du spectrogramme de Fourier.

---

## Chapitre 14 — Qualité d'image

### Obs. 14.1 — SSIM : les trois cartes séparées 🔴

**Ce qu'on doit voir.** Pour une image floutée par rapport à l'originale :
- **Carte de luminance** : reste proche de 1 partout (le flou ne change pas les valeurs moyennes).
- **Carte de contraste** : légèrement dégradée aux bords des objets.
- **Carte de structure** : chute significativement aux zones de texture et aux contours — c'est elle qui « voit » la perte de netteté.

La Grid Compare Dashboard avec les trois cartes rend visible que le SSIM punit principalement la perte de structure, ce que le PSNR (aveugle à la structure) ne ferait pas.

**Pourquoi.** SSIM = l(x,y) · c(x,y) · s(x,y) avec l = luminance locale, c = contraste local, s = corrélation croisée normalisée (structure). Un flou gaussien préserve les moyennes (l ≈ 1), réduit légèrement les variances (c légèrement < 1), mais effondre la corrélation croisée (s ↓) car les hautes fréquences — là où la structure de l'image réside — sont atténuées.

---

### Obs. 14.2 — L'entropie sans référence 🔴

**Ce qu'on doit voir.** L'histogramme d'une image nette est étalé sur une large plage de niveaux de gris. Après flou gaussien (σ = 3–5), l'histogramme se concentre autour de la valeur moyenne — les queues disparaissent. L'entropie H = −Σ p_i log₂ p_i chute typiquement de 7–7,5 bits (image nette) à 6–6,5 bits (image floutée).

**Pourquoi.** Le flou est un filtre passe-bas qui atténue les hautes fréquences. Dans le domaine spatial, cela homogénéise les niveaux de gris voisins — l'image floutée a moins de variabilité locale, donc moins de niveaux distincts, donc un histogramme plus concentré, donc une entropie plus faible. L'entropie est donc un indicateur de netteté sans référence (NR-IQA), utile quand l'image originale n'est pas disponible.

---

### Obs. 14.3 — PSNR vs. SSIM : même score, perception très différente 🟠

**Ce qu'on doit voir.** Les deux images (l'une bruitée, l'autre floutée, calibrées pour la même MSE via Python Node) ont le même PSNR (ex. 28 dB). Mais :
- **SSIM du flou** : ≈ 0,70–0,80 (structure dégradée).
- **SSIM du bruit** : ≈ 0,85–0,95 (structure préservée, seul le bruit s'additionne).

La Grid Compare Dashboard montre deux images d'apparence radicalement différente pour un PSNR identique.

**Pourquoi.** PSNR = 10 log₁₀(255² / MSE) est monotone en MSE : il ne fait que compter l'erreur quadratique pixel à pixel, sans tenir compte de la structure spatiale. Un bruit gaussien éparpille l'énergie d'erreur uniformément, laissant les structures visibles. Un flou concentre l'énergie d'erreur là où les gradients sont forts, détruisant précisément les bords — ce que l'œil perçoit immédiatement. SSIM, qui pénalise la perte de corrélation structurelle, discrimine les deux.

---

## Chapitre 15 — Apprentissage profond (fonctions de coût)

### Obs. 15.1 — La focal loss : γ déplace le poids vers les exemples difficiles 🔴

**Ce qu'on doit voir.** Le graphe du facteur (1 − p)^γ en fonction de p ∈ [0, 1] pour γ = 0, 1, 2 :
- **γ = 0** : droite horizontale à 1 — tous les exemples contribuent également (cross-entropie standard).
- **γ = 1** : décroissance linéaire — les exemples faciles (p → 1) ont un poids faible.
- **γ = 2** : décroissance quadratique — pour p = 0,9, le facteur vaut 0,01 (1 % du poids nominal). Les exemples faciles sont presque ignorés.

Le passage de γ = 0 à γ = 2 révèle visuellement pourquoi la focal loss améliore la détection des objets rares.

**Pourquoi.** Dans un dataset fortement déséquilibré (beaucoup de fond, peu d'objets), les exemples faciles (fond correctement classé avec p ≈ 1) dominent le gradient total et noient le signal des exemples difficiles (vrais objets, p ≈ 0,5). Le facteur (1 − p)^γ rééquilibre cette contribution sans modifier la formule de la cross-entropie — c'est un ré-pesage adaptatif, pas une perte différente.

---

### Obs. 15.2 — La loss contrastive (InfoNCE) 🔴

**Ce qu'on doit voir.** La projection PCA (ou UMAP) des embeddings CLIP sur 2D forme des clusters séparés par catégorie visuelle — même sans étiquette de classe fournie au réseau lors de son entraînement. Les images d'une même catégorie (chiens, bâtiments, textes) sont proches dans l'espace projeté ; les catégories différentes sont éloignées.

**Pourquoi.** InfoNCE entraîne le réseau à maximiser la similarité cos(z_i, z_j+) entre paires positives (deux vues du même contenu) et à minimiser cos(z_i, z_k−) pour toutes les paires négatives dans le batch. Le résultat est un espace où la distance euclidienne / cosinus encode la similarité sémantique — sans jamais avoir annoté de catégorie. La loss contrastive est un mécanisme de mise en forme de l'espace de représentation, dual du rôle de la distance au chapitre 3.

---

### Obs. 15.3 — Smooth L1 (Huber) : la transition à δ 🟠

**Ce qu'on doit voir.** Le graphe sur l'intervalle [−3, +3] montre :
- **L1** : ligne droite, pente constante ±1.
- **L2** : parabole, pente croissante (gradient croissant avec l'erreur).
- **Huber (δ = 1)** : parabole pour |e| < 1, puis tangente aux deux branches L1 pour |e| > 1. La transition à |e| = 1 est visible : la courbe change de régime sans discontinuité.

Pour δ = 1, la transition est à e = ±1 ; pour δ = 0.5, elle est à e = ±0.5 — modifier δ déplace visuellement le point de basculement.

**Pourquoi.** La perte de Huber est L(e) = ½e² si |e| ≤ δ, et δ(|e| − ½δ) sinon. Elle combine la stabilité quadratique (gradient proportionnel à l'erreur, utile pour les petites erreurs) et la robustesse linéaire (gradient constant, non croissant, pour les grandes erreurs). Les valeurs aberrantes ne peuvent pas faire exploser le gradient — c'est le lien direct avec les M-estimateurs du chapitre 16.

---

## Chapitre 16 — Statistiques robustes

### Obs. 16.1 — MAD vs. écart-type face aux aberrants 🔴

**Ce qu'on doit voir.** Sur une image de fond uniforme à 128 avec 5 pixels à 255 :
- **Écart-type** : valeur élevée même pour un fond très uniforme — les 5 pixels aberrants gonflent σ significativement (typiquement 10–20× la valeur attendue pour le fond seul).
- **MAD** : reste quasi nulle si le fond est uniforme (médiane ≈ 128, déviations à la médiane ≈ 0 pour le fond).

En augmentant l'intensité des aberrants de 128 à 255 progressivement : la courbe σ(intensité) croît linéairement, la courbe MAD(intensité) reste plate jusqu'à ce que les aberrants représentent plus de 50 % des pixels.

**Pourquoi.** MAD = médiane(|X_i − médiane(X)|). La médiane est robuste aux extrêmes : tant que moins de 50 % des observations sont aberrantes, la médiane ne bouge pas, et donc la MAD non plus. L'écart-type, lui, est la racine de la moyenne des carrés des déviations à la moyenne — les aberrants, en carré, dominent instantanément.

---

### Obs. 16.2 — M-estimateurs : fonctions d'influence des estimateurs 🔴

**Ce qu'on doit voir.** Le graphe des fonctions ψ(e) sur [−5, +5] :
- **L2 (moindres carrés)** : ψ(e) = e, droite — l'influence est proportionnelle au résidu, sans borne.
- **Huber (c = 1.345)** : ψ(e) = e pour |e| < c, puis ψ(e) = ±c pour |e| > c — l'influence est bornée à ±c.
- **Tukey (c = 4.685)** : ψ(e) = e(1 − e²/c²)² pour |e| < c, puis ψ(e) = 0 pour |e| > c — l'influence *retombe à zéro* pour les résidus extrêmes.

Pour Tukey, un résidu de 10 (très aberrant) a une influence strictement nulle — l'estimateur l'ignore complètement.

**Pourquoi.** La fonction d'influence ψ = ρ' est la dérivée de la fonction de perte ρ. Elle dit combien une observation tire l'estimation. Pour L2, ψ est non bornée — un aberrant extrême peut déplacer l'estimation autant qu'il veut. Huber borne ψ mais ne l'annule pas. Tukey (re-descending) annule ψ pour les résidus extrêmes, au prix d'une perte de convexité — il peut ne pas converger sans bonne initialisation.

---

### Obs. 16.3 — IRLS : les poids qui diminuent 🟠

**Ce qu'on doit voir.** Dans le DF Editor affichant les poids w_i à chaque itération :
- **Itération 1** : tous les poids ≈ 1 (initialisation à moindres carrés ordinaires).
- **Itération 2–3** : les poids des 3 points aberrants commencent à baisser (0,3–0,6).
- **Itération 5–8** : les poids des aberrants tendent vers 0 (< 0,05) ; les poids des points inlines restent proches de 1.
- **Convergence** : la droite ajustée est quasiment identique à la droite ajustée sur les seuls points inlines.

**Pourquoi.** IRLS (Itératively Reweighted Least Squares) résout le M-estimateur en résolvant à chaque itération un problème de moindres carrés pondérés avec w_i = ψ(r_i/σ) / r_i. Comme la solution pondérée réduit les résidus des points inlines (ils restent bien ajustés) et augmente les résidus des aberrants (ils s'éloignent de la droite ajustée), les poids des aberrants diminuent à chaque itération. C'est une procédure auto-améliorante : plus on itère, moins les aberrants ont d'influence.

---

*Fin de l'annexe.*

---

> **Note d'usage.** Ces corrigés décrivent le phénomène attendu dans les conditions typiques d'observation. Les valeurs numériques exactes dépendent de l'image utilisée et des paramètres choisis ; ce qui ne doit pas varier, c'est la *direction* du phénomène (quel descripteur augmente, quel autre reste stable, quelle courbe domine l'autre). Si l'observation s'écarte qualitativement du corrigé, c'est généralement le signe d'un paramètre mal réglé (σ trop faible pour voir l'effet du bruit, seuil de segmentation qui ne sépare pas les régions, etc.) plutôt qu'une erreur de pipeline.
