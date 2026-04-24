"""
In-process background state for Wi-Fi probing.
"""

from __future__ import annotations

import logging
import threading
from typing import Optional

from signally.utils.time_utils import utc_now
from signally.wifi_probing.wifi_probe_detector import WifiProbeDetector
from signally.wifi_probing.wifi_probing_service import WifiProbingService

logger = logging.getLogger(__name__)


class WifiProbingState:
    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory
        self._lock = threading.Lock()
        self._thread = None  # type: Optional[threading.Thread]
        self._stop_event = threading.Event()
        self._detector = None  # type: Optional[WifiProbeDetector]
        self._interface = None  # type: Optional[str]
        self._mock_mode = False
        self._started_at = None
        self._last_error = None  # type: Optional[str]

    def start(self, interface: Optional[str], mock_mode: bool = False) -> None:
        with self._lock:
            if self.is_running():
                raise RuntimeError("Wi-Fi probing is already running")

            if not mock_mode and not interface:
                raise ValueError("interface is required when mock_mode is false")

            self._interface = interface
            self._mock_mode = mock_mode
            self._started_at = utc_now()
            self._last_error = None
            self._stop_event = threading.Event()
            self._detector = WifiProbeDetector(interface=interface, mock_mode=mock_mode)
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()

    def stop(self) -> None:
        thread = None

        with self._lock:
            if self._thread is None:
                return

            self._stop_event.set()
            thread = self._thread

        if thread is not None:
            thread.join(timeout=3.0)

        with self._lock:
            self._thread = None
            self._detector = None
            self._interface = None
            self._mock_mode = False

    def status(self) -> dict:
        return {
            "running": self.is_running(),
            "interface": self._interface,
            "mock_mode": self._mock_mode,
            "started_at": self._started_at,
            "last_error": self._last_error,
        }

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def add_mock_detection(
        self,
        mac_address: str,
        ssid: Optional[str] = None,
        rssi: Optional[int] = None,
        frame_type: str = "probe_req",
        channel: Optional[int] = None,
    ) -> None:
        if self._detector is None or not self._mock_mode:
            raise RuntimeError("mock detector is not running")
        self._detector.add_mock_detection(
            mac_address=mac_address,
            ssid=ssid,
            rssi=rssi,
            frame_type=frame_type,
            channel=channel,
        )

    def _run_loop(self) -> None:
        session = self.session_factory()
        service = WifiProbingService(session)

        try:
            service.log_started(self._interface, self._mock_mode)
            assert self._detector is not None
            self._detector.run(
                on_detection=service.handle_detection,
                stop_event=self._stop_event,
            )
        except Exception as exc:
            self._last_error = str(exc)
            logger.exception("Wi-Fi probing failed: %s", exc)
            service.log_error(self._interface, str(exc))
        finally:
            service.log_stopped(self._interface)
            session.close()
