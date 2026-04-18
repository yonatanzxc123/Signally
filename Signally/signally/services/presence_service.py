"""
Presence service.

This service determines which devices are considered currently present based on
their last_seen timestamps.

The main business question it answers is:
"Is an approved resident currently home?"
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from signally.config import PRESENCE_WINDOW_SECONDS
from signally.models.device import Device, DeviceStatus
from signally.services.decision_models import PresenceSnapshot
from signally.utils.time_utils import utc_now


class PresenceService:
    """
    Computes presence state from recently seen devices.
    """

    def __init__(
        self,
        session: Session,
        presence_window_seconds: int = PRESENCE_WINDOW_SECONDS,
    ) -> None:
        self.session = session
        self.presence_window_seconds = presence_window_seconds

    def get_presence_cutoff(self):
        """
        Devices seen after this timestamp are considered currently present.
        """
        return utc_now() - timedelta(seconds=self.presence_window_seconds)

    def get_present_devices(self) -> list[Device]:
        """
        Return all devices seen recently enough to be considered present.
        """
        cutoff = self.get_presence_cutoff()
        stmt = select(Device).where(Device.last_seen >= cutoff).order_by(Device.last_seen.desc())
        return list(self.session.scalars(stmt).all())

    def get_presence_snapshot(self) -> PresenceSnapshot:
        """
        Build a full snapshot of currently present devices grouped by status.
        """
        present_devices = self.get_present_devices()

        authorized = [d for d in present_devices if d.status == DeviceStatus.AUTHORIZED]
        pending = [d for d in present_devices if d.status == DeviceStatus.PENDING]
        blocked = [d for d in present_devices if d.status == DeviceStatus.BLOCKED]

        return PresenceSnapshot(
            present_devices=present_devices,
            present_authorized_devices=authorized,
            present_pending_devices=pending,
            present_blocked_devices=blocked,
        )

    def is_approved_user_present(self) -> bool:
        """
        Return True if at least one authorized device is currently present.
        """
        snapshot = self.get_presence_snapshot()
        return snapshot.approved_user_present