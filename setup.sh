#!/bin/bash

# --- VISION NODES SETUP SCRIPT ---
# This script unifies the installation of Node, Rust/Tauri, and Python environments.

RESET='\033[0m'
BOLD='\033[1m'
GREEN='\033[32m'
BLUE='\033[34m'
YELLOW='\033[33m'
RED='\033[31m'

echo -e "${BOLD}${BLUE}🚀 Starting VisionNodes Unified Setup...${RESET}\n"

# 1. Check Node.js
echo -e "${BOLD}[1/5] Checking Frontend Dependencies...${RESET}"
if ! command -v node &> /dev/null; then
    echo -e "${RED}❌ Node.js not found. Please install it from https://nodejs.org/${RESET}"
    exit 1
fi
echo -e "${YELLOW}Installing npm packages...${RESET}"
npm install
echo -e "${GREEN}✅ Frontend dependencies installed.${RESET}\n"

# 2. Check Rust
echo -e "${BOLD}[2/5] Checking Rust (Tauri)...${RESET}"
if ! command -v rustc &> /dev/null; then
    echo -e "${YELLOW}⚠️ Rust not found. Tauri requires Rust.${RESET}"
    echo -e "Installing Rust via rustup..."
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source $HOME/.cargo/env
else
    echo -e "${GREEN}✅ Rust is already installed.${RESET}"
fi
echo ""

# 3. Setup Python Virtual Environment
echo -e "${BOLD}[3/5] Setting up Python Environment (Isolating AI libraries)...${RESET}"
PYTHON_CMD="python3"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ python3 not found. Please install Python 3.10+${RESET}"
    exit 1
fi

if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}Creating virtual environment in .venv...${RESET}"
    $PYTHON_CMD -m venv .venv
else
    echo -e "${GREEN}✅ Virtual environment already exists.${RESET}"
fi

# 4. Install Python Requirements
echo -e "${BOLD}[4/5] Installing Python AI & Vision Libraries...${RESET}"
echo -e "${YELLOW}This may take a while (Torch and YOLO are heavy)...${RESET}"
source .venv/bin/activate
pip install --upgrade pip
pip install -r engine/requirements.txt
echo -e "${GREEN}✅ Python libraries installed.${RESET}\n"

# 5. Check System OCR (Tesseract)
echo -e "${BOLD}[5/5] Checking System OCR (Tesseract)...${RESET}"
if [[ "$OSTYPE" == "darwin"* ]]; then
    if ! command -v tesseract &> /dev/null; then
        echo -e "${YELLOW}⚠️ Tesseract OCR binary not found.${RESET}"
        if command -v brew &> /dev/null; then
            echo -e "Installing tesseract via Homebrew..."
            brew install tesseract
        else
            echo -e "${RED}❌ Homebrew not found. Please install tesseract manually: brew install tesseract${RESET}"
        fi
    else
        echo -e "${GREEN}✅ Tesseract is already installed.${RESET}"
    fi
fi

echo -e "\n${BOLD}${GREEN}🎉 Setup Complete!${RESET}"
echo -e "------------------------------------------------"
echo -e "To start the Studio:"
echo -e "${BOLD}npm run studio${RESET}"
echo -e "------------------------------------------------"
