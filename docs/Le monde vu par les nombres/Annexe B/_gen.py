# -*- coding: utf-8 -*-
"""Génère les notebooks de l'Annexe B (un .ipynb par chapitre).

Philosophie : code Python le plus simple possible, sans fonctions ni gestion
d'erreurs. Juste la syntaxe et l'usage. Stack haut-niveau (scikit-image, scipy,
scikit-learn) privilégiée. Données : synthétiques pour formes/masques,
skimage.data.astronaut() pour couleur/texture/descripteurs.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def md(text):
    return {"cell_type": "markdown", "metadata": {}, "source": text.strip("\n").splitlines(keepends=True)}


def code(text):
    return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
            "source": text.strip("\n").splitlines(keepends=True)}


# ---------------------------------------------------------------------------
# Données partagées (commentaires de cellule de setup par chapitre)
# ---------------------------------------------------------------------------

SETUP_SHAPE = """
# Masque synthétique : une ellipse pleine (forme à décrire)
import numpy as np
from skimage import measure, draw
import matplotlib.pyplot as plt

mask = np.zeros((220, 260), dtype=np.uint8)
rr, cc = draw.ellipse(110, 130, 55, 95, rotation=np.deg2rad(20))
mask[rr, cc] = 1

prop = measure.regionprops(mask)[0]      # une seule région
plt.imshow(mask, cmap="gray"); plt.title("masque d'entrée"); plt.show()
"""

SETUP_GRAY = """
# Image d'exemple en niveaux de gris
import numpy as np
from skimage import data, color
import matplotlib.pyplot as plt

img = color.rgb2gray(data.astronaut())   # float 0..1, H×W
plt.imshow(img, cmap="gray"); plt.title("image (gris)"); plt.show()
"""

SETUP_COLOR = """
# Image couleur d'exemple
import numpy as np
from skimage import data
import matplotlib.pyplot as plt

img = data.astronaut()                   # uint8, H×W×3, RGB
plt.imshow(img); plt.title("image (RGB)"); plt.show()
"""


# ---------------------------------------------------------------------------
# Contenu : (num, titre, note_donnees, setup, [(sous-titre, code), ...])
# ---------------------------------------------------------------------------

CHAPTERS = []

# ----- Chapitre 1 : descripteurs de forme -----
CHAPTERS.append((1, "Décrire une forme avec des nombres", SETUP_SHAPE, [
("1.1 — Circularité", """
# 4·π·aire / périmètre²  (= 1 pour un disque parfait)
circularite = 4 * np.pi * prop.area / prop.perimeter ** 2
print(circularite)
"""),
("1.2 — Élongation", """
# 1 − petit_axe / grand_axe  (0 = rond, →1 = très étiré)
elongation = 1 - prop.axis_minor_length / prop.axis_major_length
print(elongation)
"""),
("1.3 — Excentricité", """
# Excentricité de l'ellipse équivalente (0 = cercle, →1 = segment)
print(prop.eccentricity)
"""),
("1.4 — Solidité", """
# aire / aire de l'enveloppe convexe
print(prop.solidity)
"""),
("1.5 — Convexité", """
# périmètre de l'enveloppe convexe / périmètre réel
hull = measure.regionprops(prop.image_convex.astype(np.uint8))[0]
convexite = hull.perimeter / prop.perimeter
print(convexite)
"""),
("1.6 — Étendue (extent)", """
# aire / aire de la boîte englobante droite
print(prop.extent)
"""),
("1.7 — Diamètre équivalent", """
# diamètre du disque de même aire
print(prop.equivalent_diameter_area)
"""),
("1.8 — Rectangularité", """
# aire / aire de la boîte englobante orientée (min area rect via OpenCV)
import cv2
cnt = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0][0]
(_, (w, h), _) = cv2.minAreaRect(cnt)
print(prop.area / (w * h))
"""),
("1.9 — Rondeur", """
# 4·aire / (π·grand_axe²)  — insensible aux dentelures du bord
rondeur = 4 * prop.area / (np.pi * prop.axis_major_length ** 2)
print(rondeur)
"""),
]))

# ----- Chapitre 2 : moments -----
CHAPTERS.append((2, "Les moments d'image", SETUP_SHAPE, [
("2.1 — Moments bruts", """
# M[i,j] = Σ x^j · y^i · I(x,y)
M = measure.moments(mask, order=3)
print("aire M00 =", M[0, 0])
"""),
("2.2 — Centroïde", """
# centre de masse : (M10/M00, M01/M00)
cy, cx = M[1, 0] / M[0, 0], M[0, 1] / M[0, 0]
print(cy, cx)
"""),
("2.3 — Moments centraux", """
# moments calculés depuis le centroïde (invariants à la translation)
mu = measure.moments_central(mask, order=3)
print(mu[2, 0], mu[0, 2], mu[1, 1])
"""),
("2.4 — Moments normalisés", """
# moments centraux divisés par une puissance de l'aire (invariants à l'échelle)
nu = measure.moments_normalized(mu, order=3)
print(nu[2, 0], nu[0, 2])
"""),
("2.5 — Orientation principale", """
# angle de l'axe de moindre inertie
theta = 0.5 * np.arctan2(2 * mu[1, 1], mu[2, 0] - mu[0, 2])
print(np.rad2deg(theta), "ou directement :", np.rad2deg(prop.orientation))
"""),
("2.6 — Ellipse équivalente", """
# l'ellipse de mêmes moments d'ordre 2
print("grand axe :", prop.axis_major_length)
print("petit axe :", prop.axis_minor_length)
print("angle     :", np.rad2deg(prop.orientation))
"""),
("2.7 — Les sept invariants de Hu", """
# 7 combinaisons invariantes à translation, échelle, rotation
hu = measure.moments_hu(nu)
print(hu)
"""),
("2.8 — Moments pondérés par l'intensité", """
# mêmes moments mais sur les niveaux de gris (pas un masque binaire)
from skimage import data
g = data.coins()                 # image déjà en niveaux de gris (uint8)
Mi = measure.moments(g)
print("centroïde pondéré :", Mi[1, 0] / Mi[0, 0], Mi[0, 1] / Mi[0, 0])
"""),
]))

# ----- Chapitre 3 : distances et similarités -----
CHAPTERS.append((3, "Distances et similarités", """
# Deux vecteurs et deux histogrammes d'exemple
import numpy as np
from scipy.spatial import distance
from scipy.stats import wasserstein_distance

u = np.array([1.0, 2.0, 3.0])
v = np.array([4.0, 0.0, 1.0])

h1 = np.array([0.1, 0.4, 0.3, 0.2])
h2 = np.array([0.2, 0.2, 0.4, 0.2])
""", [
("3.1 — Distances de Minkowski (L_p)", """
# p=1 Manhattan, p=2 euclidienne, p→∞ Chebyshev
print(distance.minkowski(u, v, p=1))
print(distance.minkowski(u, v, p=2))
print(distance.chebyshev(u, v))
"""),
("3.2 — Distance de Mahalanobis", """
# distance en nombre d'écarts-types, via l'inverse de la covariance
data_pts = np.random.randn(100, 3)
VI = np.linalg.inv(np.cov(data_pts.T))
print(distance.mahalanobis(u, v, VI))
"""),
("3.3 — Similarité cosinus", """
# 1 − distance cosinus = cos de l'angle entre les vecteurs
print(1 - distance.cosine(u, v))
"""),
("3.4 — Distances entre histogrammes", """
# OpenCV : corrélation, chi-deux, intersection, Bhattacharyya
import cv2
a = h1.astype(np.float32); b = h2.astype(np.float32)
print("chi2 :", cv2.compareHist(a, b, cv2.HISTCMP_CHISQR))
print("inter:", cv2.compareHist(a, b, cv2.HISTCMP_INTERSECT))
print("bhatt:", cv2.compareHist(a, b, cv2.HISTCMP_BHATTACHARYYA))
"""),
("3.5 — Distance de transport (Wasserstein / EMD)", """
# coût minimal pour transformer une distribution en l'autre
bins = np.arange(4)
print(wasserstein_distance(bins, bins, h1, h2))
"""),
("3.6 — Distance de Hausdorff", """
# le pire écart entre deux nuages de points (frontières)
A = np.array([[0, 0], [0, 1], [1, 0]])
B = np.array([[2, 2], [2, 3], [3, 2]])
print(max(distance.directed_hausdorff(A, B)[0],
          distance.directed_hausdorff(B, A)[0]))
"""),
]))

# ----- Chapitre 4 : métriques de segmentation -----
CHAPTERS.append((4, "Métriques de segmentation", """
# Vérité terrain et prédiction (deux masques qui se recouvrent en partie)
import numpy as np
gt   = np.zeros((100, 100), dtype=bool); gt[20:70, 20:70] = True
pred = np.zeros((100, 100), dtype=bool); pred[30:80, 30:80] = True
""", [
("4.1 — IoU", """
# intersection / union
inter = (gt & pred).sum()
union = (gt | pred).sum()
print(inter / union)
"""),
("4.2 — Coefficient de Dice", """
# 2·intersection / (|A| + |B|)
print(2 * inter / (gt.sum() + pred.sum()))
"""),
("4.3 — Précision, rappel et F1", """
from sklearn.metrics import precision_score, recall_score, f1_score
y_true, y_pred = gt.ravel(), pred.ravel()
print(precision_score(y_true, y_pred))
print(recall_score(y_true, y_pred))
print(f1_score(y_true, y_pred))
"""),
("4.4 — Average Precision (AP)", """
# moyenne de la précision sur tous les seuils, à partir de scores continus
from sklearn.metrics import average_precision_score
scores = np.random.rand(gt.size)          # scores du modèle (factice)
print(average_precision_score(gt.ravel(), scores))
"""),
("4.5 — Panoptic Quality (PQ)", """
# PQ = (Σ IoU des vrais positifs) / (TP + ½FP + ½FN), version 1 objet
iou = inter / union
TP = 1 if iou > 0.5 else 0
FP, FN = 1 - TP, 1 - TP
print((iou * TP) / (TP + 0.5 * FP + 0.5 * FN))
"""),
("4.6 — Boundary F1 (BF)", """
# F1 calculé sur les bords (avec tolérance via dilatation)
from skimage.segmentation import find_boundaries
from scipy.ndimage import binary_dilation
bg, bp = find_boundaries(gt), find_boundaries(pred)
tol = 2
match_p = (bp & binary_dilation(bg, iterations=tol)).sum() / bp.sum()
match_r = (bg & binary_dilation(bp, iterations=tol)).sum() / bg.sum()
print(2 * match_p * match_r / (match_p + match_r))
"""),
]))

# ----- Chapitre 5 : filtrage et convolution -----
CHAPTERS.append((5, "Filtrage et convolution", SETUP_GRAY, [
("5.1 — La convolution 2D", """
# promener un noyau sur l'image (ici un flou-moyenne 5×5)
from scipy.ndimage import convolve
noyau = np.ones((5, 5)) / 25
flou = convolve(img, noyau)
"""),
("5.2 — Le noyau gaussien", """
from skimage.filters import gaussian
liss = gaussian(img, sigma=2)
"""),
("5.3 — DoG et LoG", """
# différence de gaussiennes (bande passante) et laplacien de gaussienne
from skimage.filters import difference_of_gaussians
from scipy.ndimage import gaussian_laplace
dog = difference_of_gaussians(img, low_sigma=1, high_sigma=3)
log = gaussian_laplace(img, sigma=2)
"""),
("5.4 — Le filtre bilatéral", """
# lisse sans franchir les bords (poids selon distance ET différence d'intensité)
from skimage.restoration import denoise_bilateral
bil = denoise_bilateral(img, sigma_color=0.1, sigma_spatial=3)
"""),
("5.5 — Le filtre de Gabor", """
# réponse à une ondulation orientée (fréquence + direction)
from skimage.filters import gabor
reel, imag = gabor(img, frequency=0.2, theta=np.pi / 4)
"""),
]))

# ----- Chapitre 6 : gradients et contours -----
CHAPTERS.append((6, "Gradients et contours", SETUP_GRAY, [
("6.1 — Le gradient d'image", """
# dérivées horizontale/verticale → norme et orientation
gy, gx = np.gradient(img)
norme = np.hypot(gx, gy)
angle = np.arctan2(gy, gx)
"""),
("6.2 — Sobel et Scharr", """
from skimage.filters import sobel, scharr
g_sobel = sobel(img)
g_scharr = scharr(img)     # meilleure isotropie
"""),
("6.3 — Le détecteur de Canny", """
# pipeline complet : lissage → gradient → suppression non-max → hystérésis
from skimage.feature import canny
bords = canny(img, sigma=2)
"""),
("6.4 — Le tenseur de structure", """
# classe chaque pixel : plat / bord / coin via les valeurs propres
from skimage.feature import structure_tensor, structure_tensor_eigenvalues
Axx, Axy, Ayy = structure_tensor(img, sigma=2)
l1, l2 = structure_tensor_eigenvalues((Axx, Axy, Ayy))
"""),
("6.5 — Coins : Harris et Shi-Tomasi", """
from skimage.feature import corner_harris, corner_shi_tomasi, corner_peaks
coins = corner_peaks(corner_harris(img), min_distance=5)
coins_st = corner_peaks(corner_shi_tomasi(img), min_distance=5)
"""),
]))

# ----- Chapitre 7 : couleur et photométrie -----
CHAPTERS.append((7, "Couleur et photométrie", SETUP_COLOR, [
("7.1 — Luminance (RGB → gris)", """
from skimage.color import rgb2gray
gris = rgb2gray(img)       # moyenne pondérée perceptuelle 0.21R+0.72G+0.07B
"""),
("7.2 — RGB → HSV", """
from skimage.color import rgb2hsv
hsv = rgb2hsv(img)         # teinte / saturation / valeur
teinte = hsv[..., 0]
"""),
("7.3 — CIELAB et la mesure perceptuelle", """
# distance de couleur perceptuelle (ΔE) dans l'espace Lab
from skimage.color import rgb2lab, deltaE_ciede2000
lab = rgb2lab(img)
dE = deltaE_ciede2000(lab[:10, :10], lab[10:20, :10])
"""),
("7.4 — Gamut et conversion RGB → CMYK", """
# conversion naïve (sans profil ICC)
rgb = img / 255.0
k = 1 - rgb.max(axis=2)
c = (1 - rgb[..., 0] - k) / (1 - k + 1e-9)
m = (1 - rgb[..., 1] - k) / (1 - k + 1e-9)
y = (1 - rgb[..., 2] - k) / (1 - k + 1e-9)
"""),
("7.5 — Égalisation d'histogramme et CLAHE", """
from skimage.exposure import equalize_hist, equalize_adapthist
from skimage.color import rgb2gray
g = rgb2gray(img)
eg = equalize_hist(g)              # global
clahe = equalize_adapthist(g, clip_limit=0.03)   # local, à contraste limité
"""),
("7.6 — Correction gamma et balance des blancs", """
from skimage.exposure import adjust_gamma
gamma = adjust_gamma(img, gamma=0.5)
# balance des blancs « monde gris » : chaque canal ramené à la même moyenne
moy = img.reshape(-1, 3).mean(axis=0)
wb = np.clip(img * (moy.mean() / moy), 0, 255).astype(np.uint8)
"""),
]))

# ----- Chapitre 8 : géométrie de la caméra -----
CHAPTERS.append((8, "Géométrie de la caméra", """
# Outils : numpy pour l'algèbre, OpenCV pour les routines caméra
import numpy as np
import cv2
""", [
("8.1 — Coordonnées homogènes", """
# ajouter un 1 → la projection devient un produit matriciel
p = np.array([3.0, 4.0])
p_h = np.append(p, 1)            # [3, 4, 1]
# retour en cartésien : diviser par la dernière coordonnée
q_h = np.array([6.0, 8.0, 2.0])
q = q_h[:2] / q_h[2]            # [3, 4]
"""),
("8.2 — Le modèle sténopé", """
# x_pixel = K · [R | t] · X_monde
K = np.array([[800, 0, 320], [0, 800, 240], [0, 0, 1.0]])
R = np.eye(3); t = np.array([[0.0], [0.0], [5.0]])
X = np.array([[1.0], [1.0], [0.0], [1.0]])     # point monde homogène
x = K @ np.hstack([R, t]) @ X
x = x[:2] / x[2]
print(x.ravel())
"""),
("8.3 — Calibration", """
# à partir de plusieurs vues d'un damier (object_points / image_points)
# ret, K, dist, rvecs, tvecs = cv2.calibrateCamera(
#     object_points, image_points, image_size, None, None)
# image_points provient de cv2.findChessboardCorners sur chaque photo
print("voir cv2.findChessboardCorners + cv2.calibrateCamera")
"""),
("8.4 — L'homographie", """
# transformation perspective entre deux plans (4 correspondances suffisent)
src = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], dtype=np.float32)
dst = np.array([[0, 0], [2, 0], [2, 3], [0, 1]], dtype=np.float32)
H, _ = cv2.findHomography(src, dst)
print(H)
"""),
("8.5 — La géométrie épipolaire", """
# matrice fondamentale reliant deux vues d'une même scène
pts1 = np.random.rand(20, 2) * 100
pts2 = pts1 + np.array([5.0, 0.0])           # décalage horizontal factice
F, mask = cv2.findFundamentalMat(pts1, pts2, cv2.FM_8POINT)
print(F)
"""),
("8.6 — Stéréovision", """
# carte de disparité → profondeur, à partir d'une paire rectifiée
left  = cv2.cvtColor(cv2.imread("left.png"),  cv2.COLOR_BGR2GRAY)  if False else np.zeros((200, 200), np.uint8)
right = cv2.cvtColor(cv2.imread("right.png"), cv2.COLOR_BGR2GRAY) if False else np.zeros((200, 200), np.uint8)
stereo = cv2.StereoBM_create(numDisparities=64, blockSize=15)
disparite = stereo.compute(left, right)
"""),
("8.7 — Distorsion", """
# corriger la distorsion de l'objectif avec K et les coefficients dist
K = np.array([[800, 0, 320], [0, 800, 240], [0, 0, 1.0]])
dist = np.array([-0.2, 0.05, 0, 0, 0])       # k1, k2, p1, p2, k3
img = np.zeros((480, 640, 3), np.uint8)
corrige = cv2.undistort(img, K, dist)
"""),
]))

# ----- Chapitre 9 : flot optique -----
CHAPTERS.append((9, "Le flot optique", """
# Deux images consécutives : la seconde est la première décalée
import numpy as np
from skimage import data, color
from scipy.ndimage import shift

f1 = color.rgb2gray(data.astronaut())
f2 = shift(f1, shift=(0, 3))     # décalage de 3 px vers la droite
""", [
("9.1 — La contrainte du flot optique", """
# Ix·u + Iy·v + It = 0   (une équation, deux inconnues)
Iy, Ix = np.gradient(f1)
It = f2 - f1
"""),
("9.2 — Le problème d'ouverture", """
# seule la composante du flot normale au bord est observable
norme = np.hypot(Ix, Iy) + 1e-9
flot_normal = -It / norme        # vitesse le long du gradient
"""),
("9.3 — Lucas-Kanade (épars)", """
# suit quelques points saillants entre f1 et f2 (OpenCV, uint8)
import cv2
a = (f1 * 255).astype(np.uint8); b = (f2 * 255).astype(np.uint8)
p0 = cv2.goodFeaturesToTrack(a, maxCorners=100, qualityLevel=0.3, minDistance=7)
p1, st, err = cv2.calcOpticalFlowPyrLK(a, b, p0, None)
"""),
("9.4 — Horn-Schunck (global / dense)", """
# flot dense avec hypothèse de régularité (variante TV-L1 de skimage)
from skimage.registration import optical_flow_tvl1
v, u = optical_flow_tvl1(f1, f2)   # composantes verticale et horizontale
"""),
("9.5 — Flot épars ou dense", """
# dense : Farnebäck calcule un vecteur par pixel
import cv2
a = (f1 * 255).astype(np.uint8); b = (f2 * 255).astype(np.uint8)
flot = cv2.calcOpticalFlowFarneback(a, b, None,
        0.5, 3, 15, 3, 5, 1.2, 0)   # → H×W×2
"""),
]))

# ----- Chapitre 10 : transformées -----
CHAPTERS.append((10, "Transformées", SETUP_GRAY, [
("10.1 — La transformée de Fourier (DFT)", """
# décomposer l'image en fréquences ; spectre centré
F = np.fft.fftshift(np.fft.fft2(img))
spectre = np.log(1 + np.abs(F))
"""),
("10.2 — Le théorème de convolution", """
# convoluer = multiplier dans le domaine de Fourier
from scipy.signal import fftconvolve
noyau = np.ones((5, 5)) / 25
flou = fftconvolve(img, noyau, mode="same")
"""),
("10.3 — La transformée en cosinus (DCT)", """
# base utilisée par JPEG : énergie concentrée en basses fréquences
from scipy.fft import dctn, idctn
C = dctn(img, norm="ortho")
"""),
("10.4 — La transformée de Hough", """
# voter pour des droites dans l'espace des paramètres (angle, distance)
from skimage.transform import hough_line, hough_line_peaks
from skimage.feature import canny
bords = canny(img, sigma=2)
h, angles, dists = hough_line(bords)
_, a_pics, d_pics = hough_line_peaks(h, angles, dists)
"""),
("10.5 — La transformée de distance", """
# distance de chaque pixel objet au fond le plus proche
from scipy.ndimage import distance_transform_edt
mask = img > 0.5
dt = distance_transform_edt(mask)
"""),
]))

# ----- Chapitre 11 : morphologie -----
CHAPTERS.append((11, "Morphologie mathématique", """
# Masque binaire bruité (texte/grains) pour voir l'effet des opérateurs
import numpy as np
from skimage import data
from skimage.morphology import disk
import matplotlib.pyplot as plt

mask = data.horse() == 0          # silhouette de cheval (bool)
se = disk(3)                      # élément structurant (la « sonde »)
plt.imshow(mask, cmap="gray"); plt.show()
""", [
("11.1 — Érosion et dilatation", """
from skimage.morphology import erosion, dilation
ero = erosion(mask, se)          # rétrécit
dil = dilation(mask, se)         # gonfle
"""),
("11.2 — Ouverture et fermeture", """
from skimage.morphology import opening, closing
ouv = opening(mask, se)          # érosion puis dilatation → enlève petits objets
fer = closing(mask, se)          # dilatation puis érosion → bouche petits trous
"""),
("11.3 — Gradient morphologique", """
# dilatation − érosion = contour épais, sans dérivée
from skimage.morphology import dilation, erosion
grad = dilation(mask, se).astype(int) - erosion(mask, se).astype(int)
"""),
("11.4 — Top-hat et black-hat", """
# top-hat : ce que l'ouverture a retiré (petits détails clairs)
from skimage.morphology import white_tophat, black_tophat
th = white_tophat(mask, se)
bh = black_tophat(mask, se)
"""),
("11.5 — Tout-ou-rien et squelette", """
# squelette : ligne médiane de la forme
from skimage.morphology import skeletonize
squelette = skeletonize(mask)
"""),
]))

# ----- Chapitre 12 : seuillage et segmentation -----
CHAPTERS.append((12, "Seuillage et segmentation", SETUP_GRAY, [
("12.1 — Seuillage d'Otsu", """
# choisit automatiquement le seuil qui sépare le mieux deux modes
from skimage.filters import threshold_otsu
seuil = threshold_otsu(img)
binaire = img > seuil
"""),
("12.2 — Seuillage adaptatif", """
# un seuil différent par voisinage (utile si l'éclairage varie)
from skimage.filters import threshold_local
seuil_local = threshold_local(img, block_size=35, offset=0.02)
binaire = img > seuil_local
"""),
("12.3 — Watershed", """
# inonder le relief depuis des marqueurs (sépare les objets collés)
from skimage.segmentation import watershed
from skimage.feature import peak_local_max
from scipy.ndimage import distance_transform_edt, label
mask = img > threshold_otsu(img) if 'threshold_otsu' in dir() else img > 0.5
dt = distance_transform_edt(mask)
marqueurs = label(np.zeros_like(mask))[0]
coords = peak_local_max(dt, labels=mask, min_distance=20)
marqueurs[tuple(coords.T)] = np.arange(1, len(coords) + 1)
labels = watershed(-dt, marqueurs, mask=mask)
"""),
("12.4 — K-means", """
# regrouper les pixels par valeur en k classes
from sklearn.cluster import KMeans
X = img.reshape(-1, 1)
km = KMeans(n_clusters=3, n_init=10).fit(X)
seg = km.labels_.reshape(img.shape)
"""),
("12.5 — Mean-shift", """
# remonte vers les pics de densité, sans fixer le nombre de classes
import cv2
from skimage import data
col = data.astronaut()
seg = cv2.pyrMeanShiftFiltering(col, sp=20, sr=30)
"""),
("12.6 — Contours actifs (snakes)", """
# une courbe élastique attirée par les bords
from skimage.segmentation import active_contour
from skimage.filters import gaussian
s = np.linspace(0, 2 * np.pi, 200)
init = np.column_stack([256 + 180 * np.sin(s), 256 + 180 * np.cos(s)])
snake = active_contour(gaussian(img, 3), init)
"""),
("12.7 — Coupe de graphe (graph cut)", """
# décision globale via marqueurs (random walker, accessible dans skimage)
from skimage.segmentation import random_walker
marqueurs = np.zeros(img.shape, dtype=int)
marqueurs[img < 0.3] = 1        # graines « fond »
marqueurs[img > 0.7] = 2        # graines « objet »
labels = random_walker(img, marqueurs)
"""),
]))

# ----- Chapitre 13 : texture -----
CHAPTERS.append((13, "La texture", """
# Image texturée en niveaux de gris (uint8 pour la GLCM)
import numpy as np
from skimage import data, img_as_ubyte
import matplotlib.pyplot as plt

img = img_as_ubyte(data.brick())     # texture déjà en niveaux de gris
plt.imshow(img, cmap="gray"); plt.show()
""", [
("13.1 — Statistiques du premier ordre", """
# moyenne, écart-type, asymétrie : décrivent l'histogramme, pas l'agencement
from scipy.stats import skew, kurtosis
print(img.mean(), img.std(), skew(img.ravel()), kurtosis(img.ravel()))
"""),
("13.2 — Matrice de cooccurrence (GLCM)", """
# compte les paires de niveaux à une distance et une direction données
from skimage.feature import graycomatrix
glcm = graycomatrix(img, distances=[1], angles=[0], levels=256, normed=True)
"""),
("13.3 — Descripteurs d'Haralick", """
# résumer la GLCM en quelques nombres
from skimage.feature import graycoprops
for p in ["contrast", "homogeneity", "energy", "correlation"]:
    print(p, graycoprops(glcm, p)[0, 0])
"""),
("13.4 — Local Binary Pattern (LBP)", """
# compare chaque pixel à ses voisins → micro-motif ; on en fait un histogramme
from skimage.feature import local_binary_pattern
lbp = local_binary_pattern(img, P=8, R=1, method="uniform")
hist, _ = np.histogram(lbp, bins=10, range=(0, 10))
"""),
("13.5 — Bancs de filtres et énergie de Gabor", """
# énergie de réponse à plusieurs orientations
from skimage.filters import gabor
energies = []
for theta in np.linspace(0, np.pi, 4, endpoint=False):
    reel, imag = gabor(img / 255.0, frequency=0.2, theta=theta)
    energies.append(np.hypot(reel, imag).mean())
print(energies)
"""),
]))

# ----- Chapitre 14 : qualité d'image -----
CHAPTERS.append((14, "Qualité d'image", """
# Image de référence et version dégradée
import numpy as np
from skimage import data, color, util

ref = color.rgb2gray(data.astronaut())
deg = util.random_noise(ref, mode="gaussian", var=0.01)
""", [
("14.1 — Modèles de bruit (Poisson–Gauss)", """
from skimage.util import random_noise
gauss = random_noise(ref, mode="gaussian", var=0.02)
poisson = random_noise(ref, mode="poisson")
"""),
("14.2 — MSE et PSNR", """
from skimage.metrics import mean_squared_error, peak_signal_noise_ratio
print("MSE :", mean_squared_error(ref, deg))
print("PSNR:", peak_signal_noise_ratio(ref, deg, data_range=1.0))
"""),
("14.3 — SSIM", """
# similarité structurelle : luminance × contraste × structure
from skimage.metrics import structural_similarity
score, carte = structural_similarity(ref, deg, data_range=1.0, full=True)
print(score)
"""),
("14.4 — Entropie d'image", """
# quantité d'information, sans image de référence
from skimage.measure import shannon_entropy
print(shannon_entropy(ref))
"""),
("14.5 — Mesures de netteté sans référence", """
# variance du Laplacien : faible = flou
import cv2
lap = cv2.Laplacian((ref * 255).astype(np.uint8), cv2.CV_64F)
print("netteté :", lap.var())
"""),
("14.6 — Métriques perceptuelles apprises (LPIPS)", """
# nécessite : pip install lpips torch
# import torch, lpips
# loss = lpips.LPIPS(net="alex")
# d = loss(img_tensor_ref, img_tensor_deg)   # tenseurs 1×3×H×W dans [-1, 1]
print("voir la librairie lpips (réseau pré-entraîné)")
"""),
]))

# ----- Chapitre 15 : apprentissage profond (fonctions de coût) -----
CHAPTERS.append((15, "Fonctions de coût (deep learning)", """
# Tout en NumPy pour montrer la formule ; pas de framework
import numpy as np

logits = np.array([2.0, 0.5, -1.0])     # scores bruts d'un classifieur
cible = 0                               # classe correcte
""", [
("15.1 — Entropie croisée et softmax", """
exp = np.exp(logits - logits.max())
proba = exp / exp.sum()                 # softmax
perte = -np.log(proba[cible])           # cross-entropy
print(proba, perte)
"""),
("15.2 — Dice loss", """
# 1 − Dice, sur des cartes de proba (segmentation)
pred = np.array([0.2, 0.8, 0.9, 0.1])
gt   = np.array([0.0, 1.0, 1.0, 0.0])
dice = 2 * (pred * gt).sum() / (pred.sum() + gt.sum())
print(1 - dice)
"""),
("15.3 — Focal loss", """
# pondère les exemples faciles vers le bas (gamma)
p = 0.9                                 # proba donnée à la bonne classe
gamma = 2.0
focal = -(1 - p) ** gamma * np.log(p)
print(focal)
"""),
("15.4 — Smooth L1 (Huber)", """
# quadratique près de 0, linéaire au-delà (robuste aux aberrations)
err = np.array([0.3, 2.5, -1.2])
beta = 1.0
sl1 = np.where(np.abs(err) < beta, 0.5 * err ** 2 / beta, np.abs(err) - 0.5 * beta)
print(sl1)
"""),
("15.5 — IoU loss et GIoU", """
# sur deux boîtes [x1, y1, x2, y2]
A = np.array([0, 0, 2, 2]); B = np.array([1, 1, 3, 3])
xi = max(A[0], B[0]); yi = max(A[1], B[1])
xa = min(A[2], B[2]); ya = min(A[3], B[3])
inter = max(0, xa - xi) * max(0, ya - yi)
union = 4 + 4 - inter
iou = inter / union
print("IoU loss :", 1 - iou)
"""),
("15.6 — Loss contrastive (InfoNCE)", """
# rapproche une paire positive, éloigne les négatives (température tau)
sim = np.array([0.9, 0.2, 0.1, 0.3])    # similarité ancre↔{positif, négatifs...}
tau = 0.1
e = np.exp(sim / tau)
infonce = -np.log(e[0] / e.sum())
print(infonce)
"""),
]))

# ----- Chapitre 16 : statistiques robustes -----
CHAPTERS.append((16, "Statistiques robustes", """
# Données avec une aberration franche
import numpy as np
x = np.array([10.0, 11.0, 9.5, 10.5, 100.0])    # le 100 est aberrant
""", [
("16.1 — Médiane et point de rupture", """
# la médiane ignore l'aberration, pas la moyenne
print("moyenne :", x.mean(), " médiane :", np.median(x))
"""),
("16.2 — MAD", """
# écart absolu médian → échelle robuste ; |z| = |x−méd| / (1.48·MAD)
from scipy.stats import median_abs_deviation
mad = median_abs_deviation(x, scale="normal")
z = np.abs(x - np.median(x)) / mad
print(z)                                  # le dernier point ressort
"""),
("16.3 — M-estimateurs (Huber, Tukey)", """
# fonctions de poids qui bornent l'influence des grosses erreurs (en NumPy)
from scipy.stats import median_abs_deviation
r = (x - np.median(x)) / median_abs_deviation(x, scale="normal")
c = 1.345
w_huber = np.where(np.abs(r) <= c, 1.0, c / np.abs(r))
c2 = 4.685
w_tukey = np.where(np.abs(r) <= c2, (1 - (r / c2) ** 2) ** 2, 0.0)
print("poids Huber :", w_huber)
print("poids Tukey :", w_tukey)        # 0 = point complètement rejeté
"""),
("16.4 — IRLS", """
# régression robuste y = a·t + b par moindres carrés repondérés itératifs
t = np.arange(20); y = 2.0 * t + 1 + np.random.randn(20)
y[10] = 80                             # une aberration au milieu
A = np.column_stack([t, np.ones_like(t)])
w = np.ones(len(y))
for _ in range(10):
    W = np.diag(w)
    beta = np.linalg.solve(A.T @ W @ A, A.T @ W @ y)   # ajustement pondéré
    resid = y - A @ beta
    s = 1.48 * np.median(np.abs(resid - np.median(resid))) + 1e-9
    w = np.minimum(1.0, 1.345 / (np.abs(resid / s) + 1e-9))  # poids Huber
print(beta)                            # ≈ [2, 1] : l'aberration est ignorée
"""),
("16.5 — RANSAC", """
# ajuste un modèle sur le plus grand consensus d'inliers
from skimage.measure import ransac, LineModelND
pts = np.column_stack([np.arange(20), np.arange(20) + np.random.randn(20)])
pts[5] = [5, 100]                         # aberration
modele, inliers = ransac(pts, LineModelND, min_samples=2,
                         residual_threshold=2, max_trials=100)
print(inliers.sum(), "inliers")
"""),
("16.6 — Au-delà du RANSAC vanilla", """
# variantes : estimateur de Theil-Sen (médiane des pentes), très robuste
from sklearn.linear_model import TheilSenRegressor
X = np.arange(20).reshape(-1, 1)
y = X.ravel() + np.random.randn(20); y[5] = 100
ts = TheilSenRegressor().fit(X, y)
print(ts.coef_, ts.intercept_)
"""),
]))

# ----- Chapitre 17 : descripteurs locaux -----
CHAPTERS.append((17, "Descripteurs locaux et appariement", """
# Une image et sa version transformée (rotation), pour apparier des points
import numpy as np
from skimage import data, color, transform

img = color.rgb2gray(data.astronaut())
img2 = transform.rotate(img, 30, resize=False)
""", [
("17.1 — Le problème de l'appariement", """
# comparer des imagettes brutes échoue dès qu'il y a rotation/échelle
patch1 = img[100:120, 100:120]
patch2 = img2[100:120, 100:120]
print("différence brute :", np.abs(patch1 - patch2).mean())
"""),
("17.2 — Échelle caractéristique", """
# détecter à quelle taille un point est saillant (blobs DoG)
from skimage.feature import blob_dog
blobs = blob_dog(img, max_sigma=30, threshold=0.1)   # (y, x, sigma)
"""),
("17.3 — HOG", """
# histogramme des orientations de gradient (descripteur de fenêtre)
from skimage.feature import hog
vecteur, visu = hog(img, orientations=9, pixels_per_cell=(16, 16),
                    cells_per_block=(2, 2), visualize=True)
"""),
("17.4 — SIFT", """
# détection + description invariantes échelle/rotation
from skimage.feature import SIFT
sift = SIFT()
sift.detect_and_extract(img)
kp, desc = sift.keypoints, sift.descriptors
"""),
("17.5 — ORB et BRIEF", """
# descripteurs binaires, rapides
from skimage.feature import ORB
orb = ORB(n_keypoints=200)
orb.detect_and_extract(img)
kp, desc = orb.keypoints, orb.descriptors
"""),
("17.6 — Le ratio test de Lowe", """
# garder un appariement seulement si le meilleur est nettement devant le 2e
from skimage.feature import SIFT, match_descriptors
s1, s2 = SIFT(), SIFT()
s1.detect_and_extract(img); s2.detect_and_extract(img2)
matches = match_descriptors(s1.descriptors, s2.descriptors,
                            max_ratio=0.7, cross_check=True)
print(len(matches), "bons appariements")
"""),
("17.7 — RANSAC et homographie", """
# imposer la cohérence géométrique entre les points appariés
from skimage.measure import ransac
from skimage.transform import ProjectiveTransform
src = s1.keypoints[matches[:, 0]][:, ::-1]   # (x, y)
dst = s2.keypoints[matches[:, 1]][:, ::-1]
modele, inliers = ransac((src, dst), ProjectiveTransform,
                         min_samples=4, residual_threshold=3, max_trials=200)
print(inliers.sum(), "appariements cohérents")
"""),
("17.8 — L'état de l'art (deep learning)", """
# détecteurs/descripteurs appris : SuperPoint, SuperGlue, LoFtR...
# disponibles via la librairie kornia (pip install kornia)
print("voir kornia.feature (SuperPoint, LoFTR) pour l'appariement appris")
"""),
]))


# ---------------------------------------------------------------------------
# Construction des notebooks
# ---------------------------------------------------------------------------

INTRO = """# Annexe B — Cahier de code, Chapitre {num}
## {title}

Ce notebook accompagne le chapitre {num} de *Fondamentaux de la Vision par
Ordinateur*. Pour **chaque sous-chapitre**, une cellule de code Python montre la
**syntaxe et l'usage** de la notion — au plus simple, sans fonctions ni gestion
d'erreurs. Le but n'est pas de produire du code de production, mais de relier la
formule du livre à son équivalent Python.

> **Pré-requis** : `pip install numpy scipy scikit-image scikit-learn opencv-python matplotlib`

Exécutez les cellules dans l'ordre : la première prépare les données d'entrée.
"""

for num, title, setup, subs in CHAPTERS:
    cells = [md(INTRO.format(num=num, title=title)),
             md("## Préparation des données"),
             code(setup)]
    for sub_title, sub_code in subs:
        cells.append(md("## " + sub_title))
        cells.append(code(sub_code))
    nb = {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    path = os.path.join(HERE, f"annexe_b_ch{num:02d}.ipynb")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(nb, fh, ensure_ascii=False, indent=1)
    print("écrit :", os.path.basename(path), f"({len(subs)} sous-chapitres)")

print("Terminé.")
