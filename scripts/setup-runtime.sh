#!/usr/bin/env bash
set -euo pipefail
# Run as deck, not root. This installs only a project-owned venv, not SteamOS packages.
if [ "$(id -u)" = 0 ]; then
    printf 'Run this script as deck, without sudo.\n' >&2
    exit 1
fi
destination="$HOME/homebrew/data/DeckyLiveCaption/venv"
if [ -e "$destination" ]; then
    printf 'Runtime already exists: %s. Inspect it before replacing it.\n' "$destination" >&2
    exit 1
fi
python3 -m venv "$destination"
"$destination/bin/python" -m pip install 'Pillow==12.0.0' 'protobuf==6.33.1'
printf 'Set the plugin Python path to: %s/bin/python\n' "$destination"
printf 'Set model_dir to your existing Screen AI resources directory. Models are not bundled.\n'
