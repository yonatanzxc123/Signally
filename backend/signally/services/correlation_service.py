"""
Three-layer correlation service.
"""

from signally.services.correlation_models import (
    CorrelationContext,
    CorrelationDecision,
)


class CorrelationService:
    def evaluate(self, context: CorrelationContext) -> CorrelationDecision:
        approved_present = context.connected_presence.approved_user_present
        blocked_present = len(context.connected_presence.blocked_connected_devices) > 0
        pending_connected = len(context.connected_presence.pending_connected_devices) > 0
        nearby_present = context.nearby_device_count > 0

        if not context.csi_presence_detected and not nearby_present:
            return CorrelationDecision(
                decision="IDLE",
                severity="INFO",
                reason="No CSI presence and no nearby device evidence.",
                csi_presence_detected=False,
                nearby_device_count=context.nearby_device_count,
                approved_user_present=approved_present,
            )

        if context.csi_presence_detected and blocked_present:
            return CorrelationDecision(
                decision="HIGH_ALERT",
                severity="CRITICAL",
                reason="CSI presence detected and a blocked connected device is present.",
                csi_presence_detected=True,
                nearby_device_count=context.nearby_device_count,
                approved_user_present=approved_present,
            )

        if context.csi_presence_detected and approved_present:
            return CorrelationDecision(
                decision="SAFE",
                severity="INFO",
                reason="CSI presence detected and at least one authorised connected device is present.",
                csi_presence_detected=True,
                nearby_device_count=context.nearby_device_count,
                approved_user_present=True,
            )

        if context.csi_presence_detected and (nearby_present or pending_connected):
            return CorrelationDecision(
                decision="ALERT",
                severity="WARNING",
                reason="CSI presence detected without an authorised connected device, and unknown nearby or pending device evidence exists.",
                csi_presence_detected=True,
                nearby_device_count=context.nearby_device_count,
                approved_user_present=False,
            )

        if context.csi_presence_detected:
            return CorrelationDecision(
                decision="WARNING",
                severity="WARNING",
                reason="CSI presence detected, but no device evidence is currently available.",
                csi_presence_detected=True,
                nearby_device_count=context.nearby_device_count,
                approved_user_present=False,
            )

        return CorrelationDecision(
            decision="OBSERVE",
            severity="INFO",
            reason="Nearby device evidence exists without CSI presence.",
            csi_presence_detected=False,
            nearby_device_count=context.nearby_device_count,
            approved_user_present=approved_present,
        )
