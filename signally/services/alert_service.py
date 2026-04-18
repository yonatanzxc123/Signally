"""
Alert service.

Centralizes alert and notification creation.
For now alerts are persisted as events in the database and also printed to the
console for demo visibility.
"""

from __future__ import annotations

from signally.config import (
    EVENT_APPROVED_USER_PRESENT,
    EVENT_BLOCKED_DEVICE_ALERT,
    EVENT_NO_APPROVED_USER_PRESENT,
    EVENT_UNAUTHORIZED_PRESENCE_ALERT,
)
from signally.services.event_service import EventService


class AlertService:
    """
    Handles creation of alert-related events.
    """

    def __init__(self, event_service: EventService) -> None:
        self.event_service = event_service

    def log_approved_user_present(self) -> None:
        message = "Approved user is currently present at home."
        print(f"[INFO] {message}")
        self.event_service.log_event(
            event_type=EVENT_APPROVED_USER_PRESENT,
            details=message,
        )

    def log_no_approved_user_present(self) -> None:
        message = "No approved user is currently present."
        print(f"[WARNING] {message}")
        self.event_service.log_event(
            event_type=EVENT_NO_APPROVED_USER_PRESENT,
            details=message,
        )

    def raise_unauthorized_presence_alert(self, device_mac: str | None = None) -> None:
        message = "Presence detected while no approved user is home and an unknown/pending device is present."
        print(f"[ALERT] {message}")
        self.event_service.log_event(
            event_type=EVENT_UNAUTHORIZED_PRESENCE_ALERT,
            details=message,
            device_mac=device_mac,
        )

    def raise_blocked_device_alert(self, device_mac: str | None = None) -> None:
        message = "Blocked device detected while presence is active."
        print(f"[HIGH ALERT] {message}")
        self.event_service.log_event(
            event_type=EVENT_BLOCKED_DEVICE_ALERT,
            details=message,
            device_mac=device_mac,
        )