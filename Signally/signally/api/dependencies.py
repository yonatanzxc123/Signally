"""
Dependency wiring for the Signally API.

This file builds the shared services and demo providers used by FastAPI.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from signally.admin.admin_manager import AdminManager
from signally.db.session import SessionLocal
from signally.network_scanner.dto import DiscoveredDevice
from signally.sensors.mock_csi_provider import MockCsiDetectionProvider
from signally.sensors.mock_wifi_probe_provider import MockWifiProbeProvider
from signally.services.alert_service import AlertService
from signally.services.decision_service import DecisionService
from signally.services.device_service import DeviceService
from signally.services.event_service import EventService
from signally.services.monitoring_service import MonitoringService
from signally.services.presence_service import PresenceService


# Shared demo providers
mock_csi_provider = MockCsiDetectionProvider()
mock_wifi_provider = MockWifiProbeProvider(
    visible_devices=[
        # You can keep this empty by default if you prefer.
        # Example owner device can be inserted here for early demo setup.
    ]
)


def get_db_session() -> Session:
    """
    Return a new SQLAlchemy session.
    """
    return SessionLocal()


def build_services(session: Session) -> dict:
    """
    Construct all business services for a request.
    """
    event_service = EventService(session)
    device_service = DeviceService(session)
    presence_service = PresenceService(session)
    decision_service = DecisionService()
    alert_service = AlertService(event_service)
    admin_manager = AdminManager(device_service, event_service)

    monitoring_service = MonitoringService(
        csi_provider=mock_csi_provider,
        wifi_probe_provider=mock_wifi_provider,
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
    """
    Optional helper:
    ensure there is a known owner device in the database for demo purposes.
    This does not make the device present, it only ensures it exists and can
    later be marked as AUTHORIZED.
    """
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