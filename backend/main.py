"""
Entry point for Signally backend.

Supports:
- CLI ARP scanning
- CLI Wi-Fi probing sniffing
- CLI admin/database commands
- running the FastAPI server
"""

from __future__ import annotations

import argparse
import logging
import threading
from typing import Iterable

import uvicorn

from signally.admin.admin_manager import AdminManager
from signally.db.init_db import initialize_database
from signally.db.session import SessionLocal
from signally.network_scanner.scanner import NetworkScanner
from signally.services.device_service import DeviceService
from signally.services.event_service import EventService
from signally.wifi_probing.wifi_probe_detector import WifiProbeDetector
from signally.wifi_probing.wifi_probing_service import WifiProbingService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Signally backend")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_parser = subparsers.add_parser("scan", help="Scan connected devices using ARP")
    scan_parser.add_argument("--target", default=None, help="CIDR to scan, e.g. 192.168.1.0/24")
    scan_parser.add_argument("--timeout", type=int, default=2, help="ARP timeout in seconds")

    probe_parser = subparsers.add_parser(
        "sniff-wifi-probes",
        help="Capture nearby Wi-Fi management/probe frames",
    )
    probe_parser.add_argument("--interface", default=None, help="Monitor-mode interface, e.g. wlan0mon")
    probe_parser.add_argument("--duration", type=int, default=30, help="Capture duration in seconds")
    probe_parser.add_argument("--mock", action="store_true", help="Run in mock mode")
    probe_parser.add_argument("--mock-mac", default="AA:BB:CC:DD:EE:99")
    probe_parser.add_argument("--mock-ssid", default="MockPhone")
    probe_parser.add_argument("--mock-rssi", type=int, default=-55)

    approve_parser = subparsers.add_parser("approve", help="Approve a device")
    approve_parser.add_argument("--mac", required=True)

    block_parser = subparsers.add_parser("block", help="Block a device")
    block_parser.add_argument("--mac", required=True)

    delete_parser = subparsers.add_parser("delete-device", help="Delete one device")
    delete_parser.add_argument("--mac", required=True)

    subparsers.add_parser("pending", help="List pending devices")
    subparsers.add_parser("devices", help="List all devices")
    subparsers.add_parser("events", help="List recent events")
    subparsers.add_parser("clear-devices", help="Delete all devices")
    subparsers.add_parser("clear-events", help="Delete all events")
    subparsers.add_parser("reset-db", help="Delete all devices and events")

    api_parser = subparsers.add_parser("serve-api", help="Run FastAPI server")
    api_parser.add_argument("--host", default="127.0.0.1")
    api_parser.add_argument("--port", type=int, default=8000)

    return parser


def print_devices(devices: Iterable) -> None:
    for device in devices:
        print(
            "MAC={0} | IP={1} | STATUS={2} | FIRST_SEEN={3} | LAST_SEEN={4}".format(
                device.mac_address,
                device.ip_address,
                device.status.value if hasattr(device.status, "value") else str(device.status),
                device.first_seen,
                device.last_seen,
            )
        )


def print_events(events: Iterable) -> None:
    for event in events:
        print(
            "[{0}] type={1} | device_mac={2} | details={3}".format(
                event.created_at,
                event.event_type,
                event.device_mac,
                event.details,
            )
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

        if args.command == "scan":
            scanner = NetworkScanner()
            discovered_devices = scanner.scan(args.target, timeout=args.timeout)

            print("\n{0}".format("=" * 50))
            print("Found {0} connected device(s) using ARP".format(len(discovered_devices)))
            print("{0}".format("=" * 50))

            for device in discovered_devices:
                print("MAC: {0} | IP: {1}".format(device.mac_address, device.ip_address))

            print("{0}\n".format("=" * 50))

            processed = device_service.process_scan_results(discovered_devices)
            print("Saved {0} device(s) to the database.".format(len(processed)))

        elif args.command == "sniff-wifi-probes":
            detector = WifiProbeDetector(interface=args.interface, mock_mode=args.mock)
            probing_service = WifiProbingService(session)
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

                probing_service.log_started(args.interface, args.mock)
                timer.start()
                detector.run(on_detection=probing_service.handle_detection, stop_event=stop_event)

            finally:
                timer.cancel()
                probing_service.log_stopped(args.interface)

            print("Wi-Fi probing run completed.")

        elif args.command == "approve":
            device = admin_manager.approve_device(args.mac)
            print("Approved device: {0}".format(device.mac_address))

        elif args.command == "block":
            device = admin_manager.block_device(args.mac)
            print("Blocked device: {0}".format(device.mac_address))

        elif args.command == "delete-device":
            admin_manager.delete_device(args.mac)
            print("Deleted device: {0}".format(args.mac.upper()))

        elif args.command == "pending":
            print_devices(admin_manager.list_pending_devices())

        elif args.command == "devices":
            print_devices(device_service.list_all_devices())

        elif args.command == "events":
            print_events(event_service.list_recent_events(limit=100))

        elif args.command == "clear-devices":
            count = admin_manager.delete_all_devices()
            print("Deleted {0} device(s).".format(count))

        elif args.command == "clear-events":
            count = admin_manager.delete_all_events()
            print("Deleted {0} event(s).".format(count))

        elif args.command == "reset-db":
            result = admin_manager.reset_database_content()
            print(
                "Database reset complete. Deleted {0} device(s) and {1} event(s).".format(
                    result["deleted_devices"],
                    result["deleted_events"],
                )
            )


if __name__ == "__main__":
    main()