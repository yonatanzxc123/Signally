"""
Service for device-related business logic.
"""

from typing import List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from signally.models.device import Device, DeviceStatus
from signally.network_scanner.dto import DiscoveredDevice
from signally.services.event_service import EventService
from signally.utils.time_utils import utc_now
from signally.config import UNASSOCIATED_IP_ADDRESS



class DeviceService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.event_service = EventService(session)

    def get_by_mac(self, mac_address: str) -> Optional[Device]:
        stmt = select(Device).where(Device.mac_address == mac_address.upper())
        return self.session.scalar(stmt)

    def list_all_devices(self) -> List[Device]:
        stmt = select(Device).order_by(Device.last_seen.desc())
        return list(self.session.scalars(stmt).all())

    def list_pending_devices(self) -> List[Device]:
        stmt = select(Device).where(Device.status == DeviceStatus.PENDING)
        return list(self.session.scalars(stmt).all())

    def process_scan_results(self, scan_results: List[DiscoveredDevice]) -> List[Device]:
        processed_devices = []

        for result in scan_results:
            existing = self.get_by_mac(result.mac_address)

            if existing is None:
                device = Device(
                    mac_address=result.mac_address.upper(),
                    ip_address=result.ip_address,
                    first_seen=utc_now(),
                    last_seen=utc_now(),
                    status=DeviceStatus.PENDING,
                )
                self.session.add(device)
                self.session.commit()
                self.session.refresh(device)

                self.event_service.log_event(
                    event_type="DEVICE_DISCOVERED_NEW",
                    details="New device discovered at IP {0}".format(device.ip_address),
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
                    details="Known device seen again at IP {0}".format(existing.ip_address),
                    device_mac=existing.mac_address,
                )
                processed_devices.append(existing)

        return processed_devices

    def update_status(self, mac_address: str, new_status: DeviceStatus) -> Device:
        device = self.get_by_mac(mac_address)
        if device is None:
            raise ValueError("Device with MAC {0} was not found".format(mac_address))

        device.status = new_status
        device.last_seen = utc_now()
        self.session.commit()
        self.session.refresh(device)
        return device

    def delete_device(self, mac_address: str) -> None:
        device = self.get_by_mac(mac_address)
        if device is None:
            raise ValueError("Device with MAC {0} was not found".format(mac_address))

        self.session.delete(device)
        self.session.commit()

    def delete_all_devices(self) -> int:
        devices = self.list_all_devices()
        count = len(devices)

        for device in devices:
            self.session.delete(device)

        self.session.commit()
        return count
    

def upsert_seen_device(self, mac_address: str, ip_address: str) -> Tuple[Device, bool]:
    normalized_mac = mac_address.upper()
    device = self.get_by_mac(normalized_mac)

    if device is None:
        device = Device(
            mac_address=normalized_mac,
            ip_address=ip_address,
            first_seen=utc_now(),
            last_seen=utc_now(),
            status=DeviceStatus.PENDING,
        )
        self.session.add(device)
        self.session.commit()
        self.session.refresh(device)
        return device, True

    device.ip_address = ip_address
    device.last_seen = utc_now()
    self.session.commit()
    self.session.refresh(device)
    return device, False
