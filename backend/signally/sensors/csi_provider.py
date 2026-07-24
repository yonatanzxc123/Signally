"""
CSI presence provider abstractions.
"""

from typing import Optional
from collections import deque
import threading
import socket
import struct
import math
import statistics
import logging
import time

from signally.config import (
    CSI_PRESENCE_THRESHOLD,
    CSI_REAL_PROVIDER_ENABLED,
    CSI_UDP_IP,
    CSI_UDP_PORT,
    CSI_VARIANCE_WINDOW,
)

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

# nexmon_csi UDP frame layout (seemoo-lab/nexmon_csi, BCM43455c0 / BCM4339 chips
# only - those chips emit plain interleaved int16 I/Q pairs; bcm4358/bcm4366c0
# use a different compressed float format not handled here):
#
#   offset  size  field
#   0       4     magic bytes, always 0x11111111
#   4       2     magic bytes, always 0x1111
#   6       6     source MAC address
#   12      2     Wi-Fi frame sequence number
#   14      2     core (low 3 bits) / spatial stream (next 3 bits)
#   16      2     chanspec
#   18      2     chip version identifier
#   20      ...   CSI data: N subcarriers x (int16 real, int16 imag) = N x 4 bytes
#                 N is 64/128/256 for 20/40/80 MHz, set when nexutil configures capture.
#
# Verified against the project's README field table; byte order (assumed
# little-endian, matching the ARM/Broadcom chip) has NOT been validated against
# a live capture. If amplitudes come out looking like noise once real hardware
# is connected, flip _HEADER_STRUCT/_CSI_VALUE_FORMAT to '>' and re-check.
_CSI_MAGIC = b"\x11\x11\x11\x11"
_HEADER_STRUCT = struct.Struct("<H6sHHHH")  # magic2, mac, seq, core_spatial, chanspec, chip
_HEADER_SIZE = 4 + _HEADER_STRUCT.size  # 4-byte magic1 prefix + the rest
_CSI_VALUE_FORMAT = "<h"  # one int16 (real or imag)


class RealCsiDetectionProvider(CsiDetectionProvider):
    def __init__(
        self,
        udp_ip: str = CSI_UDP_IP,
        udp_port: int = CSI_UDP_PORT,
        threshold: float = CSI_PRESENCE_THRESHOLD,
        window_size: int = CSI_VARIANCE_WINDOW,
    ) -> None:
        self._detected = False
        self._strength = 0.0
        self.threshold = threshold
        self.window_size = window_size

        self.udp_ip = udp_ip
        self.udp_port = udp_port
        self._last_packet_time = 0.0   # Track when we last got data

        self._amplitude_history: deque = deque(maxlen=window_size)

        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

    def is_receiving_data(self) -> bool:    
        # Returns True if  a real CSI packet was recived in the last 3 seconds, otherwise False.
        return (time.time() - self._last_packet_time) < 3.0 

    def is_presence_detected(self) -> bool:
        return self._detected

    def get_presence_strength(self) -> Optional[float]:
        return self._strength
        
    def stop(self) -> None:
        self._stop_event.set()
        if self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def _capture_loop(self) -> None:
        """
        Background thread listening to Nexmon CSI UDP stream.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(1.0)
        
        try:
            sock.bind((self.udp_ip, self.udp_port))
            logger.info("Real CSI Provider listening on %s:%s", self.udp_ip, self.udp_port)
        except Exception as e:
            logger.error("Failed to bind CSI socket: %s", e)
            return

        # Rolling window to calculate signal variance
        window_size = 50
        variance_history = []

        while not self._stop_event.is_set():
            try:
                data, _ = sock.recvfrom(8192)
                self._last_packet_time = time.time()

                mean_amplitude = self._parse_csi_frame(data)
                if mean_amplitude is None:
                    continue  # not a CSI frame (bad magic / too short) - ignore

                self._amplitude_history.append(mean_amplitude)

                # Motion shows up as variance in subcarrier amplitude over time,
                # not the raw amplitude itself - a stationary room settles to a
                # near-constant amplitude, a moving body disturbs the multipath.
                if len(self._amplitude_history) < 2:
                    continue
                current_variance = statistics.pvariance(self._amplitude_history)
                self._strength = current_variance
                self._detected = current_variance > self.threshold

            except socket.timeout:
                # Normal behavior if no packets are being sent
                continue
            except Exception as e:
                logger.error("CSI Stream Error: %s", e)

        sock.close()

    def _parse_csi_frame(self, data: bytes) -> Optional[float]:
        """Parse one nexmon_csi UDP frame, return the mean subcarrier amplitude."""
        if len(data) < _HEADER_SIZE or data[:4] != _CSI_MAGIC:
            return None

        # Header fields (mac/seq/chanspec/chip) aren't needed for a single-sensor
        # variance detector, but are unpacked here since they're required to
        # validate frame length against the declared payload.
        _magic2, _mac, _seq, _core_spatial, _chanspec, _chip = _HEADER_STRUCT.unpack_from(
            data, 4
        )

        csi_bytes = data[_HEADER_SIZE:]
        subcarrier_count = len(csi_bytes) // 4  # 4 bytes = int16 real + int16 imag
        if subcarrier_count == 0:
            return None

        values = struct.unpack_from("<%dh" % (subcarrier_count * 2), csi_bytes)
        amplitudes = [
            math.hypot(values[2 * i], values[2 * i + 1]) for i in range(subcarrier_count)
        ]
        return sum(amplitudes) / len(amplitudes)
    
    def set_detected(self, value: bool) -> None:
       # Safety method to prevent crashes during manual testing.
        self._detected = value




# Auto-fallback to "not detected" if we haven't received any data for a while
class AutoFallbackCsiProvider(CsiDetectionProvider):
    def __init__(self, real_enabled: bool = CSI_REAL_PROVIDER_ENABLED):
        self.real = RealCsiDetectionProvider() if real_enabled else None
        self.mock = FlagCsiDetectionProvider()

    def is_presence_detected(self) -> bool:
        # If the Pi is actually sending data, use it. Otherwise, use Mock.
        if self.real is not None and self.real.is_receiving_data():
            return self.real.is_presence_detected()
        # Automatically fall back if the Pi is off!
        return self.mock.is_presence_detected()

    def get_presence_strength(self) -> Optional[float]:
        if self.real is not None and self.real.is_receiving_data():
            return self.real.get_presence_strength()
        return self.mock.get_presence_strength()

    def set_detected(self, value: bool) -> None:
        # Route your Swagger API testing clicks to the mock provider
        self.mock.set_detected(value)
        
    def set_strength(self, value: Optional[float]) -> None:
        self.mock.set_strength(value)

    def stop(self) -> None:
        if self.real is not None:
            self.real.stop()
