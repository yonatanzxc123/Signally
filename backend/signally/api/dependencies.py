"""
Dependency wiring for the Signally API.
"""

import os
from sqlalchemy.orm import Session

from signally.admin.admin_manager import AdminManager
from signally.db.session import SessionLocal
from signally.sensors.csi_provider import FlagCsiDetectionProvider, RealCsiDetectionProvider
from signally.services.alert_service import AlertService
from signally.services.correlation_service import CorrelationService
from signally.services.device_service import DeviceService
from signally.services.event_service import EventService
from signally.services.presence_service import PresenceService


#--- CONFIGURABLE CSI TOGGLE ---
# Set to "True" when we want to use the actual Raspberry Pi Wi-Fi adapter stream.
# Set to "False" for we to use the mock one.
USE_REAL_CSI = os.getenv("SIGNALLY_USE_REAL_CSI", "False").lower() == "true"

if USE_REAL_CSI:
    csi_provider = RealCsiDetectionProvider(udp_ip="127.0.0.1", udp_port=5500)
else:
    csi_provider = FlagCsiDetectionProvider()


def get_db_session() -> Session:
    return SessionLocal()


def build_services(session: Session) -> dict:
    event_service = EventService(session)
    device_service = DeviceService(session)
    presence_service = PresenceService(session)
    correlation_service = CorrelationService()
    alert_service = AlertService(event_service)
    admin_manager = AdminManager(device_service, event_service)

    return {
        "event_service": event_service,
        "device_service": device_service,
        "presence_service": presence_service,
        "correlation_service": correlation_service,
        "alert_service": alert_service,
        "admin_manager": admin_manager,
    }
