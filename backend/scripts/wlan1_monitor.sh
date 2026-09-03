#!/bin/bash
# Puts the Wi-Fi probing adapter (default wlan1) into monitor mode at boot.
# Mirrors setup.sh's approach for the CSI-adjacent USB adapter, but for the
# probing interface specifically. Runs as root via systemd (see
# signally-wlan1-monitor.service) - no sudo needed here.
#
# Sleeps between steps are deliberate: without them, this can lose a race
# against NetworkManager reclaiming the interface before "iw ... set type
# monitor" takes effect, silently leaving it in managed mode (confirmed
# 2026-09-03 - probing reported "running: true" with no error while
# actually capturing nothing).
set -e

IFACE="${SIGNALLY_WIFI_PROBING_INTERFACE:-wlan1}"

echo "[1/4] Releasing $IFACE from NetworkManager..."
nmcli dev set "$IFACE" managed no
sleep 1

echo "[2/4] Bringing $IFACE down..."
ip link set "$IFACE" down
sleep 1

echo "[3/4] Setting monitor mode..."
iw dev "$IFACE" set type monitor
sleep 1

echo "[4/4] Bringing $IFACE up..."
ip link set "$IFACE" up
sleep 1

MODE=$(iw dev "$IFACE" info | grep "type" | awk '{print $2}')
if [ "$MODE" = "monitor" ]; then
  echo "Done - $IFACE is in monitor mode."
else
  echo "WARNING: expected monitor mode but got: $MODE"
  exit 1
fi
