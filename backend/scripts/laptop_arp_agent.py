#!/usr/bin/env python3
"""Scan the laptop's LAN with ARP and submit observations to the Pi over USB."""

from __future__ import annotations

import argparse
import os
import socket
import time
import uuid
from datetime import datetime, timezone

import httpx
from scapy.all import ARP, Ether, srp  # type: ignore


def scan(target: str, interface: str | None, timeout: float) -> list[dict[str, str]]:
    answered, _ = srp(
        Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(pdst=target),
        iface=interface,
        timeout=timeout,
        verbose=False,
    )
    seen: dict[str, str] = {}
    for _, response in answered:
        seen[str(response.hwsrc).upper()] = str(response.psrc)
    return [
        {"mac_address": mac, "ip_address": ip}
        for mac, ip in sorted(seen.items())
    ]


def submit(url: str, token: str, scanner_id: str, devices: list[dict[str, str]]) -> None:
    payload = {
        "scan_id": str(uuid.uuid4()),
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "scanner_id": scanner_id,
        "devices": devices,
    }
    response = httpx.post(
        url.rstrip("/") + "/arp/ingest",
        headers={"X-Signally-Ingest-Token": token},
        json=payload,
        timeout=10,
    )
    response.raise_for_status()
    result = response.json()
    print(
        "{0} discovered={1} processed={2}".format(
            payload["captured_at"],
            len(devices),
            result["processed_devices_count"],
        ),
        flush=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", default=os.getenv("SIGNALLY_ARP_TARGET", "192.168.1.0/24"))
    parser.add_argument("--interface", default=os.getenv("SIGNALLY_ARP_INTERFACE") or None)
    parser.add_argument("--backend", default=os.getenv("SIGNALLY_BACKEND_URL", "http://10.12.194.1:8000"))
    parser.add_argument("--token", default=os.getenv("SIGNALLY_ARP_INGEST_TOKEN", ""))
    parser.add_argument("--interval", type=float, default=10.0)
    parser.add_argument("--timeout", type=float, default=2.0)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    if not args.token:
        raise SystemExit("Set SIGNALLY_ARP_INGEST_TOKEN or pass --token")

    scanner_id = "{0}:{1}".format(socket.gethostname(), args.interface or "default")
    while True:
        started = time.monotonic()
        devices = scan(args.target, args.interface, args.timeout)
        submit(args.backend, args.token, scanner_id, devices)
        if args.once:
            return
        time.sleep(max(0.0, args.interval - (time.monotonic() - started)))


if __name__ == "__main__":
    main()
