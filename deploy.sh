#!/usr/bin/env bash
# Deploy xbindkeys config and restart xbindkeys

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cp "$SCRIPT_DIR/dot_xbindkeysrc" ~/.xbindkeysrc
echo "Copied dot_xbindkeysrc to ~/.xbindkeysrc"

killall xbindkeys 2>/dev/null
xbindkeys
echo "xbindkeys restarted"
