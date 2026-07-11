"""
Persistence service for Wi-Fi probe detections.

Probe-only devices are NOT added to the device table.
They are logged as events and counted for proximity awareness.
"""

from __future__ import annotations

from datetime import timedelta, timezone
from typing import Set

from sqlalchemy.orm import Session

from signally.config import (
    CURRENT_UNKNOWN_WINDOW_SECONDS,
    EVENT_WIFI_PROBE_NEARBY_ACTIVITY,
    EVENT_WIFI_PROBING_ERROR,
    EVENT_WIFI_PROBING_STARTED,
    EVENT_WIFI_PROBING_STOPPED,
    WIFI_PROBING_RECENT_EVENT_LIMIT,
    WIFI_PROBING_STRONG_RSSI_MIN,
)
from signally.models.correlation_models import NearbyPresenceSnapshot
from signally.services.event_service import EventService
from signally.utils.time_utils import utc_now
from signally.wifi_probing.dto import WifiProbeDetection


class WifiProbingService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.event_service = EventService(session)

    def handle_detection(self, detection: WifiProbeDetection) -> None:
        if not self._has_strong_signal(detection):
            return
        self.event_service.log_event(
            event_type=EVENT_WIFI_PROBE_NEARBY_ACTIVITY,
            details=self._build_details(detection),
            device_mac=detection.mac_address,
        )

    def get_presence_snapshot(
        self,
        window_seconds: int = CURRENT_UNKNOWN_WINDOW_SECONDS,
    ) -> NearbyPresenceSnapshot:
        events = self._list_probe_events(window_seconds=window_seconds)

        seen_macs: Set[str] = set()
        first_probe_seen_at = None

        for event in events:
            if not event.device_mac:
                continue
            mac = event.device_mac.upper()
            event_time = self._event_time(event.created_at)
            if first_probe_seen_at is None or event_time < first_probe_seen_at:
                first_probe_seen_at = event_time
            seen_macs.add(mac)

        return NearbyPresenceSnapshot(
            nearby_probe_count=len(seen_macs),
            first_probe_seen_at=first_probe_seen_at,
            window_seconds=window_seconds,
        )

    def log_started(self, interface: str, mock_mode: bool) -> None:
        self.event_service.log_event(
            event_type=EVENT_WIFI_PROBING_STARTED,
            details="interface={0}; mock_mode={1}".format(interface or "None", mock_mode),
        )

    def log_stopped(self, interface: str) -> None:
        self.event_service.log_event(
            event_type=EVENT_WIFI_PROBING_STOPPED,
            details="interface={0}".format(interface or "None"),
        )

    def log_error(self, interface: str, error_message: str) -> None:
        self.event_service.log_event(
            event_type=EVENT_WIFI_PROBING_ERROR,
            details="interface={0}; error={1}".format(interface or "None", error_message),
        )

    def _has_strong_signal(self, detection: WifiProbeDetection) -> bool:
        return detection.rssi is not None and detection.rssi >= WIFI_PROBING_STRONG_RSSI_MIN

    def _list_probe_events(self, window_seconds: int):
        events = self.event_service.list_recent_events_by_types(
            event_types=(EVENT_WIFI_PROBE_NEARBY_ACTIVITY,),
            limit=WIFI_PROBING_RECENT_EVENT_LIMIT,
        )
        cutoff = utc_now() - timedelta(seconds=window_seconds)
        return [e for e in events if self._event_time(e.created_at) >= cutoff]

    def _event_time(self, value):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    def _build_details(self, detection: WifiProbeDetection) -> str:
        return "frame_type={0}; ssid={1}; rssi={2}; interface={3}; channel={4}".format(
            detection.frame_type,
            detection.ssid or "",
            detection.rssi if detection.rssi is not None else "",
            detection.interface or "",
            detection.channel if detection.channel is not None else "",
        )
