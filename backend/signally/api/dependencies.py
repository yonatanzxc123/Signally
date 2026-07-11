"""
Dependency wiring for the Signally API.
"""

from sqlalchemy.orm import Session

from signally.admin.admin_manager import AdminManager
from signally.db.session import SessionLocal
from signally.sensors.csi_provider import FlagCsiDetectionProvider, RealCsiDetectionProvider
from signally.services.alert_service import AlertService
from signally.services.background_monitor import BackgroundMonitor
from signally.services.correlation_service import CorrelationService
from signally.services.device_service import DeviceService
from signally.services.event_service import EventService
from signally.services.presence_service import PresenceService
from signally.services.security_mode_service import SecurityModeService
from signally.services.system_state_service import SystemStateService
from signally.services.user_service import UserService
from signally.wifi_probing.wifi_probing_state import WifiProbingState
from signally.sensors.csi_provider import AutoFallbackCsiProvider



csi_provider = AutoFallbackCsiProvider()
wifi_probing_state = WifiProbingState(SessionLocal)
background_monitor = BackgroundMonitor(SessionLocal, csi_provider)

def get_db_session() -> Session:
    return SessionLocal()


def build_services(session: Session) -> dict:
    event_service = EventService(session)
    device_service = DeviceService(session)
    user_service = UserService(session)
    presence_service = PresenceService(session)
    security_mode_service = SecurityModeService(session)
    correlation_service = CorrelationService()
    alert_service = AlertService(event_service)
    admin_manager = AdminManager(device_service, event_service, user_service)
    system_state_service = SystemStateService(session, csi_provider)

    return {
        "event_service": event_service,
        "device_service": device_service,
        "presence_service": presence_service,
        "security_mode_service": security_mode_service,
        "user_service": user_service,
        "correlation_service": correlation_service,
        "alert_service": alert_service,
        "admin_manager": admin_manager,
        "system_state_service": system_state_service,
    }
