#!/bin/bash
# Bounded end-to-end Nexmon CSI diagnostic.
# Usage: sudo ./csi_check.sh [seconds] [max_frames]
set -euo pipefail

DURATION="${1:-30}"
MAX_FRAMES="${2:-20}"
INTERFACE="${SIGNALLY_CSI_INTERFACE:-wlan0}"
PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PCAP="/tmp/signally_csi_check.pcap"

if [ "$(id -u)" -ne 0 ]; then
  echo "Run with sudo: sudo $0 [seconds] [max_frames]" >&2
  exit 2
fi

echo "=== CSI state ==="
systemctl is-active signally-csi.service
nexutil -I"$INTERFACE" -k
nexutil -I"$INTERFACE" -m

echo "=== Capturing for up to ${DURATION}s / ${MAX_FRAMES} frames ==="
rm -f "$PCAP"
timeout --signal=INT "$DURATION" tcpdump -ni "$INTERFACE" -w "$PCAP" \
  -c "$MAX_FRAMES" dst port 5500 2>&1 || true

packet_count="$(tcpdump -nn -r "$PCAP" 2>/dev/null | wc -l)"
echo "CSI_PACKETS=$packet_count"

if [ "$packet_count" -eq 0 ]; then
  echo "FAIL: firmware is armed, but no CSI frames arrived."
  echo "Generate Wi-Fi traffic on the configured channel and retry."
  exit 1
fi

echo "=== First packets ==="
tcpdump -nn -r "$PCAP" 2>/dev/null | head -5

echo "=== Decode ==="
"$PROJECT_ROOT/.venv/bin/python" \
  "$PROJECT_ROOT/backend/scripts/csi_validate.py" "$PCAP"

if [ "$packet_count" -lt "$MAX_FRAMES" ]; then
  echo "FAIL: captured only ${packet_count}/${MAX_FRAMES} requested CSI frames in ${DURATION}s."
  echo "The decoded frames are real, but the CSI source is not sustained enough."
  exit 1
fi

echo "PASS: real CSI frames were captured and decoded."
