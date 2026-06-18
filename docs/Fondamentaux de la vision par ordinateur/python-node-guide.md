# La node « Python Code » dans VNStudio — guide de référence

> **À qui s'adresse ce document ?**
> À Claude, qui rédige le livret d'accompagnement (manuel de Computer Vision) mais ne
> connaît VNStudio que de façon globale. Ce fichier décrit **le contrat exact** de la node
> Python afin que les scripts proposés aux étudiants soient corrects du premier coup.
> Les premiers chapitres du manuel (descripteurs, moments, excentricité…) reposent sur le
> schéma : **un masque entre dans la node Python, un scalaire/dictionnaire en sort, et une
> node Inspecteur affiche le résultat.**

---

## 1. Ce qu'est la node Python (`logic_python`)

- **Nom affiché dans l'app** : *Python Script* / *Python Node*. **Catégorie** : `logic`.
- C'est une node à **entrées et sorties dynamiques** : il n'y a au départ qu'une entrée
  (`a`) et une sortie (`out_a`). De nouveaux ports apparaissent **au fur et à mesure** que
  l'étudiant tire un lien vers le port `+`.
- Le script est édité en **double-cliquant** sur la node (ouvre l'éditeur de code).
- **Modèle d'exécution** : le script est ré-exécuté **à chaque frame** (~30 fps en flux
  webcam). Sur une image fixe ou un masque statique, il s'exécute aussi en boucle, mais le
  résultat est stable. ⇒ Écrire du code **idempotent** ; ne pas accumuler d'état sauf via
  `state` (voir §6).

### Schéma typique pour les chapitres « descripteurs / moments »

```
[Webcam / Image]→[Seuil / Masque]→( a )[ Python Node ]( out_a )→( data )[ Inspector ]
```

L'étudiant connecte un **masque** sur l'entrée `a`, calcule des caractéristiques dans le
script, expose un **dictionnaire** sur `out_a`, et **lit le résultat dans l'Inspecteur**.

---

## 2. Les entrées : ports nommés `a, b, c, d …`

- Chaque lien connecté devient **une variable Python du même nom** : la 1ʳᵉ entrée est `a`,
  la 2ᵉ `b`, la 3ᵉ `c`, etc. (lettres `a`→`z`).
- La variable contient **directement la donnée**, déjà désérialisée selon le type du port.
- **Toujours tester le type** avant d'utiliser une entrée (elle peut être `None` si rien
  n'est branché, ou d'un type inattendu).

### Table des types de port → valeur Python reçue

| Couleur / type de port | Valeur Python | Détails |
|---|---|---|
| `image` (bleu) | `np.ndarray` | `H×W×3`, `uint8`, **BGR** (ordre OpenCV) |
| `mask` (gris) | `np.ndarray` | `H×W`, `uint8`, **binaire 0/255** |
| `markers` | `np.ndarray` | `H×W`, `int32`, carte de labels (0 = fond) |
| `flow` | `np.ndarray` | `H×W×2`, `float32` (flux optique dx/dy) |
| `data` (orange) | `pd.DataFrame` | pandas |
| `contours` | `list[np.ndarray]` | chaque contour `(N,1,2) int32` (format `cv2`) |
| `regions` | `list[dict]` | ex. `{'area':…, 'centroid':(y,x), 'bbox':…}` |
| `points` | `list[dict]` | `{'x':float, 'y':float, 'label':int}` (1=fg, 0=bg) |
| `scalar` (jaune) | `int` \| `float` | |
| `string` | `str` | |
| `dict` (vert) | `dict` | |
| `list` (violet) | `list` | |
| `any` (blanc) | n'importe quoi | |

> **Point clé pour les premiers chapitres** : un **masque** arrive comme un tableau NumPy
> `H×W` en `uint8` à valeurs **0 ou 255**. C'est la donnée d'entrée des exercices sur les
> moments et l'excentricité.

---

## 3. Ce qui est disponible dans le script (globals injectés)

| Nom | Contenu |
|---|---|
| `np` | NumPy (toujours dispo) |
| `cv2` | OpenCV (toujours dispo) |
| `pd` | pandas (peut être `None` si non installé — tester avant usage) |
| `state` | `dict` **persistant entre les frames** (voir §6) |
| `a, b, c …` | les entrées connectées |

Pas besoin d'`import numpy` / `import cv2` : ils sont déjà là.

### Imports : autorisés (sauf liste noire), si le module est installé

La node **accepte les `import`** — elle bloque seulement une liste noire (système / fichiers /
réseau, voir §7). Les bibliothèques scientifiques suivantes sont **installées et importables**
dans le moteur :

| Module | Module |
|---|---|
| `numpy` | `skimage` (scikit-image) |
| `cv2` (OpenCV) | `scipy` |
| `pandas` | `sklearn` (scikit-learn) |
| `PIL` (Pillow) | `matplotlib` |
| `shapely` | `networkx` |

> **Très utile pour les descripteurs** : `skimage.measure.regionprops` donne aire, centroïde,
> **excentricité**, orientation, solidité… « clé en main » :
>
> ```python
> from skimage.measure import label, regionprops
> props = regionprops(label(a > 0))[0]      # a = masque
> out_a = {'aire': float(props.area),
>          'excentricite': float(props.eccentricity),
>          'orientation_rad': float(props.orientation),
>          'solidite': float(props.solidity)}
> ```
>
> C'est une **alternative directe** au calcul manuel par moments du §8.3 — à présenter au choix
> dans le manuel (pédagogie « à la main » vs outil tout fait).

---

## 4. Les sorties : variables `out_*`

- **Toute variable dont le nom commence par `out_`** est exposée sur un **port de sortie**.
  La sortie par défaut est `out_a` ; les suivantes sont `out_b`, `out_c`, … (créées en
  tirant un lien depuis le port `+` de sortie).
- Le **type du port de sortie est déduit automatiquement** de la node à laquelle on le
  connecte. Pour afficher un résultat numérique/textuel, on connecte la sortie à
  l'**Inspecteur** (entrée `data`, blanche).
- Valeurs renvoyables : `np.ndarray` (image/masque), `float`/`int` (scalaire), `str`,
  `dict`, `list`, `bool`… Pour un **résultat de mesure lisible**, renvoyer un **`dict`**
  (clé → valeur) est idéal : l'Inspecteur l'affiche en arbre.
- Une sortie spéciale `out_e` contient le **message d'erreur** éventuel (chaîne vide si OK).
  Inutile de la définir : la node la fournit toute seule, et l'éditeur l'affiche.

> ⚠️ Pour les **scalaires**, caster explicitement en `float(...)` / `int(...)`. NumPy
> renvoie souvent des `np.float64` ; un `float()` garantit une valeur propre côté Inspecteur
> et côté ports `scalar`.

---

## 5. Lire le résultat : la node « Inspector » (`data_inspector`)

- **Nom affiché** : *Inspector*. **Catégorie** : `visualize`. **Icône** : œil.
- Entrées : `image` (bleu) **et** `data` (blanc, type `any`). Pour lire une mesure, on
  branche la sortie `out_a` de la node Python sur l'entrée **`data`**.
- L'Inspecteur **affiche le contenu brut** de la donnée (nombres, listes, dictionnaires) en
  arbre déroulant. C'est l'outil de lecture standard pour ces chapitres.
- Il **laisse passer** la donnée (sortie `data_out`) : on peut donc le chaîner.

---

## 6. Persistance entre frames (`state`)

Pour mémoriser quelque chose d'une frame à l'autre (compteur, moyenne glissante, valeur
précédente) :

```python
state['n'] = state.get('n', 0) + 1          # compteur de frames
state['ema'] = 0.9 * state.get('ema', 0.0) + 0.1 * float(np.mean(a))
out_a = {'frame': state['n'], 'aire_lissee': state['ema']}
```

`state` est un dictionnaire propre à **chaque** node Python, vidé au redémarrage du moteur.

---

## 7. Bac à sable (sécurité) — ce qui est **interdit**

La node exécute le script dans un environnement restreint. À **ne pas** proposer aux
étudiants :

- **Imports bloqués** : `os`, `sys`, `subprocess`, `shutil`, `socket`, `http`, `urllib`,
  `requests`, `pathlib`, `glob`, `importlib`, `ctypes`, `threading`, `multiprocessing`,
  `io`, etc. ⇒ **aucune lecture/écriture de fichier, aucun réseau** depuis la node.
- `open`, `eval`, `exec`, `input`, `__import__` direct, accès au système de fichiers :
  indisponibles.
- Builtins autorisés (liste blanche) : les usuels purs — `abs, all, any, bool, dict,
  enumerate, float, int, len, list, map, max, min, range, round, set, sorted, str, sum,
  tuple, type, zip, print, isinstance, getattr, hasattr…` et les exceptions courantes.

Tout le calcul d'image/mesure se fait via **`np` et `cv2`**, qui suffisent largement pour
les descripteurs.

---

## 8. Recettes prêtes à l'emploi (chapitres descripteurs & moments)

> Convention des exemples : **un masque binaire est branché sur l'entrée `a`**. Chaque
> script renvoie un **`dict`** sur `out_a`, à brancher sur l'entrée `data` de l'Inspecteur.

### 8.1 Garde-fous + extraction du contour principal

Patron de base réutilisé dans tous les exercices : sécuriser l'entrée, binariser, prendre le
**plus grand contour** (l'objet d'intérêt).

```python
# a : masque binaire (H×W uint8, 0/255)
if not isinstance(a, np.ndarray):
    out_a = {'erreur': 'aucun masque en entree'}
else:
    m = a if a.ndim == 2 else cv2.cvtColor(a, cv2.COLOR_BGR2GRAY)
    _, m = cv2.threshold(m, 127, 255, cv2.THRESH_BINARY)   # garantit 0/255

    contours, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        out_a = {'erreur': 'masque vide'}
    else:
        cnt = max(contours, key=cv2.contourArea)
        out_a = {'n_contours': len(contours), 'aire_objet': float(cv2.contourArea(cnt))}
```

### 8.2 Aire, périmètre, centroïde, circularité (moments d'ordre 0 et 1)

```python
m = a if a.ndim == 2 else cv2.cvtColor(a, cv2.COLOR_BGR2GRAY)
_, m = cv2.threshold(m, 127, 255, cv2.THRESH_BINARY)
contours, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

if contours:
    cnt = max(contours, key=cv2.contourArea)
    M = cv2.moments(cnt)
    aire = float(M['m00'])
    perim = float(cv2.arcLength(cnt, True))
    cx = float(M['m10'] / M['m00']) if M['m00'] else 0.0   # centroïde x
    cy = float(M['m01'] / M['m00']) if M['m00'] else 0.0   # centroïde y
    circularite = float(4 * np.pi * aire / (perim ** 2)) if perim else 0.0  # 1 = cercle

    out_a = {
        'aire': aire,
        'perimetre': perim,
        'centroide': {'x': cx, 'y': cy},
        'circularite': circularite,
    }
else:
    out_a = {'erreur': 'masque vide'}
```

### 8.3 Excentricité et orientation (moments centraux d'ordre 2)

Méthode « moments » : on construit la matrice de covariance à partir des **moments centraux
normalisés**, puis on en prend les valeurs propres.

```python
m = a if a.ndim == 2 else cv2.cvtColor(a, cv2.COLOR_BGR2GRAY)
_, m = cv2.threshold(m, 127, 255, cv2.THRESH_BINARY)
contours, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

if contours:
    cnt = max(contours, key=cv2.contourArea)
    M = cv2.moments(cnt)
    if M['m00'] > 0:
        # moments centraux normalisés (covariance de la forme)
        a20 = M['mu20'] / M['m00']
        a02 = M['mu02'] / M['m00']
        a11 = M['mu11'] / M['m00']

        commun = np.sqrt(max(0.0, (a20 - a02) ** 2 + 4 * a11 ** 2))
        lam1 = (a20 + a02 + commun) / 2.0   # valeur propre majeure
        lam2 = (a20 + a02 - commun) / 2.0   # valeur propre mineure

        excentricite = float(np.sqrt(1 - lam2 / lam1)) if lam1 > 0 else 0.0
        # orientation de l'axe principal, en degrés
        orientation = float(0.5 * np.degrees(np.arctan2(2 * a11, a20 - a02)))

        out_a = {
            'excentricite': excentricite,     # 0 = cercle, →1 = très allongé
            'orientation_deg': orientation,
            'demi_axe_majeur': float(2 * np.sqrt(lam1)),
            'demi_axe_mineur': float(2 * np.sqrt(lam2)),
        }
    else:
        out_a = {'erreur': 'aire nulle'}
else:
    out_a = {'erreur': 'masque vide'}
```

> **Variante pédagogique** : `cv2.fitEllipse(cnt)` renvoie `((cx,cy),(MA,ma),angle)` ; on
> peut alors poser `excentricite = sqrt(1 - (ma/MA)**2)`. Utile pour comparer les deux
> définitions (ellipse ajustée vs moments) dans le manuel.

### 8.4 Moments de Hu (descripteurs invariants)

```python
m = a if a.ndim == 2 else cv2.cvtColor(a, cv2.COLOR_BGR2GRAY)
_, m = cv2.threshold(m, 127, 255, cv2.THRESH_BINARY)
M = cv2.moments(m, binaryImage=True)
hu = cv2.HuMoments(M).flatten()
# compression log usuelle pour rendre les ordres de grandeur comparables
hu_log = [float(-np.sign(h) * np.log10(abs(h) + 1e-30)) for h in hu]
out_a = {f'hu{i+1}': v for i, v in enumerate(hu_log)}
```

### 8.5 Boîte englobante, rectangle orienté, solidité, extent

```python
m = a if a.ndim == 2 else cv2.cvtColor(a, cv2.COLOR_BGR2GRAY)
_, m = cv2.threshold(m, 127, 255, cv2.THRESH_BINARY)
contours, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

if contours:
    cnt = max(contours, key=cv2.contourArea)
    aire = float(cv2.contourArea(cnt))
    x, y, w, h = cv2.boundingRect(cnt)
    hull = cv2.convexHull(cnt)
    aire_hull = float(cv2.contourArea(hull))

    out_a = {
        'bbox': {'x': int(x), 'y': int(y), 'w': int(w), 'h': int(h)},
        'extent': aire / (w * h) if w * h else 0.0,          # aire / bbox
        'solidite': aire / aire_hull if aire_hull else 0.0,  # aire / enveloppe convexe
        'ratio_aspect': float(w) / h if h else 0.0,
    }
else:
    out_a = {'erreur': 'masque vide'}
```

---

## 9. Pièges à connaître quand on rédige des exercices

1. **Le masque est en 0/255, pas 0/1.** Re-seuiller (`cv2.threshold(..., 127, 255, ...)`)
   évite les surprises si le masque vient d'un autre traitement.
2. **Toujours gérer `None` et le masque vide** (`if not contours: …`). Le script tourne
   à chaque frame ; une frame sans objet ne doit pas planter.
3. **Caster les scalaires** : `float(...)` / `int(...)`. Sinon des `np.float64`/`np.int64`
   peuvent mal s'afficher ou mal transiter sur les ports `scalar`.
4. **Renvoyer un `dict`** pour un résultat multi-valeurs : c'est le format le plus lisible
   dans l'Inspecteur.
5. **Pas d'I/O ni de réseau** (voir §7) : tout exercice doit être 100 % calcul en mémoire.
6. **Convention OpenCV** : images en **BGR**, axes `(ligne y, colonne x)`. Les centroïdes de
   `cv2.moments` sont en coordonnées image `(x, y)`.
7. **Une seule entrée nommée `a`** au départ : si un exercice a besoin de deux entrées
   (ex. image + masque), préciser à l'étudiant de connecter la 2ᵉ sur le port `+`, elle
   deviendra `b`.

---

## 10. Aide-mémoire ultra-court (à garder en tête en rédigeant)

```text
ENTRÉE   : a, b, c…              (masque → np.ndarray H×W uint8 0/255)
DISPO    : np, cv2, pd, state
SORTIE   : out_a = <valeur>      (dict recommandé pour une mesure)
LECTURE  : out_a → entrée "data" de la node Inspector
INTERDIT : fichiers, réseau, os/sys, open/eval/exec
SCHÉMA   : [Masque] → [Python Node] → [Inspector]
```
