#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

ensure_cmd() {
  local cmd="$1"
  local hint="$2"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Missing: $cmd"
    echo "$hint"
    return 1
  fi
  return 0
}

install_with_brew() {
  local formula="$1"
  local cask="$2"
  if command -v brew >/dev/null 2>&1; then
    if [ -n "$cask" ]; then
      brew install --cask "$cask"
    else
      brew install "$formula"
    fi
  else
    return 1
  fi
}

install_with_apt() {
  local package="$1"
  if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update
    sudo apt-get install -y "$package"
  else
    return 1
  fi
}

blender_version_ok() {
  if ! command -v blender >/dev/null 2>&1; then
    return 1
  fi
  local version
  version="$(blender --version 2>/dev/null | head -n 1 | awk '{print $2}')"
  if [ -z "$version" ]; then
    return 1
  fi
  local major minor
  major="${version%%.*}"
  minor="${version#*.}"
  minor="${minor%%.*}"
  if [ "$major" -ge 5 ]; then
    return 1
  fi
  if [ "$major" -ge 4 ]; then
    return 0
  fi
  if [ "$major" -eq 3 ] && [ "$minor" -ge 6 ]; then
    return 0
  fi
  return 1
}

remove_blender_5x() {
  if ! command -v blender >/dev/null 2>&1; then
    return 0
  fi
  local version
  version="$(blender --version 2>/dev/null | head -n 1 | awk '{print $2}')"
  if [ -z "$version" ]; then
    return 0
  fi
  local major
  major="${version%%.*}"
  if [ "$major" -lt 5 ]; then
    return 0
  fi
  echo "Detected Blender ${version} (5.x). Removing to allow 3.6/4.x install..."
  if command -v brew >/dev/null 2>&1; then
    brew uninstall --cask blender || true
  fi
  if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get remove -y blender || true
  fi
  if command -v blender >/dev/null 2>&1; then
    local post_version
    post_version="$(blender --version 2>/dev/null | awk '{print $2}')"
    if [ -n "$post_version" ] && [ "${post_version%%.*}" -ge 5 ]; then
      echo "Blender 5.x still present. Please remove it manually and re-run."
      exit 1
    fi
  fi
  return 0
}

brew_cask_exists() {
  local cask="$1"
  if ! command -v brew >/dev/null 2>&1; then
    return 1
  fi
  brew info --cask "$cask" >/dev/null 2>&1
}

install_blender_with_brew() {
  local candidates=("blender@4" "blender@lts" "blender@3.6")
  local cask
  for cask in "${candidates[@]}"; do
    if brew_cask_exists "$cask"; then
      brew install --cask "$cask"
      return 0
    fi
  done
  return 1
}

echo "== Python deps =="
ensure_cmd python3 "Install Python 3.9+ and ensure python3 is on PATH." || exit 1

if [ ! -d "venv" ]; then
  python3 -m venv venv
fi
# shellcheck disable=SC1091
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# shellcheck disable=SC1091
deactivate

echo "== Node.js deps =="
if ! ensure_cmd node "Install Node.js 18+ (recommended)."; then
  if ! install_with_brew node ""; then
    if ! install_with_apt nodejs; then
      exit 1
    fi
  fi
fi

if ! ensure_cmd npm "Install npm (bundled with Node.js)."; then
  exit 1
fi

# Install Cesium 3D Tiles tools globally for faster runs; npx still works.
if ! command -v 3d-tiles-tools >/dev/null 2>&1; then
  npm install -g 3d-tiles-tools
fi

echo "== Blender =="
remove_blender_5x
if ! ensure_cmd blender "Install Blender 3.6 or 4.x (COLLADA export required)."; then
  if ! install_blender_with_brew; then
    if ! install_with_apt blender; then
      echo "Unable to install Blender 3.6/4.x automatically. Please install Blender LTS (4.x) manually."
      exit 1
    fi
  fi
fi

if ! blender_version_ok; then
  echo "Blender 3.6 or 4.x is required for COLLADA export. Blender 5.x is not supported."
  exit 1
fi

echo "All dependencies installed."
