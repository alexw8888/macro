#!/usr/bin/env bash
# Install a native per-user app; no sudo or Python package downloads needed.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-/usr/bin/python3}"

if [[ "${1:-}" == "--help" ]]; then
  echo "Usage: ./install.sh"
  echo "Installs Text Macros for the current user, including a menu entry and login startup."
  exit 0
fi
if [[ $# -gt 0 ]]; then
  echo "Usage: ./install.sh" >&2
  exit 1
fi

if ! "$PYTHON" -c 'import gi; gi.require_version("Gtk", "3.0"); from gi.repository import Gtk' 2>/dev/null; then
  echo "Install dependencies: sudo apt install python3-gi gir1.2-gtk-3.0 xbindkeys xdotool" >&2
  exit 1
fi
for tool in xbindkeys xdotool; do
  if ! command -v "$tool" >/dev/null; then
    echo "Missing $tool. Install dependencies: sudo apt install python3-gi gir1.2-gtk-3.0 xbindkeys xdotool" >&2
    exit 1
  fi
done

"$PYTHON" - "$SCRIPT_DIR" <<'PY'
import os
from pathlib import Path
import shutil
import sys

source = Path(sys.argv[1])
data = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
config = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
target = data / "text-macros"
target.mkdir(parents=True, exist_ok=True)
for name in ("macro_app.py", "macro_core.py", "text-macros.svg"):
    if (source / name).resolve() != (target / name).resolve():
        shutil.copyfile(source / name, target / name)

# Desktop Exec has its own quoting rules, distinct from shell quoting.
def desktop_arg(value):
    value = str(value)
    if "\n" in value or "\r" in value:
        raise SystemExit("The installation path must not contain line breaks.")
    for char in ("\\", '"', "`", "$"):
        value = value.replace(char, "\\" + char)
    return '"' + value.replace("%", "%%").replace("\\", "\\\\") + '"'

python = desktop_arg(sys.executable)
icon = str(target / "text-macros.svg").replace("\\", "\\\\")
launcher = data / "applications/text-macros.desktop"
launcher.parent.mkdir(parents=True, exist_ok=True)
launcher.write_text(
    "[Desktop Entry]\nType=Application\nName=Text Macros\n"
    "Comment=Edit five text macros for Ctrl+F1 through Ctrl+F5\n"
    f"Exec={python} {desktop_arg(target / 'macro_app.py')}\n"
    f"Icon={icon}\nTerminal=false\nCategories=Utility;Accessibility;\n"
    "Keywords=keyboard;shortcut;text;macro;\nStartupNotify=true\n", encoding="utf-8",
)
startup = config / "autostart/text-macros.desktop"
startup.parent.mkdir(parents=True, exist_ok=True)
startup.write_text(
    "[Desktop Entry]\nType=Application\nName=Text Macros Shortcuts\n"
    f"Exec={python} {desktop_arg(target / 'macro_core.py')} --start-shortcuts\n"
    "Terminal=false\nX-GNOME-Autostart-enabled=true\n", encoding="utf-8",
)
print(f"Installed Text Macros in {target}")
print("Open Text Macros from your application menu, edit the five slots, then click Save & Apply.")
print("Saved shortcuts will be restored at login. An X11 session is required.")
PY
