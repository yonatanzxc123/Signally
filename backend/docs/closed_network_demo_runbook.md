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

## Confirmed working configuration (2026-09-03)

This setup was carried out and verified end-to-end on 2026-09-03. The
network is a dedicated SSID called **`Signally-Demo`** on the same physical
TP-Link router used for prior classroom testing — but on a **different
band/channel than any previous calibration**, so don't assume old values
still apply. Real secret values (Wi-Fi password, ARP ingest token) live in
`showcase_day_secrets.local.md` (gitignored, not in this file) — everything
below is safe to have in git.

- Confirmed: no WAN/internet uplink reachable from `Signally-Demo` — the
  isolation is working correctly.
- Router gateway / admin page: `192.168.0.1`. Its admin UI is a modern
  client-side-encrypted single-page app — cannot be driven by simple HTTP
  requests, has to be done by hand in a browser.
- Laptop's Wi-Fi got a DHCP reservation, confirmed stable across
  reconnects.
- **CSI does not sense `Signally-Demo` itself.** It senses the router's
  existing 5GHz band (`TP-Link_23D0_5G`, BSSID `BA:A6:E6:83:23:CF`,
  channel 36, 80MHz) instead — `Signally-Demo` (2.4GHz/20MHz) would need a
  full recalibration (different subcarrier count) rather than a channel
  tweak, so it was kept purely as the client network. This is a deliberate
  choice, not an oversight — don't "fix" it later without re-deriving why.
- `/etc/default/signally-csi` previously pointed at
  `a8:f7:d9:59:b7:a1` / channel 52 — that was the *old classroom AP*
  (`MTA WiFi`, from `classroom_csi_calibration_2026-08-14.md`), a
  completely different, no-longer-present device. `csi_check.sh` failed
  with 0 packets until this was corrected to the values above. If CSI ever
  shows 0 frames again, check this file first before assuming a channel
  drift — it might be pointed at the wrong AP entirely, not just the wrong
  channel on the right one.
- Wi-Fi probing interface `wlan1` is the same physical adapter as
  `setup.sh`'s hardcoded `wlx803f5d168019` — confirmed, no naming mismatch.
  But it was found stuck in `managed` mode on 2026-09-03 (NetworkManager
  still had it), which let `/wifi_probing/status` report `"running": true"`
  while genuinely capturing nothing — `tcpdump` even errored with
  `"802.11 link-layer types supported only on 802.11"`. Fixed with a new
  boot-time service, `signally-wlan1-monitor.service` (see step 3) — this
  is no longer a manual step, but if probing ever looks dead again, check
  `iw dev wlan1` shows `type monitor`, not `managed`, before anything else.
- CSI arming can lose a race on a genuine cold boot: `nexutil` reports
  success but the radio hasn't settled, so 0 frames flow — confirmed
  2026-09-03, fixed by making `csi_capture.sh` verify frames are actually
  arriving after arming and retry (up to 4 attempts) if not. Proven across
  two real reboot tests. No manual action needed now, but if `frames_received`
  ever stays 0 after boot despite correct channel/BSSID, this class of bug
  is why — check `journalctl -u signally-csi.service -b` for how many
  attempts it took.
- CSI's baseline can also be contaminated if someone is standing near the
  Pi during the ~30s warmup right after a backend restart — the "quiet"
  reading it learns includes whatever's near it at that moment. If
  `presence_detected` reads `true` while genuinely still, `sudo systemctl
  restart signally-backend.service` and stay clear of the Pi for the warmup
  window before trusting a reading again.

## Pre-flight (do this today, while you still have internet)

### 1. Router (TP-Link)
- Confirm no WAN/internet uplink is active.
- Confirm the DHCP server is on; note the LAN subnet and gateway.
- Add a DHCP reservation ("Address Reservation" under DHCP settings) for
  the **laptop's Wi-Fi MAC address** — find it with `ipconfig /all` on the
  laptop (look for the Wi-Fi adapter's "Physical Address"). This is the one
  address that must stay fixed, since it's what goes in the phone's
  connection panel.
- Note the current channel/band of whichever network CSI is meant to
  sense (see "Confirmed working configuration" above — it's not
  necessarily the same SSID the phone/laptop join). If it changed, CSI
  needs a recheck (step 5 below) — and check `/etc/default/signally-csi`
  isn't pointed at an AP that's no longer present at all, not just a
  drifted channel on the same one.
- The router rebooted a few times during initial setup, specifically when
  the laptop connected — stopped reproducing after the DHCP reservation
  was added, root cause not fully confirmed. If it recurs: try a different
  device first to isolate whether it's laptop-Wi-Fi-card-specific, and
  check the router's physical power connection.

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
sudo cp scripts/signally-wlan1-monitor.service /etc/systemd/system/signally-wlan1-monitor.service
sudo cp scripts/signally-backend.env.example /etc/default/signally-backend
sudo nano /etc/default/signally-backend
# fill in real values: SIGNALLY_ARP_INGEST_TOKEN, SIGNALLY_WIFI_PROBING_IGNORED_MACS
# Ctrl+O, Enter, Ctrl+X to save and exit

sudo systemctl daemon-reload
sudo systemctl enable signally-csi.service signally-wlan1-monitor.service signally-backend.service
```
`signally-wlan1-monitor.service` puts the probing adapter into monitor mode
at boot (see "Confirmed working configuration" above for why this needs to
be its own service). `signally-backend.service` already waits for it via
`After=`.

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
sudo systemctl restart signally-wlan1-monitor.service
sudo systemctl restart signally-backend.service
sudo systemctl status signally-csi.service signally-wlan1-monitor.service signally-backend.service --no-pager

sudo bash scripts/csi_check.sh 15 100
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/csi/status | python3 -m json.tool
curl -s http://127.0.0.1:8000/wifi_probing/status | python3 -m json.tool
sudo /usr/sbin/iw dev   # plain "iw dev" can fail with "command not found" over
                         # a non-interactive SSH session (PATH is more minimal)
```
- `csi_check.sh` must print `PASS`.
- `/csi/status` should show `"provider_mode": "real"` and
  `"receiving_data": true`. If `frames_received` stays at 0, check
  `/etc/default/signally-csi` isn't pointed at an AP that's no longer
  present at all (see "Confirmed working configuration" above — this bit
  us on 2026-09-03).
- `/wifi_probing/status` should show `"running": true`, `"mock_mode": false`.
  `signally-wlan1-monitor.service` handles putting `wlan1` into monitor mode
  now, but confirm with `sudo /usr/sbin/iw dev wlan1 info | grep type` — it
  must say `monitor`, not `managed`. `SIGNALLY_WIFI_PROBING_FALLBACK_TO_MOCK`
  defaults to `true`, so a broken interface fails **silently** into
  fake-looking mock data instead of an obvious error — this actually
  happened on 2026-09-03, "running: true" the whole time while capturing
  nothing.

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
1. Connect to `Signally-Demo` (the laptop stays on USB to the Pi *and*
   Wi-Fi to the closed network simultaneously — confirmed to work fine
   together).
2. Confirm the laptop got its reserved IP (`ipconfig`).
3. From the laptop, prove Wi-Fi → relay → USB → Pi works end to end:
   ```powershell
   curl.exe http://<laptop-wifi-ip>:8000/system/state
   ```
   Should return real JSON, not a connection error.

### 8. Start the laptop ARP agent
Talks to the Pi directly over USB — not through the relay, which is only
needed for the phone's direction. Real command with the actual token is in
`showcase_day_secrets.local.md` (gitignored); shape is:
```powershell
cd C:\Signally\Signally\backend
$env:SIGNALLY_ARP_INGEST_TOKEN = "<real token — see showcase_day_secrets.local.md>"
.\.venv\Scripts\python.exe scripts\laptop_arp_agent.py --interface "Wi-Fi" --target "<closed-network-subnet>/24" --backend "http://10.12.194.1:8000" --interval 10
```
Leave this running in its own window for the whole session.

### 9. Connect the phone
1. Join `Signally-Demo`.
2. Open the app → Auth screen (or User Settings if already logged in) →
   the backend connection panel.
3. Enter `http://<laptop-wifi-ip>:8000` (the laptop's reserved IP, not the
   Pi's), save & test.
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
3. `sudo systemctl status signally-csi.service signally-wlan1-monitor.service
   signally-backend.service` — all three `active` with zero manual commands
   (proven across two real reboot tests on 2026-09-03).
4. `sudo bash scripts/csi_check.sh 15 100` — `PASS`.
5. Laptop: join `Signally-Demo`, confirm the relay still works
   (`netsh interface portproxy show v4tov4`, then the `curl` check).
6. Start the ARP agent (step 8).
7. Phone: open the app, confirm it reconnects (URL is already saved).

## Troubleshooting tree

**Backend service not active**
`sudo systemctl status signally-backend.service --no-pager` — check the
error, then `sudo journalctl -u signally-backend.service -n 50 --no-pager`.
Common cause: `/etc/default/signally-backend` missing a required value, or
`../.venv/bin/pip install -r requirements.txt` not run after a `git pull`.

**CSI channel drift (or wrong AP entirely)**
`csi_check.sh` fails / reports an unexpected chanspec / `frames_received`
stays 0 → don't assume it's just a channel drift. On 2026-09-03,
`/etc/default/signally-csi` was found pointed at a completely different,
no-longer-present AP (the old classroom router). Check the file's
`SIGNALLY_CSI_SOURCE_MAC` against a fresh Wi-Fi scan before assuming the
existing target AP just changed channel. Current confirmed values are in
"Confirmed working configuration" above. Redo `csi_capture.sh` /
`csi_configure.sh` against whatever the current values actually are and
update `/etc/default/signally-csi`.

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

**Probing shows `running: true` but nothing is ever detected**
Don't trust `"running": true` alone — check `sudo /usr/sbin/iw dev wlan1 info`
shows `type monitor`. If it says `managed`, `signally-wlan1-monitor.service`
either didn't run or lost a race with NetworkManager:
`sudo systemctl status signally-wlan1-monitor.service`, then
`sudo systemctl restart signally-wlan1-monitor.service` followed by
`sudo systemctl restart signally-backend.service`. Also remember: devices
already connected to `Signally-Demo` mostly stop sending probe requests —
test with a device still searching for networks (or open the Wi-Fi picker
screen to force a scan burst), not just already-associated ones.

**CSI shows `frames_received: 0` right after a cold boot**
Check `sudo journalctl -u signally-csi.service -b` — it should say
`"CSI frames confirmed flowing on attempt N"`. If it exhausted all 4
attempts with a warning instead, the radio needed longer than ~30s to
settle this time; `sudo systemctl restart signally-csi.service` once the
Pi's been up a bit longer, then `sudo systemctl restart
signally-backend.service`.

**Pi clock drift causing `/arp/ingest` rejections**
Symptom: `/arp/status` shows submissions but they're not landing as
expected, or the agent logs 422 responses. Re-run the clock-set command
from step 4.
