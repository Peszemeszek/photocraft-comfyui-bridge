#!/usr/bin/env bash
# Starts PhotoCraft with the control channel for the ComfyUI bridge, plus the bridge window.
#   ./photocraft-ai.sh [files to open…]
# Env: PCC_PORT (default 7878), PCC_NO_GUI=1 (no bridge window), PHOTOCRAFT (path to the binary)
set -euo pipefail

CONF="${XDG_CONFIG_HOME:-$HOME/.config}/pccomfy"
XCH="$HOME/.cache/pccomfy/exchange"
PORT="${PCC_PORT:-7878}"
PHOTOCRAFT="${PHOTOCRAFT:-photocraft}"
HERE="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"

mkdir -p "$CONF/workflows" "$XCH"

"$PHOTOCRAFT" \
  --control "$PORT" \
  --control-token-file "$CONF/photocraft.token" \
  --automation-read-root "$XCH" \
  --automation-write-root "$XCH" \
  "$@" &
PC_PID=$!

if [[ "${PCC_NO_GUI:-0}" != "1" ]]; then
  # wait (up to ~15 s) for PhotoCraft to start listening on the port
  for _ in $(seq 1 75); do
    (exec 3<>"/dev/tcp/127.0.0.1/$PORT") 2>/dev/null && break
    sleep 0.2
  done
  (cd "$HERE" && python -m pccomfy) &
  GUI_PID=$!
  trap 'kill "$GUI_PID" 2>/dev/null || true' EXIT
fi

wait "$PC_PID"
