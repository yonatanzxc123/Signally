#!/bin/bash
# Arm nexmon_csi on the Raspberry Pi's onboard BCM43455 radio.
set -euo pipefail

CHANNEL="${1:-${SIGNALLY_CSI_CHANNEL:-48}}"
BANDWIDTH="${2:-${SIGNALLY_CSI_BANDWIDTH:-80}}"
SOURCE_MAC="${3:-${SIGNALLY_CSI_SOURCE_MAC:-}}"
FRAME_BYTE="${4:-${SIGNALLY_CSI_FRAME_BYTE:-0x80}}"
INTERFACE="${SIGNALLY_CSI_INTERFACE:-wlan0}"

if [ "$(id -u)" -ne 0 ]; then
  echo "Run this script as root (sudo $0 [channel] [bandwidth] [source-mac] [frame-byte])." >&2
  exit 1
fi

# Keep NetworkManager from retuning the dedicated CSI radio.
rfkill unblock wifi
nmcli dev disconnect "$INTERFACE" >/dev/null 2>&1 || true
nmcli dev set "$INTERFACE" managed no
ip link set "$INTERFACE" up

param_args=(-c "${CHANNEL}/${BANDWIDTH}" -C 1 -N 1)
if [ -n "$SOURCE_MAC" ]; then
  param_args+=(-m "$SOURCE_MAC")
fi
if [ -n "$FRAME_BYTE" ]; then
  param_args+=(-b "$FRAME_BYTE")
fi
params="$(makecsiparams "${param_args[@]}")"
nexutil -I"$INTERFACE" -s500 -b -l34 -v"$params"
nexutil -I"$INTERFACE" -m1

echo "CSI armed on ${INTERFACE}, channel ${CHANNEL}/${BANDWIDTH} MHz"
[ -z "$SOURCE_MAC" ] || echo "CSI source filter: $SOURCE_MAC"
[ -z "$FRAME_BYTE" ] || echo "CSI frame-byte filter: $FRAME_BYTE"
nexutil -I"$INTERFACE" -k
nexutil -I"$INTERFACE" -m
