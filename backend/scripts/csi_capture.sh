#!/bin/bash
# Arm nexmon_csi on the Raspberry Pi's onboard BCM43455 radio.
set -euo pipefail

CHANNEL="${1:-${SIGNALLY_CSI_CHANNEL:-48}}"
BANDWIDTH="${2:-${SIGNALLY_CSI_BANDWIDTH:-80}}"
SOURCE_MAC="${3:-${SIGNALLY_CSI_SOURCE_MAC:-}}"
FRAME_BYTE="${4:-${SIGNALLY_CSI_FRAME_BYTE:-0x80}}"
INTERFACE="${SIGNALLY_CSI_INTERFACE:-wlan0}"
MAX_ATTEMPTS="${SIGNALLY_CSI_ARM_MAX_ATTEMPTS:-4}"
UDP_PORT="${SIGNALLY_CSI_UDP_PORT:-5500}"

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

arm_once() {
  nexutil -I"$INTERFACE" -s500 -b -l34 -v"$params"
  nexutil -I"$INTERFACE" -m1
}

# A cold boot can lose a race here: nexutil reports success even when the
# radio/firmware hasn't finished settling, and no CSI frames actually flow.
# Confirmed 2026-09-03 - the exact same arming commands silently produced
# zero frames right after a cold reboot, but worked immediately when
# re-run a few minutes later with the radio already settled. Verify frames
# are actually flowing after arming, and retry the whole sequence (not
# just re-check) if not, rather than trusting nexutil's own success report.
attempt=1
while [ "$attempt" -le "$MAX_ATTEMPTS" ]; do
  if [ "$attempt" -gt 1 ]; then
    echo "Retry $attempt/$MAX_ATTEMPTS: re-arming after settling..."
    sleep 5
  else
    sleep 3  # let the radio settle after interface bring-up before first arm
  fi

  arm_once

  if timeout 5 tcpdump -i "$INTERFACE" -c 1 "dst port ${UDP_PORT}" >/dev/null 2>&1; then
    echo "CSI frames confirmed flowing on attempt $attempt."
    break
  fi

  if [ "$attempt" -eq "$MAX_ATTEMPTS" ]; then
    echo "WARNING: CSI armed but no frames observed after $MAX_ATTEMPTS attempts." >&2
    echo "Firmware is armed; the backend's own real/mock health fields will show it." >&2
  fi
  attempt=$((attempt + 1))
done

echo "CSI armed on ${INTERFACE}, channel ${CHANNEL}/${BANDWIDTH} MHz"
[ -z "$SOURCE_MAC" ] || echo "CSI source filter: $SOURCE_MAC"
[ -z "$FRAME_BYTE" ] || echo "CSI frame-byte filter: $FRAME_BYTE"
nexutil -I"$INTERFACE" -k
nexutil -I"$INTERFACE" -m
