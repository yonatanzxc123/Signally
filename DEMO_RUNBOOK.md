# Signally Demo Runbook

## Before the demo (one-time setup — already done)
- Driver installed: `rtl8812au` compiled and loaded for kernel 7.0.0
- Backend dependencies installed in `.venv`

---

## Every time you start the VM

### 1. Attach the USB WiFi adapter
In the VirtualBox menu bar:
**Devices → USB → Realtek 802.11n NIC**

Verify it appeared:
```bash
lsusb | grep Realtek
```

---

### 2. Put the adapter in monitor mode
```bash
sudo nmcli dev set wlx803f5d168019 managed no
sudo ip link set wlx803f5d168019 down
sudo iw dev wlx803f5d168019 set type monitor
sudo ip link set wlx803f5d168019 up
```

Verify:
```bash
iw dev wlx803f5d168019 info | grep type
# should say: type monitor
```

---

### 3. Go to the backend directory
```bash
cd ~/Signally/backend
```

---

## Running the demo

### Option A — Probe sniffing (captures nearby devices)
Open two terminals.

**Terminal 1 — start sniffing:**
```bash
cd ~/Signally/backend
sudo .venv/bin/python main.py sniff-wifi-probes --interface wlx803f5d168019 --duration 120
```

**Terminal 2 — watch events live** (run while Terminal 1 is sniffing):
```bash
cd ~/Signally/backend
watch -n 2 'sudo .venv/bin/python main.py events | head -20'
```

### Option B — Start the API server
```bash
cd ~/Signally/backend
sudo .venv/bin/python main.py serve-api --host 0.0.0.0 --port 8000
```
API will be available at: `http://localhost:8000`

---

## Useful commands

| What | Command |
|------|---------|
| Show captured events | `sudo .venv/bin/python main.py events` |
| Show known devices | `sudo .venv/bin/python main.py devices` |
| Scan local network | `sudo .venv/bin/python main.py scan` |
| Reset database | `sudo .venv/bin/python main.py reset-db` |

---

## Troubleshooting

**Adapter not showing up in `lsusb`:**
→ VirtualBox menu: Devices → USB → Realtek 802.11n NIC

**No probes being captured:**
→ Check monitor mode: `iw dev wlx803f5d168019 info | grep type`
→ NetworkManager may have taken over — re-run Step 2

**Driver not loaded after reboot:**
```bash
sudo modprobe 88XXau
```
