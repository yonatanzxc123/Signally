"""Family-device naming and debounced presence timeline logic."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from signally.config import (
    EVENT_DEVICE_DISCOVERED_NEW,
    EVENT_DEVICE_SEEN_AGAIN,
    EVENT_FAMILY_MEMBER_ENTERED,
    EVENT_FAMILY_MEMBER_LEFT,
    PRESENCE_ARRIVAL_SCANS,
    PRESENCE_DEPARTURE_GRACE_SECONDS,
    PRESENCE_WINDOW_SECONDS,
)
from signally.models.device import Device, DeviceStatus
from signally.models.event import Event
from signally.models.presence_state import PresenceState
from signally.services.event_service import EventService
from signally.utils.time_utils import utc_now


TIMELINE_EVENT_TYPES = (EVENT_FAMILY_MEMBER_ENTERED, EVENT_FAMILY_MEMBER_LEFT)


class TimelineService:
    def __init__(
        self,
        session: Session,
        arrival_scans: int = PRESENCE_ARRIVAL_SCANS,
        departure_grace_seconds: int = PRESENCE_DEPARTURE_GRACE_SECONDS,
    ) -> None:
        self.session = session
        self.arrival_scans = max(1, arrival_scans)
        self.departure_grace_seconds = max(1, departure_grace_seconds)
        self.event_service = EventService(session)

    def set_family_member_name(self, device: Device, name: str) -> Device:
        cleaned = name.strip()
        if not cleaned:
            raise ValueError("Family member name is required")
        if len(cleaned) > 100:
            raise ValueError("Family member name must be 100 characters or fewer")
        if device.status != DeviceStatus.AUTHORIZED or device.owner_role != "FAMILY":
            raise ValueError("Only an approved family device can be named")
        device.owner_name = cleaned
        self.session.commit()
        self.session.refresh(device)

        # reconcile_scan() only tracks devices that are already named, so any
        # ARP sightings before this moment are otherwise lost. Without this,
        # naming someone while they're already home can mean no "arrived"
        # event ever fires for that visit if they don't get seen again
        # before disconnecting (confirmed 2026-09-03).
        self._bootstrap_presence_if_recently_seen(device)

        return device

    def _bootstrap_presence_if_recently_seen(self, device: Device) -> None:
        recent = self.event_service.list_events_for_device_by_types(
            device_mac=device.mac_address,
            event_types=(EVENT_DEVICE_DISCOVERED_NEW, EVENT_DEVICE_SEEN_AGAIN),
            limit=1,
        )
        if not recent:
            return

        last_seen = recent[0].created_at
        if last_seen.tzinfo is None:
            last_seen = last_seen.replace(tzinfo=timezone.utc)
        if (utc_now() - last_seen).total_seconds() > PRESENCE_WINDOW_SECONDS:
            return

        state = self.session.get(PresenceState, device.mac_address)
        if state is None:
            state = PresenceState(device_mac=device.mac_address, is_present=False, consecutive_seen=0)
            self.session.add(state)

        if not state.is_present:
            state.is_present = True
            state.consecutive_seen = self.arrival_scans
            state.last_observed_at = utc_now()
            self._log_transition(EVENT_FAMILY_MEMBER_ENTERED, device)
            self.session.commit()

    def reconcile_scan(self, observed_macs: set[str], observed_at: datetime | None = None) -> None:
        now = observed_at or utc_now()
        observed = {mac.upper() for mac in observed_macs}
        devices = list(
            self.session.scalars(
                select(Device).where(
                    Device.status == DeviceStatus.AUTHORIZED,
                    Device.owner_role == "FAMILY",
                    Device.owner_name.is_not(None),
                )
            ).all()
        )

        for device in devices:
            state = self.session.get(PresenceState, device.mac_address)
            if state is None:
                state = PresenceState(
                    device_mac=device.mac_address,
                    is_present=False,
                    consecutive_seen=0,
                )
                self.session.add(state)

            if device.mac_address.upper() in observed:
                state.last_observed_at = now
                if not state.is_present:
                    state.consecutive_seen += 1
                    if state.consecutive_seen >= self.arrival_scans:
                        state.is_present = True
                        self._log_transition(EVENT_FAMILY_MEMBER_ENTERED, device)
            elif state.is_present and state.last_observed_at is not None:
                last_observed = state.last_observed_at
                if last_observed.tzinfo is None:
                    last_observed = last_observed.replace(tzinfo=timezone.utc)
                if now - last_observed >= timedelta(seconds=self.departure_grace_seconds):
                    state.is_present = False
                    state.consecutive_seen = 0
                    self._log_transition(EVENT_FAMILY_MEMBER_LEFT, device)
            elif not state.is_present:
                # Decay by one instead of resetting to zero: a single missed
                # ARP scan (common for phones cycling Wi-Fi power-save)
                # shouldn't erase all arrival progress and force starting
                # over from scratch (confirmed fragile 2026-09-03).
                state.consecutive_seen = max(0, state.consecutive_seen - 1)

        self.session.commit()

    def list_timeline(self, limit: int = 100) -> list[Event]:
        return self.event_service.list_recent_events_by_types(TIMELINE_EVENT_TYPES, limit=limit)

    def _log_transition(self, event_type: str, device: Device) -> None:
        action = "entered home" if event_type == EVENT_FAMILY_MEMBER_ENTERED else "left home"
        self.session.add(
            Event(
                event_type=event_type,
                device_mac=device.mac_address,
                details="{0} {1}".format(device.owner_name, action),
            )
        )
