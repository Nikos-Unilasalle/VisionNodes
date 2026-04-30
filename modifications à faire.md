# Audit et Feuille de Route pour la Création de Binaires (macOS, Windows, Linux)

Ce document récapitule les défis techniques et les modifications nécessaires pour transformer VisionNodes Studio en une application autonome (.app, .exe) distribuable sans installation manuelle de Python.

## 1. Architecture du Moteur (Stratégie "Blender")
Pour garantir le fonctionnement chez l'utilisateur final, nous devons adopter une structure où Python est intégré.

- [ ] **Python Sidecar** : Utiliser `PyInstaller` ou `Nuitka` pour transformer `engine/engine.py` en un exécutable binaire indépendant.
- [ ] **Interpréteur Embarqué** : Inclure un dossier `python_env` minimal à l'intérieur du bundle de l'application.
- [ ] **Gestion des Chemins** : Modifier `engine.py` pour qu'il calcule ses chemins (plugins, modèles) à partir de `sys.executable` ou `sys._MEIPASS` au lieu de chemins relatifs au dossier de dev.

## 2. Gestion des Dépendances
Le système actuel de `pip install` à la volée doit évoluer pour la production.

- [ ] **Division Core / Plugins** : 
    - **Core** (à empaqueter d'office) : `numpy`, `opencv-python`, `pillow`, `scipy`.
    - **Dynamique** (à charger à la volée) : `mediapipe`, `librosa`, `torch`.
- [ ] **Dossier de Librairies Utilisateur** : Modifier le système de vérification des dépendances pour qu'il installe les nouveaux modules dans un dossier autorisé en écriture (ex: `~/Library/Application Support/VisionNodes/libs` ou `%AppData%/VisionNodes/libs`) plutôt que dans le dossier d'installation de l'app.
- [ ] **Isolation du sys.path** : Ajouter ce dossier utilisateur au `sys.path` au démarrage du moteur.

## 3. Intégration Tauri
- [ ] **Resource Bundling** : Configurer `tauri.conf.json` pour inclure le binaire Python et les dossiers de plugins dans les `resources`.
- [ ] **Communication** : S'assurer que le port WebSocket (8765) est libre ou utiliser un port dynamique communiqué par le moteur au frontend lors du lancement.

## 4. Sécurité et Signature
- [ ] **Signature de Code** : Nécessaire pour éviter les blocages SmartScreen (Windows) et Gatekeeper (macOS).
- [ ] **Notarisation Apple** : Indispensable pour distribuer sur Mac. Nécessite un compte Apple Developer et un script de signature pour tous les binaires Python inclus.

## 5. Défis Spécifiques par Plateforme
- **Windows** : S'assurer que les runtimes Visual C++ sont inclus ou installés via le `.msi`.
- **macOS** : Gérer les architectures Intel (x64) et Apple Silicon (arm64) séparément ou via un binaire "Universal".
- **Linux** : Utiliser le format `AppImage` pour éviter les conflits de librairies système (`libstdc++`, etc.).
