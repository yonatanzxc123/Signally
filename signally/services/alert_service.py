"""
Alert service.
"""

from typing import Optional

from signally.config import (
    EVENT_APPROVED_USER_PRESENT,
    EVENT_BLOCKED_DEVICE_ALERT,
    EVENT_NO_APPROVED_USER_PRESENT,
    EVENT_UNAUTHORIZED_PRESENCE_ALERT,
)
from signally.services.event_service import EventService


class AlertService:
    def __init__(self, event_service: EventService) -> None:
        self.event_service = event_service

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
        message = "Presence detected while no approved user is home and an unknown/pending device is present."
        print("[ALERT] {0}".format(message))
        self.event_service.log_event(
            event_type=EVENT_UNAUTHORIZED_PRESENCE_ALERT,
            details=message,
            device_mac=device_mac,
        )

    def raise_blocked_device_alert(self, device_mac: Optional[str] = None) -> None:
        message = "Blocked device detected while presence is active."
        print("[HIGH ALERT] {0}".format(message))
        self.event_service.log_event(
            event_type=EVENT_BLOCKED_DEVICE_ALERT,
            details=message,
            device_mac=device_mac,
        )