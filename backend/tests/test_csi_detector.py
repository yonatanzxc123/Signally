"""Unit tests for the classical CSI motion detector."""

import numpy as np

from signally.sensors.csi_detector import CsiMotionDetector, hampel_filter


def test_hampel_removes_spike_on_noisy_baseline():
    rng = np.random.default_rng(1)
    values = 50 + rng.normal(0, 1.0, 64)
    values[20] = 500.0

    cleaned = hampel_filter(values, sigma=3.0)

    assert cleaned[20] < 100  # spike pulled back toward the median
    assert np.allclose(cleaned[0], values[0])  # non-outlier untouched


def test_hampel_leaves_constant_array_untouched():
    values = np.full(8, 5.0)
    assert np.allclose(hampel_filter(values), values)


def _feed(detector, base, noise, count, rng):
    reading = None
    for _ in range(count):
        reading = detector.update(base + rng.normal(0, noise, base.size))
    return reading


def test_quiet_room_does_not_detect():
    rng = np.random.default_rng(42)
    det = CsiMotionDetector(window_size=30, baseline_factor=3.0, baseline_warmup=40)
    base = np.full(64, 50.0)

    reading = _feed(det, base, noise=0.5, count=120, rng=rng)

    assert reading.detected is False
    assert reading.confidence == 0.0


def test_motion_detected_with_confidence():
    rng = np.random.default_rng(42)
    det = CsiMotionDetector(window_size=30, baseline_factor=3.0, baseline_warmup=40)
    base = np.full(64, 50.0)

    _feed(det, base, noise=0.5, count=120, rng=rng)  # establish quiet baseline

    detected_any = False
    max_conf = 0.0
    for _ in range(60):
        r = det.update(base + rng.normal(0, 15.0, 64))
        detected_any = detected_any or r.detected
        max_conf = max(max_conf, r.confidence)

    assert detected_any is True
    assert max_conf > 0.0


def test_relaxes_back_to_quiet_after_motion():
    rng = np.random.default_rng(7)
    det = CsiMotionDetector(window_size=30, baseline_factor=3.0, baseline_warmup=40)
    base = np.full(64, 50.0)

    _feed(det, base, noise=0.5, count=120, rng=rng)
    _feed(det, base, noise=15.0, count=60, rng=rng)  # motion
    reading = _feed(det, base, noise=0.5, count=150, rng=rng)  # quiet again

    assert reading.detected is False
