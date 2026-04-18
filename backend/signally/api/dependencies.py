"""
Dependency wiring for the Signally API.
"""

from typing import Dict

from sqlalchemy.orm import Session

from signally.admin.admin_manager import AdminManager
from signally.db.session import SessionLocal
from signally.network_scanner.dto import DiscoveredDevice
from signally.sensors.csi_provider import AlwaysOffCsiProvider, AlwaysOnCsiProvider
from signally.sensors.mock_csi_provider import MockCsiDetectionProvider
from signally.sensors.mock_wifi_probe_provider import MockWifiProbeProvider
from signally.sensors.wifi_probe_provider import WifiProbeProvider
from signally.services.alert_service import AlertService
from signally.services.decision_service import DecisionService
from signally.services.device_service import DeviceService
from signally.services.event_service import EventService
from signally.services.monitoring_service import MonitoringService
from signally.services.presence_service import PresenceService


mock_csi_provider = MockCsiDetectionProvider()
mock_wifi_provider = MockWifiProbeProvider()
real_wifi_provider = WifiProbeProvider()
always_on_csi_provider = AlwaysOnCsiProvider()
always_off_csi_provider = AlwaysOffCsiProvider()

_RUNTIME_MODES = {
    "wifi_mode": "mock",
    "csi_mode": "mock",
}  # type: Dict[str, str]


def get_db_session() -> Session:
    return SessionLocal()


def get_current_wifi_provider():
    if _RUNTIME_MODES["wifi_mode"] == "real":
        return real_wifi_provider
    return mock_wifi_provider


def get_current_csi_provider():
    if _RUNTIME_MODES["csi_mode"] == "always_on":
        return always_on_csi_provider
    if _RUNTIME_MODES["csi_mode"] == "always_off":
        return always_off_csi_provider
    return mock_csi_provider


def set_wifi_mode(mode: str) -> None:
    if mode not in ("mock", "real"):
        raise ValueError("wifi mode must be 'mock' or 'real'")
    _RUNTIME_MODES["wifi_mode"] = mode


def set_csi_mode(mode: str) -> None:
    if mode not in ("mock", "always_on", "always_off"):
        raise ValueError("csi mode must be 'mock', 'always_on', or 'always_off'")
    _RUNTIME_MODES["csi_mode"] = mode


def get_mode_state() -> Dict[str, str]:
    return dict(_RUNTIME_MODES)


def build_services(session: Session) -> dict:
    event_service = EventService(session)
    device_service = DeviceService(session)
    presence_service = PresenceService(session)
    decision_service = DecisionService()
    alert_service = AlertService(event_service)
    admin_manager = AdminManager(device_service, event_service)

    monitoring_service = MonitoringService(
        csi_provider=get_current_csi_provider(),
        wifi_probe_provider=get_current_wifi_provider(),
        device_service=device_service,
        presence_service=presence_service,
        decision_service=decision_service,
        alert_service=alert_service,
        event_service=event_service,
    )

    return {
        "event_service": event_service,
        "device_service": device_service,
        "presence_service": presence_service,
        "decision_service": decision_service,
        "alert_service": alert_service,
        "admin_manager": admin_manager,
        "monitoring_service": monitoring_service,
    }


def seed_demo_owner_if_missing() -> None:
    session = SessionLocal()
    try:
        device_service = DeviceService(session)

        owner_mac = "AA:BB:CC:DD:EE:01"
        owner = device_service.get_by_mac(owner_mac)

        if owner is None:
            device_service.process_scan_results(
                [
                    DiscoveredDevice(
                        ip_address="192.168.1.10",
                        mac_address=owner_mac,
                    )
                ]
            )
    finally:
        session.close()