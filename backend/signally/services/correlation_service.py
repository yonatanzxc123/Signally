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
        blocked_present = (
            len(context.connected_presence.blocked_connected_devices) > 0
            or len(context.nearby_presence.blocked_nearby_devices) > 0
        )
        csi_detected = context.csi_presence_detected
        security_mode = context.security_mode
        away_mode = security_mode == SecurityMode.AWAY
        current_intruder_count = max(
            len(context.connected_presence.pending_connected_devices),
            context.nearby_presence.effective_unknown_nearby_count,
        )
        review_grace_active = self._is_admin_review_grace_active(context)

        # 1. CRITICAL: Blocked device physically here
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
                current_intruder_count=max(1, current_intruder_count),
                ignored_authorized_duplicate_count=context.nearby_presence.ignored_authorized_duplicate_count,
                notification_audience=["ADMIN", "FAMILY"],
            )

        # 2. HOME: unknown device gets reviewed without arming a loud intruder alert.
        if current_intruder_count > 0 and not away_mode:
            audience = ["ADMIN"] if review_grace_active else ["ADMIN", "FAMILY"]
            return CorrelationDecision(
                decision="HOME_REVIEW",
                severity="MEDIUM",
                reason="Unknown device detected while Home mode is active.",
                security_mode=security_mode,
                csi_presence_detected=csi_detected,
                nearby_device_count=context.nearby_device_count,
                approved_user_present=approved_present,
                admin_present=admin_present,
                family_present=family_present,
                guest_present=guest_present,
                current_intruder_count=current_intruder_count,
                ignored_authorized_duplicate_count=context.nearby_presence.ignored_authorized_duplicate_count,
                admin_review_grace_active=review_grace_active,
                notification_audience=audience,
            )

        # 3. AWAY REVIEW: unknown current device while an admin is home.
        if current_intruder_count > 0 and admin_present and review_grace_active:
            return CorrelationDecision(
                decision="ADMIN_REVIEW",
                severity="MEDIUM",
                reason="Unknown device detected. Admin review window is active before family notification.",
                security_mode=security_mode,
                csi_presence_detected=csi_detected,
                nearby_device_count=context.nearby_device_count,
                approved_user_present=approved_present,
                admin_present=admin_present,
                family_present=family_present,
                guest_present=guest_present,
                current_intruder_count=current_intruder_count,
                ignored_authorized_duplicate_count=context.nearby_presence.ignored_authorized_duplicate_count,
                admin_review_grace_active=True,
                notification_audience=["ADMIN"],
            )

        # 4. AWAY ALERT: unknown device stayed unresolved or no admin is present.
        if current_intruder_count > 0:
            return CorrelationDecision(
                decision="ALERT",
                severity="HIGH" if csi_detected else "MEDIUM",
                reason="Unknown current device requires attention.",
                security_mode=security_mode,
                csi_presence_detected=csi_detected,
                nearby_device_count=context.nearby_device_count,
                approved_user_present=approved_present,
                admin_present=admin_present,
                family_present=family_present,
                guest_present=guest_present,
                current_intruder_count=current_intruder_count,
                ignored_authorized_duplicate_count=context.nearby_presence.ignored_authorized_duplicate_count,
                notification_audience=["ADMIN", "FAMILY"],
            )

        # 5. HOME: CSI presence alone is occupancy evidence, not an intruder verdict.
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
                ignored_authorized_duplicate_count=context.nearby_presence.ignored_authorized_duplicate_count,
            )

        # 6. AWAY ALERT: CSI motion + NO authorized phone connected
        if csi_detected and not approved_present:
            reason = "Physical presence detected while Away mode is armed and no authorized devices are home."
            
            return CorrelationDecision(
                decision="ALERT",
                severity="MEDIUM",
                reason=reason,
                security_mode=security_mode,
                csi_presence_detected=csi_detected,
                nearby_device_count=context.nearby_device_count,
                approved_user_present=False,
                admin_present=admin_present,
                family_present=family_present,
                guest_present=guest_present,
                current_intruder_count=1,
                ignored_authorized_duplicate_count=context.nearby_presence.ignored_authorized_duplicate_count,
                notification_audience=["ADMIN", "FAMILY"],
            )

        # 7. SAFE: CSI motion + Authorized user is home
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
                ignored_authorized_duplicate_count=context.nearby_presence.ignored_authorized_duplicate_count,
            )

        # 8. IDLE: No unresolved current unknowns and no CSI motion.
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
            ignored_authorized_duplicate_count=context.nearby_presence.ignored_authorized_duplicate_count,
        )

   def _is_admin_review_grace_active(self, context: CorrelationContext) -> bool:
        first_unknown_seen_at = context.nearby_presence.first_unknown_seen_at
        if first_unknown_seen_at is None:
            pending_devices = context.connected_presence.pending_connected_devices
            if not pending_devices:
                return True
            first_unknown_seen_at = min(device.first_seen for device in pending_devices)

        if first_unknown_seen_at.tzinfo is None:
            first_unknown_seen_at = first_unknown_seen_at.replace(tzinfo=timezone.utc)

        age_seconds = (utc_now() - first_unknown_seen_at).total_seconds()
        return age_seconds < ADMIN_REVIEW_GRACE_SECONDS
