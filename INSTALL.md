# VisionNodes — Guide d'installation

## Prérequis système

### macOS
- **Node.js** v18+ — [nodejs.org](https://nodejs.org/)
- **Rust** — [rustup.rs](https://rustup.rs/)
- **Python** 3.10+ — [python.org](https://python.org/)

### Linux (Ubuntu / Debian)
```bash
# Dépendances système pour Tauri + WebKit
sudo apt install -y \
  libwebkit2gtk-4.1-dev libgtk-3-dev libayatana-appindicator3-dev \
  librsvg2-dev patchelf build-essential curl

# Node.js v18+ (via nvm ou nodejs.org)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source "$HOME/.cargo/env"

# Python 3.10+ et venv (le paquet venv doit correspondre à la version Python)
sudo apt install -y python3 python3-pip python3.12-venv
# Adaptez python3.12-venv à votre version (python3 --version)
```

### Linux (Arch / Manjaro)
```bash
sudo pacman -S webkit2gtk-4.1 gtk3 base-devel nodejs npm python python-pip
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
```

---

## Installation

```bash
git clone https://github.com/Nikos-Unilasalle/VisionNodes.git
cd VisionNodes
npm run setup
```

Le script `setup` fait automatiquement :
1. `npm install` — dépendances frontend
2. Vérifie Rust, installe via rustup si absent
3. Crée le venv `.venv` (installe `python3-venv` via apt si nécessaire sur Linux)
4. `pip install --no-build-isolation -r engine/requirements.txt` — toutes les librairies IA/CV
5. Installe Tesseract OCR (Homebrew sur macOS, apt sur Linux)

> **Note :** L'installation est longue (~10–20 min) car elle télécharge PyTorch, YOLOv11, SAM-2, etc.

---

## Lancer le studio

```bash
npm run studio
```

Ou depuis n'importe où si vous avez configuré la commande shell :

```bash
vnstudio
```

---

## Résolution des problèmes

### Écran blanc au démarrage (Linux Wayland)
```bash
WEBKIT_DISABLE_DMABUF_RENDERER=1 npm run studio
```
Ce flag est déjà inclus dans `npm run studio`.

### Erreur : `.venv` introuvable
```bash
npm run setup
```

### Erreur : `python3-venv` manquant (Ubuntu/Debian)
```bash
sudo apt install python3.$(python3 -c "import sys; print(sys.version_info.minor)")-venv
```
Le script `setup` gère cela automatiquement si `sudo` est disponible.

### Accès caméra refusé
- **macOS** : Réglages Système → Confidentialité et sécurité → Appareil photo
- **Linux** : Vérifiez que votre utilisateur est dans le groupe `video` :
  ```bash
  sudo usermod -aG video $USER
  # Se déconnecter/reconnecter pour appliquer
  ```

### Nœud SAM-2 / chargement de modèle échoue
Le modèle s'installe à la demande lors du premier usage. Si l'installation échoue, relancez l'engine — `ensure_packages` réessaiera. SAM-2 nécessite ~2 GB de RAM supplémentaires.

### Tesseract OCR manquant
- **macOS** : `brew install tesseract`
- **Linux** : `sudo apt install tesseract-ocr`

---

© 2026 VisionNodes Studio
