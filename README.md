# Signally

Signally is a home-network presence and security monitoring system. It combines network discovery, nearby Wi-Fi activity, and Wi-Fi Channel State Information (CSI) to help distinguish known household devices from unknown activity and surface meaningful alerts.

The project consists of a Python/FastAPI backend and an Expo React Native application. It is being designed for an offline Raspberry Pi deployment, while retaining mock modes that make local development and demonstrations possible without the full hardware setup.

## How it works

Signally collects several types of evidence:

- **ARP discovery** identifies devices connected to the local network.
- **Wi-Fi probe monitoring** observes nearby devices that may not be connected.
- **CSI motion detection** uses changes in Wi-Fi channel measurements as physical presence evidence.
- **Correlation rules** combine this evidence with the selected `HOME` or `AWAY` security mode.

The resulting state is exposed through the API and displayed in the mobile app, where an administrator can review devices, approve family members or guests, block devices, switch security modes, and inspect recent activity.

## Features

- Discover and persist local-network devices
- Classify devices as pending, authorized, or blocked
- Assign approved devices to family members or guests
- Monitor nearby Wi-Fi probe activity
- Process real or simulated CSI presence data
- Correlate connected, nearby, and physical-presence signals
- Generate alerts with cooldown protection
- Browse device and event history
- Authenticate users with role-based access
- Run from a CLI, REST API, or Expo mobile interface

## Architecture

```text
ARP scans -----------+
Wi-Fi probe frames --+--> FastAPI correlation engine --> SQLite --> Expo app
CSI measurements ----+              |
                                    +--> alerts and event history
```

| Area | Technology |
| --- | --- |
| Mobile app | Expo, React Native, TypeScript, React Navigation, TanStack Query |
| API | FastAPI, Pydantic, Uvicorn |
| Data | SQLAlchemy, SQLite |
| Network monitoring | Scapy, ARP, 802.11 probe frames |
| Presence sensing | Nexmon CSI over UDP, NumPy-based detection |
| Authentication | JWT, bcrypt |
| Tests | pytest |

## Repository structure

```text
Signally/
|-- backend/          Python backend, API, monitoring services, and tests
|-- SignallyApp/      Expo React Native application
|-- DEMO_RUNBOOK.md   Hardware demo procedure
|-- PLAN.md           Implementation and validation plan
`-- README.md         Project overview
```

## Quick start

### 1. Start the backend

Python 3.10 or newer is recommended.

```bash
cd backend
python -m venv .venv
```

Activate the environment:

```bash
# Linux/macOS
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1
```

Install dependencies and run the API:

```bash
pip install -r requirements.txt
python main.py serve-api --host 0.0.0.0 --port 8000
```

The API is available at `http://localhost:8000`. Interactive API documentation is available at `http://localhost:8000/docs`.

> ARP scanning and Wi-Fi frame capture may require administrator/root privileges and compatible network hardware. Use only on networks and devices you are authorized to monitor.

### 2. Start the app

Node.js 20 or newer is recommended.

```bash
cd SignallyApp
npm install
npm start
```

From the Expo terminal, open the web app, an Android emulator, an iOS simulator, or scan the QR code with a compatible device. The web build connects to `http://127.0.0.1:8000`; for a physical device, set the backend address in `SignallyApp/src/api/client.ts` to an address the device can reach.

## Useful backend commands

Run these from `backend/` with the virtual environment active:

```bash
python main.py scan --target 192.168.1.0/24
python main.py devices
python main.py pending
python main.py approve --mac AA:BB:CC:DD:EE:FF
python main.py block --mac AA:BB:CC:DD:EE:FF
python main.py events
python main.py sniff-wifi-probes --mock --duration 10
```

Run the automated checks:

```bash
cd backend
pytest

cd ../SignallyApp
npm run typecheck
```

## Configuration

Backend behavior is configured with `SIGNALLY_` environment variables. Common options include:

| Variable | Purpose | Default |
| --- | --- | --- |
| `SIGNALLY_DATABASE_URL` | SQLAlchemy database URL | `sqlite:///signally.db` |
| `SIGNALLY_JWT_SECRET` | Token-signing secret | Development value; change for deployment |
| `SIGNALLY_DEFAULT_SCAN_TARGET` | Default ARP scan range | `192.168.1.0/24` |
| `SIGNALLY_AUTO_START_MONITORING` | Start correlation monitoring with the API | `true` |
| `SIGNALLY_WIFI_PROBING_INTERFACE` | Monitor-mode Wi-Fi interface | `wlan1` |
| `SIGNALLY_WIFI_PROBING_MOCK_MODE` | Use simulated Wi-Fi detections | `false` |
| `SIGNALLY_CSI_REAL_PROVIDER_ENABLED` | Listen for real Nexmon CSI frames | `false` |
| `SIGNALLY_CSI_UDP_PORT` | CSI frame UDP port | `5500` |

Never deploy with the default JWT secret.

## Hardware mode

The complete hardware path targets a Raspberry Pi with compatible Wi-Fi adapters:

- A monitor-mode adapter captures nearby 802.11 probe frames.
- A Nexmon-compatible device streams CSI frames to the backend over UDP.
- The Raspberry Pi runs the API, correlation engine, and SQLite database locally.
- The app connects to the Pi over the configured local or USB-network address.

See [DEMO_RUNBOOK.md](DEMO_RUNBOOK.md) for the current demonstration procedure and [PLAN.md](PLAN.md) for integration and validation progress.

## Project status

Signally is an active prototype. The API, mobile app, authentication, device management, event history, mock sensor flows, and CSI processing pipeline are implemented. Hardware installation, calibration, cold-boot reliability, and end-to-end Raspberry Pi validation are still in progress.

This software is intended for authorized defensive monitoring and research. Wireless capture laws and consent requirements vary by location; verify the rules that apply before enabling live capture.
