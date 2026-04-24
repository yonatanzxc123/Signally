"""
CSI presence provider abstractions.
"""

from typing import Optional
import threading
import socket
import struct
import math
import logging

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
    def __init__(self, udp_ip: str = "127.0.0.1", udp_port: int = 5500, threshold: float = 15.0) -> None:
        self._detected = False
        self._strength = 0.0
        self.threshold = threshold
        
        self.udp_ip = udp_ip
        self.udp_port = udp_port
        
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

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
                data, _ = sock.recvfrom(4096)
                
                # NOTE: Nexmon payloads require specific struct unpacking.
                # Example: bypassing the MAC header and extracting complex numbers (I & Q)
                # i_val, q_val = struct.unpack('hh', data[some_offset:some_offset+4])
                
                # --- TEMPLATE MATH LOGIC ---
                # 1. Extract I (In-phase) and Q (Quadrature) from raw memory bytes.
                # 2. Calculate Amplitude: amplitude = math.sqrt(I**2 + Q**2)
                # 3. Calculate Variance of the amplitude over the last N packets.
                
                # Dummy variance calculation to keep the loop valid until hardware arrives
                current_variance = 0.0  
                
                self._strength = current_variance
                
                # If the variance spikes above the baseline threshold, someone is moving
                if current_variance > self.threshold:
                    self._detected = True
                else:
                    self._detected = False

            except socket.timeout:
                # Normal behavior if no packets are being sent
                continue
            except Exception as e:
                logger.error("CSI Stream Error: %s", e)
                
        sock.close()