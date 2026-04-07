#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${CONFIG_FILE:-$SCRIPT_DIR/dot_xbindkeysrc}"
DEPLOY_SCRIPT="${DEPLOY_SCRIPT:-$SCRIPT_DIR/deploy.sh}"

if [[ ! -f "$CONFIG_FILE" ]]; then
  echo "Missing config file: $CONFIG_FILE" >&2
  exit 1
fi

if [[ ! -f "$DEPLOY_SCRIPT" ]]; then
  echo "Missing deploy script: $DEPLOY_SCRIPT" >&2
  exit 1
fi

read -r -p "Enter new macro text for Control+F1: " macro_text

if [[ -z "$macro_text" ]]; then
  echo "Macro text cannot be empty." >&2
  exit 1
fi

macro_b64="$(printf '%s' "$macro_text" | base64 -w 0)"
replacement="\"/usr/bin/env MACRO_B64=$macro_b64 /usr/bin/bash -lc 'sleep 0.08; /usr/bin/xdotool type --clearmodifiers -- \"\$(printf %s \"\$MACRO_B64\" | base64 -d)\"; /usr/bin/xdotool keyup Control_L Control_R; /usr/bin/xdotool key Return'\""

tmp_file="$(mktemp)"
cleanup() {
  rm -f "$tmp_file"
}
trap cleanup EXIT

REPLACEMENT_LINE="$replacement" perl -0e '
  my $replacement = $ENV{REPLACEMENT_LINE};
  local $/;
  $_ = <>;
  my $count = s/^".*?"\n([ \t]*control \+ F1[ \t]*)$/$replacement\n$1/m;
  die "control + F1 binding not found\n" unless $count;
  print;
' "$CONFIG_FILE" > "$tmp_file"

mv "$tmp_file" "$CONFIG_FILE"
trap - EXIT

bash "$DEPLOY_SCRIPT"
