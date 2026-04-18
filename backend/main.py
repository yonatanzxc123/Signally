"""
Entry point for Signally.

This file supports:
- CLI administration and scanning
- running the FastAPI server for frontend integration/demo
"""

from __future__ import annotations

import argparse
import logging
from typing import Iterable

import uvicorn

from signally.admin.admin_manager import AdminManager
from signally.db.init_db import initialize_database
from signally.db.session import SessionLocal
from signally.network_scanner.scanner import NetworkScanner
from signally.services.device_service import DeviceService
from signally.services.event_service import EventService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Signally backend")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_parser = subparsers.add_parser("scan", help="Scan the local network")
    scan_parser.add_argument(
        "--target",
        default=None,
        help="CIDR to scan, e.g. 192.168.1.0/24 (auto-detected if omitted)",
    )
    scan_parser.add_argument(
        "--timeout",
        type=int,
        default=2,
        help="ARP response timeout in seconds",
    )

    approve_parser = subparsers.add_parser("approve", help="Approve a device")
    approve_parser.add_argument("--mac", required=True, help="Device MAC address")

    block_parser = subparsers.add_parser("block", help="Block a device")
    block_parser.add_argument("--mac", required=True, help="Device MAC address")

    subparsers.add_parser("pending", help="List pending devices")
    subparsers.add_parser("devices", help="List all devices")
    subparsers.add_parser("events", help="List recent events")
    subparsers.add_parser("purge", help="Delete all devices and events so they can be re-registered")

    api_parser = subparsers.add_parser("serve-api", help="Run the FastAPI server")
    api_parser.add_argument("--host", default="127.0.0.1", help="Host to bind")
    api_parser.add_argument("--port", type=int, default=8000, help="Port to bind")

    return parser


def print_devices(devices: Iterable) -> None:
    for device in devices:
        print(
            f"MAC={device.mac_address} | IP={device.ip_address} | "
            f"STATUS={device.status} | TYPE={device.device_type or 'UNKNOWN'} | "
            f"VENDOR={device.vendor or 'Unknown'} | "
            f"FIRST_SEEN={device.first_seen} | LAST_SEEN={device.last_seen}"
        )


def print_events(events: Iterable) -> None:
    for event in events:
        print(
            f"[{event.created_at}] type={event.event_type} | "
            f"device_mac={event.device_mac} | details={event.details}"
        )


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    initialize_database()
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "serve-api":
        uvicorn.run("signally.api.app:app", host=args.host, port=args.port, reload=False)
        return

    with SessionLocal() as session:
        device_service = DeviceService(session)
        event_service = EventService(session)
        admin_manager = AdminManager(device_service, event_service)
        scanner = NetworkScanner()

        if args.command == "scan":
            discovered_devices = scanner.scan(args.target, timeout=args.timeout)
            print(f"\n{'='*50}")
            print(f"  Found {len(discovered_devices)} device(s) on the network")
            print(f"{'='*50}")
            for d in discovered_devices:
                print(f"  MAC: {d.mac_address}  |  IP: {d.ip_address}")
            print(f"{'='*50}\n")
            processed = device_service.process_scan_results(discovered_devices)
            print(f"Saved {len(processed)} device(s) to the database.")

        elif args.command == "approve":
            device = admin_manager.approve_device(args.mac)
            print(f"Approved device: {device.mac_address}")

        elif args.command == "block":
            device = admin_manager.block_device(args.mac)
            print(f"Blocked device: {device.mac_address}")

        elif args.command == "pending":
            pending_devices = admin_manager.list_pending_devices()
            print_devices(pending_devices)

        elif args.command == "devices":
            all_devices = device_service.list_all_devices()
            print_devices(all_devices)

        elif args.command == "events":
            events = event_service.list_recent_events(limit=100)
            print_events(events)

        elif args.command == "purge":
            count = device_service.delete_all_devices()
            print(f"Purged {count} device(s) and all associated events. Run 'scan' to re-register.")


if __name__ == "__main__":
    main()