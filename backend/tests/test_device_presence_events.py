from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from signally.db.base import Base
from signally.models.event import Event
from signally.network_scanner.dto import DiscoveredDevice
from signally.services.device_service import DeviceService
from signally.services.presence_service import PresenceService


def build_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return session_factory()


def test_known_arp_device_logs_seen_again_and_stays_present():
    session = build_session()
    device_service = DeviceService(session)
    presence_service = PresenceService(session, presence_window_seconds=30)
    discovered = [
        DiscoveredDevice(
            mac_address="AA:BB:CC:DD:EE:10",
            ip_address="192.168.1.10",
        )
    ]

    device_service.process_scan_results(discovered)
    device_service.process_scan_results(discovered)

    events = session.query(Event).order_by(Event.id).all()
    present_devices = presence_service.get_present_devices()

    assert [event.event_type for event in events] == [
        "DEVICE_DISCOVERED_NEW",
        "DEVICE_SEEN_AGAIN",
    ]
    assert len(present_devices) == 1
    assert present_devices[0].mac_address == "AA:BB:CC:DD:EE:10"
