from datetime import timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from signally.config import PRESENCE_WINDOW_SECONDS
from signally.db.base import Base
from signally.models.device import DeviceStatus
from signally.models.event import Event
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


def test_naming_an_already_present_device_arrives_immediately():
    # Regression test for 2026-09-03: a device seen by ARP, then approved
    # and named while still connected, previously never got an "arrived"
    # event unless it happened to be seen again *after* being named -
    # reconcile_scan() only tracks already-named devices, so every prior
    # sighting was invisible to it.
    session, device_service, timeline = build_services()
    device_service.process_scan_results(
        [DiscoveredDevice(mac_address="AA:BB:CC:DD:EE:71", ip_address="192.168.1.71")]
    )
    device = device_service.get_by_mac("AA:BB:CC:DD:EE:71")
    device.status = DeviceStatus.AUTHORIZED
    device.owner_role = "FAMILY"
    session.commit()

    assert timeline.list_timeline() == []

    timeline.set_family_member_name(device, "Tali")

    assert [event.event_type for event in timeline.list_timeline()] == [
        "FAMILY_MEMBER_ENTERED"
    ]


def test_naming_a_long_absent_device_does_not_fabricate_arrival():
    session, device_service, timeline = build_services()
    device_service.process_scan_results(
        [DiscoveredDevice(mac_address="AA:BB:CC:DD:EE:72", ip_address="192.168.1.72")]
    )
    device = device_service.get_by_mac("AA:BB:CC:DD:EE:72")
    device.status = DeviceStatus.AUTHORIZED
    device.owner_role = "FAMILY"
    session.commit()

    # Push the discovery event far enough into the past that it falls
    # outside the presence window - simulates naming someone long after
    # they were last actually seen.
    stale_event = session.scalars(select(Event).where(Event.device_mac == device.mac_address)).one()
    stale_event.created_at = utc_now() - timedelta(seconds=PRESENCE_WINDOW_SECONDS + 30)
    session.commit()

    timeline.set_family_member_name(device, "Tali")

    assert timeline.list_timeline() == []


def test_single_missed_scan_does_not_erase_arrival_progress():
    # With arrival_scans=3, this sequence (hit, hit, miss, hit, hit) never
    # contains 3 *consecutive* hits - the old reset-to-zero behavior would
    # never fire an arrival for it at all. Decaying by one instead lets the
    # two hits before the miss still count for something, so the 5th scan
    # (2 -> 3) crosses the threshold.
    session, device_service, _ = build_services()
    device = family_device(device_service, name="Idan")
    start = utc_now()

    timeline = TimelineService(session, arrival_scans=3, departure_grace_seconds=90)

    timeline.reconcile_scan({device.mac_address}, start)
    timeline.reconcile_scan({device.mac_address}, start + timedelta(seconds=10))
    timeline.reconcile_scan(set(), start + timedelta(seconds=20))  # one missed scan
    timeline.reconcile_scan({device.mac_address}, start + timedelta(seconds=30))
    assert timeline.list_timeline() == []  # not yet - still building back up

    timeline.reconcile_scan({device.mac_address}, start + timedelta(seconds=40))

    assert [event.event_type for event in timeline.list_timeline()] == [
        "FAMILY_MEMBER_ENTERED"
    ]
