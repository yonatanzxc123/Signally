"""
Service for device-related business logic.

Responsibilities:
- insert new devices
- update existing devices
- list devices by status
- log detection events
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from signally.capture.probe_sniffer import ProbeResult
from signally.models.device import Device, DeviceStatus
from signally.network_scanner.dto import DiscoveredDevice
from signally.network_scanner.vendor_lookup import VendorLookup
from signally.services.event_service import EventService
from signally.utils.time_utils import utc_now


class DeviceService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.event_service = EventService(session)
        self._vendor_lookup = VendorLookup()

    def get_by_mac(self, mac_address: str) -> Device | None:
        stmt = select(Device).where(Device.mac_address == mac_address.upper())
        return self.session.scalar(stmt)

    def list_all_devices(self) -> list[Device]:
        stmt = select(Device).order_by(Device.last_seen.desc())
        return list(self.session.scalars(stmt).all())

    def list_pending_devices(self) -> list[Device]:
        stmt = select(Device).where(Device.status == DeviceStatus.PENDING)
        return list(self.session.scalars(stmt).all())

    def process_scan_results(self, scan_results: list[DiscoveredDevice]) -> list[Device]:
        """
        Process all discovered devices from a network scan.

        Rules:
        - if device is new => insert with PENDING status
        - if device exists => update last_seen and current IP address
        - always log events
        """

        processed_devices: list[Device] = []

        for result in scan_results:
            existing = self.get_by_mac(result.mac_address)

            if existing is None:
                vendor, device_type = self._vendor_lookup.enrich(result.mac_address)
                device = Device(
                    mac_address=result.mac_address.upper(),
                    ip_address=result.ip_address,
                    first_seen=utc_now(),
                    last_seen=utc_now(),
                    status=DeviceStatus.PENDING,
                    vendor=vendor,
                    device_type=device_type,
                )
                self.session.add(device)
                self.session.commit()
                self.session.refresh(device)

                self.event_service.log_event(
                    event_type="DEVICE_DISCOVERED_NEW",
                    details=(
                        f"New device discovered at IP {device.ip_address} | "
                        f"type={device.device_type or 'UNKNOWN'} | "
                        f"vendor={device.vendor or 'Unknown'}"
                    ),
                    device_mac=device.mac_address,
                )
                processed_devices.append(device)
            else:
                existing.ip_address = result.ip_address
                existing.last_seen = utc_now()
                self.session.commit()
                self.session.refresh(existing)

                self.event_service.log_event(
                    event_type="DEVICE_SEEN_AGAIN",
                    details=(
                        f"Known device seen again at IP {existing.ip_address} | "
                        f"type={existing.device_type or 'UNKNOWN'} | "
                        f"vendor={existing.vendor or 'Unknown'}"
                    ),
                    device_mac=existing.mac_address,
                )
                processed_devices.append(existing)

        return processed_devices

    def process_probe_results(self, probe_results: list[ProbeResult]) -> list[Device]:
        """
        Process probe-request observations.

        Rules:
        - If the MAC is already in the DB → mark device_type as PHONE (probes
          come from phones by definition) and refresh last_seen.
        - If the MAC is new → insert with PHONE type and no IP (probe requests
          carry no IP address).
        - Always log a PROBE_REQUEST event.
        """
        processed: list[Device] = []

        for result in probe_results:
            existing = self.get_by_mac(result.mac_address)

            if existing is None:
                vendor, _ = self._vendor_lookup.enrich(result.mac_address)
                device = Device(
                    mac_address=result.mac_address.upper(),
                    ip_address="N/A",
                    first_seen=utc_now(),
                    last_seen=utc_now(),
                    status=DeviceStatus.PENDING,
                    vendor=vendor,
                    device_type="PHONE",
                )
                self.session.add(device)
                self.session.commit()
                self.session.refresh(device)
                self.event_service.log_event(
                    event_type="PROBE_REQUEST_NEW",
                    details=(
                        f"New device detected via probe request"
                        f"{' for SSID ' + repr(result.ssid) if result.ssid else ' (wildcard probe)'} | "
                        f"vendor={device.vendor or 'Unknown'}"
                    ),
                    device_mac=device.mac_address,
                )
            else:
                existing.device_type = "PHONE"
                existing.last_seen = utc_now()
                self.session.commit()
                self.session.refresh(existing)
                self.event_service.log_event(
                    event_type="PROBE_REQUEST_SEEN",
                    details=(
                        f"Known device confirmed as PHONE via probe request"
                        f"{' for SSID ' + repr(result.ssid) if result.ssid else ' (wildcard probe)'}"
                    ),
                    device_mac=existing.mac_address,
                )
                processed.append(existing)
                continue

            processed.append(device)

        return processed

    def delete_all_devices(self) -> int:
        """Delete all devices and their associated events. Returns count deleted."""
        from signally.models.event import Event

        count = self.session.query(Device).count()
        self.session.query(Event).delete()
        self.session.query(Device).delete()
        self.session.commit()
        return count

    def update_status(self, mac_address: str, new_status: DeviceStatus) -> Device:
        device = self.get_by_mac(mac_address)
        if device is None:
            raise ValueError(f"Device with MAC {mac_address} was not found")

        device.status = new_status
        device.last_seen = utc_now()
        self.session.commit()
        self.session.refresh(device)
        return device
