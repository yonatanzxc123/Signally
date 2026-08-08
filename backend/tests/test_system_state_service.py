from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from signally.config import EVENT_UNAUTHORIZED_PRESENCE_ALERT
from signally.db.base import Base
from signally.models.device import Device
from signally.models.event import Event
from signally.models.security_mode import SecurityMode, SecurityState
from signally.models.user import User, UserRole
from signally.network_scanner.dto import DiscoveredDevice
from signally.services.device_service import DeviceService
from signally.services.security_mode_service import SecurityModeService
from signally.services.system_state_service import SystemStateService


class FakeCsiProvider:
    def __init__(self, detected=False, strength=None):
        self.detected = detected
        self.strength = strength

    def is_presence_detected(self):
        return self.detected

    def get_presence_strength(self):
        return self.strength


class FailingScanner:
    def scan(self):
        raise AssertionError("local scanner should be disabled")


def build_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return session_factory()


def test_system_state_service_collects_mode_and_normalized_decision():
    session = build_session()
    SecurityModeService(session).set_mode(SecurityMode.AWAY, actor_role=UserRole.ADMIN)
    DeviceService(session).process_scan_results(
        [DiscoveredDevice(mac_address="AA:BB:CC:DD:EE:41", ip_address="192.168.1.41")]
    )

    snapshot = SystemStateService(session, FakeCsiProvider()).collect_state()

    assert snapshot.security_state.mode == SecurityMode.AWAY
    assert snapshot.decision.decision == "ALERT"
    assert snapshot.decision.current_intruder_count == 1


def test_repeated_alert_is_suppressed_within_cooldown():
    session = build_session()
    SecurityModeService(session).set_mode(SecurityMode.AWAY, actor_role=UserRole.ADMIN)
    DeviceService(session).process_scan_results(
        [DiscoveredDevice(mac_address="AA:BB:CC:DD:EE:42", ip_address="192.168.1.42")]
    )
    service = SystemStateService(
        session,
        FakeCsiProvider(),
        alert_cooldown_seconds=60,
    )

    service.collect_state(persist_alerts=True)
    service.collect_state(persist_alerts=True)

    alerts = (
        session.query(Event)
        .filter(Event.event_type == EVENT_UNAUTHORIZED_PRESENCE_ALERT)
        .all()
    )
    assert len(alerts) == 1


def test_different_alert_details_are_not_suppressed():
    session = build_session()
    SecurityModeService(session).set_mode(SecurityMode.AWAY, actor_role=UserRole.ADMIN)
    DeviceService(session).process_scan_results(
        [DiscoveredDevice(mac_address="AA:BB:CC:DD:EE:43", ip_address="192.168.1.43")]
    )
    csi_provider = FakeCsiProvider()
    service = SystemStateService(
        session,
        csi_provider,
        alert_cooldown_seconds=60,
    )

    service.collect_state(persist_alerts=True)
    csi_provider.detected = True
    service.collect_state(persist_alerts=True)

    alerts = (
        session.query(Event)
        .filter(Event.event_type == EVENT_UNAUTHORIZED_PRESENCE_ALERT)
        .all()
    )
    assert len(alerts) == 2


def test_external_arp_mode_skips_the_pi_local_scanner():
    session = build_session()
    service = SystemStateService(
        session,
        FakeCsiProvider(),
        scanner=FailingScanner(),
        local_scan_enabled=False,
    )

    snapshot = service.collect_state(run_scan=True)

    assert snapshot.scan_error is None
    assert snapshot.processed_devices_count == 0
