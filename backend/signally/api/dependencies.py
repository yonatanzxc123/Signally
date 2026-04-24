"""
Dependency wiring for the Signally API.
"""

from sqlalchemy.orm import Session

from signally.admin.admin_manager import AdminManager
from signally.db.session import SessionLocal
from signally.sensors.csi_provider import FlagCsiDetectionProvider
from signally.services.device_service import DeviceService
from signally.services.event_service import EventService
from signally.wifi_probing.wifi_probing_state import WifiProbingState

csi_provider = FlagCsiDetectionProvider()
wifi_probing_state = WifiProbingState(SessionLocal)


def get_db_session() -> Session:
    return SessionLocal()


def build_services(session: Session) -> dict:
    event_service = EventService(session)
    device_service = DeviceService(session)
    admin_manager = AdminManager(device_service, event_service)

    return {
        "event_service": event_service,
        "device_service": device_service,
        "admin_manager": admin_manager,
    }
