# Signally CSI Capture and Test Runbook

This is the presentation workflow for the Raspberry Pi 5 Nexmon CSI receiver.
It uses access-point beacon frames as the stable CSI source. The laptop does
not need to run `iperf3` in beacon mode.

The verified 2026-08-14 classroom topology, measurements, sensitivity, and
next-session recovery checklist are recorded in
[`classroom_csi_calibration_2026-08-14.md`](classroom_csi_calibration_2026-08-14.md).

## 1. Find the classroom router details

Connect a Windows laptop to the classroom Wi-Fi and run:

```powershell
netsh wlan show interfaces
```

Record these fields:

```text
AP BSSID : aa:bb:cc:dd:ee:ff
Channel  : 48
```

Use the AP BSSID, not the laptop's physical address.

## 2. Configure beacon CSI temporarily

Replace `48` and `aa:bb:cc:dd:ee:ff` with the classroom values:

```bash
sudo bash ~/Signally/backend/scripts/csi_capture.sh \
  48 80 aa:bb:cc:dd:ee:ff 0x80
```

The arguments are:

```text
channel bandwidth source-mac frame-byte
```

`0x80` selects 802.11 beacon frames.

If the BSSID is unavailable, the calibration helper can select the most
frequently observed beacon source on a known channel:

```bash
sudo bash ~/Signally/backend/scripts/csi_configure.sh 48 80 8
```

Manual BSSID selection is preferable in a room containing several access
points.

## 3. Make the configuration survive reboot

Edit the service environment:

```bash
sudo nano /etc/default/signally-csi
```

Set:

```text
SIGNALLY_CSI_CHANNEL=48
SIGNALLY_CSI_BANDWIDTH=80
SIGNALLY_CSI_SOURCE_MAC=aa:bb:cc:dd:ee:ff
SIGNALLY_CSI_FRAME_BYTE=0x80
```

Apply and enable it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable signally-csi.service
sudo systemctl restart signally-csi.service
```

## 4. Verify receiver state

```bash
systemctl is-enabled signally-csi.service
systemctl is-active signally-csi.service
nexutil -Iwlan0 -k
nexutil -Iwlan0 -m
nmcli -f DEVICE,TYPE,STATE,CONNECTION device status
```

Expected state:

```text
signally-csi.service: enabled and active
chanspec: selected channel/bandwidth
monitor: 1
wlan0: unmanaged
```

View the boot/service configuration log with:

```bash
journalctl -b -u signally-csi.service --no-pager
```

## 5. Run the bounded CSI health check

```bash
sudo bash ~/Signally/backend/scripts/csi_check.sh 15 100
```

A valid sustained source must end with:

```text
CSI_PACKETS=100
frames=100
subcarriers=256
PASS: real CSI frames were captured and decoded.
```

Do not collect calibration data if this command reports `FAIL`.

## 6. Capture quiet-room measurements

Keep the router, Pi, furniture, doors and people stationary during every empty
capture:

```bash
sudo bash ~/Signally/backend/scripts/csi_test.sh empty_1 30
sudo bash ~/Signally/backend/scripts/csi_test.sh empty_2 30
sudo bash ~/Signally/backend/scripts/csi_test.sh empty_3 30
```

The captures are written to:

```text
/tmp/csi_empty_1.pcap
/tmp/csi_empty_2.pcap
/tmp/csi_empty_3.pcap
```

## 7. Capture tripwire crossings

Keep the Pi and transmitter fixed. Walk across the intended tripwire several
times during each capture:

```bash
sudo bash ~/Signally/backend/scripts/csi_test.sh crossing_1 30
sudo bash ~/Signally/backend/scripts/csi_test.sh crossing_2 30
sudo bash ~/Signally/backend/scripts/csi_test.sh crossing_3 30
```

Also record doorway/outside controls when establishing the sensing boundary:

```bash
sudo bash ~/Signally/backend/scripts/csi_test.sh doorway_inside 30
sudo bash ~/Signally/backend/scripts/csi_test.sh hallway_outside 30
```

Reject and repeat any capture that fails the script's minimum-frame check.

## 8. Preserve captures outside `/tmp`

```bash
mkdir -p ~/csi_calibration
sudo cp /tmp/csi_empty_*.pcap /tmp/csi_crossing_*.pcap ~/csi_calibration/
sudo cp /tmp/csi_doorway_inside.pcap /tmp/csi_hallway_outside.pcap \
  ~/csi_calibration/ 2>/dev/null || true
sudo chown -R idanyo:idanyo ~/csi_calibration
```

Files in `/tmp` may disappear after reboot.

## 9. Compare quiet and crossing captures

```bash
cd ~/Signally/backend

./.venv/bin/python scripts/csi_compare.py \
  ~/csi_calibration/csi_empty_1.pcap \
  ~/csi_calibration/csi_crossing_1.pcap
```

Repeat for the other pairs:

```bash
./.venv/bin/python scripts/csi_compare.py \
  ~/csi_calibration/csi_empty_2.pcap \
  ~/csi_calibration/csi_crossing_2.pcap

./.venv/bin/python scripts/csi_compare.py \
  ~/csi_calibration/csi_empty_3.pcap \
  ~/csi_calibration/csi_crossing_3.pcap
```

Use the normalized mean, median, p95 and moving/empty ratio. The raw
`MOTION_METRIC` printed during capture is a decoder sanity check and should not
be used alone to choose the final threshold.

Before accepting a threshold, compare two empty captures as well. Their
normalized statistics should be reasonably similar:

```bash
./.venv/bin/python scripts/csi_compare.py \
  ~/csi_calibration/csi_empty_1.pcap \
  ~/csi_calibration/csi_empty_2.pcap
```

## 10. Decode one saved capture directly

```bash
cd ~/Signally/backend
./.venv/bin/python scripts/csi_validate.py \
  ~/csi_calibration/csi_empty_1.pcap
```

## 11. Recovery commands

Reapply the saved configuration:

```bash
sudo systemctl restart signally-csi.service
```

Inspect failures:

```bash
systemctl --no-pager --full status signally-csi.service
journalctl -u signally-csi.service -n 50 --no-pager
```

Confirm no normal Wi-Fi manager reclaimed `wlan0`:

```bash
nmcli device status
ps -ef | grep -E 'wpa_supplicant|hostapd|iwd' | grep -v grep
```

## Optional laptop-data experiment

This is not the presentation path. The tested Intel AX201 produced bursty CSI
even while IP traffic remained constant. To restore any temporary laptop-data
filter, restart the beacon service:

```bash
sudo systemctl restart signally-csi.service
```

