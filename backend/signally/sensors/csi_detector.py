"""
Classical CSI motion/presence detector.

This is the RuView-inspired *capability* we actually need for Signally, and
nothing more: outlier-filtered amplitude features feeding a variance-vs-baseline
motion decision with a confidence score. No pose, no breathing/heart-rate, no
neural model, no multi-channel fusion.

Why variance and not raw amplitude: a stationary room settles to a near-constant
per-subcarrier amplitude; a moving body perturbs the multipath, so amplitude
*varies over time*. We track that temporal variance across a rolling window and
compare it to a learned empty-room baseline.

The class is pure (no sockets/threads/clock) so it can be unit-tested by feeding
it synthetic amplitude vectors: quiet input -> no detection, perturbed input ->
detection with rising confidence.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass(frozen=True)
class PresenceReading:
    detected: bool
    confidence: float  # 0.0 .. 1.0
    motion_metric: float  # raw variance metric, for calibration/telemetry
    baseline: Optional[float]  # current learned baseline, None until warmed up


def hampel_filter(values: np.ndarray, sigma: float = 3.0) -> np.ndarray:
    """
    Replace impulsive outliers in a 1-D array using the Hampel identifier
    (median + scaled MAD). This is RuView's first preprocessing stage and the
    piece the earlier attempt lacked - without it, a single corrupt subcarrier
    reading spikes the variance and fakes a detection.

    Operates over the whole array (a single frame's subcarriers), which is the
    cheap, allocation-free variant appropriate at ~100 Hz.
    """
    if values.size == 0:
        return values
    median = np.median(values)
    diff = np.abs(values - median)
    # 1.4826 scales MAD to be a consistent estimator of std for normal data.
    scale = 1.4826 * np.median(diff)
    if scale == 0:
        # Degenerate: more than half the values are identical, so there is no
        # robust noise floor to define an outlier against. Real CSI (64 noisy
        # subcarriers) never lands here; leave the frame untouched.
        return values
    mask = diff > sigma * scale
    if not mask.any():
        return values
    cleaned = values.copy()
    cleaned[mask] = median
    return cleaned


class CsiMotionDetector:
    def __init__(
        self,
        window_size: int = 50,
        baseline_factor: float = 3.0,
        hampel_sigma: float = 3.0,
        baseline_warmup: int = 30,
        baseline_alpha: float = 0.01,
    ) -> None:
        """
        window_size     number of recent frames the variance is computed over.
        baseline_factor how far above baseline the metric must rise to count as
                        motion (detected = metric > baseline * factor).
        hampel_sigma    outlier threshold in MADs for the Hampel filter.
        baseline_warmup full-window metrics to observe before the baseline is
                        trusted / any detection is emitted (assumes an empty
                        room at startup).
        baseline_alpha  EMA rate for adapting the baseline. Only updated while
                        NOT detecting, so a person standing still never trains
                        itself into the baseline.
        """
        self.window_size = window_size
        self.baseline_factor = baseline_factor
        self.hampel_sigma = hampel_sigma
        self.baseline_warmup = max(1, baseline_warmup)
        self.baseline_alpha = baseline_alpha

        self._window: deque = deque(maxlen=window_size)
        self._warmup_metrics: deque = deque(maxlen=self.baseline_warmup)
        self._baseline: Optional[float] = None
        self._frames_seen = 0

    def reset(self) -> None:
        self._window.clear()
        self._warmup_metrics.clear()
        self._baseline = None
        self._frames_seen = 0

    @property
    def baseline(self) -> Optional[float]:
        return self._baseline

    @property
    def threshold(self) -> Optional[float]:
        if self._baseline is None:
            return None
        return self._baseline * self.baseline_factor

    @property
    def frames_seen(self) -> int:
        return self._frames_seen

    @property
    def ready(self) -> bool:
        return self._baseline is not None

    def update(self, amplitudes: np.ndarray) -> PresenceReading:
        """Feed one frame's per-subcarrier amplitudes, get a presence reading."""
        self._frames_seen += 1

        cleaned = hampel_filter(np.asarray(amplitudes, dtype=np.float64), self.hampel_sigma)
        # Normalise so absolute signal strength / gain drift doesn't move the
        # metric - we care about the *shape* changing over time, not its level.
        norm = np.linalg.norm(cleaned)
        if norm > 0:
            cleaned = cleaned / norm
        self._window.append(cleaned)

        # A partial rolling window systematically starts near zero and produced
        # a permanently low baseline in live tests. Do not calibrate until the
        # configured temporal window is completely populated.
        if len(self._window) < self.window_size:
            return PresenceReading(False, 0.0, 0.0, self._baseline)

        # Temporal variance per subcarrier, averaged across subcarriers.
        stacked = np.vstack(self._window)
        metric = float(np.mean(np.var(stacked, axis=0)))

        # Warm-up: use the median of several full-window quiet metrics. Seeding
        # an EMA from the first partial-window metric can trap detection high
        # forever because the baseline is intentionally frozen during motion.
        if self._baseline is None:
            self._warmup_metrics.append(metric)
            if len(self._warmup_metrics) >= self.baseline_warmup:
                self._baseline = float(np.median(np.asarray(self._warmup_metrics)))
            return PresenceReading(False, 0.0, metric, self._baseline)

        threshold = self._baseline * self.baseline_factor
        detected = metric > threshold

        if detected:
            # confidence scales how far past threshold we are, saturating at 2x.
            confidence = min(1.0, (metric - threshold) / max(threshold, 1e-12))
        else:
            confidence = 0.0
            # Adapt baseline only when quiet, so slow gain drift is tracked but a
            # present person is never absorbed into "normal".
            self._baseline = (
                (1 - self.baseline_alpha) * self._baseline
                + self.baseline_alpha * metric
            )

        return PresenceReading(detected, confidence, metric, self._baseline)
