# Closed-Network Demo Runbook

This is the operating procedure for running Signally on a closed TP-Link
network with no internet uplink — the classroom Wi-Fi's client isolation was
blocking ARP discovery, so the TP-Link runs as its own isolated network
instead of bridging to the classroom LAN (the fallback already described in
`PLAN.md`'s "Fallback if the classroom LAN blocks discovery" section).

**Read this before you lose internet access.** Once the laptop joins the
closed network, there is no other connectivity available to troubleshoot
with — everything you need should be on this page or reachable from the Pi
over SSH.

## Topology

```text
Pi wlan0  -> passive Nexmon CSI monitor mode (unchanged, not on the closed network)
Pi wlan1  -> passive Wi-Fi probe monitor mode (unchanged, not on the closed network)
Pi usb0   -> static private link to the laptop, 10.12.194.1 (unchanged)

Laptop Wi-Fi -> joins the closed TP-Link network (ARP scanning + relay)
Laptop USB   -> 10.12.194.2, private link to the Pi (unchanged)

Phone Wi-Fi  -> joins the closed TP-Link network, talks to the laptop's
                relay (port 8000), which forwards to the Pi over USB
```

The Pi is never a member of the closed Wi-Fi network. The laptop is the only
device on both networks at once, and relays one port so the phone can reach
the Pi through it.

## Pre-flight (do this today, while you still have internet)

### 1. Router (TP-Link)
- Confirm no WAN/internet uplink is active.
- Confirm the DHCP server is on; note the LAN subnet and gateway.
- Add a DHCP reservation ("Address Reservation" under DHCP settings) for
  the **laptop's Wi-Fi MAC address** — find it with `ipconfig /all` on the
  laptop (look for the Wi-Fi adapter's "Physical Address"). This is the one
  address that must stay fixed, since it's what goes in the phone's
  connection panel.
- Note the current channel/band. If it changed from the last classroom
  calibration (`classroom_csi_calibration_2026-08-14.md`: channel 52/80MHz,
  `MTA WiFi` / `a8:f7:d9:59:b7:a1`), CSI needs a recheck (step 3 below).

### 2. SSH into the Pi
1. Plug the Pi into the laptop via USB-C (powers it and carries the private
   gadget network). Wait ~30-60s after power-on.
2. Confirm the laptop's USB Ethernet adapter has its static address:
   ```powershell
   ipconfig | findstr /C:"10.12.194"
   ```
   If it doesn't show `10.12.194.2`, re-set it (this has happened before):
   ```powershell
   netsh interface ipv4 set address name="Ethernet 2" source=static address=10.12.194.2 mask=255.255.255.240 gateway=none
   ```
   (Check `Get-NetAdapter` if the adapter name isn't `Ethernet 2` anymore.)
3. `ping 10.12.194.1` — expect replies under 1ms.
4. SSH in: `ssh -i C:\Users\idani\.ssh\signally_codex idanyo@10.12.194.1`

### 3. Update the Pi and install the backend service
```bash
cd ~/Signally
git pull
git branch --show-current
git status --short
cd backend
../.venv/bin/pip install -r requirements.txt

sudo cp scripts/signally-backend.service /etc/systemd/system/signally-backend.service
sudo cp scripts/signally-backend.env.example /etc/default/signally-backend
sudo nano /etc/default/signally-backend
# fill in real values: SIGNALLY_ARP_INGEST_TOKEN, SIGNALLY_WIFI_PROBING_IGNORED_MACS
# Ctrl+O, Enter, Ctrl+X to save and exit

sudo systemctl daemon-reload
sudo systemctl enable signally-csi.service signally-backend.service
```

### 4. Set the Pi's clock — do this every session
The Pi has no path to NTP once offline, and without a battery-backed RTC its
clock resets on every cold boot. `POST /arp/ingest` rejects anything more
than 30s stale or 5s in the future, so a wrong clock silently breaks ARP
evidence. The last classroom session recorded the Pi's clock **6 days**
off without this step.

From PowerShell on the laptop (not inside the SSH session), one line:
```powershell
$now = (Get-Date).ToUniversalTime().ToString("yyyy-MM-dd HH:mm:ss")
ssh -i C:\Users\idani\.ssh\signally_codex idanyo@10.12.194.1 "sudo date -u -s '$now'"
```
If the Pi has an RTC module (HAT with a coin cell), set it once from correct
time and it'll hold across reboots without repeating this step — otherwise
repeat it every boot, before starting the backend service.

### 5. Restart services and verify on the Pi
```bash
sudo systemctl restart signally-csi.service
sudo systemctl restart signally-backend.service
sudo systemctl status signally-csi.service --no-pager
sudo systemctl status signally-backend.service --no-pager

sudo bash scripts/csi_check.sh 15 100
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/csi/status | python3 -m json.tool
iw dev
```
- `csi_check.sh` must print `PASS`.
- `/csi/status` should show `"provider_mode": "real"` and
  `"receiving_data": true`.
- `iw dev` should show the interface actually in monitor mode — confirm its
  name matches `SIGNALLY_WIFI_PROBING_INTERFACE` (default `wlan1`) in
  `/etc/default/signally-backend`. `setup.sh` hardcodes a specific USB
  adapter name (`wlx803f5d168019`) that may not be the same name the system
  assigns as `wlan1` — if they don't match, fix the env var, don't assume.
  This matters because `SIGNALLY_WIFI_PROBING_FALLBACK_TO_MOCK` defaults to
  `true`: a mismatched interface fails **silently** into fake-looking-real
  mock probe data instead of an obvious error.

If anything here looks wrong, stop and fix it now — this is the last point
you'll have easy help available.

### 6. Laptop: set up the relay (one time; persists across reboots)
```powershell
cd C:\Signally\Signally\backend\scripts
.\setup_laptop_relay.ps1
```
Run from an elevated PowerShell. It's idempotent — safe to re-run. It
prints the laptop's current IPv4 addresses at the end; note the Wi-Fi one.

### 7. Join the closed Wi-Fi from the laptop and verify the chain
1. Connect to the TP-Link SSID (the laptop stays on USB to the Pi *and*
   Wi-Fi to the closed network simultaneously).
2. Confirm the laptop got its reserved IP (`ipconfig`).
3. From the laptop, prove Wi-Fi → relay → USB → Pi works end to end:
   ```powershell
   curl.exe http://<laptop-wifi-ip>:8000/system/state
   ```
   Should return real JSON, not a connection error.

### 8. Start the laptop ARP agent
Talks to the Pi directly over USB — not through the relay, which is only
needed for the phone's direction:
```powershell
cd C:\Signally\Signally\backend
$env:SIGNALLY_ARP_INGEST_TOKEN = "<same token as /etc/default/signally-backend>"
.\.venv\Scripts\python.exe scripts\laptop_arp_agent.py --interface "Wi-Fi" --target "<closed-network-subnet>/24" --backend "http://10.12.194.1:8000" --interval 10
```
Leave this running in its own window for the whole session.

### 9. Connect the phone
1. Join the same closed Wi-Fi SSID.
2. Open the app → Auth screen (or User Settings if already logged in) →
   the backend connection panel.
3. Enter `http://<laptop-wifi-ip>:8000`, save & test.
4. Note: this override doesn't survive an app uninstall/reinstall
   (SecureStore is tied to the install) — don't uninstall before the demo.

**Worth knowing:** every previously-tested run of this app was on the
laptop itself, over its own direct USB link — that path has real mileage.
A phone reaching the Pi through a laptop relay is new territory on top of
everything else that's new here. Cheap mitigation: the laptop can still
load the app directly (nothing to set up) as a fallback if the phone/relay
path has trouble.

### 10. Final go/no-go check — still while you have real internet
- `/system/state` on the phone shows a decision, not an error.
- Walk a known/approved device onto the closed Wi-Fi; confirm it shows up
  as authorized within the ARP agent's 10s scan interval.
- Toggle Home/Away from the app; confirm the decision text changes.
- Only after all of the above pass, disconnect from any other network path.

## Boot checklist (subsequent sessions)

1. Power the Pi, wait for boot.
2. SSH in (step 2 above), set the clock (step 4).
3. `sudo systemctl status signally-csi.service signally-backend.service` —
   both `active` with zero manual commands.
4. `sudo bash scripts/csi_check.sh 15 100` — `PASS`.
5. Laptop: join the closed Wi-Fi, confirm the relay still works
   (`netsh interface portproxy show v4tov4`, then the `curl` check).
6. Start the ARP agent (step 8).
7. Phone: open the app, confirm it reconnects (URL is already saved).

## Troubleshooting tree

**Backend service not active**
`sudo systemctl status signally-backend.service --no-pager` — check the
error, then `sudo journalctl -u signally-backend.service -n 50 --no-pager`.
Common cause: `/etc/default/signally-backend` missing a required value, or
`../.venv/bin/pip install -r requirements.txt` not run after a `git pull`.

**CSI channel drift**
`csi_check.sh` fails or reports an unexpected chanspec → the router's
channel/BSSID changed. Redo `csi_capture.sh` / `csi_configure.sh` against
the current values and update `/etc/default/signally-csi`.

**Portproxy rule missing after a laptop reboot**
`netsh interface portproxy show v4tov4` — if empty, re-run
`setup_laptop_relay.ps1` (elevated). Confirm `netsh advfirewall firewall
show rule name="Signally API relay"` shows the rule too.

**Phone can't reach the relay**
- Confirm the laptop actually has its reserved Wi-Fi IP (not a different
  DHCP-assigned one) — `ipconfig`.
- Confirm the firewall rule exists and Windows Defender Firewall is set to
  allow it on the network profile the Wi-Fi adapter is using (Private,
  not Public — Windows treats unrecognized networks as Public by default,
  which can block the inbound rule).
- `curl.exe http://<laptop-wifi-ip>:8000/system/state` from the laptop
  itself first, to isolate whether it's a relay problem or a phone problem.

**ARP not finding devices**
- Confirm `laptop_arp_agent.py` is still running (its own window).
- Confirm the token matches between the agent's `SIGNALLY_ARP_INGEST_TOKEN`
  and `/etc/default/signally-backend`'s value.
- `curl -s http://127.0.0.1:8000/arp/status | python3 -m json.tool` on the
  Pi — `healthy: false` means no recent successful ingestion.

**Probing silently in mock mode**
`/system/state`'s probe fields look suspiciously clean/static → check
`iw dev` on the Pi against `SIGNALLY_WIFI_PROBING_INTERFACE`. A mismatch
degrades to mock data without any visible error (`SIGNALLY_WIFI_PROBING_FALLBACK_TO_MOCK`
defaults to `true`).

**Pi clock drift causing `/arp/ingest` rejections**
Symptom: `/arp/status` shows submissions but they're not landing as
expected, or the agent logs 422 responses. Re-run the clock-set command
from step 4.
