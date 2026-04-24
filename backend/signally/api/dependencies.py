"""
Dependency wiring for the Signally API.
"""

from sqlalchemy.orm import Session

from signally.admin.admin_manager import AdminManager
from signally.db.session import SessionLocal
from signally.sensors.csi_provider import FlagCsiDetectionProvider
from signally.services.alert_service import AlertService
from signally.services.correlation_service import CorrelationService
from signally.services.device_service import DeviceService
from signally.services.event_service import EventService
from signally.services.presence_service import PresenceService


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
