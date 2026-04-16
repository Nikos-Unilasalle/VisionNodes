# VisionNodes Studio

VisionNodes est un environnement de développement nodale ultra-fluide pour le prototypage rapide d'algorithmes de Vision par Ordinateur (CV) et d'IA. Entièrement programmé par Gemini 3.1 Pro et Gemini 3 Flash, il combine la puissance de **OpenCV** et **MediaPipe** avec une interface React moderne et réactive.

![VisionNodes Header](https://raw.githubusercontent.com/Nikos-Unilasalle/VisionNodes/main/public/header_preview.png) *(Note: Placeholder pour une future capture d'écran)*

---

## Installation Rapide

### 1. Prérequis
- Node.js (v18+)
- Python 3.10+
- Clés SSH configurées pour GitHub

### 2. Clonage et Dépendances
```bash
git clone git@github.com:Nikos-Unilasalle/VisionNodes.git
cd VisionNodes

# Frontend
npm install

# Backend (Python)
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows
pip install opencv-python mediapipe websockets numpy
```

### 3. Lancement
Il faut lancer le moteur Python ET l'interface :
- **Moteur** : `python engine/engine.py`
- **UI** : `npm run dev`

---

## Guide du Développeur : Créer de nouveaux Nœuds

VisionNodes utilise un système de **Plugins Dynamiques**. Vous n'avez pas besoin de toucher au code source du moteur ou de l'interface pour ajouter des fonctionnalités.

### Le Système de Plugins
Tous les fichiers `.py` placés dans le dossier `engine/plugins/` sont automatiquement chargés au démarrage.

#### Structure d'un Nœud (Exemple: Invert Color)
Créez un fichier `engine/plugins/mon_filtre.py` :

```python
from __main__ import vision_node, NodeProcessor
import cv2

@vision_node(
    type_id='mon_filtre_unique',   # Identifiant unique
    label='Inverser Couleurs',     # Nom affiché dans l'UI
    category='cv',                 # Catégorie (cv, mask, math, noise, ai, help...)
    icon='Zap',                   # Icône Lucide-React
    inputs=[{'id': 'image', 'color': 'image'}],
    outputs=[{'id': 'main', 'color': 'image'}],
    params=[
        {'id': 'intensity', 'min': 0, 'max': 100, 'default': 50}
    ]
)
class InvertNode(NodeProcessor):
    def process(self, inputs, params):
        # 1. Récupérer les entrées
        img = inputs.get('image')
        if img is None: return {'main': None}
        
        # 2. Logique de traitement (OpenCV)
        res = cv2.bitwise_not(img)
        
        # 3. Retourner les sorties
        return {'main': res}
```

### Paramètres de la Décoration `@vision_node`
| Champ | Description |
| :--- | :--- |
| `type_id` | Identifiant interne (doit être unique). |
| `label` | Nom humain affiché sur le nœud. |
| `category` | Organise le nœud dans le menu "Add Module". |
| `icon` | Nom d'une icône [Lucide](https://lucide.dev/icons). |
| `inputs` | Liste des ports d'entrée (ID + Couleur). |
| `outputs` | Liste des ports de sortie. |
| `params` | Génère automatiquement des Sliders dans l'inspecteur de droite. |

### Couleurs des Connecteurs
Utilisez ces noms de couleurs pour assurer la compatibilité entre les nœuds :
- `image` : Flux vidéo standard (BGR).
- `mask` : Masques binaires (1 canal).
- `scalar` / `data` / `dict` : Valeurs numériques ou objets JSON.
- `list` : Listes de détections.
- `flow` : Vecteurs de mouvement (Optical Flow).
- `any` : Connecteur universel (accepte tout).

---

## Structure du Projet

```text
.
├── engine/              # Moteur Python (Core)
│   ├── engine.py        # Logic principal & Serveur WebSocket
│   └── plugins/         # Vos nœuds personnalisés (.py)
├── src/                 # Code source React (Frontend)
│   ├── components/      # Définitions UI des nœuds
│   └── App.tsx          # Gestion de la Graph-Logic
├── public/              # Assets statiques
└── package.json         # Dépendances Node.js
```

---

## Licence
Projet développé dans un but éducatif et de recherche. Libre d'utilisation sous licence MIT.
