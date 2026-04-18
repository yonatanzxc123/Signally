# Signally MVP Backend

This project is the **first backend MVP** for **Signally**, a networking security project.

The current version focuses on **local network discovery** using **ARP scanning**, device persistence, event logging, and a simple admin interface.

## Why this design?

The code is intentionally structured so it can later evolve into:

- **FastAPI** endpoints
- **Redis** for real-time state
- **PostgreSQL** instead of SQLite
- deployment on **Raspberry Pi**

To stay migration-friendly, the project uses **SQLAlchemy ORM** instead of raw SQLite queries.
That means moving from SQLite to PostgreSQL later should mostly require changing the database URL.

## Features

- Scan the local network using **Scapy ARP scanning**
- Insert new devices with status `PENDING`
- Update `last_seen` for known devices
- Store events in a separate `events` table
- Approve devices
- Block devices
- List pending devices
- Simple CLI admin interface

## Folder structure

```text
signally_mvp_backend/
│
├── main.py
├── requirements.txt
├── README.md
│
├── signally/
│   ├── __init__.py
│   ├── config.py
│   │
│   ├── db/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── session.py
│   │   └── init_db.py
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── device.py
│   │   └── event.py
│   │
│   ├── network_scanner/
│   │   ├── __init__.py
│   │   ├── scanner.py
│   │   └── dto.py
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── device_service.py
│   │   └── event_service.py
│   │
│   ├── admin/
│   │   ├── __init__.py
│   │   └── admin_manager.py
│   │
│   └── utils/
│       ├── __init__.py
│       └── time_utils.py
│
└── tests/
    └── test_placeholder.py
```

## Installation

```bash
python -m venv .venv
source .venv/bin/activate        # Linux / macOS
# .venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

## Run the MVP

```bash
python main.py scan --target 192.168.1.0/24
python main.py pending
python main.py approve --mac AA:BB:CC:DD:EE:FF
python main.py block --mac AA:BB:CC:DD:EE:FF
python main.py devices
python main.py events
```

## Notes for Raspberry Pi

- Run with `sudo` when ARP scanning requires elevated privileges.
- On Raspberry Pi OS / Linux, install dependencies in a virtual environment.
- If Scapy ARP broadcasting is restricted in a given environment, this scanner module can later be replaced with another implementation without changing the services layer.

## Future extension ideas

- Add FastAPI routes around the service layer
- Add Redis caching for “currently visible devices”
- Add scheduler/background scanning loop
- Add vendor lookup / hostname enrichment
- Add real-time alerts for blocked devices
