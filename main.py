"""
Entry point for the Signally MVP backend.

This file provides a simple command-line interface so the project can be tested
without a web framework yet. Later, the same services can be reused in FastAPI.
"""

from __future__ import annotations

import argparse
import logging
from typing import Iterable

from signally.admin.admin_manager import AdminManager
from signally.db.init_db import initialize_database
from signally.db.session import SessionLocal
from signally.network_scanner.scanner import NetworkScanner
from signally.services.device_service import DeviceService
from signally.services.event_service import EventService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Signally MVP backend CLI")
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

    return parser


def print_devices(devices: Iterable) -> None:
    for device in devices:
        print(
            f"MAC={device.mac_address} | IP={device.ip_address} | "
            f"STATUS={device.status} | FIRST_SEEN={device.first_seen} | "
            f"LAST_SEEN={device.last_seen}"
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


if __name__ == "__main__":
    main()
