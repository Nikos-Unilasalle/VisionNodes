# 🚀 VisionNodes - Installation Guide

Ce guide explique comment installer VisionNodes Studio sur votre machine (macOS recommandé).

## 📋 Prérequis

Avant de commencer, assurez-vous d'avoir installé :
- **Node.js** (v18+) : [https://nodejs.org/](https://nodejs.org/)
- **Rust** : [https://rustup.rs/](https://rustup.rs/) (nécessaire pour Tauri)
- **Python** (v3.10+) : [https://python.org/](https://python.org/)

## ⚡ Installation Rapide (One-Click)

Nous avons inclus un script automatisé qui s'occupe de tout (Node, Python Venv, AI Libraries).

```bash
# 1. Ouvrez un terminal dans le dossier du projet
# 2. Lancez l'installation unifiée
npm run setup
```

## 🔍 Ce que fait l'installation :
1. **Frontend** : Installe les dépendances React et Lucide.
2. **Rust** : Vérifie que le compilateur Tauri est prêt.
3. **Python (Isolé)** : Crée un environnement virtuel(`.venv`) et installe :
   - **OpenCV** (Traitement d'image)
   - **MediaPipe** (Face & Hand Tracking)
   - **YOLOv11** & **Torch** (IA & Détection d'objets)
   - **Pytesseract** (OCR)
4. **OCR** : Installe le moteur Tesseract via Homebrew (sur macOS).

## 🎬 Lancer le Studio

Une fois l'installation terminée, vous pouvez lancer l'application à tout moment avec :

```bash
npm run studio
```

## 🛠️ Résolution des problèmes

### Problème : Erreur Tesseract (OCR)
Si le nœud OCR affiche une erreur, vérifiez que Tesseract est installé manuellement :
```bash
brew install tesseract
```

### Problème : Accès Caméra
Sur macOS, la première fois que vous lancez l'application, le système vous demandera l'autorisation d'accéder à la caméra. Si l'image reste noire, vérifiez les permissions dans `Réglages Système > Confidentialité et sécurité > Appareil photo`.

---
© 2026 VisionNodes Studio
