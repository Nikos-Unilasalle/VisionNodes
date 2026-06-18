# Annexe 1 — Scripts (ajouts ch. 12, 14, 17)

> Scripts relégués depuis le corps des chapitres, regroupés ici par section. Dans le corps, chacun est remplacé par un schéma de nœuds. Numérotation `A1‑<chapitre>.<section>`.

---

## A1‑12.4 — Watershed (ligne de partage des eaux)

**a) Watershed par marqueurs sur transformée de distance** (séparer des objets convexes accolés) :

```python
import numpy as np
from scipy import ndimage as ndi
from skimage.segmentation import watershed
from skimage.feature import peak_local_max

# masque binaire des objets (ici : deux blobs qui se touchent)
mask = M.astype(bool)                      # M : votre masque 0/1

# 1) relief = transformée de distance ; intérieur des objets = sommets
dt = ndi.distance_transform_edt(mask)      # DT euclidienne, max au coeur des blobs

# 2) marqueurs = maxima locaux de DT, UN par objet convexe
#    min_distance évite plusieurs marqueurs sur un même objet ;
#    labels=mask restreint la recherche à l'intérieur du masque
coords = peak_local_max(dt, labels=mask, min_distance=5)
markers = np.zeros(dt.shape, dtype=int)    # carte de marqueurs vide
markers[tuple(coords.T)] = np.arange(1, len(coords) + 1)  # un entier par graine

# 3) inondation de -dt (minima = coeurs des blobs) restreinte au masque
labels = watershed(-dt, markers, mask=mask)   # NOTE le signe moins : sans lui, tout fusionne

print("nombre d'objets séparés :", labels.max())
```

**b) Variante « relief de contours »** (régions non pleines) :

```python
from skimage.filters import sobel
elevation = sobel(image_gris)              # relief : les bords sont des crêtes
# markers : 1 = fond certain (zones très sombres), 2 = objets certains (zones très claires)
labels = watershed(elevation, markers)     # inonde depuis les marqueurs imposés
```

---

## A1‑14.1 — Modèles de bruit (Poisson–Gauss)

```python
import numpy as np
from skimage.restoration import estimate_sigma

# --- 1) Simuler le modèle Poisson-Gauss (signal linéaire, en électrons) ---
rng = np.random.default_rng(0)
lam = signal_e            # carte d'éclairement moyen, en électrons (proportionnelle aux photons)
sigma_r = 5.0             # bruit de lecture (électrons RMS)
photons = rng.poisson(lam)                      # grenaille : Var = moyenne
read    = rng.normal(0, sigma_r, size=lam.shape)  # lecture : additif, indépendant du signal
mesure  = photons + read                        # Var(mesure) = lam + sigma_r^2

# --- 2) Stabiliser la variance (Anscombe) avant un débruiteur gaussien ---
def anscombe(x):          # rend Var ~ 1 quel que soit le niveau
    return 2.0 * np.sqrt(np.maximum(x, 0) + 3.0/8.0)

def anscombe_inv(y):      # inverse non biaisé (Makitalo-Foi, forme asymptotique)
    return (y/2.0)**2 - 1.0/8.0 + 0.25*np.sqrt(1.5)/y - 11.0/(8.0*y**2) + 0.625*np.sqrt(1.5)/y**3

z = anscombe(mesure)      # ... débruiter z ici comme un bruit gaussien sigma=1 ...
# debruite = anscombe_inv(z_debruite)

# --- 3) Estimer sigma sur une image inconnue (MAD des détails fins, ch.16) ---
sigma_hat = estimate_sigma(mesure.astype(float))  # = MAD(HH)/0.6745 en interne
print("sigma estimé :", round(float(sigma_hat), 2))
```

---

## A1‑17.1 — Pixels bruts vs gradient (échec de l'appariement naïf)

```python
import numpy as np
# le SSD sur pixels bruts explose pour une transformation photométrique triviale
P  = patch.astype(float)                    # patch de référence
Pt = 1.3 * P - 10.0                         # même point, gain 1.3 et offset -10
ssd = np.sum((P - Pt)**2)                   # énorme, alors que c'est le même point
print("SSD pixels bruts :", ssd)            # -> des milliers
# le gradient ignore l'offset ; sa magnitude ne garde qu'un facteur d'échelle global
gy, gx = np.gradient(P)
print("offset éliminé par le gradient :", np.allclose(np.gradient(P-10)[0], gy))
```

## A1‑17.2 — Échelle caractéristique (DoG)

```python
from skimage.feature import blob_dog
import numpy as np
# blob_dog approxime le LoG par différence de gaussiennes (§5.3), rapide
# retourne (y, x, sigma) : position ET échelle caractéristique de chaque blob
blobs = blob_dog(image_gris.astype(float),
                 min_sigma=2, max_sigma=16,   # plage d'échelles explorée
                 threshold=0.05)              # seuil sur la réponse (rejette le bruit)
for y, x, sigma in blobs:
    rayon = sigma * np.sqrt(2)               # rayon du blob (convention DoG)
    # ... extraire un descripteur sur un voisinage proportionnel à sigma ...
```

## A1‑17.3 — HOG

```python
from skimage.feature import hog
# orientations=9 bins, cellules 8x8, blocs 2x2 normalisés L2 (schéma de Dalal-Triggs)
descripteur, image_hog = hog(image_gris,
                             orientations=9,
                             pixels_per_cell=(8, 8),
                             cells_per_block=(2, 2),
                             block_norm='L2-Hys',     # normalisation + clipping (robuste)
                             visualize=True)
# 'descripteur' : vecteur concaténé de tous les blocs ; 'image_hog' : visualisation des cellules
```

## A1‑17.4 — SIFT (avec astuce RootSIFT)

```python
import cv2
sift = cv2.SIFT_create()                          # détecteur + descripteur SIFT
kp, des = sift.detectAndCompute(image_gris, None) # kp : points-clés ; des : (N, 128) float32
# astuce RootSIFT (Hellinger) : souvent meilleure que le SIFT brut, presque gratuite
import numpy as np
des /= (des.sum(axis=1, keepdims=True) + 1e-7)    # normalisation L1
des = np.sqrt(des)                                # racine -> apparier ensuite en L2 = Hellinger
```

## A1‑17.5 — ORB

```python
import cv2
orb = cv2.ORB_create(nfeatures=2000)              # détecteur FAST + descripteur ORB
kp1, d1 = orb.detectAndCompute(img1, None)
kp2, d2 = orb.detectAndCompute(img2, None)
# IMPORTANT : NORM_HAMMING pour des descripteurs binaires (jamais NORM_L2)
bf = cv2.BFMatcher(cv2.NORM_HAMMING)
matches = bf.knnMatch(d1, d2, k=2)                # 2 plus proches voisins (pour le ratio test)
```

## A1‑17.6 — Ratio test de Lowe

```python
# matches = bf.knnMatch(d1, d2, k=2)  (cf. A1-17.5)
bons = []
for m, n in matches:                  # m : plus proche voisin ; n : deuxième
    if m.distance < 0.8 * n.distance:  # ratio test de Lowe
        bons.append(m)
print(f"{len(bons)} appariements retenus sur {len(matches)}")
```

## A1‑17.7 — RANSAC + homographie

```python
import cv2, numpy as np
pts1 = np.float32([kp1[m.queryIdx].pt for m in bons]).reshape(-1, 1, 2)
pts2 = np.float32([kp2[m.trainIdx].pt for m in bons]).reshape(-1, 1, 2)
# RANSAC : H robuste + masque des inliers ; seuil de reprojection en pixels
H, mask = cv2.findHomography(pts1, pts2, cv2.RANSAC, ransacReprojThreshold=3.0)
print("inliers :", int(mask.sum()), "/", len(bons))   # le consensus du meilleur modèle
```
