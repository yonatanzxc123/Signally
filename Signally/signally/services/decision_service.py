"""
Decision service.

This service combines CSI presence information with Wi-Fi/device presence
information and decides whether the situation is safe or suspicious.
"""

from __future__ import annotations

from signally.services.decision_models import DecisionResult, PresenceSnapshot


class DecisionService:
    """
    Combines CSI and Wi-Fi/device state into a final decision.
    """

    def evaluate(
        self,
        csi_presence_detected: bool,
        presence_snapshot: PresenceSnapshot,
    ) -> DecisionResult:
        """
        Evaluate the current system state and return a structured decision.
        """

        approved_present = presence_snapshot.approved_user_present
        blocked_present = len(presence_snapshot.present_blocked_devices) > 0
        pending_present = len(presence_snapshot.present_pending_devices) > 0

        # Case 1: no CSI presence and no special concern
        if not csi_presence_detected:
            return DecisionResult(
                csi_presence_detected=False,
                approved_user_present=approved_present,
                decision="IDLE",
                reason="No CSI presence detected.",
                authorized_devices=presence_snapshot.present_authorized_devices,
                pending_devices=presence_snapshot.present_pending_devices,
                blocked_devices=presence_snapshot.present_blocked_devices,
            )

        # Case 2: blocked device present => strongest alert
        if blocked_present:
            return DecisionResult(
                csi_presence_detected=True,
                approved_user_present=approved_present,
                decision="HIGH_ALERT",
                reason="CSI presence detected and a blocked device is currently present.",
                authorized_devices=presence_snapshot.present_authorized_devices,
                pending_devices=presence_snapshot.present_pending_devices,
                blocked_devices=presence_snapshot.present_blocked_devices,
            )

        # Case 3: approved resident is home => safe
        if approved_present:
            return DecisionResult(
                csi_presence_detected=True,
                approved_user_present=True,
                decision="SAFE",
                reason="CSI presence detected and at least one approved device is present.",
                authorized_devices=presence_snapshot.present_authorized_devices,
                pending_devices=presence_snapshot.present_pending_devices,
                blocked_devices=presence_snapshot.present_blocked_devices,
            )

        # Case 4: no approved device but pending/unknown device is present => alert
        if pending_present:
            return DecisionResult(
                csi_presence_detected=True,
                approved_user_present=False,
                decision="ALERT",
                reason="CSI presence detected, no approved device is home, and an unknown/pending device is present.",
                authorized_devices=presence_snapshot.present_authorized_devices,
                pending_devices=presence_snapshot.present_pending_devices,
                blocked_devices=presence_snapshot.present_blocked_devices,
            )

        # Case 5: CSI detected something, but Wi-Fi has no visible devices
        return DecisionResult(
            csi_presence_detected=True,
            approved_user_present=False,
            decision="WARNING",
            reason="CSI presence detected, but no approved or identified Wi-Fi device is currently visible.",
            authorized_devices=presence_snapshot.present_authorized_devices,
            pending_devices=presence_snapshot.present_pending_devices,
            blocked_devices=presence_snapshot.present_blocked_devices,
        )