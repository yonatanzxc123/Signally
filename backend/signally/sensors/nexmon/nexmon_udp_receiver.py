"""Background UDP receiver for Nexmon CSI packets."""

from __future__ import annotations

from collections import deque
from datetime import datetime
import logging
import socket
import threading
from typing import Optional

from signally.config import CSI_PACKET_BUFFER_SIZE, CSI_UDP_HOST, CSI_UDP_PORT
from signally.sensors.nexmon.nexmon_packet import (
    NexmonCsiPacket,
    NexmonPacketParseError,
    parse_nexmon_udp_payload,
)
from signally.utils.time_utils import utc_now

logger = logging.getLogger(__name__)


class NexmonUdpReceiver:
    def __init__(
        self,
        host: str = CSI_UDP_HOST,
        port: int = CSI_UDP_PORT,
        buffer_size: int = CSI_PACKET_BUFFER_SIZE,
    ) -> None:
        self.host = host
        self.port = port
        self.buffer_size = buffer_size
        self._packets: deque[NexmonCsiPacket] = deque(maxlen=buffer_size)
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._socket: Optional[socket.socket] = None
        self._last_packet_at: Optional[datetime] = None
        self._last_error: Optional[str] = None
        self._parse_error_count = 0
        self._received_packet_count = 0

    def start(self) -> bool:
        with self._lock:
            if self.is_running():
                return False
            self._stop_event = threading.Event()
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()
            return True

    def stop(self, timeout: float = 2.0) -> None:
        with self._lock:
            thread = self._thread
            self._stop_event.set()
            sock = self._socket
            self._socket = None

        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass

        if thread is not None:
            thread.join(timeout=timeout)

        with self._lock:
            if self._thread is thread:
                self._thread = None

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def recent_packets(self, window_seconds: Optional[float] = None) -> list[NexmonCsiPacket]:
        with self._lock:
            packets = list(self._packets)

        if window_seconds is None:
            return packets

        now = utc_now()
        return [
            packet
            for packet in packets
            if (now - packet.received_at).total_seconds() <= window_seconds
        ]

    def packets_since(self, started_at: datetime) -> list[NexmonCsiPacket]:
        with self._lock:
            return [packet for packet in self._packets if packet.received_at >= started_at]

    def packet_rate(self, window_seconds: float = 5.0) -> float:
        packets = self.recent_packets(window_seconds=window_seconds)
        if window_seconds <= 0:
            return 0.0
        return len(packets) / window_seconds

    def last_packet_age_ms(self) -> Optional[int]:
        with self._lock:
            last_packet_at = self._last_packet_at

        if last_packet_at is None:
            return None
        return int((utc_now() - last_packet_at).total_seconds() * 1000)

    def status(self) -> dict:
        with self._lock:
            parsed_count = len(self._packets)
            last_error = self._last_error
            parse_error_count = self._parse_error_count
            received_packet_count = self._received_packet_count

        return {
            "running": self.is_running(),
            "host": self.host,
            "port": self.port,
            "parsed_packet_count": parsed_count,
            "received_packet_count": received_packet_count,
            "parse_error_count": parse_error_count,
            "last_error": last_error,
            "packets_per_second": self.packet_rate(),
            "last_packet_age_ms": self.last_packet_age_ms(),
        }

    def _run_loop(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(1.0)

        try:
            sock.bind((self.host, self.port))
        except OSError as exc:
            with self._lock:
                self._last_error = "Could not bind Nexmon CSI UDP receiver: {0}".format(exc)
            logger.exception("Could not bind Nexmon CSI UDP receiver")
            try:
                sock.close()
            except OSError:
                pass
            return

        with self._lock:
            self._socket = sock
            self._last_error = None

        while not self._stop_event.is_set():
            try:
                payload, _ = sock.recvfrom(65535)
                received_at = utc_now()
                packet = parse_nexmon_udp_payload(payload, received_at=received_at)
                with self._lock:
                    self._received_packet_count += 1
                    self._last_packet_at = received_at
                    self._packets.append(packet)
            except socket.timeout:
                continue
            except NexmonPacketParseError as exc:
                with self._lock:
                    self._received_packet_count += 1
                    self._parse_error_count += 1
                    self._last_error = str(exc)
            except OSError as exc:
                if not self._stop_event.is_set():
                    with self._lock:
                        self._last_error = str(exc)
                    logger.exception("Nexmon CSI UDP receiver failed")
                break
            except Exception as exc:
                with self._lock:
                    self._last_error = str(exc)
                logger.exception("Unexpected Nexmon CSI receiver error")

        try:
            sock.close()
        except OSError:
            pass
