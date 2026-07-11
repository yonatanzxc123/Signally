from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from signally.db.base import Base
from signally.models.device import Device
from signally.models.event import Event
from signally.wifi_probing.dto import WifiProbeDetection
import signally.wifi_probing.wifi_probing_service as wifi_probing_module
from signally.wifi_probing.wifi_probing_service import WifiProbingService


def build_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return session_factory()


def test_weak_probe_does_not_create_device(monkeypatch):
    monkeypatch.setattr(wifi_probing_module, "WIFI_PROBING_STRONG_RSSI_MIN", -60)
    session = build_session()
    service = WifiProbingService(session)

    result = service.handle_detection(
        WifiProbeDetection(
            mac_address="AA:BB:CC:DD:EE:01",
            frame_type="probe_req",
            ssid="HomeWiFi",
            rssi=-75,
        )
    )

    assert result is None
    assert session.query(Device).count() == 0


def test_probe_without_rssi_does_not_create_device(monkeypatch):
    session = build_session()
    service = WifiProbingService(session)

    result = service.handle_detection(
        WifiProbeDetection(
            mac_address="AA:BB:CC:DD:EE:02",
            frame_type="probe_req",
            ssid="HomeWiFi",
            rssi=None,
        )
    )

    assert result is None
    assert session.query(Device).count() == 0


def test_strong_probe_logs_nearby_activity_without_creating_device(monkeypatch):
    monkeypatch.setattr(wifi_probing_module, "WIFI_PROBING_STRONG_RSSI_MIN", -60)
    session = build_session()
    service = WifiProbingService(session)

    result = service.handle_detection(
        WifiProbeDetection(
            mac_address="AA:BB:CC:DD:EE:03",
            frame_type="probe_req",
            ssid="HomeWiFi",
            rssi=-55,
        )
    )

    assert result is None
    assert session.query(Device).count() == 0
    assert session.query(Event).count() == 1


def test_strong_probe_seen_again_logs_event(monkeypatch):
    monkeypatch.setattr(wifi_probing_module, "WIFI_PROBING_STRONG_RSSI_MIN", -60)
    session = build_session()
    service = WifiProbingService(session)

    detection = WifiProbeDetection(
        mac_address="AA:BB:CC:DD:EE:04",
        frame_type="probe_req",
        ssid="HomeWiFi",
        rssi=-55,
    )

    service.handle_detection(detection)
    result = service.handle_detection(detection)

    assert result is None
    assert session.query(Device).count() == 0
    assert session.query(Event).count() == 2


def test_repeated_probe_same_mac_counts_once_in_nearby_snapshot(monkeypatch):
    monkeypatch.setattr(wifi_probing_module, "WIFI_PROBING_STRONG_RSSI_MIN", -60)
    session = build_session()
    service = WifiProbingService(session)

    detection = WifiProbeDetection(
        mac_address="AA:BB:CC:DD:EE:05",
        frame_type="probe_req",
        ssid="HomeWiFi",
        rssi=-55,
    )
    service.handle_detection(detection)
    service.handle_detection(detection)
    snapshot = service.get_presence_snapshot()

    assert snapshot.nearby_probe_count == 1
