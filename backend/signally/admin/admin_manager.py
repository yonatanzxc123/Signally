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
        owner_role: UserRole | str,
        actor_role: UserRole | str = UserRole.ADMIN,
    ) -> Device:
        self.user_service.require_admin(actor_role)
        role_value = owner_role.value if isinstance(owner_role, UserRole) else owner_role
        device = self.device_service.update_status(mac_address, DeviceStatus.AUTHORIZED)
        device.owner_role = role_value
        device.approved_at = utc_now()
        self.device_service.session.commit()
        self.event_service.log_event(
            event_type="DEVICE_APPROVED",
            details="Admin approved device as {0}".format(role_value),
            device_mac=device.mac_address,
        )
        return device

    def approve_all_pending_devices(
        self,
        owner_role: UserRole | str,
        actor_role: UserRole | str = UserRole.ADMIN,
    ) -> list[Device]:
        self.user_service.require_admin(actor_role)
        role_value = owner_role.value if isinstance(owner_role, UserRole) else owner_role
        devices = self.device_service.list_pending_devices()
        now = utc_now()

        for device in devices:
            device.status = DeviceStatus.AUTHORIZED
            device.owner_role = role_value
            device.approved_at = now
            device.last_seen = now
            self.event_service.log_event(
                event_type="DEVICE_APPROVED",
                details="Admin approved device as {0} via bulk action".format(role_value),
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
        }

    def list_pending_devices(self) -> list[Device]:
        return self.device_service.list_pending_devices()
