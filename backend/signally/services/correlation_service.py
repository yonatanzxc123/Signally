"""
Three-layer correlation service.
"""

from datetime import timezone

from signally.config import ADMIN_REVIEW_GRACE_SECONDS
from signally.models.correlation_models import (
    CorrelationContext,
    CorrelationDecision,
)
from signally.models.security_mode import SecurityMode
from signally.utils.time_utils import utc_now


class CorrelationService:
   def evaluate(self, context: CorrelationContext) -> CorrelationDecision:
        approved_present = context.connected_presence.approved_user_present
        admin_present = context.connected_presence.admin_present
        family_present = context.connected_presence.family_present
        guest_present = context.connected_presence.guest_present
        blocked_present = len(context.connected_presence.blocked_connected_devices) > 0
        csi_detected = context.csi_presence_detected
        security_mode = context.security_mode
        away_mode = security_mode == SecurityMode.AWAY
        connected_intruder_count = len(context.connected_presence.pending_connected_devices)
        nearby_probe_activity = context.nearby_presence.nearby_probe_count > 0
        review_grace_active = self._is_admin_review_grace_active(context)

        # 1. CRITICAL: Blocked device on the network
        if blocked_present:
            return CorrelationDecision(
                decision="HIGH_ALERT",
                severity="CRITICAL",
                reason="A blocked device is active on the network.",
                security_mode=security_mode,
                csi_presence_detected=csi_detected,
                nearby_device_count=context.nearby_device_count,
                approved_user_present=approved_present,
                admin_present=admin_present,
                family_present=family_present,
                guest_present=guest_present,
                current_intruder_count=max(1, connected_intruder_count),
                notification_audience=["ADMIN", "FAMILY"],
            )

        # 2. HOME: unknown connected device — soft review, no loud alert
        if connected_intruder_count > 0 and not away_mode:
            audience = ["ADMIN"] if review_grace_active else ["ADMIN", "FAMILY"]
            return CorrelationDecision(
                decision="HOME_REVIEW",
                severity="MEDIUM",
                reason="Unknown connected device detected while Home mode is active.",
                security_mode=security_mode,
                csi_presence_detected=csi_detected,
                nearby_device_count=context.nearby_device_count,
                approved_user_present=approved_present,
                admin_present=admin_present,
                family_present=family_present,
                guest_present=guest_present,
                current_intruder_count=connected_intruder_count,
                admin_review_grace_active=review_grace_active,
                notification_audience=audience,
            )

        # 3. AWAY REVIEW: unknown connected device while admin is home within grace window
        if connected_intruder_count > 0 and admin_present and review_grace_active:
            return CorrelationDecision(
                decision="ADMIN_REVIEW",
                severity="MEDIUM",
                reason="Unknown connected device detected. Admin review window active.",
                security_mode=security_mode,
                csi_presence_detected=csi_detected,
                nearby_device_count=context.nearby_device_count,
                approved_user_present=approved_present,
                admin_present=admin_present,
                family_present=family_present,
                guest_present=guest_present,
                current_intruder_count=connected_intruder_count,
                admin_review_grace_active=True,
                notification_audience=["ADMIN"],
            )

        # 4. AWAY ALERT: unknown connected device, no grace or no admin
        if connected_intruder_count > 0:
            return CorrelationDecision(
                decision="ALERT",
                severity="HIGH" if csi_detected else "MEDIUM",
                reason="Unknown device connected to the network while armed.",
                security_mode=security_mode,
                csi_presence_detected=csi_detected,
                nearby_device_count=context.nearby_device_count,
                approved_user_present=approved_present,
                admin_present=admin_present,
                family_present=family_present,
                guest_present=guest_present,
                current_intruder_count=connected_intruder_count,
                notification_audience=["ADMIN", "FAMILY"],
            )

        # 5. AWAY ALERT: probe-only wireless activity with no approved user home
        if away_mode and nearby_probe_activity and not approved_present:
            return CorrelationDecision(
                decision="ALERT",
                severity="MEDIUM",
                reason="Unknown wireless activity detected nearby.",
                security_mode=security_mode,
                csi_presence_detected=csi_detected,
                nearby_device_count=context.nearby_device_count,
                approved_user_present=False,
                admin_present=admin_present,
                family_present=family_present,
                guest_present=guest_present,
                current_intruder_count=context.nearby_presence.nearby_probe_count,
                notification_audience=["ADMIN", "FAMILY"],
            )

        # 6. HOME: CSI presence alone — occupancy evidence, not intruder verdict
        if csi_detected and not approved_present and not away_mode:
            return CorrelationDecision(
                decision="HOME_OCCUPIED",
                severity="LOW",
                reason="Physical presence detected while Home mode is active.",
                security_mode=security_mode,
                csi_presence_detected=csi_detected,
                nearby_device_count=context.nearby_device_count,
                approved_user_present=False,
                admin_present=admin_present,
                family_present=family_present,
                guest_present=guest_present,
            )

        # 7. AWAY ALERT: CSI motion, no authorized phone home
        if csi_detected and not approved_present:
            return CorrelationDecision(
                decision="ALERT",
                severity="MEDIUM",
                reason="Physical presence detected while armed and no authorized devices are home.",
                security_mode=security_mode,
                csi_presence_detected=csi_detected,
                nearby_device_count=context.nearby_device_count,
                approved_user_present=False,
                admin_present=admin_present,
                family_present=family_present,
                guest_present=guest_present,
                current_intruder_count=1,
                notification_audience=["ADMIN", "FAMILY"],
            )

        # 8. SAFE: CSI motion + authorized user home
        if csi_detected and approved_present:
            return CorrelationDecision(
                decision="SAFE",
                severity="LOW",
                reason="Authorized user is present in the monitored area.",
                security_mode=security_mode,
                csi_presence_detected=csi_detected,
                nearby_device_count=context.nearby_device_count,
                approved_user_present=True,
                admin_present=admin_present,
                family_present=family_present,
                guest_present=guest_present,
            )

        # 9. IDLE
        return CorrelationDecision(
            decision="IDLE",
            severity="LOW",
            reason="System monitoring normally.",
            security_mode=security_mode,
            csi_presence_detected=False,
            nearby_device_count=context.nearby_device_count,
            approved_user_present=approved_present,
            admin_present=admin_present,
            family_present=family_present,
            guest_present=guest_present,
        )

   def _is_admin_review_grace_active(self, context: CorrelationContext) -> bool:
        pending_devices = context.connected_presence.pending_connected_devices
        if not pending_devices:
            return True
        first_seen = min(device.first_seen for device in pending_devices)
        if first_seen.tzinfo is None:
            first_seen = first_seen.replace(tzinfo=timezone.utc)
        return (utc_now() - first_seen).total_seconds() < ADMIN_REVIEW_GRACE_SECONDS
