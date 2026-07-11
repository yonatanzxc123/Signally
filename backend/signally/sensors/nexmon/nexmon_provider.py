"""Nexmon-backed CSI sensing provider."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from signally.config import (
    CSI_BASELINE_MIN_PACKETS,
    CSI_FEATURE_WINDOW_SECONDS,
    CSI_PACKET_STALE_AFTER_SECONDS,
)
from signally.models.csi_baseline import CsiBaseline
from signally.sensors.nexmon.baseline_service import CsiBaselineService
from signally.sensors.nexmon.csi_features import extract_csi_features
from signally.sensors.nexmon.nexmon_udp_receiver import NexmonUdpReceiver
from signally.sensors.sensing_snapshot import SensingProviderStatus, SensingSnapshot
from signally.utils.time_utils import utc_now


class NexmonCsiProvider:
    def __init__(
        self,
        receiver: Optional[NexmonUdpReceiver] = None,
        auto_start: bool = True,
        stale_after_seconds: float = CSI_PACKET_STALE_AFTER_SECONDS,
        feature_window_seconds: float = CSI_FEATURE_WINDOW_SECONDS,
        baseline_min_packets: int = CSI_BASELINE_MIN_PACKETS,
    ) -> None:
        self.receiver = receiver or NexmonUdpReceiver()
        self.stale_after_seconds = stale_after_seconds
        self.feature_window_seconds = feature_window_seconds
        self.baseline_min_packets = baseline_min_packets
        self._calibration_started_at: Optional[datetime] = None

        if auto_start:
            self.start()

    def start(self) -> bool:
        return self.receiver.start()

    def stop(self) -> None:
        self.receiver.stop()

    def is_receiving_data(self) -> bool:
        age_ms = self.receiver.last_packet_age_ms()
        if age_ms is None:
            return False
        return age_ms <= int(self.stale_after_seconds * 1000)

    def is_presence_detected(self) -> bool:
        return self.get_snapshot().presence_detected

    def get_presence_strength(self) -> Optional[float]:
        return self.get_snapshot().confidence

    def get_snapshot(self, session: Optional[Session] = None) -> SensingSnapshot:
        status = self.receiver.status()
        last_age_ms = status["last_packet_age_ms"]
        raw_summary = {
            "receiver": status,
            "calibrating": self.is_calibrating(),
        }

        if status["last_error"] and (
            status["parse_error_count"] >= 3 or not status["running"]
        ) and status["parsed_packet_count"] == 0:
            return SensingSnapshot(
                source="NEXMON",
                provider_status=SensingProviderStatus.ERROR,
                presence_detected=False,
                packets_per_second=status["packets_per_second"],
                last_packet_age_ms=last_age_ms,
                reason=status["last_error"],
                raw_summary=raw_summary,
            )

        if last_age_ms is None or last_age_ms > int(self.stale_after_seconds * 1000):
            return SensingSnapshot(
                source="NEXMON",
                provider_status=SensingProviderStatus.NO_DATA,
                presence_detected=False,
                packets_per_second=status["packets_per_second"],
                last_packet_age_ms=last_age_ms,
                reason="No recent Nexmon CSI packets received.",
                raw_summary=raw_summary,
            )

        packets = self.receiver.recent_packets(window_seconds=self.feature_window_seconds)
        features = extract_csi_features(packets)
        raw_summary["features"] = features.as_dict()

        if session is None:
            return SensingSnapshot(
                source="NEXMON",
                provider_status=SensingProviderStatus.NO_BASELINE,
                presence_detected=False,
                packets_per_second=status["packets_per_second"],
                last_packet_age_ms=last_age_ms,
                reason="Nexmon CSI packets are arriving, but no database session was provided for baseline lookup.",
                raw_summary=raw_summary,
            )

        baseline = CsiBaselineService(session).get_current_baseline()
        if baseline is None:
            return SensingSnapshot(
                source="NEXMON",
                provider_status=SensingProviderStatus.NO_BASELINE,
                presence_detected=False,
                packets_per_second=status["packets_per_second"],
                last_packet_age_ms=last_age_ms,
                reason="Nexmon CSI packets are arriving, but no CSI baseline has been calibrated.",
                raw_summary=raw_summary,
            )

        comparison = CsiBaselineService(session).compare_to_baseline(features, baseline)
        raw_summary["baseline"] = {
            "id": baseline.id,
            "threshold": baseline.threshold,
            "sample_count": baseline.sample_count,
            "packet_count": baseline.packet_count,
            "created_at": baseline.created_at.isoformat(),
        }

        return SensingSnapshot(
            source="NEXMON",
            provider_status=SensingProviderStatus.OK,
            presence_detected=comparison.presence_detected,
            confidence=comparison.confidence,
            baseline_deviation=comparison.baseline_deviation,
            packets_per_second=status["packets_per_second"],
            last_packet_age_ms=last_age_ms,
            reason=comparison.reason,
            raw_summary=raw_summary,
        )

    def start_calibration(self) -> dict:
        self._calibration_started_at = utc_now()
        return {
            "started_at": self._calibration_started_at,
            "source": "NEXMON",
            "message": "CSI calibration started. Keep the room in a normal empty/baseline state.",
        }

    def stop_calibration(self, session: Session) -> CsiBaseline:
        if self._calibration_started_at is None:
            raise ValueError("CSI calibration has not been started.")

        started_at = self._calibration_started_at
        self._calibration_started_at = None
        packets = self.receiver.packets_since(started_at)
        features = extract_csi_features(packets)
        if features.packet_count < self.baseline_min_packets:
            raise ValueError(
                "Not enough CSI packets to create a baseline. Collected {0}, need at least {1}.".format(
                    features.packet_count,
                    self.baseline_min_packets,
                )
            )

        return CsiBaselineService(session).create_baseline(
            features,
            source="NEXMON",
            provider_metadata={
                "started_at": started_at.isoformat(),
                "stopped_at": utc_now().isoformat(),
                "receiver": self.receiver.status(),
            },
        )

    def is_calibrating(self) -> bool:
        return self._calibration_started_at is not None

    def get_baseline(self, session: Session) -> Optional[CsiBaseline]:
        return CsiBaselineService(session).get_current_baseline()

    def delete_baseline(self, session: Session) -> int:
        return CsiBaselineService(session).delete_baseline()
