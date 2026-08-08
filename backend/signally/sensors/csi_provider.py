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

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
import threading
import socket
import logging
import time

from signally.config import (
    CSI_BASELINE_FACTOR,
    CSI_BASELINE_WARMUP,
    CSI_HAMPEL_SIGMA,
    CSI_DETECTION_HOLD_SECONDS,
    CSI_REAL_PROVIDER_ENABLED,
    CSI_UDP_IP,
    CSI_UDP_PORT,
    CSI_VARIANCE_WINDOW,
    CSI_STALE_AFTER_SECONDS,
    CSI_WARMUP_SECONDS,
)
from signally.sensors.csi_detector import CsiMotionDetector
from signally.sensors.csi_frame import parse_csi_frame

logger = logging.getLogger(__name__)
_SUPPORTED_SUBCARRIER_COUNTS = frozenset((64, 128, 256))


@dataclass(frozen=True)
class CsiState:
    provider_mode: str
    receiving_data: bool = False
    ready: bool = False
    currently_detected: bool = False
    recently_detected: bool = False
    motion_metric: Optional[float] = None
    baseline: Optional[float] = None
    threshold: Optional[float] = None
    baseline_factor: float = CSI_BASELINE_FACTOR
    confidence: float = 0.0
    frames_received: int = 0
    invalid_frames: int = 0
    last_packet_at: Optional[datetime] = None
    last_error: Optional[str] = None


class CsiDetectionProvider:
    def get_state(self) -> CsiState:
        raise NotImplementedError

    def is_presence_detected(self) -> bool:
        return self.get_state().recently_detected

    def get_presence_strength(self) -> Optional[float]:
        return self.get_state().motion_metric


# --- MOCK PROVIDER (For Presentation & Testing) ---

class FlagCsiDetectionProvider(CsiDetectionProvider):
    def __init__(self, detected: bool = False, strength: Optional[float] = None) -> None:
        self._detected = detected
        self._strength = strength

    def is_presence_detected(self) -> bool:
        return self._detected

    def get_presence_strength(self) -> Optional[float]:
        return self._strength

    def get_state(self) -> CsiState:
        return CsiState(
            provider_mode="mock",
            receiving_data=True,
            ready=True,
            currently_detected=self._detected,
            recently_detected=self._detected,
            motion_metric=self._strength,
        )

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
        stale_after_seconds: float = CSI_STALE_AFTER_SECONDS,
        detection_hold_seconds: float = CSI_DETECTION_HOLD_SECONDS,
        warmup_seconds: float = CSI_WARMUP_SECONDS,
    ) -> None:
        self._detected = False
        self._strength = 0.0
        self._confidence = 0.0

        self.udp_ip = udp_ip
        self.udp_port = udp_port
        self._last_packet_time = 0.0  # when we last got a real CSI frame
        self._last_detection_time = 0.0
        self._started_time = time.monotonic()
        self._frames_received = 0
        self._invalid_frames = 0
        self._last_error: Optional[str] = None
        self._frame_width: Optional[int] = None
        self._lock = threading.Lock()
        self._stale_after_seconds = stale_after_seconds
        self._detection_hold_seconds = detection_hold_seconds
        self._warmup_seconds = warmup_seconds

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
        return self.get_state().receiving_data

    def is_presence_detected(self) -> bool:
        return self.get_state().recently_detected

    def get_presence_strength(self) -> Optional[float]:
        return self.get_state().motion_metric

    def get_confidence(self) -> float:
        return self.get_state().confidence

    def get_state(self) -> CsiState:
        now = time.monotonic()
        with self._lock:
            receiving = self._last_packet_time > 0 and now - self._last_packet_time < self._stale_after_seconds
            ready = receiving and self._detector.ready and now - self._started_time >= self._warmup_seconds
            recent = ready and self._last_detection_time > 0 and now - self._last_detection_time <= self._detection_hold_seconds
            packet_at = None
            if self._last_packet_time > 0:
                age = max(0.0, now - self._last_packet_time)
                packet_at = datetime.fromtimestamp(time.time() - age, tz=timezone.utc)
            return CsiState(
                provider_mode="real",
                receiving_data=receiving,
                ready=ready,
                currently_detected=ready and self._detected,
                recently_detected=recent,
                motion_metric=self._strength,
                baseline=self._detector.baseline,
                threshold=self._detector.threshold,
                baseline_factor=self._detector.baseline_factor,
                confidence=self._confidence,
                frames_received=self._frames_received,
                invalid_frames=self._invalid_frames,
                last_packet_at=packet_at,
                last_error=self._last_error,
            )

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
            with self._lock:
                self._last_error = str(e)
            sock.close()
            return

        while not self._stop_event.is_set():
            try:
                data, _ = sock.recvfrom(8192)
            except socket.timeout:
                continue  # no packets right now; keep waiting
            except Exception as e:
                logger.error("CSI Stream Error: %s", e)
                continue

            try:
                frame = parse_csi_frame(data)
                if frame is None:
                    with self._lock:
                        self._invalid_frames += 1
                    continue
                width = frame.subcarrier_count
                if width not in _SUPPORTED_SUBCARRIER_COUNTS:
                    with self._lock:
                        self._invalid_frames += 1
                        self._last_error = "Unsupported CSI frame width: {0}".format(width)
                    continue
                with self._lock:
                    if self._frame_width is not None and width != self._frame_width:
                        self._invalid_frames += 1
                        self._last_error = "CSI frame width changed from {0} to {1}".format(self._frame_width, width)
                        continue
                    self._frame_width = width
                    reading = self._detector.update(frame.amplitudes)
                    now = time.monotonic()
                    self._last_packet_time = now
                    self._frames_received += 1
                    self._detected = reading.detected
                    self._strength = reading.motion_metric
                    self._confidence = reading.confidence
                    self._last_error = None
                    if reading.detected:
                        self._last_detection_time = now
            except Exception as e:
                logger.exception("CSI frame processing error: %s", e)
                with self._lock:
                    self._invalid_frames += 1
                    self._last_error = str(e)

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
        return self.get_state().recently_detected

    def get_presence_strength(self) -> Optional[float]:
        return self.get_state().motion_metric

    def get_state(self) -> CsiState:
        if self.real is not None:
            return self.real.get_state()
        return self.mock.get_state()

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
