# Classroom CSI Calibration Record — 2026-08-14

This document records the exact working configuration, commands, measurements,
and recovery steps from the classroom CSI session on 2026-08-14. Use it to
restore the same setup for the next classroom test.

## 1. Verified physical and network topology

```text
Classroom AP  ~~~ 5 GHz beacon frames through tripwire ~~~>  Pi 5 wlan0
                                                               |
Windows laptop <====== USB-A to Pi USB-C Ethernet =============+
```

- The Pi does not need Ethernet, classroom Wi-Fi association, or internet.
- `wlan0` is dedicated to Nexmon CSI monitor mode.
- The laptop-to-Pi management path is private USB Ethernet.
- The Pi USB-C port supplies power and carries USB Ethernet data.

Verified private USB network:

```text
Pi usb0:              10.12.194.1/28
Windows Ethernet 2:   10.12.194.2/28
Gateway/DNS:          none
```

Verified Pi services:

```text
signally-usb0.service: enabled and active
ssh.service:           enabled
usb0:                  UP, 10.12.194.1/28
```

SSH from Windows:

```powershell
ssh -i C:\Users\idani\.ssh\signally_codex idanyo@10.12.194.1
```

If Windows loses the static USB address, run PowerShell as Administrator:

```powershell
netsh interface ipv4 set address `
  name="Ethernet 2" `
  source=static `
  address=10.12.194.2 `
  mask=255.255.255.240 `
  gateway=none
```

Confirm the link:

```powershell
ping 10.12.194.1
```

Expected replies are below 1 ms.

## 2. Verified classroom Wi-Fi source

Observed from the Windows laptop with `netsh wlan show interfaces`:

```text
SSID:          MTA WiFi
AP BSSID:      a8:f7:d9:59:b7:a1
Band:          5 GHz
Primary channel: 52
Bandwidth:     80 MHz (validated by decoded CSI, not assumed)
Radio type:    802.11ax
Beacon filter: 0x80
```

The old saved values were not valid for this classroom:

```text
Old channel/BSSID: 48/80, 50:6f:0c:0b:c2:d5
Earlier examples:  48/80, BA:A6:E6:83:23:CF and 8/20
```

## 3. Persistent Nexmon CSI configuration

The active Pi configuration is `/etc/default/signally-csi`:

```text
SIGNALLY_CSI_CHANNEL=52
SIGNALLY_CSI_BANDWIDTH=80
SIGNALLY_CSI_SOURCE_MAC=a8:f7:d9:59:b7:a1
SIGNALLY_CSI_FRAME_BYTE=0x80
```

The pre-classroom service configuration is backed up on the Pi at:

```text
/etc/default/signally-csi.pre-classroom-20260814
```

Reapply and verify the saved classroom configuration:

```bash
sudo systemctl daemon-reload
sudo systemctl enable signally-csi.service
sudo systemctl restart signally-csi.service

systemctl is-enabled signally-csi.service
systemctl is-active signally-csi.service
nexutil -Iwlan0 -k
nexutil -Iwlan0 -m
nmcli -f DEVICE,TYPE,STATE,CONNECTION device status
```

Expected state:

```text
signally-csi.service: enabled and active
chanspec:              0xe03a, 52/80
monitor:               1
wlan0:                 unmanaged
```

## 4. Required CSI health check

Run before every calibration or presentation:

```bash
cd ~/Signally/backend
sudo bash scripts/csi_check.sh 15 100
```

The classroom setup passed twice with:

```text
CSI_PACKETS=100
frames=100
subcarriers=256
0 packets dropped by kernel
UDP payload length=1042
PASS: real CSI frames were captured and decoded.
```

Observed raw decoder sanity metrics during configuration:

```text
Temporary 52/80 test:  MOTION_METRIC=1524.87
Persisted service test: MOTION_METRIC=2070.87
```

These raw metrics prove decoding works; they are not the sensitivity threshold.

## 5. Capture commands used

Authenticate `sudo` before pasting loops so later lines are not consumed by a
password prompt:

```bash
cd ~/Signally/backend
sudo -v
```

Initial empty captures:

```bash
for i in 1 2 3; do
  read -rp "Prepare empty/still room, then press Enter for empty_$i: "
  sudo bash scripts/csi_test.sh "empty_$i" 30
  echo "Finished empty_$i"
done
```

Initial crossing captures:

```bash
for i in 1 2 3; do
  read -rp "Prepare to cross, then press Enter for crossing_$i: "
  sudo bash scripts/csi_test.sh "crossing_$i" 30
  echo "Finished crossing_$i"
done
```

Improved-geometry retry captures:

```bash
for i in 1 2 3; do
  read -rp "Make everything completely still; press Enter for new_retry_empty_$i: "
  sudo bash scripts/csi_test.sh "new_retry_empty_$i" 30
  echo "Finished new_retry_empty_$i"
done

for i in 1 2 3; do
  read -rp "Prepare to repeatedly cross the direct AP-Pi line; press Enter for new_retry_crossing_$i: "
  sudo bash scripts/csi_test.sh "new_retry_crossing_$i" 30
  echo "Finished new_retry_crossing_$i"
done
```

During crossing captures, repeatedly cross the shortest direct AP-to-Pi line
for the full 30 seconds. Keep the AP, Pi, furniture, and doors fixed.

## 6. Comparison command

Always filter analysis to the classroom AP BSSID:

```bash
cd ~/Signally/backend

../.venv/bin/python scripts/csi_compare.py \
  /tmp/csi_new_retry_empty_1.pcap \
  /tmp/csi_new_retry_crossing_1.pcap \
  a8:f7:d9:59:b7:a1
```

Repeat for pairs 2 and 3. Also compare empty 1 to empty 2 and empty 2 to
empty 3 to measure quiet-room stability.

## 7. Initial dataset statistics

All captures contained only the selected AP source and decoded to 256
subcarriers.

| Capture | Frames | Normalized mean | Median | p95 |
|---|---:|---:|---:|---:|
| `empty_1` | 285 | 0.00056902471 | 0.00055814976 | 0.00066280050 |
| `crossing_1` | 288 | 0.00060647456 | 0.00060021358 | 0.00067574731 |
| `empty_2` | 288 | 0.00044609795 | 0.00043507346 | 0.00052410238 |
| `crossing_2` | 288 | 0.00047690627 | 0.00047762810 | 0.00052330360 |
| `empty_3` | 287 | 0.00047048058 | 0.00046793316 | 0.00049237380 |
| `crossing_3` | 288 | 0.00059329025 | 0.00059034072 | 0.00065493356 |

Initial crossing/empty normalized mean ratios:

```text
Pair 1: 1.066x
Pair 2: 1.069x
Pair 3: 1.261x
```

Initial empty stability ratios:

```text
empty_2 / empty_1: 0.784x
empty_3 / empty_2: 1.055x
```

Conclusion: the initial geometry did not separate motion reliably enough from
empty-room variation. No factor was accepted from this dataset.

Saved on the Pi at:

```text
~/csi_calibration/classroom_initial/
```

## 8. Improved `new_retry` dataset statistics

| Capture | Frames | Normalized mean | Median | p95 |
|---|---:|---:|---:|---:|
| `new_retry_empty_1` | 288 | 0.00045745298 | 0.00045142879 | 0.00052389847 |
| `new_retry_crossing_1` | 287 | 0.00059565538 | 0.00058723031 | 0.00073545714 |
| `new_retry_empty_2` | 290 | 0.00049306908 | 0.00049120976 | 0.00052168226 |
| `new_retry_crossing_2` | 286 | 0.00054510601 | 0.00055449913 | 0.00070414091 |
| `new_retry_empty_3` | 287 | 0.00036373367 | 0.00037005621 | 0.00040091394 |
| `new_retry_crossing_3` | 287 | 0.00053202940 | 0.00055776217 | 0.00063500830 |

Improved crossing/empty normalized mean ratios:

```text
Pair 1: 1.302x
Pair 2: 1.106x
Pair 3: 1.463x
```

Improved empty stability ratios:

```text
empty_2 / empty_1: 1.078x
empty_3 / empty_2: 0.738x
```

Interpretation:

- Empty-window p95 reached approximately 1.16x its local median.
- A factor near 1.10 risks empty-room false triggers.
- The previous room-derived factor 1.30 misses weaker classroom crossings.
- `1.20` was selected as the live-test compromise.
- The 15-second detection hold covers intermittent threshold crossings.

Saved on the Pi at:

```text
~/csi_calibration/classroom_new_retry/
```

## 9. Validated classroom sensitivity

The successfully live-tested classroom value is:

```text
SIGNALLY_CSI_BASELINE_FACTOR=1.20
```

The live test succeeded with an empty-room warmup followed by repeated direct
AP-to-Pi crossings. The detector stayed quiet during the baseline and detected
the crossings.

Start the isolated calibration backend:

```bash
cd ~/Signally/backend

sudo env \
  SIGNALLY_CSI_REAL_PROVIDER_ENABLED=true \
  SIGNALLY_CSI_BASELINE_FACTOR=1.20 \
  SIGNALLY_AUTO_START_MONITORING=false \
  SIGNALLY_AUTO_START_WIFI_PROBING=false \
  ../.venv/bin/python -m uvicorn signally.api.app:app \
  --host 0.0.0.0 --port 8000
```

Keep the tripwire empty and still for 30 seconds after backend startup so the
adaptive baseline is seeded from the current room state.

Watch the detector from a second SSH terminal:

```bash
while true; do
  curl -s http://127.0.0.1:8000/csi/status |
    python -c "import sys,json; d=json.load(sys.stdin); print('ready=',d['ready'],'current=',d['currently_detected'],'recent=',d['recently_detected'],'metric=',d['motion_metric'],'baseline=',d['baseline'],'threshold=',d['threshold'],'confidence=',d['confidence'],'frames=',d['frames_received'])"
  sleep 1
done
```

Expected behavior:

```text
Empty warmup: ready becomes true; current remains false
Crossing:     current becomes true
After motion: recent remains true for the 15-second hold, then clears
```

## 10. Full backend launch for this classroom

After calibration validation, launch the full backend with the classroom
factor explicitly supplied:

```bash
cd ~/Signally/backend

sudo env \
  SIGNALLY_CSI_REAL_PROVIDER_ENABLED=true \
  SIGNALLY_CSI_BASELINE_FACTOR=1.20 \
  SIGNALLY_LOCAL_ARP_SCAN_ENABLED=false \
  SIGNALLY_ARP_INGEST_TOKEN='REPLACE_WITH_SHARED_SECRET' \
  ../.venv/bin/python -m uvicorn signally.api.app:app \
  --host 0.0.0.0 --port 8000
```

Do not put the real ARP ingest secret in Git.

Start the frontend from Windows:

```powershell
cd C:\Signally\Signally\SignallyApp
$env:EXPO_PUBLIC_API_URL="http://10.12.194.1:8000"
npm.cmd start
```

## 11. Next-week restart checklist

1. Place the AP and Pi in the same geometry used for `new_retry`.
2. Connect laptop USB-A to Pi USB-C and wait for boot.
3. Confirm `ping 10.12.194.1` and SSH.
4. Confirm the laptop is observing `MTA WiFi`, BSSID
   `a8:f7:d9:59:b7:a1`, channel 52. If the BSSID/channel changed, recalibrate
   before using the saved values.
5. Restart `signally-csi.service` and require a passing 100-frame health check.
6. Run one new 30-second empty capture and one crossing capture.
7. Compare them against each other and against the saved `classroom_new_retry`
   captures.
8. Start the backend with `SIGNALLY_CSI_BASELINE_FACTOR=1.20`.
9. Hold the room empty/still for the first 30 seconds.
10. Verify at least three crossings and three quiet periods before the demo.

Quick commands:

```bash
cd ~/Signally/backend
sudo systemctl restart signally-csi.service
sudo bash scripts/csi_check.sh 15 100
```

Do not proceed if the health check fails, the AP BSSID/channel changed, or the
empty-room baseline is unstable.

## 12. Timekeeping note

During this session, the Windows date was 2026-08-14 while the Pi logs and pcap
timestamps reported 2026-08-08. Correct or account for the Pi clock before
future evidence correlation and presentation logging.
