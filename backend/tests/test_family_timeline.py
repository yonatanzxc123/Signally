from datetime import timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from signally.db.base import Base
from signally.models.device import DeviceStatus
from signally.network_scanner.dto import DiscoveredDevice
from signally.services.device_service import DeviceService
from signally.services.timeline_service import TimelineService
from signally.utils.time_utils import utc_now


def build_services():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, future=True)()
    return session, DeviceService(session), TimelineService(
        session, arrival_scans=2, departure_grace_seconds=90
    )


def family_device(device_service, name="Idan"):
    device_service.process_scan_results(
        [DiscoveredDevice(mac_address="AA:BB:CC:DD:EE:70", ip_address="192.168.1.70")]
    )
    device = device_service.get_by_mac("AA:BB:CC:DD:EE:70")
    device.status = DeviceStatus.AUTHORIZED
    device.owner_role = "FAMILY"
    device.owner_name = name
    device_service.session.commit()
    return device


def test_two_sightings_create_one_arrival_and_absence_grace_creates_one_departure():
    _, device_service, timeline = build_services()
    device = family_device(device_service)
    start = utc_now()

    timeline.reconcile_scan({device.mac_address}, start)
    assert timeline.list_timeline() == []

    timeline.reconcile_scan({device.mac_address}, start + timedelta(seconds=10))
    timeline.reconcile_scan({device.mac_address}, start + timedelta(seconds=20))
    assert [event.event_type for event in timeline.list_timeline()] == ["FAMILY_MEMBER_ENTERED"]

    timeline.reconcile_scan(set(), start + timedelta(seconds=99))
    assert len(timeline.list_timeline()) == 1

    timeline.reconcile_scan(set(), start + timedelta(seconds=101))
    timeline.reconcile_scan(set(), start + timedelta(seconds=120))
    assert [event.event_type for event in reversed(timeline.list_timeline())] == [
        "FAMILY_MEMBER_ENTERED",
        "FAMILY_MEMBER_LEFT",
    ]


def test_unnamed_family_device_is_not_added_to_timeline():
    _, device_service, timeline = build_services()
    device = family_device(device_service, name=None)
    now = utc_now()

    timeline.reconcile_scan({device.mac_address}, now)
    timeline.reconcile_scan({device.mac_address}, now + timedelta(seconds=10))

    assert timeline.list_timeline() == []
