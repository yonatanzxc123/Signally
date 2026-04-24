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
    probe_parser = subparsers.add_parser(
    "sniff-wifi-probes",
    help="Capture nearby Wi-Fi management/probe frames",
)
    probe_parser.add_argument("--interface", default=None, help="Monitor-mode interface, e.g. wlan0mon")
    probe_parser.add_argument("--duration", type=int, default=30, help="Capture duration in seconds")
    probe_parser.add_argument("--mock", action="store_true", help="Run in mock mode")
    probe_parser.add_argument("--mock-mac", default="AA:BB:CC:DD:EE:99", help="Mock MAC address")
    probe_parser.add_argument("--mock-ssid", default="MockPhone", help="Mock SSID")
    probe_parser.add_argument("--mock-rssi", type=int, default=-55, help="Mock RSSI")

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

    delete_parser = subparsers.add_parser("delete-device", help="Delete a device from the database")
    delete_parser.add_argument("--mac", required=True, help="Device MAC address")

    subparsers.add_parser("clear-devices", help="Delete all devices from the database")
    subparsers.add_parser("clear-events", help="Delete all events from the database")
    subparsers.add_parser("reset-db", help="Delete all devices and events from the database")

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

        elif args.command == "delete-device":
            admin_manager.delete_device(args.mac)
            print("Deleted device: {0}".format(args.mac.upper()))

        elif args.command == "clear-devices":
            deleted_count = admin_manager.delete_all_devices()
            print("Deleted {0} device(s).".format(deleted_count))

        elif args.command == "clear-events":
            deleted_count = admin_manager.delete_all_events()
            print("Deleted {0} event(s).".format(deleted_count))

        elif args.command == "reset-db":
            result = admin_manager.reset_database_content()
            print(
                "Database reset complete. Deleted {0} device(s) and {1} event(s).".format(
                    result["deleted_devices"],
                    result["deleted_events"],
                )
            )
        elif args.command == "sniff-wifi-probes":
            detector = WifiProbeDetector(interface=args.interface, mock_mode=args.mock)
            service = WifiProbingService(session)
            stop_event = threading.Event()
            timer = threading.Timer(float(args.duration), stop_event.set)

            try:
                if args.mock:
                    detector.add_mock_detection(
                        mac_address=args.mock_mac,
                        ssid=args.mock_ssid,
                        rssi=args.mock_rssi,
                        frame_type="probe_req",
                    )

                service.log_started(args.interface, args.mock)
                timer.start()
                detector.run(on_detection=service.handle_detection, stop_event=stop_event)
            finally:
                timer.cancel()
                service.log_stopped(args.interface)

            print("Wi-Fi probing run completed.")



if __name__ == "__main__":
    main()