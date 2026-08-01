#!/bin/bash
# Capture Nexmon CSI for a fixed duration and report its motion metric.
# Usage: sudo bash ./csi_test.sh <label> [seconds]
set -euo pipefail

LABEL="${1:-test}"
SAFE_LABEL="${LABEL//[^a-zA-Z0-9_-]/_}"
DURATION="${2:-30}"
INTERFACE="${SIGNALLY_CSI_INTERFACE:-wlan0}"
PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PCAP="/tmp/csi_${SAFE_LABEL}.pcap"

if [ "$(id -u)" -ne 0 ]; then
  echo "Run with sudo: sudo bash $0 <label> [seconds]" >&2
  exit 2
fi

echo "[csi-test] capturing CSI for ${DURATION}s for '$LABEL' -- hold the scenario NOW..."
rm -f "$PCAP"
# SIGINT asks tcpdump to flush and close the pcap normally when the window ends.
timeout --signal=INT "$DURATION" \
  tcpdump -ni "$INTERFACE" -w "$PCAP" dst port 5500 || true

if [ ! -s "$PCAP" ]; then
  echo "No CSI frames were captured during the ${DURATION}s window." >&2
  exit 1
fi

"$PROJECT_ROOT/.venv/bin/python" \
  "$PROJECT_ROOT/backend/scripts/csi_validate.py" "$PCAP"
