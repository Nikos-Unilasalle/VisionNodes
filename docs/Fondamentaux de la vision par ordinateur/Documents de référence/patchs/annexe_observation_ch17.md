# Annexe — Scripts d'observation (addendum chapitre 17)

> **Insertion.** Ajouter cette section à `annexe_scripts_observation.md`, après le chapitre 15. Mettre à jour la phrase d'introduction de l'annexe : « Les chapitres 9, 10, 12, 15 **et 17** proposaient des exercices d'observation… ».
>
> Même contrat que le reste de l'annexe : scripts autonomes, exécutables au terminal ou dans Jupyter, qui génèrent leurs propres données synthétiques (remplaçables par vos images via `cv2.imread`), calculent, impriment les constats et sauvegardent une figure. **Bibliothèques :** `numpy`, `opencv-contrib-python` (pour SIFT), `scikit-image`, `matplotlib`.

---

## Chapitre 17 — Descripteurs locaux et appariement

### Observation 17.A — Pixels bruts contre descripteurs : qui survit à la transformation ?

**Concept mis en jeu.** Un patch de pixels bruts comparé par SSD est dominé par la rotation, l'échelle et le gain ; il perd le point homologue. Un descripteur (ORB) encode l'invariance et le retrouve. La même paire d'images donne deux verdicts opposés selon ce qu'on compare.

```python
import numpy as np, cv2, matplotlib.pyplot as plt

# --- Paire synthétique : A texturée, B = A tournée/agrandie/éclaircie ---
# Pour vos images : A = cv2.imread("vue1.png") ; B = cv2.imread("vue2.png")
def scene_paire(seed=0, angle=30, echelle=1.2, lumiere=40):
    rng = np.random.default_rng(seed); H, W = 360, 480
    A = np.full((H, W, 3), 30, np.uint8)
    for _ in range(120):                                   # semer des motifs distinctifs
        x, y = int(rng.integers(20, W-20)), int(rng.integers(20, H-20))
        c = tuple(int(v) for v in rng.integers(80, 255, 3))
        s = int(rng.integers(3, 15))
        cv2.rectangle(A, (x-s, y-s), (x+s, y+s), c, -1)
        cv2.circle(A, (x, y), int(rng.integers(2, 8)), c, -1)
    M = cv2.getRotationMatrix2D((W/2, H/2), angle, echelle)  # rotation + échelle
    B = cv2.convertScaleAbs(cv2.warpAffine(A, M, (W, H)), alpha=1.0, beta=lumiere)  # + lumière
    return A, B

A, B = scene_paire()
gA, gB = cv2.cvtColor(A, cv2.COLOR_BGR2GRAY), cv2.cvtColor(B, cv2.COLOR_BGR2GRAY)

def ratio_filter(knn, tau=0.75):                            # ratio test de Lowe
    return [p[0] for p in knn if len(p) == 2 and p[0].distance < tau * p[1].distance]

# --- Voie 1 : descripteurs ORB + distance de Hamming ---
orb = cv2.ORB_create(1500)
k1, d1 = orb.detectAndCompute(gA, None)
k2, d2 = orb.detectAndCompute(gB, None)
bf = cv2.BFMatcher(cv2.NORM_HAMMING)                        # NORM_HAMMING : descripteurs binaires
bons_orb = ratio_filter(bf.knnMatch(d1, d2, k=2))

# --- Voie 2 : patchs 16x16 bruts comparés par SSD ---
def patch(g, kp, r=8):
    x, y = int(round(kp.pt[0])), int(round(kp.pt[1]))
    if x-r < 0 or y-r < 0 or x+r >= g.shape[1] or y+r >= g.shape[0]: return None
    return g[y-r:y+r, x-r:x+r].astype(np.float32)
P1 = [(i, patch(gA, kp)) for i, kp in enumerate(k1)]; P1 = [(i, p) for i, p in P1 if p is not None]
P2 = [(j, patch(gB, kp)) for j, kp in enumerate(k2)]; P2 = [(j, p) for j, p in P2 if p is not None]
ssd_bons = 0
for i, p in P1[:200]:
    d = sorted((float(np.mean((p - q)**2)), j) for j, q in P2)   # SSD vers tous les patchs de B
    if len(d) >= 2 and d[0][0] < 0.75 * d[1][0]:                 # même ratio test, sur le SSD
        ssd_bons += 1

print(f"Appariements ORB (descripteurs) : {len(bons_orb)}")
print(f"Appariements SSD (patchs bruts) : {ssd_bons}   <-- bien moins fiables")

vis = cv2.drawMatches(A, k1, B, k2, bons_orb[:40], None, flags=2)
plt.figure(figsize=(11, 4)); plt.imshow(vis[:, :, ::-1]); plt.axis("off")
plt.title("Observation 17.A — ORB retrouve les points que le SSD brut perd")
plt.tight_layout(); plt.savefig("obs_17A_descripteurs.png", dpi=120); plt.show()
```

**Missions**
1. Combien d'appariements ORB obtenez-vous, contre combien en SSD brut ? L'écart confirme-t-il que l'invariance se construit dans le descripteur ?
2. Augmentez progressivement `angle` (10, 30, 60, 90). À partir de quel angle ORB commence-t-il à perdre des appariements ? L'invariance n'est jamais parfaite.
3. Annulez la transformation (`angle=0, echelle=1, lumiere=0`). Le SSD brut redevient-il fiable ? Pourquoi ne l'est-il que dans ce cas dégénéré ?

---

### Observation 17.B — Le cercle qui suit le zoom

**Concept mis en jeu.** Un point-clé n'est pas qu'une position : il a une échelle caractéristique `σ`. Le rayon d'un blob est proportionnel à son `σ`, et zoomer l'image d'un facteur 2 double le `σ` détecté de chaque structure. C'est l'invariance d'échelle, rendue mesurable.

```python
import numpy as np, cv2, matplotlib.pyplot as plt
from skimage.feature import blob_dog

# --- Image synthétique : trois disques de rayons connus très différents ---
H, W = 300, 560
img = np.zeros((H, W), np.uint8)
rayons = [(120, 150, 6), (300, 150, 12), (460, 150, 18)]   # (x, y, rayon)
for x, y, r in rayons:
    cv2.circle(img, (x, y), r, 255, -1)

def detecte(g):
    # blob_dog (différence de gaussiennes) renvoie (y, x, sigma) : position ET échelle
    return blob_dog(g.astype(float) / 255.0, min_sigma=2, max_sigma=45,
                    sigma_ratio=1.4, threshold=0.03)

img2 = cv2.resize(img, None, fx=2, fy=2)                    # zoom x2
b1, b2 = detecte(img), detecte(img2)

def sigma_au_point(blobs, x, y, sc=1):                      # σ du blob le plus proche du centre
    d = [(abs(bx - x*sc) + abs(by - y*sc), bs) for by, bx, bs in blobs]
    return min(d)[1] if d else None

print("rayon | σ (x1) | σ (x2) | rapport | σ / rayon")
for x, y, r in rayons:
    s1, s2 = sigma_au_point(b1, x, y, 1), sigma_au_point(b2, x, y, 2)
    print(f"  {r:2d}  | {s1:5.1f} | {s2:5.1f} |  {s2/s1:.2f}  |  {s1/r:.2f}")
# Constat : σ/rayon ≈ constant (σ ∝ taille) et rapport x2 ≈ 2.0 (σ suit le zoom)

fig, ax = plt.subplots(1, 2, figsize=(11, 4))
for a, im, blobs, t in [(ax[0], img, b1, "original"), (ax[1], img2, b2, "zoom x2")]:
    a.imshow(im, cmap="gray")
    for by, bx, bs in blobs:
        a.add_patch(plt.Circle((bx, by), bs*np.sqrt(2), color="red", fill=False, lw=1.5))
    a.set_title(f"{t} — cercle ∝ σ"); a.axis("off")
plt.suptitle("Observation 17.B — l'échelle caractéristique suit l'agrandissement")
plt.tight_layout(); plt.savefig("obs_17B_echelle.png", dpi=120); plt.show()
```

**Missions**
1. La colonne `σ / rayon` est-elle à peu près constante d'un disque à l'autre ? C'est la proportionnalité entre rayon et échelle caractéristique.
2. La colonne `rapport` est-elle proche de 2 pour les trois disques ? Pourquoi un zoom ×2 doit-il doubler le `σ` détecté ?
3. Cas d'opérateur : vos objets apparaissent à des distances variables (caméra mobile, zoom). Pourquoi un détecteur **sans** espace d'échelle (Harris nu, §6.5) ne pourrait-il pas les apparier d'une prise à l'autre ?

---

### Observation 17.C — HOG : insensible à la lumière, sensible à la rotation

**Concept mis en jeu.** HOG décrit la distribution locale des orientations de bord. Le passage au gradient puis la normalisation par bloc le rendent quasi insensible à l'éclairage. Mais une rotation de l'image fait tourner toutes les orientations : HOG n'est pas invariant en rotation.

```python
import numpy as np, cv2, matplotlib.pyplot as plt
from skimage.feature import hog

# --- Scène synthétique (remplaçable par votre image : silhouette, pièce mécanique) ---
rng = np.random.default_rng(0); H, W = 360, 480
A = np.full((H, W, 3), 30, np.uint8)
for _ in range(90):
    x, y = int(rng.integers(20, W-20)), int(rng.integers(20, H-20))
    cv2.rectangle(A, (x, y), (x+int(rng.integers(8, 30)), y+int(rng.integers(8, 30))),
                  tuple(int(v) for v in rng.integers(80, 255, 3)), -1)

clair  = cv2.convertScaleAbs(A, alpha=1.0, beta=60)                      # + lumière
tourne = cv2.warpAffine(A, cv2.getRotationMatrix2D((W/2, H/2), 20, 1), (W, H))  # + rotation 20°

def hog_vis(img):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, hi = hog(g, orientations=9, pixels_per_cell=(16, 16),
                cells_per_block=(2, 2), visualize=True, block_norm="L2-Hys")
    return hi

h0, hc, ht = hog_vis(A), hog_vis(clair), hog_vis(tourne)
corr = lambda a, b: float(np.corrcoef(a.ravel(), b.ravel())[0, 1])
print(f"Corrélation HOG original / +lumière : {corr(h0, hc):.3f}   (proche de 1 = stable)")
print(f"Corrélation HOG original / +rotation: {corr(h0, ht):.3f}   (faible = HOG a changé)")

fig, ax = plt.subplots(1, 3, figsize=(13, 4))
for a, im, t in zip(ax, [h0, hc, ht], ["original", "+lumière", "+rotation 20°"]):
    a.imshow(im, cmap="gray"); a.set_title("HOG " + t); a.axis("off")
plt.suptitle("Observation 17.C — HOG : stable en éclairage, instable en rotation")
plt.tight_layout(); plt.savefig("obs_17C_hog.png", dpi=120); plt.show()
```

**Missions**
1. La corrélation HOG sous changement d'éclairage est-elle proche de 1 ? Pourquoi le gradient puis la normalisation rendent-ils HOG aveugle à la lumière ?
2. La corrélation sous rotation est-elle nettement plus faible ? Faites varier l'angle (5°, 20°, 45°) : à partir de quand le glyphe devient-il méconnaissable ?
3. Réflexe : pour quels cas HOG convient-il (piétons debout, caractères d'orientation connue) et quand faut-il lui préférer SIFT (objets d'orientation quelconque) ?

---

### Observation 17.D — Les flèches qui tournent avec la scène

**Concept mis en jeu.** SIFT mesure d'abord l'orientation dominante d'un point-clé, puis décrit ses gradients dans ce repère tourné. Une rotation de l'image fait tourner les flèches d'orientation avec la structure, si bien que le descripteur ne change pas et que les appariements survivent.

```python
import numpy as np, cv2, matplotlib.pyplot as plt

def scene_paire(seed=0, angle=45, echelle=1.0, lumiere=20):     # (cf. 17.A)
    rng = np.random.default_rng(seed); H, W = 360, 480
    A = np.full((H, W, 3), 30, np.uint8)
    for _ in range(120):
        x, y = int(rng.integers(20, W-20)), int(rng.integers(20, H-20))
        c = tuple(int(v) for v in rng.integers(80, 255, 3)); s = int(rng.integers(3, 15))
        cv2.rectangle(A, (x-s, y-s), (x+s, y+s), c, -1)
        cv2.circle(A, (x, y), int(rng.integers(2, 8)), c, -1)
    M = cv2.getRotationMatrix2D((W/2, H/2), angle, echelle)
    return A, cv2.convertScaleAbs(cv2.warpAffine(A, M, (W, H)), alpha=1.0, beta=lumiere)

A, B = scene_paire(angle=45)
gA, gB = cv2.cvtColor(A, cv2.COLOR_BGR2GRAY), cv2.cvtColor(B, cv2.COLOR_BGR2GRAY)

sift = cv2.SIFT_create()
k1, d1 = sift.detectAndCompute(gA, None)
k2, d2 = sift.detectAndCompute(gB, None)
bf = cv2.BFMatcher(cv2.NORM_L2)                                 # NORM_L2 : descripteurs réels
bons = [p[0] for p in bf.knnMatch(d1, d2, k=2) if len(p) == 2 and p[0].distance < 0.75 * p[1].distance]
print(f"Appariements SIFT corrects après rotation de 45° : {len(bons)}")

# DRAW_RICH_KEYPOINTS dessine, pour chaque point, le cercle d'échelle ET la flèche d'orientation
visA = cv2.drawKeypoints(A, k1, None, flags=cv2.DRAW_MATCHES_FLAGS_DRAW_RICH_KEYPOINTS)
visB = cv2.drawKeypoints(B, k2, None, flags=cv2.DRAW_MATCHES_FLAGS_DRAW_RICH_KEYPOINTS)
fig, ax = plt.subplots(1, 2, figsize=(11, 4))
ax[0].imshow(visA[:, :, ::-1]); ax[0].set_title("vue droite — orientations"); ax[0].axis("off")
ax[1].imshow(visB[:, :, ::-1]); ax[1].set_title("vue tournée 45° — orientations"); ax[1].axis("off")
plt.suptitle("Observation 17.D — l'orientation dominante absorbe la rotation")
plt.tight_layout(); plt.savefig("obs_17D_orientation.png", dpi=120); plt.show()
```

**Missions**
1. Pour un même coin, l'écart entre la flèche d'orientation sur les deux vues correspond-il à la rotation appliquée (45°) ?
2. Faites varier `angle` (0, 45, 90) et relevez le nombre de bons appariements. La chute est-elle douce (SIFT robuste) ou brutale ?
3. Comparez à l'Observation 17.C : combien d'appariements HOG survivraient à 45° ? L'étape d'orientation est ce qui sépare SIFT de HOG.

---

### Observation 17.E — ORB ou SIFT : mesurer le compromis sur son cas

**Concept mis en jeu.** ORB échange du pouvoir de distinction et de la robustesse contre de la vitesse. Le bon choix n'est pas un théorème : c'est un compromis qui se mesure sur ses propres images, en nombre d'appariements d'un côté et en temps de calcul de l'autre.

```python
import numpy as np, cv2, time

def scene_paire(seed=0, angle=30, echelle=1.2, lumiere=40):    # (cf. 17.A)
    rng = np.random.default_rng(seed); H, W = 360, 480
    A = np.full((H, W, 3), 30, np.uint8)
    for _ in range(120):
        x, y = int(rng.integers(20, W-20)), int(rng.integers(20, H-20))
        c = tuple(int(v) for v in rng.integers(80, 255, 3)); s = int(rng.integers(3, 15))
        cv2.rectangle(A, (x-s, y-s), (x+s, y+s), c, -1); cv2.circle(A, (x, y), int(rng.integers(2, 8)), c, -1)
    M = cv2.getRotationMatrix2D((W/2, H/2), angle, echelle)
    return A, cv2.convertScaleAbs(cv2.warpAffine(A, M, (W, H)), alpha=1.0, beta=lumiere)

A, B = scene_paire()
gA, gB = cv2.cvtColor(A, cv2.COLOR_BGR2GRAY), cv2.cvtColor(B, cv2.COLOR_BGR2GRAY)

def chrono(detecteur, norm):
    t = time.perf_counter()
    a1, b1 = detecteur.detectAndCompute(gA, None)
    a2, b2 = detecteur.detectAndCompute(gB, None)
    knn = cv2.BFMatcher(norm).knnMatch(b1, b2, k=2)
    bons = [p[0] for p in knn if len(p) == 2 and p[0].distance < 0.75 * p[1].distance]
    return len(bons), (time.perf_counter() - t) * 1000

n_orb,  t_orb  = chrono(cv2.ORB_create(1500), cv2.NORM_HAMMING)
n_sift, t_sift = chrono(cv2.SIFT_create(),    cv2.NORM_L2)
print(f"ORB  : {n_orb:4d} bons appariements en {t_orb:6.1f} ms")
print(f"SIFT : {n_sift:4d} bons appariements en {t_sift:6.1f} ms")
print(f"-> SIFT ~ x{t_sift/max(t_orb,1e-3):.1f} plus lent (l'ordre de grandeur varie selon la machine)")
```

**Missions**
1. Relevez, pour ORB et SIFT, le nombre d'appariements et le temps. Quel rapport de vitesse observez-vous (souvent un ordre de grandeur) ?
2. Dégradez la paire : ajoutez du bruit (`cv2.randn`) ou un fort changement de point de vue (`cv2.warpPerspective`). Lequel résiste le mieux ?
3. Décision : pour du temps réel à 30 fps (≈ 33 ms par image), ORB tient-il le budget ? Pour un recalage hors ligne où seule la qualité compte, SIFT apporte-t-il assez d'appariements pour justifier son coût ?

---

### Observation 17.F — Le curseur du ratio test : du désordre aux lignes parallèles

**Concept mis en jeu.** Le ratio test mesure la distinctivité d'un appariement. Serrer le seuil `τ` élimine les appariements ambigus (lignes qui se croisent en désordre). Sur une scène à texture répétée, chaque point a des jumeaux : même un `τ` standard affame l'appariement.

```python
import numpy as np, cv2, matplotlib.pyplot as plt

def scene(motif="texture", seed=0, angle=20):
    rng = np.random.default_rng(seed); H, W = 360, 480
    A = np.full((H, W, 3), 30, np.uint8)
    if motif == "texture":                                     # motifs distinctifs -> appariement facile
        for _ in range(120):
            x, y = int(rng.integers(20, W-20)), int(rng.integers(20, H-20))
            c = tuple(int(v) for v in rng.integers(80, 255, 3)); s = int(rng.integers(3, 15))
            cv2.rectangle(A, (x-s, y-s), (x+s, y+s), c, -1)
    else:                                                      # grille répétée -> points non distinctifs
        for y in range(40, H-20, 40):
            for x in range(40, W-20, 40):
                cv2.rectangle(A, (x-12, y-12), (x+12, y+12), (200, 200, 200), -1)
    M = cv2.getRotationMatrix2D((W/2, H/2), angle, 1.0)
    return A, cv2.warpAffine(A, M, (W, H))

MOTIF = "texture"           # <-- passez à "repetitif" pour la scène piège
A, B = scene(MOTIF)
gA, gB = cv2.cvtColor(A, cv2.COLOR_BGR2GRAY), cv2.cvtColor(B, cv2.COLOR_BGR2GRAY)
orb = cv2.ORB_create(1500)
k1, d1 = orb.detectAndCompute(gA, None); k2, d2 = orb.detectAndCompute(gB, None)
knn = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(d1, d2, k=2)

fig, ax = plt.subplots(1, 3, figsize=(14, 3))
for a, tau in zip(ax, [0.95, 0.80, 0.60]):                     # le "curseur" du ratio test
    bons = [p[0] for p in knn if len(p) == 2 and p[0].distance < tau * p[1].distance]
    print(f"motif={MOTIF}  τ={tau:.2f} : {len(bons)} appariements")
    v = cv2.drawMatches(A, k1, B, k2, bons[:60], None, flags=2)
    a.imshow(v[:, :, ::-1]); a.axis("off"); a.set_title(f"τ = {tau} ({len(bons)})")
plt.suptitle(f"Observation 17.F — ratio test, scène '{MOTIF}'")
plt.tight_layout(); plt.savefig(f"obs_17F_ratio_{MOTIF}.png", dpi=120); plt.show()
```

**Missions**
1. Sur la scène `texture`, à quelle valeur de `τ` les lignes qui se croisent disparaissent-elles ? Combien d'appariements reste-t-il à `τ = 0,8` ?
2. Passez `MOTIF` à `"repetitif"`. Pourquoi le ratio test rejette-t-il presque tout, même à `τ = 0,8` ? Que faut-il faire à la place (s'appuyer sur la cohérence géométrique, Observation 17.G) ?
3. Réflexe : devant un nuage de lignes incohérentes, le premier geste est de serrer `τ`. Devant une scène répétitive, le ratio ne suffira pas — il faut un modèle géométrique.

---

### Observation 17.G — Voir le panorama se former (et l'inverse sans RANSAC)

**Concept mis en jeu.** Même après le ratio test, des aberrants subsistent. RANSAC cherche le plus grand sous-ensemble d'appariements cohérents avec une même homographie, marque le reste comme aberrant, et fournit la transformation qui aligne les deux images. Estimée sur tous les appariements (sans RANSAC), l'homographie dérive.

```python
import numpy as np, cv2, matplotlib.pyplot as plt

def scene_paire(seed=0, angle=25, echelle=1.1, lumiere=30):    # (cf. 17.A)
    rng = np.random.default_rng(seed); H, W = 360, 480
    A = np.full((H, W, 3), 30, np.uint8)
    for _ in range(120):
        x, y = int(rng.integers(20, W-20)), int(rng.integers(20, H-20))
        c = tuple(int(v) for v in rng.integers(80, 255, 3)); s = int(rng.integers(3, 15))
        cv2.rectangle(A, (x-s, y-s), (x+s, y+s), c, -1); cv2.circle(A, (x, y), int(rng.integers(2, 8)), c, -1)
    M = cv2.getRotationMatrix2D((W/2, H/2), angle, echelle)
    return A, cv2.convertScaleAbs(cv2.warpAffine(A, M, (W, H)), alpha=1.0, beta=lumiere)

A, B = scene_paire()
gA, gB = cv2.cvtColor(A, cv2.COLOR_BGR2GRAY), cv2.cvtColor(B, cv2.COLOR_BGR2GRAY)
sift = cv2.SIFT_create()
k1, d1 = sift.detectAndCompute(gA, None); k2, d2 = sift.detectAndCompute(gB, None)
knn = cv2.BFMatcher(cv2.NORM_L2).knnMatch(d1, d2, k=2)
bons = [p[0] for p in knn if len(p) == 2 and p[0].distance < 0.75 * p[1].distance]

# coordonnées des vrais appariements (pour mesurer l'erreur), + injection de faux pour voir l'effet de RANSAC
pts1 = np.float32([k1[m.queryIdx].pt for m in bons]).reshape(-1, 1, 2)
pts2 = np.float32([k2[m.trainIdx].pt for m in bons]).reshape(-1, 1, 2)
rng = np.random.default_rng(1)
faux = [cv2.DMatch(m.queryIdx, int(rng.integers(len(k2))), 0) for m in bons[:60]]   # appariements aberrants
tous = bons + faux
p1 = np.float32([k1[m.queryIdx].pt for m in tous]).reshape(-1, 1, 2)
p2 = np.float32([k2[m.trainIdx].pt for m in tous]).reshape(-1, 1, 2)

H_ransac, mask = cv2.findHomography(p1, p2, cv2.RANSAC, 3.0)    # robuste : 4 points + consensus
H_tous,   _    = cv2.findHomography(p1, p2, 0)                  # moindres carrés sur TOUT (sans RANSAC)
err = lambda Hh: float(np.mean(np.linalg.norm(
        (cv2.perspectiveTransform(pts1, Hh) - pts2).reshape(-1, 2), axis=1)))
print(f"inliers RANSAC : {int(mask.sum())} / {len(tous)}")
print(f"erreur de reprojection  RANSAC : {err(H_ransac):4.1f} px")
print(f"erreur de reprojection  sans RANSAC : {err(H_tous):4.0f} px   <-- l'homographie a dérivé")

vis = cv2.drawMatches(A, k1, B, k2, tous, None, matchesMask=mask.ravel().tolist(),
                      matchColor=(0, 255, 0), singlePointColor=(0, 0, 255), flags=2)  # verts=inliers
overlay = cv2.addWeighted(cv2.warpPerspective(A, H_ransac, (480, 360)), 0.5, B, 0.5, 0)
fig, ax = plt.subplots(1, 2, figsize=(12, 4))
ax[0].imshow(vis[:, :, ::-1]); ax[0].set_title(f"inliers verts ({int(mask.sum())}) / outliers rouges"); ax[0].axis("off")
ax[1].imshow(overlay[:, :, ::-1]); ax[1].set_title("A recalée sur B (homographie RANSAC)"); ax[1].axis("off")
plt.suptitle("Observation 17.G — RANSAC : tri des aberrants et alignement")
plt.tight_layout(); plt.savefig("obs_17G_ransac.png", dpi=120); plt.show()
```

**Missions**
1. Combien d'inliers RANSAC retient-il, et les lignes vertes sont-elles cohérentes ? Comparez l'erreur de reprojection avec et sans RANSAC.
2. Dans l'overlay, les zones communes des deux images se recouvrent-elles ? C'est le panorama en train de se former.
3. Cas d'opérateur : modifiez la scène pour qu'elle contienne deux plans de mouvements différents. Une seule homographie ne peut pas tout aligner — quels appariements RANSAC déclare-t-il inliers, et pourquoi faut-il alors l'appliquer en séquence, un plan à la fois ?
