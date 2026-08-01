#!/bin/bash
# Arm nexmon_csi on the Raspberry Pi's onboard BCM43455 radio.
set -euo pipefail

CHANNEL="${1:-8}"
BANDWIDTH="${2:-20}"
INTERFACE="${SIGNALLY_CSI_INTERFACE:-wlan0}"

if [ "$(id -u)" -ne 0 ]; then
  echo "Run this script as root (sudo $0 [channel] [bandwidth])." >&2
  exit 1
fi

# Keep NetworkManager from retuning the dedicated CSI radio.
nmcli dev disconnect "$INTERFACE" >/dev/null 2>&1 || true
nmcli dev set "$INTERFACE" managed no
ip link set "$INTERFACE" up

params="$(makecsiparams -c "${CHANNEL}/${BANDWIDTH}" -C 1 -N 1)"
nexutil -I"$INTERFACE" -s500 -b -l34 -v"$params"
nexutil -I"$INTERFACE" -m1

echo "CSI armed on ${INTERFACE}, channel ${CHANNEL}/${BANDWIDTH} MHz"
nexutil -I"$INTERFACE" -k
nexutil -I"$INTERFACE" -m
