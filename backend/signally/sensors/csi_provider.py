"""
CSI presence provider abstractions.

Transport + wiring only. The two hard parts are delegated:
  - byte parsing  -> signally.sensors.csi_frame.parse_csi_frame
  - motion logic  -> signally.sensors.csi_detector.CsiMotionDetector

RealCsiDetectionProvider owns the UDP socket + background thread and feeds frames
through those two. Its public surface
(is_presence_detected / get_presence_strength / is_receiving_data / stop) is
unchanged, so nothing downstream (dependencies.py, system_state_service, the
/csi endpoints) has to change.
"""

from typing import Optional
import threading
import socket
import logging
import time

from signally.config import (
    CSI_BASELINE_FACTOR,
    CSI_BASELINE_WARMUP,
    CSI_HAMPEL_SIGMA,
    CSI_REAL_PROVIDER_ENABLED,
    CSI_UDP_IP,
    CSI_UDP_PORT,
    CSI_VARIANCE_WINDOW,
)
from signally.sensors.csi_detector import CsiMotionDetector
from signally.sensors.csi_frame import parse_csi_frame

logger = logging.getLogger(__name__)


class CsiDetectionProvider:
    def is_presence_detected(self) -> bool:
        raise NotImplementedError

    def get_presence_strength(self) -> Optional[float]:
        return None


# --- MOCK PROVIDER (For Presentation & Testing) ---

class FlagCsiDetectionProvider(CsiDetectionProvider):
    def __init__(self, detected: bool = False, strength: Optional[float] = None) -> None:
        self._detected = detected
        self._strength = strength

    def is_presence_detected(self) -> bool:
        return self._detected

    def get_presence_strength(self) -> Optional[float]:
        return self._strength

    def set_detected(self, value: bool) -> None:
        self._detected = value

    def set_strength(self, value: Optional[float]) -> None:
        self._strength = value


# --- REAL PROVIDER (For Raspberry Pi Integration) ---

class RealCsiDetectionProvider(CsiDetectionProvider):
    def __init__(
        self,
        udp_ip: str = CSI_UDP_IP,
        udp_port: int = CSI_UDP_PORT,
        window_size: int = CSI_VARIANCE_WINDOW,
        baseline_factor: float = CSI_BASELINE_FACTOR,
        baseline_warmup: int = CSI_BASELINE_WARMUP,
        hampel_sigma: float = CSI_HAMPEL_SIGMA,
    ) -> None:
        self._detected = False
        self._strength = 0.0
        self._confidence = 0.0

        self.udp_ip = udp_ip
        self.udp_port = udp_port
        self._last_packet_time = 0.0  # when we last got a real CSI frame

        self._detector = CsiMotionDetector(
            window_size=window_size,
            baseline_factor=baseline_factor,
            baseline_warmup=baseline_warmup,
            hampel_sigma=hampel_sigma,
        )

        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

    def is_receiving_data(self) -> bool:
        # True if a real CSI frame arrived in the last 3 seconds.
        return (time.time() - self._last_packet_time) < 3.0

    def is_presence_detected(self) -> bool:
        return self._detected

    def get_presence_strength(self) -> Optional[float]:
        return self._strength

    def get_confidence(self) -> float:
        return self._confidence

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def _capture_loop(self) -> None:
        """Background thread: listen to the nexmon CSI UDP stream."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(1.0)
        try:
            sock.bind((self.udp_ip, self.udp_port))
            logger.info("Real CSI Provider listening on %s:%s", self.udp_ip, self.udp_port)
        except Exception as e:
            logger.error("Failed to bind CSI socket: %s", e)
            return

        while not self._stop_event.is_set():
            try:
                data, _ = sock.recvfrom(8192)
            except socket.timeout:
                continue  # no packets right now; keep waiting
            except Exception as e:
                logger.error("CSI Stream Error: %s", e)
                continue

            frame = parse_csi_frame(data)
            if frame is None:
                continue  # not a valid CSI datagram - ignore

            self._last_packet_time = time.time()
            reading = self._detector.update(frame.amplitudes)
            self._detected = reading.detected
            self._strength = reading.motion_metric
            self._confidence = reading.confidence

        sock.close()

    def set_detected(self, value: bool) -> None:
        # Safety hook for manual testing; does not touch the detector state.
        self._detected = value


# Auto-fallback to the mock provider whenever real CSI data isn't arriving.
class AutoFallbackCsiProvider(CsiDetectionProvider):
    def __init__(self, real_enabled: bool = CSI_REAL_PROVIDER_ENABLED):
        self.real = RealCsiDetectionProvider() if real_enabled else None
        self.mock = FlagCsiDetectionProvider()

    def is_presence_detected(self) -> bool:
        if self.real is not None and self.real.is_receiving_data():
            return self.real.is_presence_detected()
        return self.mock.is_presence_detected()

    def get_presence_strength(self) -> Optional[float]:
        if self.real is not None and self.real.is_receiving_data():
            return self.real.get_presence_strength()
        return self.mock.get_presence_strength()

    def is_using_real(self) -> bool:
        return self.real is not None and self.real.is_receiving_data()

    def set_detected(self, value: bool) -> None:
        # Route Swagger /csi/set testing clicks to the mock provider.
        self.mock.set_detected(value)

    def set_strength(self, value: Optional[float]) -> None:
        self.mock.set_strength(value)

    def stop(self) -> None:
        if self.real is not None:
            self.real.stop()
