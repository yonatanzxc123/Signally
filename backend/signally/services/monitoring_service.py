"""
Monitoring service.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Dict, Optional

from signally.config import EVENT_MONITORING_CYCLE_COMPLETED, MONITOR_INTERVAL_SECONDS
from signally.services.alert_service import AlertService
from signally.services.decision_models import DecisionResult
from signally.services.decision_service import DecisionService
from signally.services.device_service import DeviceService
from signally.services.event_service import EventService
from signally.services.presence_service import PresenceService


class MonitoringService:
    def __init__(
        self,
        csi_provider,
        wifi_probe_provider,
        device_service: DeviceService,
        presence_service: PresenceService,
        decision_service: DecisionService,
        alert_service: AlertService,
        event_service: EventService,
    ) -> None:
        self.csi_provider = csi_provider
        self.wifi_probe_provider = wifi_probe_provider
        self.device_service = device_service
        self.presence_service = presence_service
        self.decision_service = decision_service
        self.alert_service = alert_service
        self.event_service = event_service

        self._running = False
        self._thread = None  # type: Optional[threading.Thread]

    def run_cycle(self) -> Dict[str, Any]:
        csi_presence_detected = self.csi_provider.is_presence_detected()

        discovered_devices = self.wifi_probe_provider.scan_devices()
        processed_devices = self.device_service.process_scan_results(discovered_devices)

        presence_snapshot = self.presence_service.get_presence_snapshot()
        decision = self.decision_service.evaluate(
            csi_presence_detected=csi_presence_detected,
            presence_snapshot=presence_snapshot,
        )

        if decision.decision == "SAFE":
            self.alert_service.log_approved_user_present()
        elif decision.decision == "ALERT":
            self.alert_service.log_no_approved_user_present()
            device_mac = decision.pending_devices[0].mac_address if decision.pending_devices else None
            self.alert_service.raise_unauthorized_presence_alert(device_mac=device_mac)
        elif decision.decision == "HIGH_ALERT":
            device_mac = decision.blocked_devices[0].mac_address if decision.blocked_devices else None
            self.alert_service.raise_blocked_device_alert(device_mac=device_mac)
        elif decision.decision == "WARNING":
            self.alert_service.log_no_approved_user_present()

        self.event_service.log_event(
            event_type=EVENT_MONITORING_CYCLE_COMPLETED,
            details="Monitoring cycle completed with decision={0}".format(decision.decision),
        )

        return {
            "csi_presence_detected": decision.csi_presence_detected,
            "approved_user_present": decision.approved_user_present,
            "decision": decision.decision,
            "reason": decision.reason,
            "processed_devices_count": len(processed_devices),
            "present_devices_count": len(presence_snapshot.present_devices),
            "authorized_devices_count": len(presence_snapshot.present_authorized_devices),
            "pending_devices_count": len(presence_snapshot.present_pending_devices),
            "blocked_devices_count": len(presence_snapshot.present_blocked_devices),
            "processed_devices": processed_devices,
            "presence_snapshot": presence_snapshot,
        }

    def _loop(self, interval_seconds: int) -> None:
        while self._running:
            self.run_cycle()
            time.sleep(interval_seconds)

    def start_background_monitoring(self, interval_seconds: int = MONITOR_INTERVAL_SECONDS) -> None:
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._loop,
            args=(interval_seconds,),
            daemon=True,
        )
        self._thread.start()

    def stop_background_monitoring(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None

    def is_running(self) -> bool:
        return self._running