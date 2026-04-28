"""
Persistence service for Wi-Fi probing detections.
"""

from __future__ import annotations

from typing import List, Set

from sqlalchemy.orm import Session

from signally.config import (
    EVENT_WIFI_PROBE_DEVICE_DISCOVERED_NEW,
    EVENT_WIFI_PROBE_DEVICE_SEEN_AGAIN,
    EVENT_WIFI_PROBING_ERROR,
    WIFI_PROBING_RECENT_EVENT_LIMIT,
    EVENT_WIFI_PROBING_STARTED,
    EVENT_WIFI_PROBING_STOPPED,
    NETWORK_SSID,
)
from signally.models.device import Device
from signally.services.device_service import DeviceService
from signally.services.event_service import EventService
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

        device, created = self.device_service.upsert_seen_device(
            mac_address=detection.mac_address,
            ip_address=None,
        )

        event_type = (
            EVENT_WIFI_PROBE_DEVICE_DISCOVERED_NEW
            if created
            else EVENT_WIFI_PROBE_DEVICE_SEEN_AGAIN
        )
        self.event_service.log_event(
            event_type=event_type,
            details=self._build_details(detection),
            device_mac=device.mac_address,
        )
        return device

    def list_recent_devices(self, limit: int = 50) -> List[Device]:
        events = self.event_service.list_recent_events_by_types(
            event_types=WIFI_PROBE_DEVICE_EVENT_TYPES,
            limit=WIFI_PROBING_RECENT_EVENT_LIMIT,  
        )

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
