"""
Connected-device presence service.

This service answers:
'Which devices are currently connected/present according to recent ARP evidence?'
"""

from __future__ import annotations

from datetime import timedelta, timezone
from typing import List, Set

from sqlalchemy.orm import Session

from signally.config import (
    EVENT_DEVICE_DISCOVERED_NEW,
    EVENT_DEVICE_SEEN_AGAIN,
    PRESENCE_WINDOW_SECONDS,
)
from signally.models.device import Device, DeviceStatus
from signally.models.correlation_models import ConnectedPresenceSnapshot
from signally.services.device_service import DeviceService
from signally.services.event_service import EventService
from signally.utils.time_utils import utc_now


ARP_PRESENCE_EVENT_TYPES = (
    EVENT_DEVICE_DISCOVERED_NEW,
    EVENT_DEVICE_SEEN_AGAIN,
)


class PresenceService:
    def __init__(
        self,
        session: Session,
        presence_window_seconds: int = PRESENCE_WINDOW_SECONDS,
    ) -> None:
        self.session = session
        self.presence_window_seconds = presence_window_seconds
        self.device_service = DeviceService(session)
        self.event_service = EventService(session)

    def get_presence_cutoff(self):
        return utc_now() - timedelta(seconds=self.presence_window_seconds)

    def get_present_devices(self) -> List[Device]:
        cutoff = self.get_presence_cutoff()
        events = self.event_service.list_recent_events_by_types(
            event_types=ARP_PRESENCE_EVENT_TYPES,
            limit=500,
        )

        seen_macs = set()  # type: Set[str]
        devices = []

        for event in events:
         
            event_time = event.created_at
            if event_time.tzinfo is None:
                event_time = event_time.replace(tzinfo=timezone.utc)

            if event_time < cutoff or not event.device_mac:
                continue

            mac_address = event.device_mac.upper()
            if mac_address in seen_macs:
                continue

            device = self.device_service.get_by_mac(mac_address)
            if device is None:
                continue

            devices.append(device)
            seen_macs.add(mac_address)

        return devices

    def get_presence_snapshot(self) -> ConnectedPresenceSnapshot:
        present_devices = self.get_present_devices()

        authorised = [d for d in present_devices if d.status == DeviceStatus.AUTHORIZED]
        pending = [d for d in present_devices if d.status == DeviceStatus.PENDING]
        blocked = [d for d in present_devices if d.status == DeviceStatus.BLOCKED]

        return ConnectedPresenceSnapshot(
            connected_devices=present_devices,
            authorised_connected_devices=authorised,
            pending_connected_devices=pending,
            blocked_connected_devices=blocked,
        )

    def is_approved_user_present(self) -> bool:
        return self.get_presence_snapshot().approved_user_present
