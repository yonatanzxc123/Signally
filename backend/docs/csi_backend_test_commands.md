# CSI and Backend Test Commands

This is the copy/paste command sheet for testing Signally on the Raspberry Pi.
Run commands in the section whose heading names the correct machine.

## Windows-Only Frontend and Auth Testing

You can run the backend locally without the Pi when testing authentication,
navigation, general frontend changes, and mock CSI behavior. Open PowerShell:

```powershell
cd D:\Signally\backend
$env:SIGNALLY_CSI_REAL_PROVIDER_ENABLED="false"
$env:SIGNALLY_AUTO_START_MONITORING="false"
$env:SIGNALLY_AUTO_START_WIFI_PROBING="false"
.\.venv\Scripts\python.exe -m uvicorn signally.api.app:app --host 0.0.0.0 --port 8000
```

Disabling the two background hardware loops prevents Windows from attempting Pi
ARP/probe operations. The existing Windows `backend/signally.db` supplies the
local auth and device data; it is separate from the Pi's database.

Confirm the Windows backend in another PowerShell:

```powershell
curl.exe http://127.0.0.1:8000/system/state
```

For an Android Studio emulator, start Expo with Android's host-machine alias:

```powershell
cd D:\Signally\SignallyApp
$env:EXPO_PUBLIC_API_URL="http://10.0.2.2:8000"
npx expo start -c
```

For Expo Web instead, use:

```powershell
$env:EXPO_PUBLIC_API_URL="http://127.0.0.1:8000"
npx expo start --web -c
```

Toggle mock CSI from another PowerShell to test frontend states:

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/csi/set `
  -ContentType application/json `
  -Body '{"detected":true}'
```

Clear mock motion:

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/csi/set `
  -ContentType application/json `
  -Body '{"detected":false}'
```

This workflow validates application behavior but not Nexmon capture, real CSI
calibration, monitor-mode probing, USB networking, or laptop ARP submission.

## 1. Update the Raspberry Pi

Run on the Pi:

```bash
cd ~/Signally
git pull
cd backend
../.venv/bin/pip install -r requirements.txt
```

Confirm the branch and working tree:

```bash
git branch --show-current
git status --short
```

## 2. Arm and Check Nexmon CSI

Restart the installed CSI capture service:

```bash
cd ~/Signally/backend
sudo systemctl restart signally-csi.service
sudo systemctl status signally-csi.service --no-pager -l
sudo ./scripts/csi_check.sh
```

If the service fails, inspect its log:

```bash
sudo journalctl -u signally-csi.service -n 100 --no-pager
```

Manually arm the currently calibrated access point when needed:

```bash
cd ~/Signally/backend
sudo bash scripts/csi_capture.sh 48 80 BA:A6:E6:83:23:CF 0x80
```

Confirm raw Nexmon packets are arriving:

```bash
sudo tcpdump -i wlan0 dst port 5500 -c 20
```

The BSSID, channel, bandwidth, and baseline factor must be recalibrated in the
classroom.

## 3. Start the Backend with Real CSI

Run on the Pi from `~/Signally/backend`:

```bash
cd ~/Signally/backend
sudo env \
  SIGNALLY_CSI_REAL_PROVIDER_ENABLED=true \
  ../.venv/bin/python -m uvicorn signally.api.app:app \
  --host 0.0.0.0 --port 8000
```

Uvicorn stays in the foreground while it is running. Keep this terminal open.
Press `Ctrl+C` once and wait for graceful shutdown when finished.

### Classroom laptop-ARP architecture

Disable the Pi's local ARP scanner and configure the shared ingest token:

```bash
cd ~/Signally/backend
sudo env \
  SIGNALLY_CSI_REAL_PROVIDER_ENABLED=true \
  SIGNALLY_LOCAL_ARP_SCAN_ENABLED=false \
  SIGNALLY_ARP_INGEST_TOKEN='REPLACE_WITH_SHARED_SECRET' \
  ../.venv/bin/python -m uvicorn signally.api.app:app \
  --host 0.0.0.0 --port 8000
```

Do not put the real shared secret in Git.

## 4. Find and Test the Pi Address

On the Pi:

```bash
hostname -I
```

Test locally on the Pi:

```bash
curl http://127.0.0.1:8000/system/state
```

From Windows, replace `PI_IP` with the reachable Pi Ethernet or USB address:

```cmd
curl http://PI_IP:8000/system/state
```

For the configured private USB-Ethernet link, connect from Windows with the
dedicated SSH key:

```powershell
ssh -i C:\Users\idani\.ssh\signally_codex idanyo@10.12.194.1
```

Remember: `127.0.0.1` on Windows refers to Windows, not the Pi.

## 5. Inspect CSI Health

Readable full status on the Pi:

```bash
curl -s http://127.0.0.1:8000/csi/status | python -m json.tool
```

Important fields:

- `provider_mode` should be `real`.
- `receiving_data` should be `true`.
- `ready` becomes `true` after quiet calibration.
- `currently_detected` is the live detector result.
- `recently_detected` includes the configured motion latch.
- `motion_metric` is compared with `threshold`.
- `invalid_frames` should normally remain zero.
- `last_error` should normally be `null`.

Watch the key values every two seconds:

```bash
while true; do curl -s http://127.0.0.1:8000/csi/status | python -c "import sys,json; d=json.load(sys.stdin); print('ready=',d['ready'],'current=',d['currently_detected'],'recent=',d['recently_detected'],'metric=',d['motion_metric'],'threshold=',d['threshold'],'confidence=',d['confidence'],'frames=',d['frames_received'],'invalid=',d['invalid_frames'])"; sleep 2; done
```

Stop the watch loop with `Ctrl+C`.

## 6. Inspect Correlation Evidence

Show the decision and whether CSI or probe activity is active:

```bash
curl -s http://127.0.0.1:8000/system/state | python -c "import sys,json; d=json.load(sys.stdin); print('mode:',d['security_mode']); print('decision:',d['decision']); print('reason:',d['reason']); print('approved:',d['approved_user_present']); print('CSI:',d['csi']['recently_detected']); print('probe:',d['probe_activity_detected']); print('probe observations:',d['probe_observation_count']); print('ARP healthy:',d['arp_scanner_healthy'])"
```

Expected CSI reason in Away mode:

```text
Physical presence detected while Away mode is armed.
```

Expected probe-only reason in Away mode:

```text
Unknown wireless activity detected nearby.
```

When both are active, CSI has decision priority, while both evidence flags remain
visible.

## 7. Change Home and Away Mode

Set Away mode from the Pi:

```bash
curl -s -X PUT http://127.0.0.1:8000/security-mode \
  -H 'Content-Type: application/json' \
  -H 'X-Signally-User-Role: ADMIN' \
  -d '{"mode":"AWAY"}' | python -m json.tool
```

Set Home mode:

```bash
curl -s -X PUT http://127.0.0.1:8000/security-mode \
  -H 'Content-Type: application/json' \
  -H 'X-Signally-User-Role: ADMIN' \
  -d '{"mode":"HOME"}' | python -m json.tool
```

Expected policy:

```text
HOME + CSI + approved presence -> SAFE
HOME + CSI without approved presence -> REVIEW
AWAY + CSI -> ALERT, regardless of approved ARP presence
AWAY + probe-only activity -> ALERT
```

CSI and randomized probe activity are evidence, not intruder/device counts.

## 8. Capture Empty and Moving CSI Samples

Run while the tripwire is empty and still:

```bash
cd ~/Signally/backend
sudo bash scripts/csi_test.sh empty 30
```

Run while crossing the tripwire:

```bash
sudo bash scripts/csi_test.sh moving 30
```

Compare the captures using the selected AP BSSID:

```bash
./.venv/bin/python scripts/csi_compare.py \
  /tmp/csi_empty.pcap /tmp/csi_moving.pcap \
  BA:A6:E6:83:23:CF
```

If this repository's virtual environment is one directory above `backend`, use:

```bash
../.venv/bin/python scripts/csi_compare.py \
  /tmp/csi_empty.pcap /tmp/csi_moving.pcap \
  BA:A6:E6:83:23:CF
```

## 9. Start the Frontend Emulator

First verify Windows can reach the Pi:

```cmd
curl http://PI_IP:8000/system/state
```

Start Expo from PowerShell with the same Pi address:

```powershell
cd D:\Signally\SignallyApp
$env:EXPO_PUBLIC_API_URL="http://PI_IP:8000"
echo $env:EXPO_PUBLIC_API_URL
npx expo start -c
```

The frontend refreshes correlated CSI/system state every second. During testing,
the Home screen should show `CSI calibrating`, `CSI online`, `CSI motion`, or
`CSI unavailable`.

If the app reports `Network request failed`, open this address in the emulator's
browser:

```text
http://PI_IP:8000/docs
```

Also watch the Uvicorn terminal for incoming requests.

## 10. Run the Laptop ARP Agent

Run from an elevated Windows PowerShell with Npcap installed. Replace the target,
Wi-Fi interface name, Pi USB address, and shared secret:

```powershell
cd D:\Signally\backend
$env:SIGNALLY_ARP_INGEST_TOKEN="REPLACE_WITH_SHARED_SECRET"
.\.venv\Scripts\python.exe scripts\laptop_arp_agent.py `
  --interface "Wi-Fi" `
  --target "10.100.102.0/24" `
  --backend "http://PI_USB_IP:8000" `
  --interval 10
```

Submit one scan only:

```powershell
.\.venv\Scripts\python.exe scripts\laptop_arp_agent.py `
  --interface "Wi-Fi" `
  --target "10.100.102.0/24" `
  --backend "http://PI_USB_IP:8000" `
  --token "REPLACE_WITH_SHARED_SECRET" `
  --once
```

Check scanner health on the Pi:

```bash
curl -s http://127.0.0.1:8000/arp/status | python -m json.tool
```

## 11. Verify Wi-Fi Probe Capture

Check interface and service state:

```bash
iw dev
nmcli device status
sudo systemctl status signally-csi.service --no-pager -l
```

Inspect the probing portion of system state:

```bash
curl -s http://127.0.0.1:8000/system/state | python -c "import sys,json; d=json.load(sys.stdin); print('probe active=',d['probe_activity_detected'],'observations=',d['probe_observation_count'])"
```

Probe requests are intermittent and clients often randomize MAC addresses. The
activity flag may become quiet when no accepted probe request has appeared in the
30-second rolling window; it is not a stable device count.

## 12. Run Automated Checks Before Pushing

Backend on Windows:

```powershell
cd D:\Signally\backend
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
```

Frontend:

```powershell
cd D:\Signally\SignallyApp
npm run typecheck
```

Repository diff check:

```powershell
cd D:\Signally
git diff --check
git status --short
```

## 13. Graceful Shutdown

For a foreground Uvicorn or watch process, press `Ctrl+C` once and wait. Pressing
it repeatedly can interrupt the Wi-Fi probing thread's shutdown and print a
harmless `KeyboardInterrupt` traceback.

