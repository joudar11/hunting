#!/usr/bin/env bash
# Instalace/aktualizace projektu do ~/Documents (nebo lokalizovaných Dokumentů)

set -euo pipefail

# Najdi složku Dokumenty (funguje i na lokalizovaných systémech)
if command -v xdg-user-dir >/dev/null 2>&1; then
  DOCS_DIR="$(xdg-user-dir DOCUMENTS || echo "$HOME/Documents")"
else
  DOCS_DIR="$HOME/Documents"
fi
mkdir -p "$DOCS_DIR"

REPO_NAME="hb_scraper"
REPO_URL="https://github.com/joudar11/hunting"
REPO_DIR="$DOCS_DIR/$REPO_NAME"

echo "📂 Cílová složka: $REPO_DIR"

# Clone nebo update
if [[ -d "$REPO_DIR/.git" ]]; then
  echo "🔄 Repo existuje – provádím update…"
  git -C "$REPO_DIR" fetch --all
  git -C "$REPO_DIR" reset --hard HEAD
  git -C "$REPO_DIR" pull
else
  echo "📥 Klonuji repo…"
  git clone "$REPO_URL" "$REPO_DIR"
fi

cd "$REPO_DIR"

# Vytvoř venv pokud chybí
if [[ ! -d ".venv" ]]; then
  echo "🐍 Vytvářím virtualenv…"
  python3 -m venv .venv
fi

# Aktivace venv
# shellcheck source=/dev/null
source .venv/bin/activate
export VIRTUAL_ENV_DISABLE_PROMPT=1

echo "⬆️ Upgraduji pip…"
python -m pip install --upgrade pip

echo "📦 Instalace závislostí…"
pip install -r requirements.txt

# Přejmenuj data_sample.py -> data.py pouze pokud data.py ještě neexistuje
if [[ -f "data_sample.py" && ! -f "data.py" ]]; then
  echo "📁 Kopíruji data_sample.py → data.py"
  cp data_sample.py data.py
fi

# Deaktivace venv
type deactivate >/dev/null 2>&1 && deactivate || true

echo "✅ Hotovo. Projekt je v: $REPO_DIR"
# echo "   Spuštění:  bash $REPO_DIR/spustit_plny_zavod.sh  (nebo tvůj run skript)"
read -r -p "Stiskni Enter pro ukončení…"
