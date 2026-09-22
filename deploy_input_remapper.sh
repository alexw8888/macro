#!/usr/bin/env bash
# Deploy or revert the input-remapper presets and autoload config
# Usage: ./deploy_input_remapper.sh [--revert]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$SCRIPT_DIR/input-remapper"
CONFIG_DIR="${INPUT_REMAPPER_CONFIG_DIR:-$HOME/.config/input-remapper-2}"
REVERT=0

usage() {
  echo "Usage: $(basename "$0") [--revert]" >&2
  echo "  no args    copy presets and autoload config into $CONFIG_DIR" >&2
  echo "  --revert   remove the presets and autoload entries added by this repo" >&2
}

for arg in "$@"; do
  case "$arg" in
    --revert) REVERT=1 ;;
    -h|--help) usage; exit 0 ;;
    *) usage; exit 1 ;;
  esac
done

if [[ ! -f "$REPO_DIR/config.json" ]]; then
  echo "Missing config file: $REPO_DIR/config.json" >&2
  exit 1
fi

if [[ ! -d "$REPO_DIR/presets" ]]; then
  echo "Missing presets directory: $REPO_DIR/presets" >&2
  exit 1
fi

if [[ "$REVERT" -eq 1 ]]; then
  REPO_CONFIG="$REPO_DIR/config.json" TARGET_CONFIG="$CONFIG_DIR/config.json" python3 - <<'PY'
import json
import os
import shutil
import subprocess

with open(os.environ["REPO_CONFIG"]) as file:
    repo_config = json.load(file)

target_path = os.environ["TARGET_CONFIG"]
target_dir = os.path.dirname(target_path)
try:
    with open(target_path) as file:
        target_config = json.load(file)
except FileNotFoundError:
    target_config = {}

control = shutil.which("input-remapper-control")
changed = False

for device, preset in repo_config.get("autoload", {}).items():
    if control:
        subprocess.run(
            [
                control,
                "--config-dir",
                target_dir,
                "--command",
                "stop",
                "--device",
                device,
            ],
            check=False,
        )

    if target_config.get("autoload", {}).get(device) == preset:
        del target_config["autoload"][device]
        changed = True
        print(f'Removed autoload entry "{device}": "{preset}"')

    preset_path = os.path.join(target_dir, "presets", device, f"{preset}.json")
    if os.path.exists(preset_path):
        os.remove(preset_path)
        print(f"Removed {preset_path}")
        try:
            os.rmdir(os.path.dirname(preset_path))
        except OSError:
            pass

if changed:
    with open(target_path, "w") as file:
        json.dump(target_config, file, indent=4)
        file.write("\n")
    print(f"Updated autoload in {target_path}")
PY
  echo "input-remapper presets reverted"
  exit 0
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
