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
        nearby_present = context.nearby_device_count > 0
        csi_detected = context.csi_presence_detected

        # 1. CRITICAL: Blocked device physically here
        if blocked_present:
            return CorrelationDecision(
                decision="HIGH_ALERT",
                severity="CRITICAL",
                reason="A blocked device is active on the network.",
                csi_presence_detected=csi_detected,
                nearby_device_count=context.nearby_device_count,
                approved_user_present=approved_present
            )

        # 2. ALERT: CSI motion + NO authorized phone connected
        if csi_detected and not approved_present:
            reason = "Physical presence detected via CSI, but no authorized devices are home."
            if nearby_present:
                reason = "Physical presence detected, and an unknown nearby device is probing."
            
            return CorrelationDecision(
                decision="ALERT",
                severity="MEDIUM",
                reason=reason,
                csi_presence_detected=csi_detected,
                nearby_device_count=context.nearby_device_count,
                approved_user_present=False
            )

        # 3. SAFE: CSI motion + Authorized user is home
        if csi_detected and approved_present:
            return CorrelationDecision(
                decision="SAFE",
                severity="LOW",
                reason="Authorized user is present in the monitored area.",
                csi_presence_detected=csi_detected,
                nearby_device_count=context.nearby_device_count,
                approved_user_present=True
            )

        # 4. IDLE: No motion
        return CorrelationDecision(
            decision="IDLE",
            severity="LOW",
            reason="System monitoring normally.",
            csi_presence_detected=False,
            nearby_device_count=context.nearby_device_count,
            approved_user_present=approved_present
        )