"""CSI baseline persistence and comparison."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from signally.config import (
    CSI_BASELINE_MIN_THRESHOLD,
    CSI_BASELINE_THRESHOLD_MULTIPLIER,
)
from signally.models.csi_baseline import CsiBaseline
from signally.sensors.nexmon.csi_features import CsiFeatureWindow


@dataclass
class BaselineComparison:
    presence_detected: bool
    confidence: float
    baseline_deviation: float
    reason: str


class CsiBaselineService:
    def __init__(
        self,
        session: Session,
        threshold_multiplier: float = CSI_BASELINE_THRESHOLD_MULTIPLIER,
        minimum_threshold: float = CSI_BASELINE_MIN_THRESHOLD,
    ) -> None:
        self.session = session
        self.threshold_multiplier = threshold_multiplier
        self.minimum_threshold = minimum_threshold

    def get_current_baseline(self) -> Optional[CsiBaseline]:
        stmt = select(CsiBaseline).order_by(CsiBaseline.created_at.desc(), CsiBaseline.id.desc())
        return self.session.scalar(stmt)

    def create_baseline(
        self,
        features: CsiFeatureWindow,
        source: str = "NEXMON",
        provider_metadata: Optional[dict] = None,
    ) -> CsiBaseline:
        self.delete_baseline(commit=False)
        threshold = max(
            self.minimum_threshold,
            features.stddev * self.threshold_multiplier,
            features.mean_abs_delta * self.threshold_multiplier,
        )
        baseline = CsiBaseline(
            source=source,
            provider_metadata=json.dumps(provider_metadata or {}, sort_keys=True),
            mean_amplitude=features.mean_amplitude,
            variance=features.variance,
            stddev=features.stddev,
            mean_abs_delta=features.mean_abs_delta,
            threshold=threshold,
            sample_count=features.sample_count,
            packet_count=features.packet_count,
        )
        self.session.add(baseline)
        try:
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        self.session.refresh(baseline)
        return baseline

    def delete_baseline(self, commit: bool = True) -> int:
        result = self.session.execute(delete(CsiBaseline))
        deleted_count = int(result.rowcount or 0)
        if commit:
            try:
                self.session.commit()
            except Exception:
                self.session.rollback()
                raise
        return deleted_count

    def compare_to_baseline(
        self,
        features: CsiFeatureWindow,
        baseline: CsiBaseline,
    ) -> BaselineComparison:
        amplitude_delta = abs(features.mean_amplitude - baseline.mean_amplitude)
        movement_delta = abs(features.mean_abs_delta - baseline.mean_abs_delta)
        deviation = max(amplitude_delta, movement_delta)
        threshold = max(baseline.threshold, self.minimum_threshold)
        confidence = max(0.0, min(deviation / (threshold * 2.0), 1.0))
        presence_detected = deviation >= threshold

        if presence_detected:
            reason = "CSI features deviate from calibrated baseline."
        else:
            reason = "CSI features are within calibrated baseline."

        return BaselineComparison(
            presence_detected=presence_detected,
            confidence=confidence,
            baseline_deviation=deviation,
            reason=reason,
        )
