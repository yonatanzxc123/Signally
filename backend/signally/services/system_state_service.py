"""Central assembly of Signally monitoring state."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy.orm import Session

from signally.config import (
    ALERT_COOLDOWN_SECONDS,
    EVENT_BLOCKED_DEVICE_ALERT,
    EVENT_UNAUTHORIZED_PRESENCE_ALERT,
)
from signally.models.correlation_models import (
    ConnectedPresenceSnapshot,
    CorrelationContext,
    CorrelationDecision,
    NearbyPresenceSnapshot,
)
from signally.models.event import Event
from signally.models.security_mode import SecurityState
from signally.network_scanner.scanner import NetworkScanner
from signally.services.alert_service import AlertService
from signally.services.correlation_service import CorrelationService
from signally.services.device_service import DeviceService
from signally.services.event_service import EventService
from signally.services.presence_service import PresenceService
from signally.services.security_mode_service import SecurityModeService
from signally.wifi_probing.wifi_probing_service import WifiProbingService


ALERT_EVENT_TYPES = (
    EVENT_UNAUTHORIZED_PRESENCE_ALERT,
    EVENT_BLOCKED_DEVICE_ALERT,
)


@dataclass
class SystemStateSnapshot:
    security_state: SecurityState
    csi_presence_detected: bool
    csi_presence_strength: Optional[float]
    connected_presence: ConnectedPresenceSnapshot
    nearby_presence: NearbyPresenceSnapshot
    decision: CorrelationDecision
    processed_devices_count: int = 0
    scan_error: Optional[str] = None
    recent_alerts: list[Event] = field(default_factory=list)

    @property
    def authorized_devices_count(self) -> int:
        return len(self.connected_presence.authorised_connected_devices)

    @property
    def pending_devices_count(self) -> int:
        return len(self.connected_presence.pending_connected_devices)

    @property
    def blocked_devices_count(self) -> int:
        return len(self.connected_presence.blocked_connected_devices)

    @property
    def present_devices_count(self) -> int:
        return len(self.connected_presence.connected_devices)


class SystemStateService:
    def __init__(
        self,
        session: Session,
        csi_provider,
        scanner: Optional[NetworkScanner] = None,
        alert_cooldown_seconds: int = ALERT_COOLDOWN_SECONDS,
    ) -> None:
        self.session = session
        self.csi_provider = csi_provider
        self.scanner = scanner or NetworkScanner()
        self.alert_cooldown_seconds = alert_cooldown_seconds
        self.device_service = DeviceService(session)
        self.event_service = EventService(session)
        self.presence_service = PresenceService(session)
        self.security_mode_service = SecurityModeService(session)
        self.correlation_service = CorrelationService()
        self.alert_service = AlertService(self.event_service)
        self.wifi_probing_service = WifiProbingService(session)

    def collect_state(
        self,
        run_scan: bool = False,
        persist_alerts: bool = False,
    ) -> SystemStateSnapshot:
        processed_devices_count = 0
        scan_error = None

        if run_scan:
            try:
                discovered = self.scanner.scan()
                processed = self.device_service.process_scan_results(discovered)
                processed_devices_count = len(processed)
            except Exception as exc:
                self.session.rollback()
                scan_error = str(exc)

        csi_detected = self.csi_provider.is_presence_detected()
        csi_strength = self.csi_provider.get_presence_strength()
        connected_presence = self.presence_service.get_presence_snapshot()
        nearby_presence = self.wifi_probing_service.get_presence_snapshot()
        security_state = self.security_mode_service.get_state()

        context = CorrelationContext(
            csi_presence_detected=csi_detected,
            nearby_device_count=nearby_presence.nearby_probe_count,
            connected_presence=connected_presence,
            nearby_presence=nearby_presence,
            security_mode=security_state.mode,
        )
        decision = self.correlation_service.evaluate(context)

        if persist_alerts and decision.decision == "ALERT":
            self._persist_alert(decision, connected_presence, nearby_presence, csi_detected)

        recent_alerts = self.event_service.list_recent_events_by_types(
            event_types=ALERT_EVENT_TYPES,
            limit=10,
        )

        return SystemStateSnapshot(
            security_state=security_state,
            csi_presence_detected=csi_detected,
            csi_presence_strength=csi_strength,
            connected_presence=connected_presence,
            nearby_presence=nearby_presence,
            decision=decision,
            processed_devices_count=processed_devices_count,
            scan_error=scan_error,
            recent_alerts=recent_alerts,
        )

    def _persist_alert(
        self,
        decision: CorrelationDecision,
        connected_presence: ConnectedPresenceSnapshot,
        nearby_presence: NearbyPresenceSnapshot,
        csi_detected: bool,
    ) -> None:
        blocked_devices = connected_presence.blocked_connected_devices
        first_blocked = blocked_devices[0] if blocked_devices else None
        details = self._alert_details(decision, connected_presence, nearby_presence, csi_detected)

        if first_blocked is not None:
            self.alert_service.raise_blocked_device_alert(
                device_mac=first_blocked.mac_address,
                details=details,
                cooldown_seconds=self.alert_cooldown_seconds,
            )
            return

        first_pending = (
            connected_presence.pending_connected_devices[0]
            if connected_presence.pending_connected_devices
            else None
        )
        self.alert_service.raise_unauthorized_presence_alert(
            device_mac=first_pending.mac_address if first_pending else None,
            details=details,
            cooldown_seconds=self.alert_cooldown_seconds,
        )

    def _alert_details(
        self,
        decision: CorrelationDecision,
        connected_presence: ConnectedPresenceSnapshot,
        nearby_presence: NearbyPresenceSnapshot,
        csi_detected: bool,
    ) -> str:
        return (
            "mode={0}; decision={1}; reason={2}; pending_connected={3}; "
            "blocked_connected={4}; nearby_probe_count={5}; csi_presence={6}"
        ).format(
            decision.security_mode.value,
            decision.decision,
            decision.reason,
            len(connected_presence.pending_connected_devices),
            len(connected_presence.blocked_connected_devices),
            nearby_presence.nearby_probe_count,
            csi_detected,
        )
