"""
Admin manager.

This class acts like a simple admin interface in code.
Later, these methods can be called from:
- FastAPI endpoints
- a web dashboard
- a mobile app backend
"""

from __future__ import annotations

from signally.models.device import Device, DeviceStatus
from signally.services.device_service import DeviceService
from signally.services.event_service import EventService


class AdminManager:
    def __init__(self, device_service: DeviceService, event_service: EventService) -> None:
        self.device_service = device_service
        self.event_service = event_service

    def approve_device(self, mac_address: str) -> Device:
        device = self.device_service.update_status(mac_address, DeviceStatus.AUTHORIZED)
        self.event_service.log_event(
            event_type="DEVICE_APPROVED",
            details="Admin approved device",
            device_mac=device.mac_address,
        )
        return device

    def block_device(self, mac_address: str) -> Device:
        device = self.device_service.update_status(mac_address, DeviceStatus.BLOCKED)
        self.event_service.log_event(
            event_type="DEVICE_BLOCKED",
            details="Admin blocked device",
            device_mac=device.mac_address,
        )
        return device

    def list_pending_devices(self) -> list[Device]:
        return self.device_service.list_pending_devices()
