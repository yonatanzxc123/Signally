"""
Alert service.
"""

from datetime import timezone
from typing import Optional

from signally.config import (
    ALERT_EVENT_COOLDOWN_SECONDS,
    EVENT_APPROVED_USER_PRESENT,
    EVENT_BLOCKED_DEVICE_ALERT,
    EVENT_NO_APPROVED_USER_PRESENT,
    EVENT_UNAUTHORIZED_PRESENCE_ALERT,
)
from signally.services.event_service import EventService
from signally.utils.time_utils import utc_now


class AlertService:
    def __init__(self, event_service: EventService) -> None:
        self.event_service = event_service

    def _should_log_alert(self, event_type: str, device_mac: Optional[str] = None) -> bool:
        if ALERT_EVENT_COOLDOWN_SECONDS <= 0:
            return True

        now = utc_now()
        recent_alerts = self.event_service.list_recent_events_by_types([event_type], limit=25)

        for event in recent_alerts:
            if device_mac and (event.device_mac or "").upper() != device_mac.upper():
                continue

            created_at = event.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)

            if (now - created_at).total_seconds() < ALERT_EVENT_COOLDOWN_SECONDS:
                return False

        return True

    def log_approved_user_present(self) -> None:
        message = "Approved user is currently present at home."
        print("[INFO] {0}".format(message))
        self.event_service.log_event(
            event_type=EVENT_APPROVED_USER_PRESENT,
            details=message,
        )

    def log_no_approved_user_present(self) -> None:
        message = "No approved user is currently present."
        print("[WARNING] {0}".format(message))
        self.event_service.log_event(
            event_type=EVENT_NO_APPROVED_USER_PRESENT,
            details=message,
        )

    def raise_unauthorized_presence_alert(self, device_mac: Optional[str] = None) -> None:
        if not self._should_log_alert(EVENT_UNAUTHORIZED_PRESENCE_ALERT, device_mac):
            return

        message = "Presence detected while no approved user is home and an unknown/pending device is present."
        print("[ALERT] {0}".format(message))
        self.event_service.log_event(
            event_type=EVENT_UNAUTHORIZED_PRESENCE_ALERT,
            details=message,
            device_mac=device_mac,
        )

    def raise_blocked_device_alert(self, device_mac: Optional[str] = None) -> None:
        if not self._should_log_alert(EVENT_BLOCKED_DEVICE_ALERT, device_mac):
            return

        message = "Blocked device detected while presence is active."
        print("[HIGH ALERT] {0}".format(message))
        self.event_service.log_event(
            event_type=EVENT_BLOCKED_DEVICE_ALERT,
            details=message,
            device_mac=device_mac,
        )
