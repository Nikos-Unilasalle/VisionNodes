#!/bin/bash

# --- VISION NODES SETUP SCRIPT ---
# Installs Node, Rust/Tauri, and Python environments.

set -e

RESET='\033[0m'
BOLD='\033[1m'
GREEN='\033[32m'
BLUE='\033[34m'
YELLOW='\033[33m'
RED='\033[31m'

echo -e "${BOLD}${BLUE}🚀 Starting VisionNodes Unified Setup...${RESET}\n"

# ── 1. Node.js ────────────────────────────────────────────────────────────────
echo -e "${BOLD}[1/5] Checking Frontend Dependencies...${RESET}"
if ! command -v node &> /dev/null; then
    echo -e "${RED}❌ Node.js not found. Please install it from https://nodejs.org/${RESET}"
    exit 1
fi
echo -e "${YELLOW}Installing npm packages...${RESET}"
npm install
echo -e "${GREEN}✅ Frontend dependencies installed.${RESET}\n"

# ── 2. Rust ───────────────────────────────────────────────────────────────────
echo -e "${BOLD}[2/5] Checking Rust (Tauri)...${RESET}"
if ! command -v rustc &> /dev/null; then
    echo -e "${YELLOW}⚠️ Rust not found. Installing via rustup...${RESET}"
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source "$HOME/.cargo/env"
else
    echo -e "${GREEN}✅ Rust $(rustc --version) is already installed.${RESET}"
fi
echo ""

# ── 3. Python venv ───────────────────────────────────────────────────────────
echo -e "${BOLD}[3/5] Setting up Python Environment...${RESET}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ python3 not found. Please install Python 3.10+${RESET}"
    exit 1
fi

PYTHON_CMD="python3"
PY_VERSION=$($PYTHON_CMD -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")

if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}Creating virtual environment (.venv) with Python $PY_VERSION...${RESET}"
    # On Debian/Ubuntu, python3-venv may need to be installed separately.
    if ! $PYTHON_CMD -m venv .venv 2>/dev/null; then
        echo -e "${YELLOW}⚠️  python3-venv not found — trying to install it (requires sudo)...${RESET}"
        if command -v apt-get &> /dev/null; then
            sudo apt-get install -y "python${PY_VERSION}-venv"
        elif command -v apt &> /dev/null; then
            sudo apt install -y "python${PY_VERSION}-venv"
        else
            echo -e "${RED}❌ Could not install python3-venv automatically."
            echo -e "   Run: sudo apt install python${PY_VERSION}-venv${RESET}"
            exit 1
        fi
        $PYTHON_CMD -m venv .venv
    fi
    echo -e "${GREEN}✅ Virtual environment created.${RESET}"
else
    echo -e "${GREEN}✅ Virtual environment already exists.${RESET}"
fi

# ── 4. Python dependencies ────────────────────────────────────────────────────
echo -e "${BOLD}[4/5] Installing Python AI & Vision Libraries...${RESET}"
echo -e "${YELLOW}This may take a while (Torch, YOLO, SAM2 are heavy)...${RESET}"
.venv/bin/pip install --upgrade pip --quiet

# --no-build-isolation reuses already-downloaded packages (avoids re-downloading
# torch as a build dependency for packages like SAM-2 that build from source).
.venv/bin/pip install --no-build-isolation -r engine/requirements.txt

echo -e "${GREEN}✅ Python libraries installed.${RESET}\n"

# ── 5. Tesseract OCR ──────────────────────────────────────────────────────────
echo -e "${BOLD}[5/5] Checking System OCR (Tesseract)...${RESET}"
if command -v tesseract &> /dev/null; then
    echo -e "${GREEN}✅ Tesseract is already installed.${RESET}"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    if command -v brew &> /dev/null; then
        echo -e "${YELLOW}Installing tesseract via Homebrew...${RESET}"
        brew install tesseract
    else
        echo -e "${YELLOW}⚠️ Install tesseract manually: brew install tesseract${RESET}"
    fi
elif command -v apt-get &> /dev/null || command -v apt &> /dev/null; then
    echo -e "${YELLOW}Installing tesseract via apt...${RESET}"
    sudo apt-get install -y tesseract-ocr 2>/dev/null || sudo apt install -y tesseract-ocr
else
    echo -e "${YELLOW}⚠️ Tesseract not found. Install it for OCR node support.${RESET}"
fi

# ── Create required Tauri resource dirs (needed for the Rust build step) ──────
mkdir -p src-tauri/resources/pyengine src-tauri/resources/engine
touch src-tauri/resources/pyengine/.gitkeep src-tauri/resources/engine/.gitkeep

echo -e "\n${BOLD}${GREEN}🎉 Setup Complete!${RESET}"
echo -e "------------------------------------------------"
echo -e "Launch the Studio with:"
echo -e "  ${BOLD}npm run studio${RESET}"
echo -e "------------------------------------------------"
