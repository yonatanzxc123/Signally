#!/bin/bash
set -e

IFACE="wlx803f5d168019"

echo "[1/4] Releasing interface from NetworkManager..."
sudo nmcli dev set "$IFACE" managed no

echo "[2/4] Bringing interface down..."
sudo ip link set "$IFACE" down

echo "[3/4] Setting monitor mode..."
sudo iw dev "$IFACE" set type monitor

echo "[4/4] Bringing interface up..."
sudo ip link set "$IFACE" up

# Verify
MODE=$(iw dev "$IFACE" info | grep "type" | awk '{print $2}')
if [ "$MODE" = "monitor" ]; then
  echo ""
  echo "Done — $IFACE is in monitor mode."
  echo "Now run: sudo .venv/bin/python main.py serve-api --host 0.0.0.0 --port 8000"
else
  echo ""
  echo "WARNING: expected monitor mode but got: $MODE"
  exit 1
fi
