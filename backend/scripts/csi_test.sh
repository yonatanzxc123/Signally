#!/bin/bash
# Capture N Nexmon CSI frames and report their motion metric.
# Usage: sudo ./csi_test.sh <label> [nframes]
set -euo pipefail

LABEL="${1:-test}"
FRAME_COUNT="${2:-300}"
INTERFACE="${SIGNALLY_CSI_INTERFACE:-wlan0}"
PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PCAP="/tmp/csi_${LABEL}.pcap"

if [ "$(id -u)" -ne 0 ]; then
  echo "Run with sudo: sudo $0 <label> [nframes]" >&2
  exit 2
fi

echo "[csi-test] capturing $FRAME_COUNT CSI frames for '$LABEL' -- hold the scenario NOW..."
tcpdump -ni "$INTERFACE" -w "$PCAP" -c "$FRAME_COUNT" dst port 5500 2>/dev/null
"$PROJECT_ROOT/.venv/bin/python" \
  "$PROJECT_ROOT/backend/scripts/csi_validate.py" "$PCAP"
