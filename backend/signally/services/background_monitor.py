"""Stoppable background monitoring loop."""

from __future__ import annotations

import logging
import threading
from typing import Optional

from signally.config import MONITOR_INTERVAL_SECONDS
from signally.services.system_state_service import SystemStateService

logger = logging.getLogger(__name__)


class BackgroundMonitor:
    def __init__(
        self,
        session_factory,
        csi_provider,
        interval_seconds: int = MONITOR_INTERVAL_SECONDS,
    ) -> None:
        self.session_factory = session_factory
        self.csi_provider = csi_provider
        self.interval_seconds = interval_seconds
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_error: Optional[str] = None

    def start(self) -> bool:
        with self._lock:
            if self.is_running():
                return False
            self._stop_event = threading.Event()
            self._last_error = None
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()
            return True

    def stop(self, timeout: float = 5.0) -> None:
        with self._lock:
            thread = self._thread
            if thread is None:
                return
            self._stop_event.set()

        thread.join(timeout=timeout)

        with self._lock:
            if self._thread is thread:
                self._thread = None

    def status(self) -> dict:
        return {
            "running": self.is_running(),
            "interval_seconds": self.interval_seconds,
            "last_error": self._last_error,
        }

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def run_once(self) -> None:
        session = self.session_factory()
        try:
            SystemStateService(
                session=session,
                csi_provider=self.csi_provider,
            ).collect_state(run_scan=True, persist_alerts=True)
        finally:
            session.close()

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.run_once()
            except Exception as exc:
                self._last_error = str(exc)
                logger.exception("Background monitoring cycle failed: %s", exc)

            self._stop_event.wait(self.interval_seconds)
