# Annexe — Scripts d'observation : exercices autonomes en Python

Les chapitres 9, 10, 12 et 15 proposaient des exercices d'observation conçus pour l'environnement VNStudio. Cette annexe les reformule en scripts Python autonomes, exécutables directement depuis un terminal ou un notebook Jupyter, sans aucune dépendance à un outil tiers.

Chaque script est autocontenu : il génère ses propres données synthétiques ou précise quelle image charger, effectue le calcul, et produit une figure commentée. Les missions pédagogiques sont conservées telles quelles — seul le vecteur d'exécution change.

**Bibliothèques requises :** `numpy`, `opencv-python` (`cv2`), `scipy`, `scikit-image`, `matplotlib`. Toutes sont installables via `pip install numpy opencv-python scipy scikit-image matplotlib`.

---

## Chapitre 9 — Flot optique et mouvement

### Observation 9.A — La contrainte OFCE : une équation pour deux inconnues

**Concept mis en jeu.** L'équation de flot optique contraint le vecteur (u, v) dans une seule direction : perpendiculairement au contour. La composante parallèle au contour reste libre. Sur une barre verticale, la composante horizontale est mesurable ; la composante verticale est invisible aux données.

```python
import numpy as np
import cv2
import matplotlib.pyplot as plt

# --- Génération des deux frames synthétiques ---
# Une barre verticale et une barre horizontale se déplacent
# toutes deux en diagonale : déplacement réel = (+3 px, +2 px).

H, W = 128, 128
DEPLACEMENT_REEL = (3, 2)   # (dx, dy) en pixels

def make_frame(barre_v_x, barre_h_y):
    """Crée une frame avec une barre verticale et une barre horizontale."""
    img = np.zeros((H, W), dtype=np.uint8)
    img[:, barre_v_x : barre_v_x + 10] = 220   # barre verticale
    img[barre_h_y : barre_h_y + 10, :] = 180   # barre horizontale
    return img

frame1 = make_frame(barre_v_x=30, barre_h_y=60)
frame2 = make_frame(barre_v_x=30 + DEPLACEMENT_REEL[0],
                    barre_h_y=60 + DEPLACEMENT_REEL[1])

# --- Points à suivre : milieu de la barre verticale et d'un coin ---
pts_milieu_v = np.array([[35.0, 64.0]], dtype=np.float32).reshape(-1, 1, 2)  # (x, y)
pts_coin     = np.array([[35.0, 60.0]], dtype=np.float32).reshape(-1, 1, 2)  # coin barre V/H

pts_suivis_v, st_v, _ = cv2.calcOpticalFlowPyrLK(
    frame1, frame2, pts_milieu_v, None,
    winSize=(21, 21), maxLevel=0    # maxLevel=0 : pas de pyramide
)
pts_suivis_c, st_c, _ = cv2.calcOpticalFlowPyrLK(
    frame1, frame2, pts_coin, None,
    winSize=(21, 21), maxLevel=0
)

dx_v = pts_suivis_v[0, 0, 0] - pts_milieu_v[0, 0, 0]
dy_v = pts_suivis_v[0, 0, 1] - pts_milieu_v[0, 0, 1]
dx_c = pts_suivis_c[0, 0, 0] - pts_coin[0, 0, 0]
dy_c = pts_suivis_c[0, 0, 1] - pts_coin[0, 0, 1]

print(f"Déplacement réel        : dx={DEPLACEMENT_REEL[0]}, dy={DEPLACEMENT_REEL[1]}")
print(f"Milieu barre verticale  : dx={dx_v:.2f}, dy={dy_v:.2f}")
print(f"  → composante ||au contour (dx) : fiable ?  {abs(dx_v - DEPLACEMENT_REEL[0]) < 0.5}")
print(f"  → composante ⊥au contour (dy)  : libre   (attendu {DEPLACEMENT_REEL[1]}, obtenu {dy_v:.2f})")
print(f"Coin (intersection)     : dx={dx_c:.2f}, dy={dy_c:.2f}")
print(f"  → les deux composantes fiables : {abs(dx_c - DEPLACEMENT_REEL[0]) < 0.8 and abs(dy_c - DEPLACEMENT_REEL[1]) < 0.8}")

fig, axes = plt.subplots(1, 2, figsize=(10, 4))
for ax, frame, titre in zip(axes, [frame1, frame2], ["Frame 1", "Frame 2"]):
    ax.imshow(frame, cmap="gray", vmin=0, vmax=255)
    ax.set_title(titre)
    ax.axis("off")
# Flèche sur la frame 2 : déplacement estimé au milieu de la barre
axes[1].annotate("", xy=(pts_suivis_v[0,0,0], pts_suivis_v[0,0,1]),
                 xytext=(pts_milieu_v[0,0,0], pts_milieu_v[0,0,1]),
                 arrowprops=dict(arrowstyle="->", color="red", lw=2))
axes[1].annotate("", xy=(pts_suivis_c[0,0,0], pts_suivis_c[0,0,1]),
                 xytext=(pts_coin[0,0,0], pts_coin[0,0,1]),
                 arrowprops=dict(arrowstyle="->", color="cyan", lw=2))
axes[1].legend(handles=[
    plt.Line2D([0],[0], color="red",  label="milieu barre (composante libre)"),
    plt.Line2D([0],[0], color="cyan", label="coin (vecteur complet)"),
])
plt.suptitle("Observation 9.A — Contrainte OFCE : composante libre vs. contrainte")
plt.tight_layout()
plt.savefig("obs_9A_ofce.png", dpi=120)
plt.show()
```

**Missions**
1. La composante `dx` au milieu de la barre verticale est-elle proche de la valeur réelle (+3 px) ? La composante `dy` l'est-elle ?
2. Comparez avec le coin : les deux composantes sont-elles correctement estimées ? Pourquoi le coin lève-t-il l'ambiguïté ?
3. Relancez le script en changeant `maxLevel=0` à `maxLevel=3`. Le résultat au milieu de la barre change-t-il ? Pourquoi la pyramide n'aide pas ici (le déplacement est déjà petit) ?

---

### Observation 9.B — Les trois zones du flot : coin, bord, plat

**Concept mis en jeu.** La carte des valeurs propres du tenseur de structure prédit, avant tout calcul de flot, où les vecteurs seront fiables (coins), orientés selon le contour (bords), ou purement bruités (zones plates).

```python
import numpy as np
import cv2
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

# --- Génération d'une image avec les trois types de zones ---
H, W = 200, 300
frame1 = np.ones((H, W), dtype=np.float32) * 40   # fond sombre (zone plate)
# Bord horizontal (bord du « bâtiment »)
frame1[80:160, :] = 180
# Fenêtres = coins
for col in [80, 140, 200, 260]:
    frame1[90:130, col:col+30] = 40

frame2 = np.roll(frame1, shift=5, axis=1).copy()   # panoramique de 5 px vers la droite
frame1_u8 = frame1.astype(np.uint8)
frame2_u8 = frame2.astype(np.uint8)

# --- Tenseur de structure : λ₂ (plus petite valeur propre) ---
Ix = cv2.Sobel(frame1_u8, cv2.CV_32F, 1, 0, ksize=3)
Iy = cv2.Sobel(frame1_u8, cv2.CV_32F, 0, 1, ksize=3)
sigma = 3.0
Ix2 = cv2.GaussianBlur(Ix * Ix, (0, 0), sigma)
Iy2 = cv2.GaussianBlur(Iy * Iy, (0, 0), sigma)
Ixy = cv2.GaussianBlur(Ix * Iy, (0, 0), sigma)

trace  = Ix2 + Iy2
det    = Ix2 * Iy2 - Ixy * Ixy
disc   = np.sqrt(np.maximum(0, (trace / 2) ** 2 - det))
lambda2 = trace / 2 - disc   # plus petite valeur propre

# --- Flot dense (Farneback) ---
flow = cv2.calcOpticalFlowFarneback(
    frame1_u8, frame2_u8, None,
    pyr_scale=0.5, levels=3, winsize=15,
    iterations=3, poly_n=5, poly_sigma=1.1, flags=0
)
mag, ang = cv2.cartToPolar(flow[..., 0], flow[..., 1])

# --- Figure ---
fig, axes = plt.subplots(1, 3, figsize=(14, 4))

axes[0].imshow(frame1_u8, cmap="gray")
axes[0].set_title("Frame 1")
axes[0].axis("off")

im1 = axes[1].imshow(lambda2, cmap="hot")
axes[1].set_title("Tenseur de structure (λ₂)\nrouge=coin, noir=plat")
axes[1].axis("off")
plt.colorbar(im1, ax=axes[1], fraction=0.046)

im2 = axes[2].imshow(mag, cmap="viridis")
axes[2].set_title("Magnitude du flot dense\n(Farneback)")
axes[2].axis("off")
plt.colorbar(im2, ax=axes[2], fraction=0.046)

plt.suptitle("Observation 9.B — Tenseur de structure prédit où le flot est fiable")
plt.tight_layout()
plt.savefig("obs_9B_trois_zones.png", dpi=120)
plt.show()

# Diagnostic quantitatif
coin_mask  = lambda2 > np.percentile(lambda2, 95)
plat_mask  = lambda2 < np.percentile(lambda2, 10)
print(f"Magnitude flot aux COINS  : {mag[coin_mask].mean():.2f} px (attendu ≈ 5)")
print(f"Magnitude flot zones PLATES: {mag[plat_mask].mean():.2f} px (attendu bruité ≈ aléatoire)")
```

**Missions**
1. Comparez la carte `λ₂` et la carte de magnitude du flot. Les zones rouges (coins) correspondent-elles aux zones où le flot est fort et cohérent ?
2. Dans les zones de fond uni (valeur sombre, λ₂ ≈ 0), la magnitude du flot est-elle nulle ou bruitée ? Pourquoi ?
3. Modifiez `sigma` de 3 à 10 dans le calcul du tenseur. La carte λ₂ devient-elle plus ou moins sélective ? Cela change-t-il le seuil de fiabilité du flot ?

---

### Observation 9.C — La pyramide : pourquoi les grands déplacements posent problème

**Concept mis en jeu.** Sans pyramide, Lucas-Kanade cherche la correspondance dans une fenêtre fixe. Si le déplacement réel dépasse la moitié de la fenêtre, le tracker perd le point. Chaque niveau de pyramide divise le déplacement apparent par 2.

```python
import numpy as np
import cv2
import matplotlib.pyplot as plt

H, W = 128, 128
DEPLACEMENTS = [2, 5, 10, 15, 20]   # en pixels

def make_frame_with_circle(cx, cy, r=8):
    img = np.zeros((H, W), dtype=np.uint8)
    cv2.circle(img, (cx, cy), r, 200, -1)
    return img

resultats = {"sans_pyramide": [], "avec_pyramide": []}

for dx in DEPLACEMENTS:
    f1 = make_frame_with_circle(W // 2, H // 2)
    f2 = make_frame_with_circle(W // 2 + dx, H // 2)

    p0 = np.array([[W / 2, H / 2]], dtype=np.float32).reshape(-1, 1, 2)

    for label, maxLevel in [("sans_pyramide", 0), ("avec_pyramide", 3)]:
        p1, st, _ = cv2.calcOpticalFlowPyrLK(
            f1, f2, p0, None, winSize=(21, 21), maxLevel=maxLevel,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01)
        )
        if st[0, 0] == 1:
            erreur = abs(p1[0, 0, 0] - (W / 2 + dx))
        else:
            erreur = float("nan")
        resultats[label].append(erreur)

# Affichage
fig, ax = plt.subplots(figsize=(8, 5))
ax.plot(DEPLACEMENTS, resultats["sans_pyramide"], "o-r", label="Sans pyramide (maxLevel=0)")
ax.plot(DEPLACEMENTS, resultats["avec_pyramide"],  "s-b", label="Avec pyramide (maxLevel=3)")
ax.axvline(21 / 2, linestyle="--", color="gray", label="Moitié de la fenêtre (10.5 px)")
ax.set_xlabel("Déplacement réel (px)")
ax.set_ylabel("Erreur d'estimation (px)")
ax.set_title("Observation 9.C — Erreur de Lucas-Kanade selon le déplacement\net le nombre de niveaux de pyramide")
ax.legend()
ax.grid(True)
plt.tight_layout()
plt.savefig("obs_9C_pyramide.png", dpi=120)
plt.show()

print("Déplacement | Erreur sans pyramide | Erreur avec pyramide")
for dx, e0, e3 in zip(DEPLACEMENTS, resultats["sans_pyramide"], resultats["avec_pyramide"]):
    print(f"   {dx:4d} px  |       {e0:6.2f} px      |      {e3:6.2f} px")
```

**Missions**
1. À partir de quel déplacement l'erreur sans pyramide explose-t-elle ? Ce seuil correspond-il à la moitié de la fenêtre (21/2 ≈ 10.5 px) comme le prédit la théorie ?
2. Avec la pyramide (maxLevel=3), le déplacement de 15 px est réduit à 15/8 ≈ 2 px au niveau le plus grossier. Ce chiffre est-il inférieur à la moitié de la fenêtre ? L'erreur est-elle bien inférieure ?
3. Calculez mentalement le nombre de niveaux nécessaires pour ramener un déplacement de 40 px sous la moitié de la fenêtre (fenêtre = 21 px). Vérifiez en modifiant `DEPLACEMENTS` et `maxLevel`.

---

### Observation 9.D — Horn-Schunck : α règle la conductivité thermique

**Concept mis en jeu.** Le paramètre de lissage α dans Horn-Schunck (et son équivalent `winsize` / `pyr_scale` dans Farneback) contrôle la diffusion du flot depuis les zones contraintes vers les zones plates. α grand → fond lisse mais bords flous ; α petit → fond bruité mais bords nets.

```python
import numpy as np
import cv2
import matplotlib.pyplot as plt

# --- Scène : objet texturé (grille) sur fond sombre ---
H, W = 256, 256

def make_scene(shift_x=4):
    """Frame avec une zone texturée centrale déplacée de shift_x pixels."""
    img = np.zeros((H, W), dtype=np.uint8)
    # Grille texturée
    for i in range(40, 180, 20):
        img[i:i+10, 40:220] = 180
        img[40:220, i:i+10] = 180
    return img

f1 = make_scene(0)
f2 = np.zeros_like(f1)
f2[4:, :] = f1[:H-4, :]   # décalage vertical de 4 px

configs = [
    ("α faible  (winsize=5)",  5, "Fond bruité, bords nets"),
    ("α moyen   (winsize=15)", 15, "Compromis"),
    ("α élevé   (winsize=35)", 35, "Fond lisse, bords flous"),
]

fig, axes = plt.subplots(2, 3, figsize=(14, 8))

for col, (label, winsize, commentaire) in enumerate(configs):
    flow = cv2.calcOpticalFlowFarneback(
        f1, f2, None,
        pyr_scale=0.5, levels=3, winsize=winsize,
        iterations=5, poly_n=5, poly_sigma=1.1, flags=0
    )
    # Visualisation HSV : teinte = direction, luminosité = magnitude
    mag, ang = cv2.cartToPolar(flow[..., 0], flow[..., 1])
    hsv = np.zeros((H, W, 3), dtype=np.uint8)
    hsv[..., 0] = ang * 180 / (2 * np.pi)
    hsv[..., 1] = 255
    hsv[..., 2] = cv2.normalize(mag, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    rgb = cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)

    # Métriques
    fond_mask   = f1 < 10   # pixels de fond (sombres)
    objet_mask  = f1 > 50   # pixels de l'objet texturé
    bruit_fond  = mag[fond_mask].std()
    mag_objet   = mag[objet_mask].mean()

    axes[0, col].imshow(rgb)
    axes[0, col].set_title(f"{label}\n{commentaire}")
    axes[0, col].axis("off")

    axes[1, col].hist(mag[fond_mask].ravel(),  bins=40, alpha=0.6, label="Fond (idéal : 0)")
    axes[1, col].hist(mag[objet_mask].ravel(), bins=40, alpha=0.6, label="Objet (idéal : 4)")
    axes[1, col].set_xlim(0, 12)
    axes[1, col].set_xlabel("Magnitude du flot (px)")
    axes[1, col].set_title(f"Bruit fond σ={bruit_fond:.2f} | Moy. objet={mag_objet:.2f}")
    axes[1, col].legend(fontsize=7)

plt.suptitle("Observation 9.D — Farneback : winsize règle la diffusion (α)")
plt.tight_layout()
plt.savefig("obs_9D_alpha.png", dpi=120)
plt.show()
```

**Missions**
1. Avec `winsize=5` : l'histogramme du fond montre-t-il une dispersion élevée (bruit) ? La magnitude moyenne sur l'objet est-elle proche de 4 px (déplacement réel) ?
2. Avec `winsize=35` : le bruit dans le fond diminue-t-il ? La magnitude sur l'objet reste-t-elle proche de 4 px, ou la diffusion depuis le fond nul tire-t-elle la valeur vers le bas ?
3. En contexte d'IRM cardiaque (mesure du déplacement du myocarde), quel critère utiliserait-on pour choisir α ? Formulez la réponse en termes de compromis bruit-fond / précision-bords.

---

### Observation 9.E — Épars vs. dense : voir ce que chaque approche couvre et manque

**Concept mis en jeu.** Le flot épars (Lucas-Kanade sur coins) ne produit des vecteurs que là où le gradient est riche. Le flot dense couvre toute l'image mais interpole dans les zones sans texture.

```python
import numpy as np
import cv2
import matplotlib.pyplot as plt

# --- Scène synthétique : « foule » de rectangles sur fond uni ---
H, W = 256, 256
rng = np.random.default_rng(42)

def make_crowd_frame(dx=0, dy=0):
    img = np.zeros((H, W), dtype=np.uint8) + 30  # fond sombre uniforme
    for _ in range(20):
        cx = int(rng.integers(20, W - 20))
        cy = int(rng.integers(20, H - 20))
        img[cy+dy:cy+dy+15, cx+dx:cx+dx+10] = int(rng.integers(150, 220))
    return img

rng_fixed = np.random.default_rng(42)  # même seed pour positions
def make_crowd_fixed(dx=0, dy=0):
    img = np.zeros((H, W), dtype=np.uint8) + 30
    for _ in range(20):
        cx = int(rng_fixed.integers(20, W - 20))
        cy = int(rng_fixed.integers(20, H - 20))
        img[cy+dy:cy+dy+15, cx+dx:cx+dx+10] = int(rng_fixed.integers(150, 220))
    return img

rng_fixed = np.random.default_rng(42)
f1 = make_crowd_fixed(dx=0, dy=0)
rng_fixed = np.random.default_rng(42)
f2 = make_crowd_fixed(dx=6, dy=0)   # déplacement horizontal de 6 px

# --- Flot épars ---
corners = cv2.goodFeaturesToTrack(f1, maxCorners=200, qualityLevel=0.01, minDistance=5)
if corners is not None:
    p1, st, _ = cv2.calcOpticalFlowPyrLK(f1, f2, corners, None,
                                          winSize=(15, 15), maxLevel=2)
    bons = st.ravel() == 1
    pts_from = corners[bons].reshape(-1, 2)
    pts_to   = p1[bons].reshape(-1, 2)

# --- Flot dense ---
flow_dense = cv2.calcOpticalFlowFarneback(
    f1, f2, None, 0.5, 3, 15, 3, 5, 1.1, 0
)
mag_dense, _ = cv2.cartToPolar(flow_dense[..., 0], flow_dense[..., 1])

# --- Figure ---
fig, axes = plt.subplots(1, 3, figsize=(15, 5))

axes[0].imshow(f1, cmap="gray")
if corners is not None:
    for (x0, y0), (x1, y1) in zip(pts_from, pts_to):
        axes[0].annotate("", xy=(x1, y1), xytext=(x0, y0),
                         arrowprops=dict(arrowstyle="->", color="red", lw=0.8))
axes[0].set_title(f"Flot ÉPARS\n{bons.sum()} vecteurs (coins seulement)")
axes[0].axis("off")

im = axes[1].imshow(mag_dense, cmap="hot", vmin=0, vmax=10)
axes[1].set_title("Magnitude flot DENSE\n(Farneback)")
axes[1].axis("off")
plt.colorbar(im, ax=axes[1], fraction=0.046)

# Comparaison : fond vs. objets
fond_mask = f1 < 40
axes[2].hist(mag_dense[fond_mask].ravel(),   bins=40, alpha=0.7, label="Fond (devrait = 0)")
axes[2].hist(mag_dense[~fond_mask].ravel(),  bins=40, alpha=0.7, label="Objets (devrait ≈ 6)")
axes[2].axvline(6, color="k", linestyle="--", label="Déplacement réel (6 px)")
axes[2].set_xlabel("Magnitude (px)")
axes[2].set_title("Distribution de la magnitude\ndense selon la zone")
axes[2].legend(fontsize=8)

plt.suptitle("Observation 9.E — Flot épars vs. dense : couverture et zones manquées")
plt.tight_layout()
plt.savefig("obs_9E_epars_dense.png", dpi=120)
plt.show()

print(f"Vecteurs épars : {bons.sum()} points suivis (sur {len(corners)} coins)")
fond_bruite = mag_dense[fond_mask].mean()
print(f"Flot dense — fond : magnitude moyenne {fond_bruite:.2f} px (idéal : 0)")
print(f"Flot dense — objets : magnitude moyenne {mag_dense[~fond_mask].mean():.2f} px (idéal : 6)")
```

**Missions**
1. Le flot épars produit-il des vecteurs dans les zones de fond uniforme ? Pourquoi `goodFeaturesToTrack` n'y place-t-il aucun coin ?
2. Dans la carte du flot dense, les zones de fond montrent-elles une magnitude nulle ou non nulle ? Cette valeur est-elle cohérente avec le déplacement réel (6 px) ?
3. Pour une tâche de comptage de flux (combien d'objets franchissent une ligne par seconde), lequel des deux champs utiliseriez-vous et pourquoi ?

---

## Chapitre 10 — Transformées

### Observation 10.A — La DFT : pics du spectre et orientation des rayures

**Concept mis en jeu.** Les pics dans le spectre de Fourier d'une image rayée apparaissent sur l'axe perpendiculaire à la direction des rayures. Leur distance au centre est l'inverse de la période spatiale.

```python
import numpy as np
import matplotlib.pyplot as plt

N = 256          # taille de l'image carrée
periode = 16     # espacement des rayures en pixels

# Rayures horizontales
img_h = np.zeros((N, N), dtype=np.float32)
for row in range(0, N, periode):
    img_h[row:row + periode // 2, :] = 1.0

# Rayures verticales
img_v = img_h.T.copy()

# Rayures diagonales (45°)
img_d = np.zeros((N, N), dtype=np.float32)
for i in range(N):
    for d in range(0, N, periode):
        if (i + d) % N < periode // 2:
            img_d[i, d:d+1] = 1.0  # approximation
# Alternative plus propre :
coords = np.indices((N, N))
img_d = ((coords[0] + coords[1]) % periode < periode // 2).astype(np.float32)

def compute_spectrum(img):
    F = np.fft.fft2(img)
    Fshift = np.fft.fftshift(F)
    mag = np.log1p(np.abs(Fshift))
    mag[N//2, N//2] = 0   # supprimer la composante DC
    return mag

spec_h = compute_spectrum(img_h)
spec_v = compute_spectrum(img_v)
spec_d = compute_spectrum(img_d)

fig, axes = plt.subplots(2, 3, figsize=(14, 9))

for col, (img, spec, titre) in enumerate([
    (img_h, spec_h, "Rayures horizontales"),
    (img_v, spec_v, "Rayures verticales"),
    (img_d, spec_d, "Rayures diagonales (45°)"),
]):
    axes[0, col].imshow(img[:64, :64], cmap="gray")
    axes[0, col].set_title(titre)
    axes[0, col].axis("off")

    axes[1, col].imshow(spec, cmap="inferno")
    # Marquer le pic attendu
    freq = N / periode
    if col == 0:   # horizontal → pic sur axe vertical
        axes[1, col].plot(N//2, N//2 - freq, "cx", ms=10, mew=2, label=f"pic attendu (0, ±{freq:.0f})")
        axes[1, col].plot(N//2, N//2 + freq, "cx", ms=10, mew=2)
    elif col == 1:  # vertical → pic sur axe horizontal
        axes[1, col].plot(N//2 - freq, N//2, "cx", ms=10, mew=2, label=f"pic attendu (±{freq:.0f}, 0)")
        axes[1, col].plot(N//2 + freq, N//2, "cx", ms=10, mew=2)
    else:           # diagonal → pic sur diagonale
        axes[1, col].plot(N//2 + freq/np.sqrt(2), N//2 - freq/np.sqrt(2), "cx", ms=10, mew=2)
    axes[1, col].set_title(f"Spectre (log amplitude)")
    axes[1, col].legend(fontsize=7)
    axes[1, col].axis("off")

plt.suptitle("Observation 10.A — Position des pics du spectre selon l'orientation des rayures")
plt.tight_layout()
plt.savefig("obs_10A_fft_pics.png", dpi=120)
plt.show()

print(f"Période des rayures : {periode} px → fréquence fondamentale : {N/periode:.1f} cycles/image")
print(f"Rayures horizontales : pics attendus en (col={N//2}, row={N//2 - N//periode}) et symétrique")
print(f"Rayures verticales   : pics attendus en (col={N//2 - N//periode}, row={N//2}) et symétrique")
```

**Missions**
1. Les pics du spectre des rayures horizontales apparaissent-ils sur l'axe vertical ou horizontal ? Est-ce bien l'axe perpendiculaire aux rayures ?
2. La distance des pics au centre vaut `N / période = 256 / 16 = 16`. Vérifiez visuellement sur la figure. Si vous réduisez la période à 8 px (rayures plus serrées), où se déplacent les pics ?
3. Que prédit la figure pour les rayures diagonales ? Tracez mentalement la position des pics avant de regarder la figure pour les rayures à 45°.

---

### Observation 10.B — La phase porte la structure : échange de modules

**Concept mis en jeu.** Reconstruire une image en échangeant les modules de deux spectres mais en conservant les phases montre que c'est la phase, et non le module, qui encode la structure spatiale visible.

```python
import numpy as np
import matplotlib.pyplot as plt
from skimage import data
from skimage.transform import resize

# Deux images très différentes
img_a = resize(data.camera(), (256, 256), anti_aliasing=True)   # portrait
img_b_raw = np.zeros((256, 256))
for i in range(0, 256, 16):
    img_b_raw[i:i+8, :] = 1.0
    img_b_raw[:, i:i+8] = np.maximum(img_b_raw[:, i:i+8], 0.5)
img_b = img_b_raw   # damier

# Transformées
Fa = np.fft.fft2(img_a)
Fb = np.fft.fft2(img_b)

module_a, phase_a = np.abs(Fa), np.angle(Fa)
module_b, phase_b = np.abs(Fb), np.angle(Fb)

# Reconstruction croisée
recon_phase_a_module_b = np.fft.ifft2(module_b * np.exp(1j * phase_a)).real
recon_phase_b_module_a = np.fft.ifft2(module_a * np.exp(1j * phase_b)).real

# Normalisation pour l'affichage
def norm(x):
    return (x - x.min()) / (x.max() - x.min() + 1e-9)

fig, axes = plt.subplots(2, 3, figsize=(14, 9))
images = [img_a, img_b, recon_phase_a_module_b, recon_phase_b_module_a]
titres = [
    "Image A (portrait)",
    "Image B (grille)",
    "Phase de A + Module de B\n→ ressemble à A ?",
    "Phase de B + Module de A\n→ ressemble à B ?",
]
positions = [(0,0),(0,1),(0,2),(1,0)]

for (r,c), img, titre in zip(positions, images, titres):
    axes[r,c].imshow(norm(img), cmap="gray")
    axes[r,c].set_title(titre, fontsize=9)
    axes[r,c].axis("off")

axes[1,1].axis("off")
axes[1,2].axis("off")

# Corrélation de structure
from scipy.stats import pearsonr
r_a, _ = pearsonr(img_a.ravel(), norm(recon_phase_a_module_b).ravel())
r_b, _ = pearsonr(img_b.ravel(), norm(recon_phase_b_module_a).ravel())
print(f"Corrélation structure A vs (phase A + module B) : r = {r_a:.3f}")
print(f"Corrélation structure B vs (phase B + module A) : r = {r_b:.3f}")

plt.suptitle("Observation 10.B — Échange de modules : la phase encode la structure")
plt.tight_layout()
plt.savefig("obs_10B_echange_phase.png", dpi=120)
plt.show()
```

**Missions**
1. L'image reconstruite avec la phase de A (portrait) et le module de B (grille) ressemble-t-elle davantage à A ou à B ? La corrélation `r_a` est-elle élevée ?
2. L'image reconstruite avec la phase de B et le module de A ressemble-t-elle à la grille ? Pourquoi reconnaît-on la structure de B malgré les niveaux d'intensité de A ?
3. En recalage d'images par corrélation de phase, on compare `exp(i·phase_A)` et `exp(i·phase_B)` plutôt que les spectres complets. Pourquoi cette approche est-elle plus robuste aux variations d'éclairage (changement de module) ?

---

### Observation 10.C — Le théorème de convolution : deux chemins, même résultat

**Concept mis en jeu.** Convoluer une image avec un filtre gaussien dans l'espace (chemin A) ou multiplier son spectre par la DFT du gaussien puis appliquer la FFT inverse (chemin B) produisent exactement le même résultat.

```python
import numpy as np
import cv2
import matplotlib.pyplot as plt
from skimage import data
from skimage.transform import resize

img = resize(data.camera(), (256, 256), anti_aliasing=True)
img_u8 = (img * 255).astype(np.uint8)

sigma = 3.0

# Chemin A : convolution spatiale directe
blur_a = cv2.GaussianBlur(img_u8, (0, 0), sigma).astype(np.float32) / 255.0

# Chemin B : multiplication fréquentielle
N = 256
# Noyau gaussien, même taille que l'image
ky, kx = np.mgrid[-N//2:N//2, -N//2:N//2]
kernel = np.exp(-(kx**2 + ky**2) / (2 * sigma**2))
kernel /= kernel.sum()

F_img    = np.fft.fft2(img)
F_kernel = np.fft.fft2(np.fft.ifftshift(kernel))   # centrage correct
F_produit = F_img * F_kernel
blur_b = np.abs(np.fft.ifft2(F_produit))

# Erreur entre les deux chemins
erreur = np.abs(blur_a - blur_b)

fig, axes = plt.subplots(1, 4, figsize=(16, 4))
axes[0].imshow(img,    cmap="gray")            ; axes[0].set_title("Image originale") ; axes[0].axis("off")
axes[1].imshow(blur_a, cmap="gray")            ; axes[1].set_title("Chemin A\n(GaussianBlur spatial)") ; axes[1].axis("off")
axes[2].imshow(blur_b, cmap="gray")            ; axes[2].set_title("Chemin B\n(mult. fréquentielle)") ; axes[2].axis("off")
im = axes[3].imshow(erreur * 255, cmap="hot") ; axes[3].set_title(f"Erreur × 255\n(max = {erreur.max()*255:.2f} niveaux)") ; axes[3].axis("off")
plt.colorbar(im, ax=axes[3], fraction=0.046)
plt.suptitle("Observation 10.C — Théorème de convolution : deux chemins, même résultat")
plt.tight_layout()
plt.savefig("obs_10C_convolution.png", dpi=120)
plt.show()

# Spectre avant et après filtrage
Fshift_avant = np.log1p(np.abs(np.fft.fftshift(F_img)))
Fshift_apres = np.log1p(np.abs(np.fft.fftshift(F_produit)))
fig2, axes2 = plt.subplots(1, 2, figsize=(10, 4))
axes2[0].imshow(Fshift_avant, cmap="inferno") ; axes2[0].set_title("Spectre avant filtrage") ; axes2[0].axis("off")
axes2[1].imshow(Fshift_apres, cmap="inferno") ; axes2[1].set_title("Spectre après filtrage\n(hautes fréq. atténuées)") ; axes2[1].axis("off")
plt.suptitle("Observation 10.C — Effet du filtre gaussien sur le spectre")
plt.tight_layout()
plt.savefig("obs_10C_spectre.png", dpi=120)
plt.show()

print(f"Erreur max entre chemin A et chemin B : {erreur.max()*255:.3f} niveaux (sur 255)")
print(f"Erreur RMS : {np.sqrt((erreur**2).mean())*255:.4f} niveaux")
```

**Missions**
1. L'erreur maximale entre les deux chemins est-elle inférieure à 1 niveau sur 255 ? Que prouve cette équivalence numérique ?
2. Dans la deuxième figure, les hautes fréquences (périphérie du spectre) sont-elles plus ou moins intenses après filtrage ? Qu'est-ce que cela signifie pour le bruit haute fréquence ?
3. Pour construire un filtre passe-haut (qui garde les contours et supprime les plages uniformes), quelle forme aurait la DFT du noyau ? Décrivez-la en une phrase et esquisez le code.

---

### Observation 10.D — La DCT : voir la compaction d'énergie sur deux blocs

**Concept mis en jeu.** Pour une zone uniforme (ciel), presque toute l'énergie d'un bloc 8×8 se concentre dans le coefficient (0,0) (la moyenne). Pour une zone texturée (feuillage), l'énergie se répartit sur tous les coefficients.

```python
import numpy as np
import matplotlib.pyplot as plt
from scipy.fft import dctn

# --- Deux blocs synthétiques ---
rng = np.random.default_rng(0)

# Bloc de ciel : gradient doux
bloc_ciel = np.full((8, 8), 180.0) + rng.normal(0, 3, (8, 8))

# Bloc de feuillage : texture aléatoire
bloc_feuillage = rng.normal(100, 40, (8, 8)).clip(0, 255)

def analyse_bloc(bloc, nom):
    dct = dctn(bloc, norm="ortho")
    energie_totale = (dct ** 2).sum()
    energie_trié = np.sort(dct.ravel() ** 2)[::-1]
    cumul = np.cumsum(energie_trié) / energie_totale

    ratio_dc = dct[0, 0] ** 2 / energie_totale
    n_pour_90 = np.searchsorted(cumul, 0.90) + 1
    n_pour_4coeff = 4  # on garde seulement les 4 plus grands

    # Reconstruction à 4 coefficients seulement
    dct_sparse = np.zeros_like(dct)
    idx = np.unravel_index(np.argsort(np.abs(dct).ravel())[-n_pour_4coeff:], dct.shape)
    dct_sparse[idx] = dct[idx]
    recon_4 = dctn(dct_sparse, norm="ortho", type=3) / (4 * len(bloc.ravel()))
    # Plus simple via scipy inverse
    from scipy.fft import idctn
    recon_4 = idctn(dct_sparse, norm="ortho")
    erreur_4coeff = np.sqrt(((bloc - recon_4)**2).mean())

    print(f"\n--- {nom} ---")
    print(f"  Ratio énergie DC (coeff 0,0) : {ratio_dc:.1%}")
    print(f"  Coefficients nécessaires pour 90% énergie : {n_pour_90}")
    print(f"  Erreur quadratique avec 4 coefficients seulement : {erreur_4coeff:.2f} niveaux")
    return dct, cumul, ratio_dc, n_pour_90

dct_ciel,      cumul_ciel,      ratio_dc_ciel,      n90_ciel      = analyse_bloc(bloc_ciel,      "Ciel (zone uniforme)")
dct_feuillage, cumul_feuillage, ratio_dc_feuillage, n90_feuillage = analyse_bloc(bloc_feuillage, "Feuillage (zone texturée)")

fig, axes = plt.subplots(2, 3, figsize=(14, 8))

for col, (bloc, dct, cumul, titre) in enumerate([
    (bloc_ciel,      dct_ciel,      cumul_ciel,      "Ciel (uniforme)"),
    (bloc_feuillage, dct_feuillage, cumul_feuillage, "Feuillage (texturé)"),
]):
    axes[0, col].imshow(bloc, cmap="gray", vmin=0, vmax=255)
    axes[0, col].set_title(f"Bloc 8×8 — {titre}")
    axes[0, col].axis("off")

    im = axes[1, col].imshow(np.log1p(np.abs(dct)), cmap="hot")
    axes[1, col].set_title("DCT (log amplitude)")
    axes[1, col].axis("off")
    plt.colorbar(im, ax=axes[1, col], fraction=0.046)

axes[0, 2].plot(range(1, 65), cumul_ciel,      "b-o", ms=4, label="Ciel")
axes[0, 2].plot(range(1, 65), cumul_feuillage, "r-s", ms=4, label="Feuillage")
axes[0, 2].axhline(0.90, linestyle="--", color="gray", label="90% énergie")
axes[0, 2].set_xlabel("Nombre de coefficients (ordre décroissant)")
axes[0, 2].set_ylabel("Fraction cumulative d'énergie")
axes[0, 2].set_title("Compaction d'énergie\n(ciel vs. feuillage)")
axes[0, 2].legend()
axes[0, 2].grid(True)

axes[1, 2].axis("off")
plt.suptitle("Observation 10.D — DCT : énergie concentrée (ciel) vs. dispersée (feuillage)")
plt.tight_layout()
plt.savefig("obs_10D_dct.png", dpi=120)
plt.show()
```

**Missions**
1. Pour le bloc de ciel, quel pourcentage de l'énergie est dans le seul coefficient (0,0) (`ratio_dc_ciel`) ? Est-ce nettement supérieur à 50 % ?
2. Pour le bloc de feuillage, combien de coefficients sont nécessaires pour atteindre 90 % de l'énergie (`n90_feuillage`) ? Comparez avec le bloc de ciel.
3. Si l'on garde seulement 4 coefficients pour reconstruire, quelle zone se reconstruit avec le moins d'erreur ? Vérifiez en lisant les deux valeurs `erreur_4coeff`.

---

### Observation 10.E — L'accumulateur de Hough : voir les votes avant les droites

**Concept mis en jeu.** L'espace (ρ, θ) de Hough accumule les votes de chaque pixel de contour. Les vraies droites correspondent à des pics nets sur un fond de votes dispersés. Le seuil de vote est la frontière entre signal et bruit.

```python
import numpy as np
import cv2
import matplotlib.pyplot as plt

# --- Image synthétique : code-barres (lignes verticales) ---
H, W = 200, 300
img = np.zeros((H, W), dtype=np.uint8)
for x in range(20, 280, 20):
    img[:, x:x+5] = 255

# Contours via Canny
edges = cv2.Canny(img, 50, 150)

# --- Calcul de l'accumulateur de Hough ---
# Paramètres de l'espace (ρ, θ)
theta_res = np.deg2rad(1)      # résolution angulaire : 1°
thetas    = np.arange(-90, 90, np.rad2deg(theta_res))
diag      = int(np.ceil(np.sqrt(H**2 + W**2)))
rhos      = np.arange(-diag, diag + 1, 1)

accumulator = np.zeros((len(rhos), len(thetas)), dtype=np.int32)
ys, xs = np.nonzero(edges)

cos_t = np.cos(np.deg2rad(thetas))
sin_t = np.sin(np.deg2rad(thetas))

for x, y in zip(xs, ys):
    rho_vals = (x * cos_t + y * sin_t).astype(int) + diag
    for t_idx, rho_idx in enumerate(rho_vals):
        if 0 <= rho_idx < len(rhos):
            accumulator[rho_idx, t_idx] += 1

# --- Détection des droites via OpenCV ---
threshold_votes = 80
lines = cv2.HoughLines(edges, 1, theta_res, threshold_votes)

# --- Figure ---
fig, axes = plt.subplots(1, 3, figsize=(16, 5))

axes[0].imshow(img, cmap="gray")
axes[0].set_title("Image originale (code-barres)")
axes[0].axis("off")

im = axes[1].imshow(accumulator, aspect="auto", cmap="hot",
                    extent=[thetas[0], thetas[-1], rhos[-1], rhos[0]])
axes[1].set_xlabel("θ (degrés)")
axes[1].set_ylabel("ρ (pixels)")
axes[1].set_title(f"Accumulateur de Hough\n(max = {accumulator.max()} votes)")
plt.colorbar(im, ax=axes[1], fraction=0.046)

# Droites sur l'image
img_lines = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
if lines is not None:
    for rho, theta in lines[:, 0, :]:
        a, b = np.cos(theta), np.sin(theta)
        x0, y0 = a * rho, b * rho
        pt1 = (int(x0 + 1000*(-b)), int(y0 + 1000*(a)))
        pt2 = (int(x0 - 1000*(-b)), int(y0 - 1000*(a)))
        cv2.line(img_lines, pt1, pt2, (0, 0, 255), 1)
axes[2].imshow(cv2.cvtColor(img_lines, cv2.COLOR_BGR2RGB))
axes[2].set_title(f"Droites détectées (seuil = {threshold_votes} votes)\n{len(lines) if lines is not None else 0} droites")
axes[2].axis("off")

plt.suptitle("Observation 10.E — Accumulateur de Hough : les votes avant les droites")
plt.tight_layout()
plt.savefig("obs_10E_hough.png", dpi=120)
plt.show()

print(f"Maximum de votes dans l'accumulateur : {accumulator.max()}")
print(f"Percentile 95 : {np.percentile(accumulator, 95):.0f} votes")
print(f"Nombre de droites détectées (seuil={threshold_votes}) : {len(lines) if lines is not None else 0}")
```

**Missions**
1. Dans l'accumulateur, comptez les pics bien distincts (zones de couleur chaude). Correspondent-ils au nombre de barres dans l'image (environ 13) ?
2. Le fond de l'accumulateur montre-t-il des valeurs entre 0 et quelques votes, bien séparées des pics ? Quel seuil maximal conserver pour ne garder que les vraies droites ?
3. Modifiez l'image pour occulter 30 % des barres (remplacez une bande verticale par des zéros). Les pics correspondants diminuent-ils en intensité ? Disparaissent-ils du résultat de `HoughLines` si le seuil est trop élevé ?

---

### Observation 10.F — La transformée de distance : voir l'épaisseur depuis l'intérieur

**Concept mis en jeu.** La carte de distance transforme un masque binaire en une carte d'altitude où chaque pixel intérieur vaut sa distance au bord le plus proche. Les maxima locaux indiquent les centres d'objets et permettent la séparation par watershed.

```python
import numpy as np
import cv2
import matplotlib.pyplot as plt
from scipy import ndimage

# --- Masque 1 : deux disques accolés (« 8 ») ---
H, W = 256, 256
mask_8 = np.zeros((H, W), dtype=np.uint8)
cv2.circle(mask_8, (W//4,    H//2), 55, 255, -1)
cv2.circle(mask_8, (3*W//4, H//2), 55, 255, -1)

# --- Masque 2 : anneau ---
mask_anneau = np.zeros((H, W), dtype=np.uint8)
cv2.circle(mask_anneau, (W//2, H//2), 90, 255, -1)
cv2.circle(mask_anneau, (W//2, H//2), 45, 0,   -1)   # trou central

def analyse_distance(mask, nom):
    dt = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
    max_val = dt.max()
    # Maxima locaux
    dt_blur = cv2.GaussianBlur(dt, (5, 5), 0)
    local_max = (dt == dt_blur) & (dt > 0.6 * max_val)
    n_maxima = ndimage.label(local_max)[1]

    print(f"\n--- {nom} ---")
    print(f"  Rayon maximal inscrit : {max_val:.1f} px")
    print(f"  Nombre de maxima locaux (>60% du max) : {n_maxima}")
    return dt

dt_8      = analyse_distance(mask_8,      "Deux disques accolés (« 8 »)")
dt_anneau = analyse_distance(mask_anneau, "Anneau")

fig, axes = plt.subplots(2, 3, figsize=(14, 9))

for row, (mask, dt, titre) in enumerate([
    (mask_8,      dt_8,      "Deux disques accolés"),
    (mask_anneau, dt_anneau, "Anneau"),
]):
    axes[row, 0].imshow(mask, cmap="gray")
    axes[row, 0].set_title(f"{titre}\n(masque binaire)")
    axes[row, 0].axis("off")

    im1 = axes[row, 1].imshow(dt, cmap="hot")
    axes[row, 1].set_title("Carte de distance\n(altitude = épaisseur)")
    axes[row, 1].axis("off")
    plt.colorbar(im1, ax=axes[row, 1], fraction=0.046)

    # Watershed pour séparer les deux disques
    if row == 0:
        sure_fg = (dt > 0.4 * dt.max()).astype(np.uint8) * 255
        sure_bg = cv2.dilate(mask, np.ones((3,3),np.uint8), iterations=3)
        unknown = cv2.subtract(sure_bg, sure_fg)
        _, markers = cv2.connectedComponents(sure_fg)
        markers += 1
        markers[unknown == 255] = 0
        img_color = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
        markers_ws = cv2.watershed(img_color, markers)
        overlay = img_color.copy()
        overlay[markers_ws == -1] = [0, 0, 255]
        axes[row, 2].imshow(cv2.cvtColor(overlay, cv2.COLOR_BGR2RGB))
        axes[row, 2].set_title("Watershed sur la carte de distance\n(frontière en rouge)")
        axes[row, 2].axis("off")
    else:
        # Profil de distance sur l'anneau (ligne horizontale centrale)
        profile = dt[H//2, :]
        axes[row, 2].plot(profile)
        axes[row, 2].set_title("Profil de distance (ligne centrale)\nMaximum = milieu de l'anneau")
        axes[row, 2].set_xlabel("colonne (px)")
        axes[row, 2].set_ylabel("distance au bord (px)")
        axes[row, 2].grid(True)

plt.suptitle("Observation 10.F — Transformée de distance : épaisseur, maxima, watershed")
plt.tight_layout()
plt.savefig("obs_10F_distance.png", dpi=120)
plt.show()
```

**Missions**
1. Sur le masque « 8 », la carte de distance montre-t-elle deux maxima distincts ? Correspondent-ils aux centres des deux disques ?
2. Le watershed (rouge) sépare-t-il les deux disques au bon endroit (la selle entre les deux bosses) ? Quel serait le résultat d'un seuillage simple sans cette étape ?
3. Sur l'anneau, le maximum de la carte de distance se trouve-t-il au centre géométrique du trou ou dans l'épaisseur du matériau ? Pourquoi le centroïde de l'anneau (qui tomberait dans le trou) n'est-il pas le bon indicateur ici ?

---

## Chapitre 12 — Seuillage et segmentation classique

### Observation 12.A — Otsu : quand la vallée existe, et quand elle n'existe pas

**Concept mis en jeu.** Otsu maximise la variance inter-classe en supposant un histogramme bimodal. Sur un histogramme unimodal, le seuil calculé est arbitraire et ne correspond à aucune frontière réelle dans l'image.

```python
import numpy as np
import cv2
import matplotlib.pyplot as plt
from skimage import data
from skimage.transform import resize

rng = np.random.default_rng(42)

# --- Trois images de test ---
# Image 1 : texte sur fond blanc → histogramme bimodal net
img_texte = np.zeros((200, 300), dtype=np.uint8) + 240
cv2.putText(img_texte, "TEXTE", (30, 120), cv2.FONT_HERSHEY_SIMPLEX, 3, 20, 8)

# Image 2 : surface uniforme → histogramme unimodal
img_uniforme = (rng.normal(128, 15, (200, 300))).clip(0, 255).astype(np.uint8)

# Image 3 : cellules en microscopie (simulé : objets clairs sur fond sombre)
img_cellules = np.zeros((200, 300), dtype=np.uint8) + 40
for _ in range(15):
    cx, cy = rng.integers(20, 280), rng.integers(20, 180)
    r = rng.integers(10, 25)
    cv2.circle(img_cellules, (cx, cy), r, int(rng.integers(160, 230)), -1)
img_cellules = cv2.GaussianBlur(img_cellules, (5, 5), 1)

images = [
    (img_texte,    "Texte sur fond blanc",          "bimodal → Otsu pertinent"),
    (img_uniforme, "Surface uniforme",               "unimodal → Otsu arbitraire"),
    (img_cellules, "Cellules (microscopie simulée)", "bimodal → Otsu pertinent"),
]

fig, axes = plt.subplots(3, 3, figsize=(14, 11))

for row, (img, nom, commentaire) in enumerate(images):
    thr, mask = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    axes[row, 0].imshow(img, cmap="gray", vmin=0, vmax=255)
    axes[row, 0].set_title(f"{nom}", fontsize=9)
    axes[row, 0].axis("off")

    hist = cv2.calcHist([img], [0], None, [256], [0, 256]).ravel()
    axes[row, 1].bar(range(256), hist, width=1, color="steelblue", alpha=0.7)
    axes[row, 1].axvline(thr, color="red", lw=2, label=f"Seuil Otsu = {thr:.0f}")
    axes[row, 1].set_title(f"Histogramme\n{commentaire}")
    axes[row, 1].legend(fontsize=8)
    axes[row, 1].set_xlim(0, 255)

    axes[row, 2].imshow(mask, cmap="gray")
    axes[row, 2].set_title(f"Masque binaire\n(seuil = {thr:.0f})")
    axes[row, 2].axis("off")

    print(f"{nom:35s} → seuil Otsu = {thr:.0f}")

plt.suptitle("Observation 12.A — Otsu : pertinent avec vallée, arbitraire sans vallée")
plt.tight_layout()
plt.savefig("obs_12A_otsu.png", dpi=120)
plt.show()
```

**Missions**
1. Pour chaque image, le seuil Otsu correspond-il visuellement à une vallée dans l'histogramme ? Pour l'image de surface uniforme, y a-t-il une vallée ?
2. Les masques des images de texte et de cellules ont-ils du sens (les objets sont-ils bien séparés du fond) ? Celui de la surface uniforme en a-t-il un ?
3. Ajoutez `img_cellules = cv2.GaussianBlur(img_cellules, (11, 11), 3)` avant le seuillage sur l'image de cellules. Le seuil change-t-il ? La vallée de l'histogramme est-elle plus marquée ? Pourquoi le flou préalable peut-il aider Otsu ?

---

### Observation 12.B — K-means : l'initialisation détermine la solution

**Concept mis en jeu.** Deux initialisations différentes (aléatoire vs. K-means++) peuvent converger vers des partitions différentes sur la même image. K-means++ réduit la variance du résultat en dispersant les centres initiaux.

```python
import numpy as np
import cv2
import matplotlib.pyplot as plt

rng = np.random.default_rng(42)

# --- Image synthétique à 4 classes dans l'espace couleur HSV ---
# Simule une image satellite (végétation dense / clairsemée / sol nu / eau)
H, W = 200, 300
K = 4
img = np.zeros((H, W, 3), dtype=np.float32)

# Eau       : bleu (H≈120°, S élevé, V moyen)
img[  0: 60, 0:150] = [120/179, 0.8, 0.5]
# Sol nu    : brun (H≈15°, S modéré, V élevé)
img[  0: 60, 150:300] = [15/179, 0.5, 0.8]
# Végétation dense : vert foncé
img[ 60:140, 0:150] = [60/179, 0.9, 0.4]
# Végétation clairsemée : vert clair
img[ 60:140, 150:300] = [75/179, 0.5, 0.7]
# Mélange sur les lignes de frontière + bruit
img += rng.normal(0, 0.03, img.shape).astype(np.float32)
img = img.clip(0, 1)

img_u8 = (img * 255).astype(np.uint8)
pixels = img_u8.reshape(-1, 3).astype(np.float32)

resultats = {}
for label, flags in [
    ("Aléatoire (RANDOM_CENTERS)", cv2.KMEANS_RANDOM_CENTERS),
    ("K-means++ (PP_CENTERS)",     cv2.KMEANS_PP_CENTERS),
]:
    energies = []
    for _ in range(5):
        energy, labels_km, centers = cv2.kmeans(
            pixels, K, None,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 100, 0.2),
            attempts=1,
            flags=flags
        )
        energies.append(energy)
    resultats[label] = {
        "energies": energies,
        "mean": np.mean(energies),
        "std":  np.std(energies),
    }
    print(f"{label}:")
    print(f"  Énergie : {energies}")
    print(f"  Moyenne = {np.mean(energies):.0f}, σ = {np.std(energies):.0f}")

# Une segmentation representative avec chaque méthode
_, labels_rand, _ = cv2.kmeans(
    pixels, K, None,
    (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 100, 0.2), 5,
    cv2.KMEANS_RANDOM_CENTERS
)
_, labels_pp, _ = cv2.kmeans(
    pixels, K, None,
    (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 100, 0.2), 5,
    cv2.KMEANS_PP_CENTERS
)

colors = np.array([[255,0,0],[0,200,0],[0,0,255],[200,200,0]], dtype=np.uint8)

seg_rand = colors[labels_rand.ravel()].reshape(H, W, 3)
seg_pp   = colors[labels_pp.ravel()  ].reshape(H, W, 3)

fig, axes = plt.subplots(1, 3, figsize=(14, 5))
axes[0].imshow(cv2.cvtColor(img_u8, cv2.COLOR_HSV2RGB))
axes[0].set_title("Image originale (HSV → RGB)")
axes[0].axis("off")

axes[1].imshow(seg_rand)
axes[1].set_title(f"K-means aléatoire\nσ énergie = {resultats['Aléatoire (RANDOM_CENTERS)']['std']:.0f}")
axes[1].axis("off")

axes[2].imshow(seg_pp)
axes[2].set_title(f"K-means++\nσ énergie = {resultats['K-means++ (PP_CENTERS)']['std']:.0f}")
axes[2].axis("off")

plt.suptitle("Observation 12.B — K-means : variance selon l'initialisation")
plt.tight_layout()
plt.savefig("obs_12B_kmeans_init.png", dpi=120)
plt.show()
```

**Missions**
1. Sur 5 lancements avec initialisation aléatoire, l'énergie finale est-elle toujours la même ? L'écart-type (`std`) est-il nettement supérieur à celui de K-means++ ?
2. K-means++ donne-t-il systématiquement une énergie inférieure ou égale à l'initialisation aléatoire ? Pourquoi K-means++ garantit-il en théorie une énergie O(log K) fois l'optimum ?
3. Créez une version de l'image où une des 4 classes occupe seulement 5 % des pixels (eau très petite zone). L'initialisation aléatoire rate-t-elle souvent cette classe ? K-means++ la trouve-t-elle plus systématiquement ?

---

### Observation 12.C — K-means : angle mort des amas non sphériques

**Concept mis en jeu.** K-means suppose des amas sphériques de tailles comparables (frontières de Voronoï). Sur des formes non sphériques (croissants imbriqués), il produit une partition artificielle. Mean-shift, sans hypothèse de forme, s'y adapte.

```python
import numpy as np
import cv2
import matplotlib.pyplot as plt
from sklearn.cluster import MeanShift, estimate_bandwidth

rng = np.random.default_rng(42)

# --- Génération de deux croissants imbriqués ---
def croissant(n, rayon, theta_min, theta_max, offset_x=0, bruit=5.0):
    angles = rng.uniform(theta_min, theta_max, n)
    r = rng.normal(rayon, bruit, n)
    x = r * np.cos(angles) + offset_x
    y = r * np.sin(angles)
    return np.stack([x, y], axis=1)

pts_a = croissant(300, 60, 0,         np.pi,     offset_x= 0)
pts_b = croissant(300, 60, np.pi, 2 * np.pi,    offset_x=30)

pts = np.vstack([pts_a, pts_b])
labels_vrai = np.array([0] * 300 + [1] * 300)

# Normalisation pour K-means
pts_norm = (pts - pts.min(0)) / (pts.max(0) - pts.min(0))
pts_u8 = (pts_norm * 254 + 1).astype(np.float32)

# K-means avec K=2
_, labels_km, _ = cv2.kmeans(
    pts_u8, 2, None,
    (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 100, 0.01), 10,
    cv2.KMEANS_PP_CENTERS
)
labels_km = labels_km.ravel()

# Mean-shift
bandwidth = estimate_bandwidth(pts, quantile=0.2, n_samples=100, random_state=42)
ms = MeanShift(bandwidth=bandwidth, bin_seeding=True)
ms.fit(pts)
labels_ms = ms.labels_

# Métriques
from sklearn.metrics import adjusted_rand_score
ari_km = adjusted_rand_score(labels_vrai, labels_km)
ari_ms = adjusted_rand_score(labels_vrai, labels_ms)
n_clusters_ms = len(np.unique(labels_ms))

print(f"K-means    : ARI = {ari_km:.3f} (1.0 = parfait)")
print(f"Mean-shift : ARI = {ari_ms:.3f}, {n_clusters_ms} clusters détectés")

couleurs = ["#e74c3c", "#3498db", "#2ecc71", "#f39c12"]
fig, axes = plt.subplots(1, 3, figsize=(14, 5))

for ax, labels, titre in zip(
    axes,
    [labels_vrai, labels_km, labels_ms],
    ["Vérité terrain\n(2 croissants)", f"K-means K=2\nARI = {ari_km:.2f}", f"Mean-shift ({n_clusters_ms} clusters)\nARI = {ari_ms:.2f}"]
):
    for c in np.unique(labels):
        mask = labels == c
        ax.scatter(pts[mask, 0], pts[mask, 1], c=couleurs[c % 4], s=10, alpha=0.7)
    ax.set_title(titre)
    ax.set_aspect("equal")
    ax.axis("off")

plt.suptitle("Observation 12.C — K-means : angle mort des amas non sphériques")
plt.tight_layout()
plt.savefig("obs_12C_kmeans_nonspherique.png", dpi=120)
plt.show()
```

**Missions**
1. Sur les croissants imbriqués, K-means (K=2) les sépare-t-il correctement ? L'ARI est-il proche de 1.0 ou bien inférieur à 0.5 ?
2. Mean-shift réussit-il mieux sur les croissants ? Quel avantage a-t-il par rapport à K-means en termes d'hypothèse sur la forme des amas ?
3. Sur un nuage de cellules rondes de tailles comparables (remplacez les croissants par deux gaussiennes isotropes), K-means et Mean-shift donnent-ils des résultats comparables ? Quel est l'avantage de Mean-shift même dans ce cas favorable à K-means ?

---

### Observation 12.D — Mean-shift : h décide du nombre de régions

**Concept mis en jeu.** La largeur de bande `h` (paramètre `sr` dans OpenCV) détermine le nombre de modes détectés. Trop petit : sur-segmentation. Trop grand : sous-segmentation. La bonne valeur fait émerger naturellement le nombre réel de classes, sans avoir à le fixer.

```python
import numpy as np
import cv2
import matplotlib.pyplot as plt

rng = np.random.default_rng(0)

# --- Frottis sanguin simulé : 3 classes de couleur ---
H, W = 256, 256
img = np.zeros((H, W, 3), dtype=np.uint8)

# Fond rosé
img[:] = [200, 170, 185]
# Globules rouges (disques rouge-orangé)
for _ in range(30):
    cx, cy = rng.integers(10, W-10), rng.integers(10, H-10)
    cv2.circle(img, (cx, cy), rng.integers(8, 14), (180, 60, 80), -1)
# Globules blancs (plus gros, violets)
for _ in range(5):
    cx, cy = rng.integers(20, W-20), rng.integers(20, H-20)
    cv2.circle(img, (cx, cy), rng.integers(15, 22), (120, 80, 160), -1)

valeurs_sr = [5, 20, 40, 80]
fig, axes = plt.subplots(1, len(valeurs_sr) + 1, figsize=(16, 4))

axes[0].imshow(img)
axes[0].set_title("Image originale\n(frottis sanguin simulé)")
axes[0].axis("off")

print("sr  | Couleurs distinctes après shift")
for col, sr in enumerate(valeurs_sr, 1):
    shifted = cv2.pyrMeanShiftFiltering(img, sp=10, sr=sr)
    # Compter les couleurs distinctes
    pixels = shifted.reshape(-1, 3)
    unique_colors = np.unique(pixels // 20 * 20, axis=0)   # quantification grossière
    n_couleurs = len(unique_colors)

    axes[col].imshow(shifted)
    axes[col].set_title(f"sr = {sr}\n~{n_couleurs} couleurs distinctes")
    axes[col].axis("off")
    print(f" {sr:2d} | {n_couleurs:4d}")

plt.suptitle("Observation 12.D — Mean-shift : sr (h) détermine le nombre de régions")
plt.tight_layout()
plt.savefig("obs_12D_meanshift_h.png", dpi=120)
plt.show()
```

**Missions**
1. Pour `sr=5`, le résultat est-il sur-segmenté (les globules rouges sont-ils chacun fragmentés en plusieurs sous-régions de nuances légèrement différentes) ?
2. Pour quelle valeur de `sr` obtient-on 3 à 5 couleurs distinctes, correspondant aux trois classes attendues (fond, globules rouges, globules blancs) ?
3. Contrairement à K-means, on n'a à aucun moment précisé le nombre de classes. Pour un contexte médical où le nombre de types cellulaires n'est pas connu à l'avance, quel est l'avantage de cette propriété ? Quel est son inconvénient principal (indice : quel paramètre faut-il tout de même régler) ?

---

### Observation 12.E — Le snake : voir l'équilibre entre les trois forces

**Concept mis en jeu.** Le contour actif (snake) converge vers l'équilibre entre la tension α (qui raccourcit le contour), la rigidité β (qui le lisse), et l'énergie image (qui l'attire vers les gradients). Faire varier α et β isole l'effet de chaque jury.

```python
import numpy as np
import cv2
import matplotlib.pyplot as plt
from skimage.segmentation import active_contour
from skimage.filters import gaussian

rng = np.random.default_rng(1)

# --- Deux images de test ---
H, W = 256, 256

# Cellule ronde
img_ronde = np.zeros((H, W), dtype=np.float32)
cv2.circle(img_ronde, (W//2, H//2), 60, 1.0, -1)
img_ronde += rng.normal(0, 0.05, img_ronde.shape)
img_ronde = img_ronde.clip(0, 1)
img_ronde_blurred = gaussian(img_ronde, sigma=2)

# Cellule en haricot (concavité profonde)
img_haricot = np.zeros((H, W), dtype=np.float32)
pts_haricot = np.array([
    [W//2 - 60, H//2], [W//2 - 30, H//2 - 50], [W//2 + 60, H//2 - 30],
    [W//2 + 70, H//2], [W//2 + 60, H//2 + 30], [W//2,      H//2 + 20],
    [W//2 - 20, H//2 + 60], [W//2 - 60, H//2 + 30],
], dtype=np.int32)
cv2.fillPoly(img_haricot, [pts_haricot], 1.0)
img_haricot += rng.normal(0, 0.05, img_haricot.shape)
img_haricot = img_haricot.clip(0, 1)
img_haricot_blurred = gaussian(img_haricot, sigma=2)

# Contour initial : grand cercle
t = np.linspace(0, 2 * np.pi, 200, endpoint=False)
# init : format (K, 2) en (row, col) — convention scikit-image
init_row = H//2 + 80 * np.sin(t)
init_col = W//2 + 80 * np.cos(t)
init = np.stack([init_row, init_col], axis=-1)

configs = [
    (0.015, 10,  "α=0.015, β=10\n(paramètres par défaut)"),
    (0.5,   10,  "α=0.5, β=10\n(élastique fort → cercle compact)"),
    (0.015, 0.1, "α=0.015, β=0.1\n(peu de rigidité → bords anguleux)"),
]

fig, axes = plt.subplots(2, 3, figsize=(14, 9))

for col, (alpha, beta, titre) in enumerate(configs):
    for row, (img_b, titre_img) in enumerate([
        (img_ronde_blurred,   "Cellule ronde"),
        (img_haricot_blurred, "Cellule haricot"),
    ]):
        snake = active_contour(
            img_b, init,
            alpha=alpha, beta=beta,
            gamma=0.01, max_num_iter=500
        )
        # snake est en (row, col) → affichage : x=col, y=row
        axes[row, col].imshow(img_b, cmap="gray")
        axes[row, col].plot(init[:, 1], init[:, 0], "b--", lw=1.5, label="Init.")
        axes[row, col].plot(snake[:, 1], snake[:, 0], "r-", lw=2,   label="Snake")
        axes[row, col].set_title(f"{titre_img}\n{titre}", fontsize=8)
        axes[row, col].axis("off")
        if col == 0 and row == 0:
            axes[row, col].legend(fontsize=7)

        # Métriques : centre en coordonnées image (row, col)
        c_row = snake[:, 0].mean()
        c_col = snake[:, 1].mean()
        print(f"{titre_img:20s} | {titre[:15]:15s} | centre ≈ (row={c_row:.0f}, col={c_col:.0f})")

plt.suptitle("Observation 12.E — Snake : équilibre α (élasticité) / β (rigidité) / image")
plt.tight_layout()
plt.savefig("obs_12E_snake.png", dpi=120)
plt.show()
```

**Missions**
1. Avec `α=0.015, β=10` (défaut), le contour colle-t-il bien au bord de la cellule ronde ? Le centre estimé est-il proche du centre réel (128, 128) ?
2. Avec `α=0.5` (élastique fort), le snake converge-t-il vers un cercle compact qui reste loin du bord de la cellule ? L'élastique l'emporte-t-il sur l'attraction du bord ?
3. Sur la cellule en haricot (concavité profonde), le snake entre-t-il dans la concavité avec les paramètres par défaut ? Que faudrait-il changer dans l'initialisation ou dans les paramètres pour qu'il y parvienne (indice : une initialisation plus proche de la forme réelle) ?

---

## Chapitre 15 — Fonctions de coût (apprentissage profond)

### Observation 15.A — L'entropie croisée : visualiser la confiance et son coût

**Concept mis en jeu.** L'entropie croisée punit de façon non linéaire la confiance mal placée. Être très confiant dans la mauvaise réponse produit un gradient beaucoup plus élevé qu'hésiter modestement.

```python
import numpy as np
import matplotlib.pyplot as plt

# --- Courbe y = -log(p) et son gradient ---
p = np.linspace(0.01, 0.99, 500)
cout = -np.log(p)
grad = -1 / p    # gradient de la cross-entropy par rapport à p (pour la classe positive)

fig, axes = plt.subplots(1, 2, figsize=(12, 5))

axes[0].plot(p, cout, "b-", lw=2)
axes[0].axvline(0.9, color="green",  linestyle="--", label="p=0.9 (confident juste)")
axes[0].axvline(0.1, color="red",    linestyle="--", label="p=0.1 (confident faux)")
axes[0].axvline(0.5, color="orange", linestyle="--", label="p=0.5 (hésitant)")
for pv, color in [(0.9, "green"), (0.1, "red"), (0.5, "orange")]:
    c = -np.log(pv)
    axes[0].annotate(f"−log({pv}) = {c:.2f}", xy=(pv, c),
                     xytext=(pv + 0.05, c + 0.3), fontsize=8, color=color,
                     arrowprops=dict(arrowstyle="->", color=color, lw=0.8))
axes[0].set_xlabel("Probabilité attribuée à la bonne classe pₜ")
axes[0].set_ylabel("Coût (− log pₜ)")
axes[0].set_title("Entropie croisée — coût selon la confiance")
axes[0].legend(fontsize=8)
axes[0].set_xlim(0, 1)
axes[0].set_ylim(0, 5)
axes[0].grid(True)

axes[1].plot(p, np.abs(grad), "r-", lw=2, label="|gradient|")
axes[1].axvline(0.9, color="green",  linestyle="--")
axes[1].axvline(0.1, color="red",    linestyle="--")
axes[1].set_xlabel("pₜ")
axes[1].set_ylabel("|∂L / ∂pₜ|")
axes[1].set_title("Gradient de l'entropie croisée\n(fort pour pₜ petit = confident faux)")
axes[1].set_xlim(0, 1)
axes[1].set_ylim(0, 20)
axes[1].legend()
axes[1].grid(True)

plt.suptitle("Observation 15.A — Entropie croisée : la confiance mal placée coûte exponentiellement plus cher")
plt.tight_layout()
plt.savefig("obs_15A_cross_entropy.png", dpi=120)
plt.show()

# Cas numériques
print("\nComparaison numérique")
print(f"{'cas':<35} | coût     | |gradient|  | ratio vs. hésitant")
ref_cout = -np.log(0.5)
ref_grad = 1/0.5
for pv, desc in [
    (0.99, "Très confiant et juste (p=0.99)"),
    (0.9,  "Confiant et juste    (p=0.90)"),
    (0.5,  "Hésitant              (p=0.50)"),
    (0.1,  "Confiant et faux     (p=0.10)"),
    (0.01, "Très confiant et faux(p=0.01)"),
]:
    c = -np.log(pv)
    g = 1/pv
    print(f"{desc:<35} | {c:7.3f}  | {g:10.2f}  | ×{c/ref_cout:.1f}")
```

**Missions**
1. Pour `p=0.9` (confiant et juste), le coût est-il proche de 0 ? Le gradient est-il faible (peu de correction nécessaire) ?
2. Pour `p=0.1` (confiant dans la mauvaise classe), le coût et le gradient sont-ils beaucoup plus élevés ? Par quel facteur par rapport au cas hésitant (`p=0.5`) ?
3. Pourquoi cette asymétrie (gradient fort pour grande erreur, faible pour petite hésitation) est-elle une propriété souhaitable pour la convergence de l'apprentissage ?

---

### Observation 15.B — Dice loss vs. entropie croisée : ce que chaque coût « voit »

**Concept mis en jeu.** Sur une image fortement déséquilibrée (0.02 % de pixels positifs), un masque qui prédit « tout fond » obtient une entropie croisée quasi nulle mais un Dice loss maximal. L'entropie croisée est aveugle au déséquilibre ; le Dice loss ne regarde que le chevauchement.

```python
import numpy as np
import matplotlib.pyplot as plt

# --- Masque de vérité : une petite lésion (50 pixels sur 512×512) ---
H, W = 512, 512
N = H * W

y_true = np.zeros((H, W), dtype=np.float32)
cy, cx = 256, 256
for dy in range(-4, 5):
    for dx in range(-4, 5):
        if dy**2 + dx**2 <= 25:
            y_true[cy + dy, cx + dx] = 1.0

n_positifs = int(y_true.sum())
ratio_pos = n_positifs / N
print(f"Pixels positifs (lésion) : {n_positifs} / {N} = {ratio_pos:.4%}")

def cross_entropy(y_true, y_pred, eps=1e-7):
    y_pred = np.clip(y_pred, eps, 1 - eps)
    return -(y_true * np.log(y_pred) + (1 - y_true) * np.log(1 - y_pred)).mean()

def dice_loss(y_true, y_pred, eps=1e-6):
    num = 2 * (y_true * y_pred).sum()
    den = y_true.sum() + y_pred.sum() + eps
    return 1 - num / den

# Trois masques prédits
masques = {
    "A — Tout fond (ne détecte rien)":           np.zeros_like(y_true),
    "B — Lésion partiellement détectée (50%)":   y_true * (np.random.default_rng(0).random((H,W)) > 0.5).astype(np.float32),
    "C — Lésion + faux positifs (×5 la surface)": np.clip(y_true + (np.random.default_rng(1).random((H,W)) > 0.97).astype(np.float32), 0, 1),
}

fig, axes = plt.subplots(2, 3, figsize=(14, 8))

print(f"\n{'Masque':<45} | CE        | Dice loss")
print("-" * 65)
for col, (nom, y_pred) in enumerate(masques.items()):
    ce = cross_entropy(y_true, y_pred if y_pred.max() > 0 else y_pred + 1e-7)
    dl = dice_loss(y_true, y_pred)
    print(f"{nom:<45} | {ce:.5f}   | {dl:.4f}")

    axes[0, col].imshow(y_true + 2 * y_pred, cmap="RdYlGn", vmin=0, vmax=3)
    axes[0, col].set_title(f"{nom}\nCE={ce:.5f} | Dice loss={dl:.4f}", fontsize=7)
    axes[0, col].axis("off")

    # Zoom sur la zone de lésion
    zoom = slice(cy-20, cy+20), slice(cx-20, cx+20)
    axes[1, col].imshow((y_true[zoom] * 128 + y_pred[zoom] * 64).clip(0, 255), cmap="hot")
    axes[1, col].set_title("Zoom zone lésion\n(jaune=vrai, rouge=prédit)", fontsize=7)
    axes[1, col].axis("off")

plt.suptitle("Observation 15.B — Dice loss vs. entropie croisée sur lésion minuscule")
plt.tight_layout()
plt.savefig("obs_15B_dice_vs_ce.png", dpi=120)
plt.show()
```

**Missions**
1. Le masque A (tout fond) obtient-il une entropie croisée très faible (≈ 0) ? Son Dice loss est-il égal à 1.0 (maximum, le pire possible) ?
2. Le passage du masque A au masque B change-t-il fortement l'entropie croisée ? Et le Dice loss ? Lequel des deux coûts « voit » la différence entre « rien détecter » et « détecter 50 % de la lésion » ?
3. Le masque C a des faux positifs. Quel coût les pénalise davantage, Dice loss ou entropie croisée ? Pourquoi le Dice loss est-il plus sensible aux faux positifs quand la lésion est petite (indice : regardez le dénominateur du Dice) ?

---

### Observation 15.C — La focal loss : visualiser le facteur de modulation (1 − pₜ)^γ

**Concept mis en jeu.** Le facteur `(1 − pₜ)^γ` atténue la contribution des exemples faciles (pₜ élevé) tout en laissant intacte celle des exemples difficiles (pₜ faible). γ règle la sévérité de cette extinction.

```python
import numpy as np
import matplotlib.pyplot as plt

p = np.linspace(0.01, 0.99, 500)
gammas = [0, 0.5, 1, 2, 5]

fig, axes = plt.subplots(1, 2, figsize=(12, 5))

# Facteur de modulation
for g in gammas:
    axes[0].plot(p, (1 - p) ** g, label=f"γ = {g}")
axes[0].set_xlabel("pₜ (confiance dans la bonne classe)")
axes[0].set_ylabel("Facteur de modulation (1 − pₜ)^γ")
axes[0].set_title("Facteur de modulation de la focal loss\nγ=0 → entropie croisée standard")
axes[0].legend()
axes[0].grid(True)
axes[0].set_xlim(0, 1)

# Focal loss complète : −(1−pₜ)^γ · log(pₜ)
for g in gammas:
    fl = -(1 - p) ** g * np.log(p)
    axes[1].plot(p, fl, label=f"γ = {g}")
axes[1].set_xlabel("pₜ")
axes[1].set_ylabel("Focal loss")
axes[1].set_title("Courbe de la focal loss\n(exemples faciles pₜ → 1 atténués)")
axes[1].legend()
axes[1].grid(True)
axes[1].set_xlim(0, 1)
axes[1].set_ylim(0, 3)

plt.suptitle("Observation 15.C — Focal loss : extinction progressive des exemples faciles selon γ")
plt.tight_layout()
plt.savefig("obs_15C_focal_loss.png", dpi=120)
plt.show()

# Tableau numérique
print("\nFacteur de modulation (1 − pₜ)^γ")
print(f"{'pₜ':<8}", end="")
for g in gammas:
    print(f" γ={g:<5}", end="")
print()
for pv in [0.1, 0.3, 0.5, 0.7, 0.9, 0.99]:
    print(f"p={pv:<5}", end="")
    for g in gammas:
        fac = (1 - pv) ** g
        print(f" {fac:6.4f}", end="")
    print()
```

**Missions**
1. Pour `γ=2` et `pₜ=0.9` (exemple facile), le facteur de modulation vaut `(1−0.9)² = 0.01`. La focal loss est-elle réduite d'un facteur 100 par rapport à γ=0 ?
2. Pour `γ=2` et `pₜ=0.1` (exemple difficile), le facteur est `(1−0.1)² = 0.81`. La focal loss est-elle presque identique à l'entropie croisée standard ?
3. Pour `γ=5` et `pₜ=0.7` : le facteur est très proche de zéro. Un exemple où le modèle prédit `p=0.7` pour la bonne classe est-il traité comme « maîtrisé » ? Quel risque cela pose-t-il si ces exemples sont en réalité difficiles mais mal étiquetés ?

---

### Observation 15.D — Smooth L1 : voir les deux régimes sur une courbe

**Concept mis en jeu.** La smooth L1 (Huber) combine un régime quadratique (précis, pour les petites erreurs) et un régime linéaire (borné, pour les grandes erreurs). Le gradient de L2 explose pour les grandes erreurs ; celui de smooth L1 est borné à ±1.

```python
import numpy as np
import matplotlib.pyplot as plt

e = np.linspace(-4, 4, 500)
beta = 1.0

def l2(x):      return 0.5 * x**2
def l1(x):      return np.abs(x)
def smooth_l1(x, b=beta):
    return np.where(np.abs(x) < b, 0.5 * x**2 / b, np.abs(x) - 0.5 * b)

def grad_l2(x):      return x
def grad_l1(x):      return np.sign(x)
def grad_smooth(x, b=beta):
    return np.where(np.abs(x) < b, x / b, np.sign(x))

fig, axes = plt.subplots(1, 2, figsize=(12, 5))

for ax, (fns, titre, ylabel) in zip(axes, [
    ([(l2, "L2"), (l1, "L1"), (smooth_l1, f"Smooth L1 (β={beta})")], "Fonctions de coût", "Coût"),
    ([(grad_l2, "∂L2/∂e"), (grad_l1, "∂L1/∂e"), (grad_smooth, f"∂SmoothL1/∂e (β={beta})")], "Gradients", "Gradient"),
]):
    for fn, label in fns:
        ax.plot(e, fn(e), lw=2, label=label)
    ax.axvline(-beta, color="gray", linestyle=":", lw=1, label=f"β = ±{beta}")
    ax.axvline( beta, color="gray", linestyle=":", lw=1)
    ax.set_xlabel("Erreur e = ŷ − y")
    ax.set_ylabel(ylabel)
    ax.set_title(titre)
    ax.legend(fontsize=8)
    ax.grid(True)
    ax.set_xlim(-4, 4)

plt.suptitle("Observation 15.D — Smooth L1 (Huber) : deux régimes, une courbe continue")
plt.tight_layout()
plt.savefig("obs_15D_smooth_l1.png", dpi=120)
plt.show()

# Tableau numérique
print("\nComparaison numérique (β = 1.0)")
print(f"{'e':>6} | {'L2':>8} | {'L1':>8} | {'SmoothL1':>10} | {'grad L2':>9} | {'grad SL1':>10}")
print("-" * 65)
for ev in [0.2, 0.5, 1.0, 2.0, 3.0]:
    print(f"{ev:>6.1f} | {l2(ev):>8.3f} | {l1(ev):>8.3f} | {smooth_l1(ev):>10.3f} | {grad_l2(ev):>9.3f} | {grad_smooth(ev):>10.3f}")
```

**Missions**
1. À `e=0.5` (erreur < β=1), la smooth L1 est-elle proche de L2 ? Le gradient vaut-il `e/β = 0.5` (pas 0.5² = 0.25 comme L2) ?
2. À `e=3.0` (erreur > β=1), le gradient de L2 vaut 3.0. Celui de smooth L1 vaut-il ±1 comme prévu par la formule ?
3. Pourquoi un seul exemple aberrant avec `e=6` dans un batch domine-t-il l'apprentissage en L2 (gradient = 6) mais pas en smooth L1 (gradient = ±1) ? Calculez la contribution relative en termes de gradient.

---

### Observation 15.E — IoU loss vs. GIoU : la zone plate rendue visible

**Concept mis en jeu.** Quand deux boîtes ne se chevauchent pas, la IoU loss vaut 1 (constante) quel que soit leur écart. Le gradient est nul : un réseau avec des boîtes disjointes ne peut pas apprendre à se rapprocher. GIoU ajoute un terme basé sur la boîte englobante commune qui varie continûment même pour des boîtes disjointes.

```python
import numpy as np
import matplotlib.pyplot as plt

# Boîte cible fixe
B = np.array([50.0, 50.0, 100.0, 100.0])   # (x1, y1, x2, y2)

def iou(a, b):
    xi1, yi1 = max(a[0], b[0]), max(a[1], b[1])
    xi2, yi2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, xi2 - xi1) * max(0.0, yi2 - yi1)
    ia = (a[2] - a[0]) * (a[3] - a[1])
    ib = (b[2] - b[0]) * (b[3] - b[1])
    union = ia + ib - inter
    return inter / union if union > 0 else 0.0

def giou(a, b):
    i = iou(a, b)
    cx1, cy1 = min(a[0], b[0]), min(a[1], b[1])
    cx2, cy2 = max(a[2], b[2]), max(a[3], b[3])
    c_area = (cx2 - cx1) * (cy2 - cy1)
    ia = (a[2]-a[0]) * (a[3]-a[1])
    ib = (b[2]-b[0]) * (b[3]-b[1])
    inter = max(0.0, min(a[2],b[2]) - max(a[0],b[0])) * max(0.0, min(a[3],b[3]) - max(a[1],b[1]))
    union = ia + ib - inter
    return i - (c_area - union) / c_area if c_area > 0 else i

# Boîte prédite qui se déplace progressivement de gauche vers la cible puis la recouvre
n = 20
positions = []
iou_vals, giou_vals = [], []

for step in range(n):
    # Centre de la boîte prédite se déplace de (0,75) vers (75,75)
    cx = step * (75 / (n - 1))
    cy = 75.0
    a = np.array([cx - 25, cy - 25, cx + 25, cy + 25])
    positions.append(cx)
    iou_vals.append(iou(a, B))
    giou_vals.append(giou(a, B))

L_iou  = [1 - v for v in iou_vals]
L_giou = [1 - v for v in giou_vals]

fig, axes = plt.subplots(1, 2, figsize=(12, 5))

axes[0].plot(positions, L_iou,  "b-o", ms=5, label="L_IoU = 1 − IoU")
axes[0].plot(positions, L_giou, "r-s", ms=5, label="L_GIoU = 1 − GIoU")
axes[0].axvline(25, color="gray", linestyle="--", label="Contact (bords touchent)")
axes[0].axvline(50, color="green", linestyle="--", label="Chevauchement commence")
axes[0].set_xlabel("Position du centre de la boîte prédite (x)")
axes[0].set_ylabel("Loss (1 − metric)")
axes[0].set_title("IoU loss vs. GIoU loss\nselon la position de la boîte prédite")
axes[0].legend(fontsize=8)
axes[0].grid(True)

# Visualisation géométrique pour 4 étapes
steps_vis = [0, 5, 12, 18]
ax = axes[1]
ax.set_xlim(-20, 130)
ax.set_ylim(10, 140)
ax.set_aspect("equal")
ax.set_title("Positions illustratives\n(bleu = prédit, vert = cible)")
colors_pred = plt.cm.Blues(np.linspace(0.4, 0.9, len(steps_vis)))

for k, step in enumerate(steps_vis):
    cx = step * (75 / (n - 1))
    a = [cx - 25, 50, cx + 25, 100]
    rect_p = plt.Rectangle((a[0], a[1]), a[2]-a[0], a[3]-a[1],
                             fill=False, edgecolor=colors_pred[k], lw=2,
                             label=f"étape {step}")
    ax.add_patch(rect_p)
    ax.text(cx, 48, f"L_GIoU={L_giou[step]:.2f}", fontsize=6, ha="center", color=colors_pred[k])

rect_b = plt.Rectangle((B[0], B[1]), B[2]-B[0], B[3]-B[1],
                         fill=True, facecolor="lightgreen", edgecolor="green", lw=2, label="Cible")
ax.add_patch(rect_b)
ax.legend(fontsize=7)

plt.suptitle("Observation 15.E — Zone plate de l'IoU loss rendue visible")
plt.tight_layout()
plt.savefig("obs_15E_iou_giou.png", dpi=120)
plt.show()

print("\nPos. centre | IoU  | GIoU  | L_IoU | L_GIoU | Disjointe ?")
for pos, iouv, giouv, liou, lgiou in zip(positions, iou_vals, giou_vals, L_iou, L_giou):
    disjointe = "✓" if iouv == 0 else " "
    print(f"  {pos:6.1f}  | {iouv:.3f} | {giouv:+.3f} | {liou:.3f} | {lgiou:+.3f}  |  {disjointe}")
```

**Missions**
1. Pour les positions où les boîtes sont disjointes (`IoU=0`), la `L_IoU` reste-t-elle constante à 1.0 ? Et la `L_GIoU` est-elle décroissante (le signal de gradient existe) ?
2. Au moment où les boîtes commencent à se chevaucher, la `L_IoU` chute-t-elle soudainement ? La `L_GIoU` avait-elle déjà commencé à diminuer ?
3. Imaginez un détecteur d'objets initialisé avec des boîtes placées loin de toutes les cibles. Avec `L_IoU`, peut-il apprendre à se rapprocher des cibles lors des premières itérations ? Avec `L_GIoU`, le peut-il ? Pourquoi GIoU est-il crucial lors de l'initialisation ?

---

### Observation 15.F — InfoNCE et la température : séparation dans l'espace de représentation

**Concept mis en jeu.** Une loss contrastive entraîne l'espace de représentation à rapprocher les exemples similaires et éloigner les dissemblables. La température τ contrôle la sévérité des pénalités : τ faible force une séparation plus nette. Sans étiquettes de classe explicites, des groupes cohérents émergent naturellement.

```python
import numpy as np
import matplotlib.pyplot as plt
from scipy.special import softmax

rng = np.random.default_rng(0)

# --- Simulation d'un espace de représentation appris ---
# 5 classes, 4 exemples par classe, embeddings 2D simulés
n_classes   = 5
n_per_class = 4
dim = 2

# Centres bien séparés sur un cercle
angles_centre = np.linspace(0, 2 * np.pi, n_classes, endpoint=False)
centres = np.stack([np.cos(angles_centre), np.sin(angles_centre)], axis=1) * 3.0

# Embeddings : chaque exemple près de son centre + bruit
embeddings = []
labels_vrai = []
for c_idx, centre in enumerate(centres):
    pts = centre + rng.normal(0, 0.3, (n_per_class, dim))
    # Normalisation sur la sphère unité (cosine similarity)
    pts = pts / np.linalg.norm(pts, axis=1, keepdims=True)
    embeddings.append(pts)
    labels_vrai.extend([c_idx] * n_per_class)

embeddings = np.vstack(embeddings)   # (20, 2)
labels_vrai = np.array(labels_vrai)
N = len(embeddings)

# --- Calcul de l'InfoNCE pour différentes températures ---
def infonce_loss(embeddings, labels, tau):
    """Calcule la InfoNCE loss moyenne sur tous les exemples."""
    # Matrice de similarité cosinus (embeddings normalisés → produit scalaire)
    sim = embeddings @ embeddings.T   # (N, N)
    total_loss = 0.0
    for i in range(N):
        positifs = np.where(labels == labels[i])[0]
        positifs = positifs[positifs != i]
        if len(positifs) == 0:
            continue
        logits = sim[i] / tau
        logits[i] = -np.inf   # exclure soi-même
        log_sum_exp = np.log(np.sum(np.exp(logits - logits.max()))) + logits.max()
        loss_i = 0.0
        for j in positifs:
            loss_i += -(sim[i, j] / tau - log_sum_exp)
        total_loss += loss_i / len(positifs)
    return total_loss / N

taus = [0.05, 0.1, 0.5, 1.0, 2.0]
losses = [infonce_loss(embeddings, labels_vrai, t) for t in taus]

# Similarité intra vs. inter-classe
sim_mat = embeddings @ embeddings.T
intra, inter = [], []
for i in range(N):
    for j in range(N):
        if i == j: continue
        if labels_vrai[i] == labels_vrai[j]:
            intra.append(sim_mat[i, j])
        else:
            inter.append(sim_mat[i, j])

print(f"Similarité cosinus intra-classe  : {np.mean(intra):.3f} ± {np.std(intra):.3f}")
print(f"Similarité cosinus inter-classe  : {np.mean(inter):.3f} ± {np.std(inter):.3f}")
print(f"Séparabilité (ratio) : {np.mean(intra)/np.mean(inter):.2f}x")

fig, axes = plt.subplots(1, 3, figsize=(15, 5))

# Espace de représentation
couleurs = ["#e74c3c", "#3498db", "#2ecc71", "#f39c12", "#9b59b6"]
noms_classes = ["Globule rouge", "Globule blanc", "Bactérie", "Cristal", "Artefact"]
for i, (emb, label) in enumerate(zip(embeddings, labels_vrai)):
    axes[0].scatter(emb[0], emb[1], c=couleurs[label],
                    s=100, edgecolors="white", lw=1, zorder=3)
    if i % n_per_class == 0:
        axes[0].text(emb[0] + 0.05, emb[1] + 0.05, noms_classes[label], fontsize=7)
axes[0].set_title("Espace de représentation\n(PCA 2D simulé — embeddings normalisés)")
axes[0].set_aspect("equal")
axes[0].grid(True, alpha=0.3)
axes[0].set_xlim(-2, 2)
axes[0].set_ylim(-2, 2)

# Matrice de similarité
im = axes[1].imshow(sim_mat, cmap="RdYlGn", vmin=-1, vmax=1)
axes[1].set_title("Matrice de similarité cosinus\n(rouge=similaire, vert=dissimilaire)")
plt.colorbar(im, ax=axes[1], fraction=0.046)
# Marqueurs de classes
for c in range(n_classes):
    start = c * n_per_class
    rect = plt.Rectangle((start - 0.5, start - 0.5), n_per_class, n_per_class,
                           fill=False, edgecolor=couleurs[c], lw=2)
    axes[1].add_patch(rect)

# Courbe InfoNCE vs. température
axes[2].plot(taus, losses, "o-", ms=8, lw=2)
axes[2].set_xlabel("Température τ")
axes[2].set_ylabel("InfoNCE loss")
axes[2].set_title("InfoNCE loss selon la température τ\n(τ faible → séparation plus sévère)")
axes[2].grid(True)

plt.suptitle("Observation 15.F — InfoNCE : groupes naturels sans étiquettes de classe")
plt.tight_layout()
plt.savefig("obs_15F_infonce.png", dpi=120)
plt.show()
```

**Missions**
1. Dans la matrice de similarité, les blocs diagonaux (cases colorées) ont-ils des valeurs plus élevées que le reste de la matrice ? Cela confirme-t-il que les embeddings de même classe sont plus proches ?
2. Sans avoir jamais dit au réseau « ceci est un globule rouge », les 4 exemples de chaque classe se regroupent-ils naturellement dans l'espace 2D ? Quelle information les paires (positif/négatif) ont-elles transmise pendant l'entraînement ?
3. Comparez l'InfoNCE loss pour `τ=0.05` et `τ=2.0`. La température faible produit-elle une loss plus élevée (pénalités plus sévères) ? En pratique, `τ=0.07` est la valeur utilisée par CLIP — pourquoi une température très basse est-elle préférable pour apprendre un espace de représentation bien séparé ?

---

## Index des scripts

| Observation | Chapitre | Concept clé | Fichier produit |
|---|---|---|---|
| 9.A | Flot optique | Contrainte OFCE : composante libre vs. contrainte | `obs_9A_ofce.png` |
| 9.B | Flot optique | Tenseur de structure prédit la fiabilité du flot | `obs_9B_trois_zones.png` |
| 9.C | Flot optique | Pyramide et grands déplacements | `obs_9C_pyramide.png` |
| 9.D | Flot optique | Paramètre α (winsize) et diffusion | `obs_9D_alpha.png` |
| 9.E | Flot optique | Flot épars vs. dense : couverture et zones manquées | `obs_9E_epars_dense.png` |
| 10.A | Transformées | Pics du spectre DFT et orientation des rayures | `obs_10A_fft_pics.png` |
| 10.B | Transformées | Échange de phases : la phase encode la structure | `obs_10B_echange_phase.png` |
| 10.C | Transformées | Théorème de convolution : deux chemins identiques | `obs_10C_convolution.png` |
| 10.D | Transformées | Compaction d'énergie DCT : ciel vs. feuillage | `obs_10D_dct.png` |
| 10.E | Transformées | Accumulateur de Hough : votes avant les droites | `obs_10E_hough.png` |
| 10.F | Transformées | Transformée de distance : maxima et watershed | `obs_10F_distance.png` |
| 12.A | Segmentation | Otsu : pertinent avec vallée, arbitraire sans | `obs_12A_otsu.png` |
| 12.B | Segmentation | K-means : variance selon l'initialisation | `obs_12B_kmeans_init.png` |
| 12.C | Segmentation | K-means : angle mort des amas non sphériques | `obs_12C_kmeans_nonspherique.png` |
| 12.D | Segmentation | Mean-shift : sr détermine le nombre de régions | `obs_12D_meanshift_h.png` |
| 12.E | Segmentation | Snake : équilibre α / β / énergie image | `obs_12E_snake.png` |
| 15.A | Fonctions de coût | Entropie croisée : confiance et coût non linéaire | `obs_15A_cross_entropy.png` |
| 15.B | Fonctions de coût | Dice loss vs. entropie croisée sur lésion minuscule | `obs_15B_dice_vs_ce.png` |
| 15.C | Fonctions de coût | Focal loss : facteur de modulation selon γ | `obs_15C_focal_loss.png` |
| 15.D | Fonctions de coût | Smooth L1 : deux régimes, une courbe continue | `obs_15D_smooth_l1.png` |
| 15.E | Fonctions de coût | IoU loss vs. GIoU : zone plate rendue visible | `obs_15E_iou_giou.png` |
| 15.F | Fonctions de coût | InfoNCE : groupes naturels sans étiquettes | `obs_15F_infonce.png` |
