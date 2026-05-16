"""
Device fingerprinting from signals Signally already collects.

This service is intentionally heuristic. It does not claim exact model-level
identity; it combines ARP connection state, cached connected-device inspection,
ownership, hostname hints, and weak probe history into a device type guess.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy.orm import Session

from signally.config import (
    EVENT_WIFI_PROBE_DEVICE_DISCOVERED_NEW,
    EVENT_WIFI_PROBE_DEVICE_SEEN_AGAIN,
)
from signally.models.device import Device
from signally.services.connected_inspection_service import ConnectedInspectionService
from signally.services.event_service import EventService


PHONE_KEYWORDS = (
    "iphone",
    "ipad",
    "android",
    "galaxy",
    "samsung",
    "pixel",
    "oneplus",
    "xiaomi",
    "redmi",
    "huawei",
)
TV_KEYWORDS = (
    "tv",
    "roku",
    "chromecast",
    "bravia",
    "webos",
    "tizen",
    "lg",
    "samsungtv",
)
IOT_KEYWORDS = (
    "fridge",
    "refrigerator",
    "thermostat",
    "camera",
    "doorbell",
    "plug",
    "bulb",
    "alexa",
    "echo",
    "nest",
)
COMPUTER_KEYWORDS = ("macbook", "windows", "desktop", "laptop", "pc")

@dataclass
class DeviceFingerprint:
    device_category: str = "UNKNOWN"
    display_name: str = "Unknown Device"
    confidence: float = 0.0
    hostname: Optional[str] = None
    randomized_mac: bool = False
    primary_layer: str = "UNKNOWN"
    connected: bool = False
    signals: list[str] = field(default_factory=list)


class FingerprintService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.event_service = EventService(session)
        self.inspection_service = ConnectedInspectionService(session)

    def fingerprint_device(self, device: Device, owner=None) -> DeviceFingerprint:
        randomized_mac = self._is_randomized_mac(device.mac_address)
        inspection = self.inspection_service.get_latest_result(device.mac_address)
        hostname = inspection.hostname if inspection else None
        ssids = self._get_probe_ssids(device.mac_address)

        category = "UNKNOWN"
        confidence = 0.0
        signals = []
        connected = self._is_connected_device(device)
        primary_layer = "ARP" if connected else "PROBING"

        if connected:
            signals.append("ARP_CONNECTED")
            confidence = max(confidence, 0.30)

        if owner is not None:
            category = "PHONE"
            confidence = max(confidence, 0.90 if connected else 0.75)
            signals.append("OWNER_ASSIGNED")

        if randomized_mac:
            signals.append("RANDOMIZED_MAC")

        if inspection is not None:
            signals.extend(inspection.signals)
            if inspection.device_category != "UNKNOWN":
                category = inspection.device_category
                confidence = max(confidence, inspection.confidence)

        if hostname:
            signals.append("HOSTNAME")
            hostname_guess = self._infer_from_text(hostname)
            if hostname_guess is not None:
                category, hostname_confidence = hostname_guess
                if connected:
                    hostname_confidence = min(0.95, hostname_confidence + 0.10)
                confidence = max(confidence, hostname_confidence)

        if ssids:
            signals.append("WIFI_PROBE_SSIDS")
            if category == "UNKNOWN":
                category = "PHONE"
                confidence = max(confidence, 0.40 if randomized_mac else 0.45)
            else:
                confidence = max(confidence, min(0.98, confidence + 0.03))

        if randomized_mac and category == "UNKNOWN":
            display_name = "Randomized MAC Device"
        else:
            display_name = self._build_display_name(
                owner=owner,
                category=category,
                hostname=hostname,
            )

        return DeviceFingerprint(
            device_category=category,
            display_name=display_name,
            confidence=round(confidence, 2),
            hostname=hostname,
            randomized_mac=randomized_mac,
            primary_layer=primary_layer,
            connected=connected,
            signals=signals,
        )

    def _is_randomized_mac(self, mac_address: str) -> bool:
        first_octet = mac_address.replace("-", ":").split(":")[0]
        try:
            value = int(first_octet, 16)
        except ValueError:
            return False
        return bool(value & 0b00000010)

    def _is_connected_device(self, device: Device) -> bool:
        return bool(device.ip_address and device.ip_address.upper() != "UNASSOCIATED")

    def _get_probe_ssids(self, mac_address: str) -> list[str]:
        events = self.event_service.list_events_for_device_by_types(
            device_mac=mac_address,
            event_types=[
                EVENT_WIFI_PROBE_DEVICE_DISCOVERED_NEW,
                EVENT_WIFI_PROBE_DEVICE_SEEN_AGAIN,
            ],
            limit=50,
        )
        ssids = []
        for event in events:
            parsed = self._parse_details(event.details)
            ssid = parsed.get("ssid", "").strip()
            if ssid and ssid not in ssids:
                ssids.append(ssid)
        return ssids

    def _infer_from_text(self, text: str):
        normalized = text.lower().replace("-", "").replace("_", "")
        if any(keyword in normalized for keyword in TV_KEYWORDS):
            return "TV", 0.78
        if any(keyword in normalized for keyword in PHONE_KEYWORDS):
            return "PHONE", 0.80
        if any(keyword in normalized for keyword in IOT_KEYWORDS):
            return "IOT", 0.72
        if any(keyword in normalized for keyword in COMPUTER_KEYWORDS):
            return "COMPUTER", 0.72
        return None

    def _build_display_name(
        self,
        owner,
        category: str,
        hostname: Optional[str],
    ) -> str:
        if owner is not None:
            return owner.display_name
        if hostname:
            return hostname
        if category != "UNKNOWN":
            return category.title()
        return "Unknown Device"

    def _parse_details(self, details: str) -> dict:
        result = {}
        for part in details.split("; "):
            if "=" in part:
                key, _, value = part.partition("=")
                result[key.strip()] = value.strip()
        return result
