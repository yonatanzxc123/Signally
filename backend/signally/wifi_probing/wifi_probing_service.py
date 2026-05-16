"""
Persistence service for Wi-Fi probing detections.
"""

from __future__ import annotations

from datetime import timedelta, timezone
from typing import List, Set

from sqlalchemy.orm import Session

from signally.config import (
    CURRENT_UNKNOWN_WINDOW_SECONDS,
    EVENT_WIFI_PROBE_DEVICE_DISCOVERED_NEW,
    EVENT_WIFI_PROBE_DEVICE_SEEN_AGAIN,
    EVENT_WIFI_PROBING_ERROR,
    WIFI_PROBING_RECENT_EVENT_LIMIT,
    WIFI_PROBING_STRONG_RSSI_MIN,
    EVENT_WIFI_PROBING_STARTED,
    EVENT_WIFI_PROBING_STOPPED,
    NETWORK_SSID,
)
from signally.models.correlation_models import ConnectedPresenceSnapshot, NearbyPresenceSnapshot
from signally.models.device import Device, DeviceStatus
from signally.services.device_service import DeviceService
from signally.services.event_service import EventService
from signally.utils.time_utils import utc_now
from signally.wifi_probing.dto import WifiProbeDetection


WIFI_PROBE_DEVICE_EVENT_TYPES = (
    EVENT_WIFI_PROBE_DEVICE_DISCOVERED_NEW,
    EVENT_WIFI_PROBE_DEVICE_SEEN_AGAIN,
)


class WifiProbingService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.device_service = DeviceService(session)
        self.event_service = EventService(session)

    def handle_detection(self, detection: WifiProbeDetection) -> "Device | None":
        if NETWORK_SSID and detection.ssid != NETWORK_SSID:
            return None
        if not self._has_strong_signal(detection):
            return None

        # Deduplicate by SSID within 60-second window to handle MAC randomization
        if detection.ssid:
            recent_event = self.event_service.find_recent_probe_event_by_ssid(
                ssid=detection.ssid,
                event_types=(EVENT_WIFI_PROBE_DEVICE_DISCOVERED_NEW, EVENT_WIFI_PROBE_DEVICE_SEEN_AGAIN),
            )
            if recent_event and recent_event.device_mac:
                existing = self.device_service.get_by_mac(recent_event.device_mac)
                if existing:
                    existing, _ = self.device_service.upsert_seen_device(
                        mac_address=existing.mac_address,
                        ip_address=None,
                    )
                    self.event_service.log_event(
                        event_type=EVENT_WIFI_PROBE_DEVICE_SEEN_AGAIN,
                        details=self._build_details(detection),
                        device_mac=existing.mac_address,
                    )
                    return existing

        device, created = self.device_service.upsert_seen_device(
            mac_address=detection.mac_address,
            ip_address=None,
        )

        if created:
            self.event_service.log_event(
                event_type=EVENT_WIFI_PROBE_DEVICE_DISCOVERED_NEW,
                details=self._build_details(detection),
                device_mac=device.mac_address,
            )
        else:
            self.event_service.log_event(
                event_type=EVENT_WIFI_PROBE_DEVICE_SEEN_AGAIN,
                details=self._build_details(detection),
                device_mac=device.mac_address,
            )
        return device

    def list_recent_devices(
        self,
        limit: int = 50,
        window_seconds: int | None = None,
    ) -> List[Device]:
        events = self._list_probe_events(window_seconds=window_seconds)
        devices = []
        seen_macs = set()  # type: Set[str]

        for event in events:
            if not event.device_mac:
                continue

            mac_address = event.device_mac.upper()
            if mac_address in seen_macs:
                continue

            device = self.device_service.get_by_mac(mac_address)
            if device is None:
                continue

            devices.append(device)
            seen_macs.add(mac_address)

            if len(devices) >= limit:
                break

        return devices

    def get_presence_snapshot(
        self,
        connected_presence: ConnectedPresenceSnapshot,
        limit: int = 50,
        window_seconds: int = CURRENT_UNKNOWN_WINDOW_SECONDS,
    ) -> NearbyPresenceSnapshot:
        events = self._list_probe_events(window_seconds=window_seconds)
        devices = []
        seen_macs = set()  # type: Set[str]
        first_seen_by_mac = {}

        for event in events:
            if not event.device_mac:
                continue

            mac_address = event.device_mac.upper()
            event_time = self._event_time(event.created_at)
            current_first_seen = first_seen_by_mac.get(mac_address)
            if current_first_seen is None or event_time < current_first_seen:
                first_seen_by_mac[mac_address] = event_time

            if mac_address in seen_macs:
                continue

            device = self.device_service.get_by_mac(mac_address)
            if device is None:
                continue

            devices.append(device)
            seen_macs.add(mac_address)

            if len(devices) >= limit:
                break

        unknown_nearby = [d for d in devices if d.status == DeviceStatus.PENDING]
        blocked_nearby = [d for d in devices if d.status == DeviceStatus.BLOCKED]

        duplicate_allowance = len(connected_presence.authorised_connected_devices)
        ignored_duplicate_count = min(len(unknown_nearby), duplicate_allowance)
        effective_unknown = unknown_nearby[ignored_duplicate_count:]

        first_unknown_seen_at = None
        for device in effective_unknown:
            event_time = first_seen_by_mac.get(device.mac_address)
            if event_time is None:
                continue
            if first_unknown_seen_at is None or event_time < first_unknown_seen_at:
                first_unknown_seen_at = event_time

        return NearbyPresenceSnapshot(
            nearby_devices=devices,
            unknown_nearby_devices=unknown_nearby,
            blocked_nearby_devices=blocked_nearby,
            effective_unknown_nearby_devices=effective_unknown,
            ignored_authorized_duplicate_count=ignored_duplicate_count,
            first_unknown_seen_at=first_unknown_seen_at,
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

    def _list_probe_events(self, window_seconds: int | None = None):
        events = self.event_service.list_recent_events_by_types(
            event_types=WIFI_PROBE_DEVICE_EVENT_TYPES,
            limit=WIFI_PROBING_RECENT_EVENT_LIMIT,
        )
        if window_seconds is None:
            return events

        cutoff = utc_now() - timedelta(seconds=window_seconds)
        return [
            event
            for event in events
            if self._event_time(event.created_at) >= cutoff
        ]

    def _event_time(self, value):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    def _build_details(self, detection: WifiProbeDetection) -> str:
        return (
            "frame_type={0}; ssid={1}; rssi={2}; interface={3}; channel={4}".format(
                detection.frame_type,
                detection.ssid or "",
                detection.rssi if detection.rssi is not None else "",
                detection.interface or "",
                detection.channel if detection.channel is not None else "",
            )
        )
