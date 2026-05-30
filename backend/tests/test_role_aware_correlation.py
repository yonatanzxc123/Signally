from datetime import timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from signally.admin.admin_manager import AdminManager
from signally.db.base import Base
from signally.models.device import Device
from signally.models.correlation_models import CorrelationContext
from signally.models.security_mode import SecurityMode
from signally.models.user import DeviceOwner, User, UserRole
from signally.network_scanner.dto import DiscoveredDevice
from signally.services.correlation_service import CorrelationService
from signally.services.device_service import DeviceService
from signally.services.event_service import EventService
from signally.services.presence_service import PresenceService
from signally.services.user_service import UserService
from signally.utils.time_utils import utc_now
from signally.wifi_probing.dto import WifiProbeDetection
from signally.wifi_probing.wifi_probing_service import WifiProbingService


def build_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return session_factory()


def build_services(session):
    device_service = DeviceService(session)
    event_service = EventService(session)
    user_service = UserService(session)
    admin_manager = AdminManager(device_service, event_service, user_service)
    presence_service = PresenceService(session, presence_window_seconds=30)
    return device_service, user_service, admin_manager, presence_service


def scan_one(device_service, mac_address, ip_address):
    device_service.process_scan_results(
        [DiscoveredDevice(mac_address=mac_address, ip_address=ip_address)]
    )


def test_family_role_cannot_approve_devices():
    session = build_session()
    device_service, _, admin_manager, _ = build_services(session)
    scan_one(device_service, "AA:BB:CC:DD:EE:20", "192.168.1.20")

    with pytest.raises(PermissionError):
        admin_manager.approve_device(
            "AA:BB:CC:DD:EE:20",
            actor_role=UserRole.FAMILY,
        )


def test_intruder_enters_admin_review_before_family_alert():
    session = build_session()
    device_service, _, admin_manager, presence_service = build_services(session)

    scan_one(device_service, "AA:BB:CC:DD:EE:21", "192.168.1.21")
    scan_one(device_service, "AA:BB:CC:DD:EE:22", "192.168.1.22")
    scan_one(device_service, "AA:BB:CC:DD:EE:23", "192.168.1.23")
    admin_manager.approve_device(
        "AA:BB:CC:DD:EE:21",
        owner_name="Admin Phone",
        owner_role=UserRole.ADMIN,
    )
    admin_manager.approve_device(
        "AA:BB:CC:DD:EE:22",
        owner_name="Family Phone",
        owner_role=UserRole.FAMILY,
    )

    connected_presence = presence_service.get_presence_snapshot()
    nearby_presence = WifiProbingService(session).get_presence_snapshot(connected_presence)
    decision = CorrelationService().evaluate(
        CorrelationContext(
            csi_presence_detected=True,
            nearby_device_count=len(nearby_presence.nearby_devices),
            connected_presence=connected_presence,
            nearby_presence=nearby_presence,
            security_mode=SecurityMode.AWAY,
        )
    )

    assert connected_presence.admin_present is True
    assert connected_presence.family_present is True
    assert decision.decision == "ADMIN_REVIEW"
    assert decision.notification_audience == ["ADMIN"]
    assert decision.current_intruder_count == 1


def test_unresolved_intruder_escalates_to_family_after_review_window():
    session = build_session()
    device_service, _, admin_manager, presence_service = build_services(session)

    scan_one(device_service, "AA:BB:CC:DD:EE:24", "192.168.1.24")
    scan_one(device_service, "AA:BB:CC:DD:EE:25", "192.168.1.25")
    admin_manager.approve_device(
        "AA:BB:CC:DD:EE:24",
        owner_name="Admin Phone",
        owner_role=UserRole.ADMIN,
    )

    intruder = session.query(Device).filter_by(mac_address="AA:BB:CC:DD:EE:25").one()
    intruder.first_seen = utc_now() - timedelta(seconds=31)
    session.commit()

    connected_presence = presence_service.get_presence_snapshot()
    nearby_presence = WifiProbingService(session).get_presence_snapshot(connected_presence)
    decision = CorrelationService().evaluate(
        CorrelationContext(
            csi_presence_detected=True,
            nearby_device_count=len(nearby_presence.nearby_devices),
            connected_presence=connected_presence,
            nearby_presence=nearby_presence,
            security_mode=SecurityMode.AWAY,
        )
    )

    assert decision.decision == "ALERT"
    assert decision.notification_audience == ["ADMIN", "FAMILY"]
    assert decision.admin_review_grace_active is False


def test_home_mode_unknown_device_enters_review_without_loud_alert():
    session = build_session()
    device_service, _, admin_manager, presence_service = build_services(session)

    scan_one(device_service, "AA:BB:CC:DD:EE:28", "192.168.1.28")
    scan_one(device_service, "AA:BB:CC:DD:EE:29", "192.168.1.29")
    admin_manager.approve_device(
        "AA:BB:CC:DD:EE:28",
        owner_name="Admin Phone",
        owner_role=UserRole.ADMIN,
    )

    connected_presence = presence_service.get_presence_snapshot()
    nearby_presence = WifiProbingService(session).get_presence_snapshot(connected_presence)
    decision = CorrelationService().evaluate(
        CorrelationContext(
            csi_presence_detected=True,
            nearby_device_count=len(nearby_presence.nearby_devices),
            connected_presence=connected_presence,
            nearby_presence=nearby_presence,
            security_mode=SecurityMode.HOME,
        )
    )

    assert decision.decision == "HOME_REVIEW"
    assert decision.security_mode == SecurityMode.HOME
    assert decision.notification_audience == ["ADMIN"]


def test_home_mode_csi_without_recent_phone_is_occupied_not_intruder():
    session = build_session()
    _, _, _, presence_service = build_services(session)

    connected_presence = presence_service.get_presence_snapshot()
    nearby_presence = WifiProbingService(session).get_presence_snapshot(connected_presence)
    decision = CorrelationService().evaluate(
        CorrelationContext(
            csi_presence_detected=True,
            nearby_device_count=len(nearby_presence.nearby_devices),
            connected_presence=connected_presence,
            nearby_presence=nearby_presence,
            security_mode=SecurityMode.HOME,
        )
    )

    assert decision.decision == "HOME_OCCUPIED"
    assert decision.notification_audience == []


def test_reset_database_content_deletes_users_and_device_owners():
    session = build_session()
    device_service, _, admin_manager, _ = build_services(session)
    scan_one(device_service, "AA:BB:CC:DD:EE:27", "192.168.1.27")
    admin_manager.approve_device(
        "AA:BB:CC:DD:EE:27",
        owner_name="Admin Phone",
        owner_role=UserRole.ADMIN,
    )

    result = admin_manager.reset_database_content()

    assert result["deleted_devices"] == 1
    assert result["deleted_users"] == 1
    assert result["deleted_device_owners"] == 1
    assert session.query(Device).count() == 0
    assert session.query(User).count() == 0
    assert session.query(DeviceOwner).count() == 0
