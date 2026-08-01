#!/bin/bash
# Discover the dominant beacon source on a known channel and persist it.
# Usage: sudo bash ./csi_configure.sh <channel> [bandwidth] [scan-seconds]
set -euo pipefail

CHANNEL="${1:-}"
BANDWIDTH="${2:-80}"
SCAN_SECONDS="${3:-8}"
INTERFACE="${SIGNALLY_CSI_INTERFACE:-wlan0}"
PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PCAP="/tmp/signally_csi_source_scan.pcap"
CONFIG="/etc/default/signally-csi"

if [ "$(id -u)" -ne 0 ]; then
  echo "Run with sudo: sudo bash $0 <channel> [bandwidth] [scan-seconds]" >&2
  exit 2
fi
if [ -z "$CHANNEL" ]; then
  echo "Give the Wi-Fi channel shown on the phone, for example: sudo bash $0 48 80" >&2
  exit 2
fi

echo "[csi-configure] listening to all beacons on channel ${CHANNEL}/${BANDWIDTH}..."
bash "$PROJECT_ROOT/backend/scripts/csi_capture.sh" "$CHANNEL" "$BANDWIDTH" "" "0x80"
rm -f "$PCAP"
timeout --signal=INT "$SCAN_SECONDS" \
  tcpdump -ni "$INTERFACE" -w "$PCAP" dst port 5500 || true

SOURCE_MAC="$("$PROJECT_ROOT/.venv/bin/python" \
  "$PROJECT_ROOT/backend/scripts/csi_find_source.py" "$PCAP")"

printf '%s\n' \
  "SIGNALLY_CSI_CHANNEL=$CHANNEL" \
  "SIGNALLY_CSI_BANDWIDTH=$BANDWIDTH" \
  "SIGNALLY_CSI_SOURCE_MAC=$SOURCE_MAC" \
  "SIGNALLY_CSI_FRAME_BYTE=0x80" > "$CONFIG"

systemctl daemon-reload
systemctl restart signally-csi.service
echo "[csi-configure] saved dominant beacon $SOURCE_MAC on channel ${CHANNEL}/${BANDWIDTH}."
echo "[csi-configure] configuration: $CONFIG"
