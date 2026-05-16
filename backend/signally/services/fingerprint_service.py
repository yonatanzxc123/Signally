"""
Device fingerprinting from signals Signally already collects.

This service is intentionally heuristic. It does not claim exact model-level
identity; it combines vendor, hostname/IP hints, ownership, and probe history
into a useful category/manufacturer guess with confidence and signal reasons.
"""

from __future__ import annotations

import socket
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from signally.config import (
    EVENT_WIFI_PROBE_DEVICE_DISCOVERED_NEW,
    EVENT_WIFI_PROBE_DEVICE_SEEN_AGAIN,
)
from signally.models.device import Device
from signally.models.event import Event
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

VENDOR_HINTS = {
    "apple": ("PHONE", "Apple", 0.70),
    "samsung": ("PHONE", "Samsung", 0.62),
    "google": ("PHONE", "Google", 0.58),
    "xiaomi": ("PHONE", "Xiaomi", 0.58),
    "huawei": ("PHONE", "Huawei", 0.58),
    "oneplus": ("PHONE", "OnePlus", 0.58),
    "lg": ("TV", "LG", 0.55),
    "roku": ("TV", "Roku", 0.65),
    "amazon": ("IOT", "Amazon", 0.50),
    "sonos": ("IOT", "Sonos", 0.65),
    "philips": ("IOT", "Philips", 0.55),
}

OFFLINE_OUI_VENDOR_HINTS = {
    # Observed during Signally testing. Public OUI lookups report this as Samsung.
    "38:8A:06": "Samsung Electronics Co.,Ltd",
    # A small offline safety net for common demo devices when Scapy's manuf DB
    # is missing or stale on the Raspberry Pi.
    "A4:C3:F0": "Apple, Inc.",
    "B8:27:EB": "Raspberry Pi Foundation",
    "DC:A6:32": "Raspberry Pi Trading Ltd",
    "F0:18:98": "Apple, Inc.",
}


@dataclass
class DeviceFingerprint:
    manufacturer: Optional[str] = None
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

    def fingerprint_device(self, device: Device, owner=None) -> DeviceFingerprint:
        randomized_mac = self._is_randomized_mac(device.mac_address)
        vendor = self._get_vendor(device.mac_address)
        hostname = self._get_hostname_hint(device.mac_address) or self._get_hostname(device.ip_address)
        ssids = self._get_probe_ssids(device.mac_address)

        category = "UNKNOWN"
        manufacturer = vendor
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

        if vendor:
            signals.append("MAC_VENDOR")
            inferred = self._infer_from_vendor(vendor)
            if inferred is not None:
                category, manufacturer, vendor_confidence = inferred
                if connected and not randomized_mac:
                    vendor_confidence = min(0.85, vendor_confidence + 0.10)
                confidence = max(confidence, vendor_confidence)

        if hostname:
            signals.append("HOSTNAME_HINT" if self._get_hostname_hint(device.mac_address) else "HOSTNAME")
            hostname_guess = self._infer_from_text(hostname)
            if hostname_guess is not None:
                category, hostname_manufacturer, hostname_confidence = hostname_guess
                manufacturer = manufacturer or hostname_manufacturer
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
                manufacturer=manufacturer,
                hostname=hostname,
            )

        return DeviceFingerprint(
            manufacturer=manufacturer,
            device_category=category,
            display_name=display_name,
            confidence=round(confidence, 2),
            hostname=hostname,
            randomized_mac=randomized_mac,
            primary_layer=primary_layer,
            connected=connected,
            signals=signals,
        )

    def _get_vendor(self, mac_address: str) -> Optional[str]:
        if self._is_randomized_mac(mac_address):
            return None
        try:
            from scapy.all import conf

            vendor = conf.manufdb.getManufLong(mac_address)
            if vendor:
                return vendor
        except Exception:
            pass

        prefix = mac_address.upper().replace("-", ":")[:8]
        return OFFLINE_OUI_VENDOR_HINTS.get(prefix)

    def _is_randomized_mac(self, mac_address: str) -> bool:
        first_octet = mac_address.replace("-", ":").split(":")[0]
        try:
            value = int(first_octet, 16)
        except ValueError:
            return False
        return bool(value & 0b00000010)

    def _is_connected_device(self, device: Device) -> bool:
        return bool(device.ip_address and device.ip_address.upper() != "UNASSOCIATED")

    def _get_hostname(self, ip_address: Optional[str]) -> Optional[str]:
        if not ip_address:
            return None
        if ip_address.upper() == "UNASSOCIATED":
            return None
        try:
            hostname, _, _ = socket.gethostbyaddr(ip_address)
            return hostname if hostname else None
        except Exception:
            return None

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

    def _get_hostname_hint(self, mac_address: str) -> Optional[str]:
        stmt = (
            select(Event)
            .where(Event.device_mac == mac_address.upper())
            .where(Event.event_type == "DEVICE_HOSTNAME_HINT_SET")
            .order_by(Event.created_at.desc())
            .limit(1)
        )
        event = self.session.scalar(stmt)
        if event is None:
            return None
        parsed = self._parse_details(event.details)
        hostname = parsed.get("hostname", "").strip()
        return hostname if hostname else None

    def set_hostname_hint(self, mac_address: str, hostname: str) -> None:
        clean_hostname = hostname.strip()
        if not clean_hostname:
            raise ValueError("hostname cannot be empty")
        self.event_service.log_event(
            event_type="DEVICE_HOSTNAME_HINT_SET",
            details="hostname={0}".format(clean_hostname),
            device_mac=mac_address.upper(),
        )

    def _infer_from_vendor(self, vendor: str):
        normalized = vendor.lower()
        for needle, result in VENDOR_HINTS.items():
            if needle in normalized:
                return result
        return None

    def _infer_from_text(self, text: str):
        normalized = text.lower().replace("-", "").replace("_", "")
        if any(keyword in normalized for keyword in TV_KEYWORDS):
            manufacturer = self._manufacturer_from_text(normalized)
            return "TV", manufacturer, 0.78
        if any(keyword in normalized for keyword in PHONE_KEYWORDS):
            manufacturer = self._manufacturer_from_text(normalized)
            return "PHONE", manufacturer, 0.80
        if any(keyword in normalized for keyword in IOT_KEYWORDS):
            manufacturer = self._manufacturer_from_text(normalized)
            return "IOT", manufacturer, 0.72
        if any(keyword in normalized for keyword in COMPUTER_KEYWORDS):
            manufacturer = self._manufacturer_from_text(normalized)
            return "COMPUTER", manufacturer, 0.72
        return None

    def _manufacturer_from_text(self, text: str) -> Optional[str]:
        for manufacturer in ("Apple", "Samsung", "Google", "LG", "Roku", "Amazon"):
            if manufacturer.lower() in text:
                return manufacturer
        if "iphone" in text or "ipad" in text or "macbook" in text:
            return "Apple"
        if "galaxy" in text:
            return "Samsung"
        if "pixel" in text:
            return "Google"
        return None

    def _build_display_name(
        self,
        owner,
        category: str,
        manufacturer: Optional[str],
        hostname: Optional[str],
    ) -> str:
        if owner is not None:
            return owner.display_name
        if hostname:
            return hostname
        if manufacturer and category != "UNKNOWN":
            return "{0} {1}".format(manufacturer, category.title())
        if category != "UNKNOWN":
            return category.title()
        if manufacturer:
            return "{0} Device".format(manufacturer)
        return "Unknown Device"

    def _parse_details(self, details: str) -> dict:
        result = {}
        for part in details.split("; "):
            if "=" in part:
                key, _, value = part.partition("=")
                result[key.strip()] = value.strip()
        return result
