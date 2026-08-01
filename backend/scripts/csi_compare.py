#!/usr/bin/env python3
"""Compare two Nexmon CSI pcaps using Signally's normalized motion feature."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from nexcsi import decoder

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from signally.sensors.csi_detector import hampel_filter  # noqa: E402


def metrics(
    path: str, window: int = 50, target_mac: str | None = None
) -> tuple[int, int, np.ndarray, list[tuple[str, int]]]:
    samples = decoder("raspberrypi").read_pcap(path)
    unique_macs, counts = np.unique(samples["mac"], axis=0, return_counts=True)
    sources = sorted(
        [
            (":".join(f"{int(part):02x}" for part in mac), int(count))
            for mac, count in zip(unique_macs, counts)
        ],
        key=lambda item: item[1],
        reverse=True,
    )
    if target_mac is not None:
        wanted = np.fromiter(
            (int(part, 16) for part in target_mac.split(":")), dtype=np.uint8
        )
        samples = samples[np.all(samples["mac"] == wanted, axis=1)]
        if samples.size == 0:
            raise ValueError(f"{path}: no frames from {target_mac}")
    csi = decoder("raspberrypi").unpack(samples["csi"])
    amplitude = np.abs(csi).astype(np.float64)
    cleaned = np.vstack([hampel_filter(frame) for frame in amplitude])
    norms = np.linalg.norm(cleaned, axis=1, keepdims=True)
    normalized = np.divide(cleaned, norms, out=np.zeros_like(cleaned), where=norms > 0)

    if normalized.shape[0] < window:
        raise ValueError(f"{path}: need at least {window} frames")

    prefix = np.vstack([np.zeros((1, normalized.shape[1])), np.cumsum(normalized, axis=0)])
    prefix_sq = np.vstack(
        [np.zeros((1, normalized.shape[1])), np.cumsum(normalized * normalized, axis=0)]
    )
    means = (prefix[window:] - prefix[:-window]) / window
    means_sq = (prefix_sq[window:] - prefix_sq[:-window]) / window
    rolling = np.mean(np.maximum(means_sq - means * means, 0.0), axis=1)
    return amplitude.shape[0], amplitude.shape[1], rolling, sources


def summarize(label: str, path: str, target_mac: str | None = None) -> np.ndarray:
    frames, subcarriers, rolling, sources = metrics(path, target_mac=target_mac)
    print(
        f"{label}: frames={frames} subcarriers={subcarriers} "
        f"normalized_mean={np.mean(rolling):.8g} "
        f"median={np.median(rolling):.8g} p95={np.percentile(rolling, 95):.8g}"
    )
    print("  sources:", ", ".join(f"{mac}={count}" for mac, count in sources[:5]))
    return rolling


if __name__ == "__main__":
    if len(sys.argv) not in (3, 4):
        raise SystemExit(f"Usage: {sys.argv[0]} EMPTY.pcap MOVING.pcap [SOURCE_MAC]")
    target = sys.argv[3].lower() if len(sys.argv) == 4 else None
    if target:
        print(f"filtering analysis to source {target}")
    empty = summarize("empty", sys.argv[1], target)
    moving = summarize("moving", sys.argv[2], target)
    ratio = np.mean(moving) / max(np.mean(empty), np.finfo(float).eps)
    print(f"moving/empty normalized mean ratio={ratio:.3f}x")
