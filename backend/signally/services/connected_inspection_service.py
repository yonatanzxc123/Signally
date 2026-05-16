"""
Connected-device inspection.

ARP tells us which IPs are connected. This service inspects those IPs with
local-network tools that can reveal device type:
- mDNS/DNS-SD via avahi-browse, when available
- Nmap OS/service detection, when available

The service is intentionally best-effort. Missing tools, silent phones, or
closed ports should produce an UNKNOWN result rather than an error.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from signally.models.device import Device
from signally.models.event import Event
from signally.services.event_service import EventService


EVENT_DEVICE_INSPECTION_COMPLETED = "DEVICE_INSPECTION_COMPLETED"
EVENT_DEVICE_INSPECTION_FAILED = "DEVICE_INSPECTION_FAILED"


@dataclass
class ConnectedInspectionResult:
    device_category: str = "UNKNOWN"
    confidence: float = 0.0
    hostname: Optional[str] = None
    mdns_services: list[str] = field(default_factory=list)
    nmap_device_type: Optional[str] = None
    nmap_os: Optional[str] = None
    open_ports: list[str] = field(default_factory=list)
    signals: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(
            {
                "device_category": self.device_category,
                "confidence": self.confidence,
                "hostname": self.hostname,
                "mdns_services": self.mdns_services,
                "nmap_device_type": self.nmap_device_type,
                "nmap_os": self.nmap_os,
                "open_ports": self.open_ports,
                "signals": self.signals,
            },
            sort_keys=True,
        )

    @classmethod
    def from_json(cls, value: str) -> "ConnectedInspectionResult":
        data = json.loads(value)
        return cls(
            device_category=data.get("device_category", "UNKNOWN"),
            confidence=float(data.get("confidence", 0.0)),
            hostname=data.get("hostname"),
            mdns_services=list(data.get("mdns_services", [])),
            nmap_device_type=data.get("nmap_device_type"),
            nmap_os=data.get("nmap_os"),
            open_ports=list(data.get("open_ports", [])),
            signals=list(data.get("signals", [])),
        )


class ConnectedInspectionService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.event_service = EventService(session)

    def inspect_device(self, device: Device) -> ConnectedInspectionResult:
        if not device.ip_address or device.ip_address.upper() == "UNASSOCIATED":
            return ConnectedInspectionResult()

        mdns = self._inspect_mdns(device.ip_address)
        nmap = self._inspect_nmap(device.ip_address)
        result = self._merge_results(mdns=mdns, nmap=nmap)

        self.event_service.log_event(
            event_type=EVENT_DEVICE_INSPECTION_COMPLETED,
            details=result.to_json(),
            device_mac=device.mac_address,
        )
        return result

    def get_latest_result(self, mac_address: str) -> Optional[ConnectedInspectionResult]:
        stmt = (
            select(Event)
            .where(Event.device_mac == mac_address.upper())
            .where(Event.event_type == EVENT_DEVICE_INSPECTION_COMPLETED)
            .order_by(desc(Event.created_at))
            .limit(1)
        )
        event = self.session.scalar(stmt)
        if event is None:
            return None
        try:
            return ConnectedInspectionResult.from_json(event.details)
        except (TypeError, ValueError, json.JSONDecodeError):
            return None

    def _inspect_mdns(self, ip_address: str) -> ConnectedInspectionResult:
        if shutil.which("avahi-browse") is None:
            return ConnectedInspectionResult()

        try:
            result = subprocess.run(
                ["avahi-browse", "-artp"],
                capture_output=True,
                text=True,
                timeout=5,
            )
        except Exception:
            return ConnectedInspectionResult()

        services = []
        hostname = None

        for line in result.stdout.splitlines():
            parts = line.split(";")
            if len(parts) < 8 or parts[0] != "=":
                continue
            service_name = parts[3].strip()
            service_type = parts[4].strip()
            host = parts[6].strip()
            address = parts[7].strip()
            if address != ip_address:
                continue
            if service_type and service_type not in services:
                services.append(service_type)
            if service_name and service_name not in services:
                services.append(service_name)
            if host:
                hostname = host.rstrip(".")

        category, confidence = self._classify_from_mdns(services)
        signals = ["MDNS"] if services else []
        return ConnectedInspectionResult(
            device_category=category,
            confidence=confidence,
            hostname=hostname,
            mdns_services=services,
            signals=signals,
        )

    def _inspect_nmap(self, ip_address: str) -> ConnectedInspectionResult:
        if shutil.which("nmap") is None:
            return ConnectedInspectionResult()

        try:
            result = subprocess.run(
                ["nmap", "-O", "-sV", "--osscan-limit", "-oX", "-", ip_address],
                capture_output=True,
                text=True,
                timeout=25,
            )
        except Exception:
            return ConnectedInspectionResult()

        if not result.stdout.strip():
            return ConnectedInspectionResult()

        try:
            root = ET.fromstring(result.stdout)
        except ET.ParseError:
            return ConnectedInspectionResult()

        hostname = None
        hostname_element = root.find(".//hostnames/hostname")
        if hostname_element is not None:
            hostname = hostname_element.attrib.get("name")

        os_match = root.find(".//osmatch")
        os_name = os_match.attrib.get("name") if os_match is not None else None

        os_class = root.find(".//osclass")
        nmap_device_type = os_class.attrib.get("type") if os_class is not None else None

        open_ports = []
        for port in root.findall(".//ports/port"):
            state = port.find("state")
            if state is None or state.attrib.get("state") != "open":
                continue
            service = port.find("service")
            service_name = service.attrib.get("name") if service is not None else "unknown"
            open_ports.append("{0}/{1}".format(port.attrib.get("portid"), service_name))

        category, confidence = self._classify_from_nmap(
            device_type=nmap_device_type,
            os_name=os_name,
            open_ports=open_ports,
        )
        signals = []
        if nmap_device_type or os_name:
            signals.append("NMAP_OS")
        if open_ports:
            signals.append("NMAP_SERVICES")

        return ConnectedInspectionResult(
            device_category=category,
            confidence=confidence,
            hostname=hostname,
            nmap_device_type=nmap_device_type,
            nmap_os=os_name,
            open_ports=open_ports,
            signals=signals,
        )

    def _merge_results(
        self,
        mdns: ConnectedInspectionResult,
        nmap: ConnectedInspectionResult,
    ) -> ConnectedInspectionResult:
        if mdns.confidence >= nmap.confidence:
            category = mdns.device_category
            confidence = mdns.confidence
        else:
            category = nmap.device_category
            confidence = nmap.confidence

        return ConnectedInspectionResult(
            device_category=category,
            confidence=round(confidence, 2),
            hostname=mdns.hostname or nmap.hostname,
            mdns_services=mdns.mdns_services,
            nmap_device_type=nmap.nmap_device_type,
            nmap_os=nmap.nmap_os,
            open_ports=nmap.open_ports,
            signals=mdns.signals + nmap.signals,
        )

    def _classify_from_mdns(self, services: list[str]) -> tuple[str, float]:
        text = " ".join(services).lower()
        if not text:
            return "UNKNOWN", 0.0
        if any(token in text for token in ("androidtv", "googlecast", "airplay", "raop")):
            return "TV", 0.85
        if any(token in text for token in ("ipp", "printer", "pdl-datastream")):
            return "PRINTER", 0.90
        if any(token in text for token in ("hap", "homekit", "ewelink", "matter")):
            return "IOT", 0.82
        if any(token in text for token in ("smb", "ssh", "sftp", "workstation")):
            return "COMPUTER", 0.72
        if any(token in text for token in ("companion-link", "apple-mobdev2")):
            return "PHONE", 0.72
        return "UNKNOWN", 0.25

    def _classify_from_nmap(
        self,
        device_type: Optional[str],
        os_name: Optional[str],
        open_ports: list[str],
    ) -> tuple[str, float]:
        text = " ".join([device_type or "", os_name or "", " ".join(open_ports)]).lower()
        if not text.strip():
            return "UNKNOWN", 0.0
        if "phone" in text or "android" in text or "ios" in text:
            return "PHONE", 0.70
        if "media" in text or "tv" in text or "chromecast" in text:
            return "TV", 0.72
        if "printer" in text or "ipp" in text or "jetdirect" in text:
            return "PRINTER", 0.82
        if "router" in text or "wap" in text:
            return "ROUTER", 0.78
        if "general purpose" in text or "linux" in text or "windows" in text or "mac os" in text:
            return "COMPUTER", 0.58
        return "UNKNOWN", 0.20
