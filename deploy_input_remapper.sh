#!/usr/bin/env bash
# Deploy the input-remapper presets and autoload config

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$SCRIPT_DIR/input-remapper"
CONFIG_DIR="${INPUT_REMAPPER_CONFIG_DIR:-$HOME/.config/input-remapper-2}"

if [[ ! -f "$REPO_DIR/config.json" ]]; then
  echo "Missing config file: $REPO_DIR/config.json" >&2
  exit 1
fi

if [[ ! -d "$REPO_DIR/presets" ]]; then
  echo "Missing presets directory: $REPO_DIR/presets" >&2
  exit 1
fi

mkdir -p "$CONFIG_DIR/presets"
cp -r "$REPO_DIR/presets/." "$CONFIG_DIR/presets/"
echo "Copied presets to $CONFIG_DIR/presets"

REPO_CONFIG="$REPO_DIR/config.json" TARGET_CONFIG="$CONFIG_DIR/config.json" python3 - <<'PY'
import json
import os

with open(os.environ["REPO_CONFIG"]) as file:
    repo_config = json.load(file)

target_path = os.environ["TARGET_CONFIG"]
try:
    with open(target_path) as file:
        target_config = json.load(file)
except FileNotFoundError:
    target_config = {}

target_config.setdefault("autoload", {}).update(repo_config.get("autoload", {}))
if repo_config.get("version"):
    target_config.setdefault("version", repo_config["version"])

with open(target_path, "w") as file:
    json.dump(target_config, file, indent=4)
    file.write("\n")

print(f"Updated autoload in {target_path}")
PY

if ! command -v input-remapper-control >/dev/null; then
  echo "input-remapper-control not found, install input-remapper to apply the presets" >&2
  exit 1
fi

input-remapper-control --config-dir "$CONFIG_DIR" --command autoload
echo "input-remapper presets applied"
