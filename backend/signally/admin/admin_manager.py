"""
Admin manager.
"""

from __future__ import annotations

from signally.models.device import Device, DeviceStatus
from signally.models.security_mode import SecurityMode, SecurityState
from signally.models.user import UserRole
from signally.services.device_service import DeviceService
from signally.services.event_service import EventService
from signally.services.user_service import UserService
from signally.utils.time_utils import utc_now


class AdminManager:
    def __init__(
        self,
        device_service: DeviceService,
        event_service: EventService,
        user_service: UserService | None = None,
    ) -> None:
        self.device_service = device_service
        self.event_service = event_service
        self.user_service = user_service or UserService(device_service.session)

    def approve_device(
        self,
        mac_address: str,
        actor_role: UserRole | str = UserRole.ADMIN,
        owner_name: str | None = None,
        owner_role: UserRole | str = UserRole.GUEST,
    ) -> Device:
        self.user_service.require_admin(actor_role)
        device = self.device_service.update_status(mac_address, DeviceStatus.AUTHORIZED)
        if owner_name:
            _, device = self.user_service.create_user_for_device(
                mac_address=device.mac_address,
                display_name=owner_name,
                role=owner_role,
            )
        self.event_service.log_event(
            event_type="DEVICE_APPROVED",
            details="Admin approved device",
            device_mac=device.mac_address,
        )
        return device

    def approve_all_pending_devices(
        self,
        actor_role: UserRole | str = UserRole.ADMIN,
    ) -> list[Device]:
        self.user_service.require_admin(actor_role)
        devices = self.device_service.list_pending_devices()

        for device in devices:
            device.status = DeviceStatus.AUTHORIZED
            device.last_seen = utc_now()
            self.event_service.log_event(
                event_type="DEVICE_APPROVED",
                details="Admin approved device via bulk action",
                device_mac=device.mac_address,
            )

        self.device_service.session.commit()
        return devices

    def block_device(
        self,
        mac_address: str,
        actor_role: UserRole | str = UserRole.ADMIN,
    ) -> Device:
        self.user_service.require_admin(actor_role)
        device = self.device_service.update_status(mac_address, DeviceStatus.BLOCKED)
        self.event_service.log_event(
            event_type="DEVICE_BLOCKED",
            details="Admin blocked device",
            device_mac=device.mac_address,
        )
        return device

    def delete_device(
        self,
        mac_address: str,
        actor_role: UserRole | str = UserRole.ADMIN,
    ) -> None:
        self.user_service.require_admin(actor_role)
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
        deleted_device_owners = self.user_service.delete_all_device_owners()
        deleted_users = self.user_service.delete_all_users()

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

        security_state = self.device_service.session.get(SecurityState, 1)
        if security_state is not None:
            security_state.mode = SecurityMode.HOME
            security_state.updated_by_role = "SYSTEM"
            security_state.updated_at = utc_now()
            self.device_service.session.commit()

        return {
            "deleted_devices": deleted_devices,
            "deleted_events": deleted_events,
            "deleted_users": deleted_users,
            "deleted_device_owners": deleted_device_owners,
        }

    def list_pending_devices(self) -> list[Device]:
        return self.device_service.list_pending_devices()
