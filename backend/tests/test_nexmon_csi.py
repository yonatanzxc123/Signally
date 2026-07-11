import struct

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from signally.db.base import Base
from signally.models.csi_baseline import CsiBaseline
from signally.models.correlation_models import ConnectedPresenceSnapshot, CorrelationContext
from signally.models.security_mode import SecurityMode
from signally.sensors.nexmon.baseline_service import CsiBaselineService
from signally.sensors.nexmon.csi_features import extract_csi_features
from signally.sensors.nexmon.nexmon_packet import (
    NEXMON_CSI_MAGIC,
    NexmonPacketParseError,
    parse_nexmon_udp_payload,
)
from signally.sensors.nexmon.nexmon_provider import NexmonCsiProvider
from signally.sensors.sensing_snapshot import SensingProviderStatus
from signally.services.correlation_service import CorrelationService
from signally.utils.time_utils import utc_now


def build_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return session_factory()


def build_payload(samples, sequence_number=7):
    header = (
        NEXMON_CSI_MAGIC
        + bytes.fromhex("AABBCCDDEE01")
        + struct.pack("<HBBH", sequence_number, 1, 0, 36)
    )
    csi = b"".join(struct.pack("<hh", real, imag) for real, imag in samples)
    return header + csi


class FakeReceiver:
    def __init__(self, packets=None, status_overrides=None):
        self.packets = packets or []
        self.status_overrides = status_overrides or {}

    def start(self):
        return False

    def stop(self):
        return None

    def status(self):
        status = {
            "running": True,
            "host": "0.0.0.0",
            "port": 5500,
            "parsed_packet_count": len(self.packets),
            "received_packet_count": len(self.packets),
            "parse_error_count": 0,
            "last_error": None,
            "packets_per_second": len(self.packets) / 5.0,
            "last_packet_age_ms": 100 if self.packets else None,
        }
        status.update(self.status_overrides)
        return status

    def recent_packets(self, window_seconds=None):
        return self.packets

    def packets_since(self, started_at):
        return self.packets

    def last_packet_age_ms(self):
        return self.status()["last_packet_age_ms"]


def packets_from_levels(levels):
    packets = []
    for index, level in enumerate(levels):
        payload = build_payload([(level, 0), (level + 1, 0), (level + 2, 0)], index)
        packets.append(parse_nexmon_udp_payload(payload, received_at=utc_now()))
    return packets


def test_parse_valid_fake_nexmon_packet():
    packet = parse_nexmon_udp_payload(build_payload([(3, 4), (-5, 12)]))

    assert packet.source_mac == "AA:BB:CC:DD:EE:01"
    assert packet.sequence_number == 7
    assert packet.core == 1
    assert packet.spatial_stream == 0
    assert packet.channel == 36
    assert packet.csi_samples == [complex(3, 4), complex(-5, 12)]


def test_rejects_malformed_nexmon_packet():
    try:
        parse_nexmon_udp_payload(b"bad")
    except NexmonPacketParseError as exc:
        assert "too short" in str(exc)
    else:
        raise AssertionError("Malformed packet should have been rejected.")

    try:
        parse_nexmon_udp_payload(b"\x22\x22\x22\x22" + b"0" * 20)
    except NexmonPacketParseError as exc:
        assert "magic" in str(exc)
    else:
        raise AssertionError("Packet with bad magic should have been rejected.")


def test_extracts_amplitude_features():
    packets = packets_from_levels([10, 20, 30])

    features = extract_csi_features(packets)

    assert features.packet_count == 3
    assert features.sample_count == 9
    assert features.mean_amplitude > 0
    assert features.stddev > 0
    assert features.mean_abs_delta > 0


def test_baseline_creation_and_deviation_comparison():
    session = build_session()
    baseline_features = extract_csi_features(packets_from_levels([10, 11, 12]))
    baseline = CsiBaselineService(session).create_baseline(baseline_features)
    current_features = extract_csi_features(packets_from_levels([60, 61, 62]))

    comparison = CsiBaselineService(session).compare_to_baseline(current_features, baseline)

    assert session.query(CsiBaseline).count() == 1
    assert baseline.sample_count == baseline_features.sample_count
    assert comparison.presence_detected is True
    assert comparison.confidence > 0
    assert comparison.baseline_deviation > baseline.threshold


def test_provider_snapshot_no_data():
    session = build_session()
    provider = NexmonCsiProvider(receiver=FakeReceiver(), auto_start=False)

    snapshot = provider.get_snapshot(session)

    assert snapshot.provider_status == SensingProviderStatus.NO_DATA
    assert snapshot.presence_detected is False


def test_provider_snapshot_no_baseline_when_packets_arrive():
    session = build_session()
    provider = NexmonCsiProvider(
        receiver=FakeReceiver(packets_from_levels([10, 11, 12])),
        auto_start=False,
    )

    snapshot = provider.get_snapshot(session)

    assert snapshot.provider_status == SensingProviderStatus.NO_BASELINE
    assert snapshot.presence_detected is False


def test_provider_snapshot_ok_after_baseline():
    session = build_session()
    CsiBaselineService(session).create_baseline(
        extract_csi_features(packets_from_levels([10, 11, 12]))
    )
    provider = NexmonCsiProvider(
        receiver=FakeReceiver(packets_from_levels([60, 61, 62])),
        auto_start=False,
    )

    snapshot = provider.get_snapshot(session)

    assert snapshot.provider_status == SensingProviderStatus.OK
    assert snapshot.presence_detected is True
    assert snapshot.confidence > 0
    assert snapshot.baseline_deviation is not None


def test_provider_snapshot_error_after_repeated_parse_failures():
    session = build_session()
    provider = NexmonCsiProvider(
        receiver=FakeReceiver(
            status_overrides={
                "running": True,
                "parsed_packet_count": 0,
                "received_packet_count": 3,
                "parse_error_count": 3,
                "last_error": "Nexmon CSI magic bytes are missing.",
                "last_packet_age_ms": None,
            }
        ),
        auto_start=False,
    )

    snapshot = provider.get_snapshot(session)

    assert snapshot.provider_status == SensingProviderStatus.ERROR
    assert "magic" in snapshot.reason


def test_calibration_stop_persists_baseline():
    session = build_session()
    provider = NexmonCsiProvider(
        receiver=FakeReceiver(packets_from_levels([10, 11, 12])),
        auto_start=False,
        baseline_min_packets=2,
    )

    provider.start_calibration()
    baseline = provider.stop_calibration(session)

    assert baseline.id is not None
    assert baseline.packet_count == 3


def test_correlation_alerts_on_csi_presence_away_mode():
    decision = CorrelationService().evaluate(
        CorrelationContext(
            csi_presence_detected=True,
            nearby_device_count=0,
            connected_presence=ConnectedPresenceSnapshot(),
            security_mode=SecurityMode.AWAY,
        )
    )

    assert decision.decision == "ALERT"
    assert "CSI-based presence" in decision.reason
