import socket
import time

from signally.sensors.csi_frame import build_csi_frame
from signally.sensors.csi_provider import FlagCsiDetectionProvider, RealCsiDetectionProvider
from signally.api.app import to_csi_response


def _free_udp_port():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def test_real_provider_reports_health_and_survives_invalid_width():
    port = _free_udp_port()
    provider = RealCsiDetectionProvider(
        udp_ip="127.0.0.1",
        udp_port=port,
        window_size=2,
        baseline_warmup=1,
        warmup_seconds=0,
        stale_after_seconds=1,
    )
    sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        time.sleep(0.05)
        sender.sendto(build_csi_frame([(1, 1)] * 4), ("127.0.0.1", port))
        sender.sendto(build_csi_frame([(10, 1)] * 64), ("127.0.0.1", port))
        sender.sendto(build_csi_frame([(11, 1)] * 64), ("127.0.0.1", port))
        deadline = time.time() + 2
        while provider.get_state().frames_received < 2 and time.time() < deadline:
            time.sleep(0.01)
        state = provider.get_state()
        assert state.provider_mode == "real"
        assert state.receiving_data is True
        assert state.ready is True
        assert state.frames_received == 2
        assert state.invalid_frames == 1
    finally:
        sender.close()
        provider.stop()


def test_csi_response_keeps_legacy_status_fields():
    provider = FlagCsiDetectionProvider(detected=True, strength=0.42)

    response = to_csi_response(provider.get_state())

    assert response.presence_detected is True
    assert response.presence_strength == 0.42
    assert response.detected is True
    assert response.strength == 0.42
    assert response.recently_detected is True
