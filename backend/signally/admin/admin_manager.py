"""
Admin manager.
"""

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

    def delete_device(self, mac_address: str) -> None:
        self.device_service.delete_device(mac_address)
        self.event_service.log_event(
            event_type="DEVICE_DELETED",
            details="Admin deleted device",
            device_mac=mac_address.upper(),
        )

    def delete_all_devices(self) -> int:
        return self.device_service.delete_all_devices()

    def delete_all_events(self) -> int:
        return self.event_service.delete_all_events()

    def reset_database_content(self) -> dict:
        devices = self.device_service.list_all_devices()
        deleted_devices = len(devices)

        for device in devices:
            self.device_service.session.delete(device)
        self.device_service.session.commit()

        events = self.event_service.list_recent_events(limit=1000000)
        deleted_events = len(events)

        for event in events:
            self.event_service.session.delete(event)
        self.event_service.session.commit()

        return {
            "deleted_devices": deleted_devices,
            "deleted_events": deleted_events,
        }

    def list_pending_devices(self) -> list[Device]:
        return self.device_service.list_pending_devices()