#!/usr/bin/env bash
# Aktualizace repo + instalace requirements v Linuxu

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
cd "$SCRIPT_DIR"

echo "🔄 Git update..."
git fetch --all
git reset --hard HEAD
git pull

echo "🐍 Aktivace virtuálního prostředí..."
# shellcheck source=/dev/null
source "$SCRIPT_DIR/.venv/bin/activate"

echo "📦 Instalace Python závislostí..."
pip install -r requirements.txt

echo "✅ Hotovo."
read -p "Stiskni Enter pro ukončení..."