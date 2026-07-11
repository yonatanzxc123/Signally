"""Small CSI feature extraction helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from statistics import mean, pvariance

from signally.sensors.nexmon.nexmon_packet import NexmonCsiPacket
from signally.utils.time_utils import utc_now


@dataclass
class CsiFeatureWindow:
    mean_amplitude: float
    variance: float
    stddev: float
    mean_abs_delta: float
    sample_count: int
    packet_count: int
    created_at: datetime

    def as_dict(self) -> dict:
        return {
            "mean_amplitude": self.mean_amplitude,
            "variance": self.variance,
            "stddev": self.stddev,
            "mean_abs_delta": self.mean_abs_delta,
            "sample_count": self.sample_count,
            "packet_count": self.packet_count,
            "created_at": self.created_at.isoformat()
            if hasattr(self.created_at, "isoformat")
            else self.created_at,
        }


def amplitudes_from_packet(packet: NexmonCsiPacket) -> list[float]:
    amplitudes = [abs(sample) for sample in packet.csi_samples]
    return [value for value in amplitudes if value > 0.0]


def extract_csi_features(packets: list[NexmonCsiPacket]) -> CsiFeatureWindow:
    all_amplitudes: list[float] = []
    per_packet_means: list[float] = []

    for packet in packets:
        amplitudes = amplitudes_from_packet(packet)
        if not amplitudes:
            continue
        all_amplitudes.extend(amplitudes)
        per_packet_means.append(mean(amplitudes))

    if not all_amplitudes:
        return CsiFeatureWindow(
            mean_amplitude=0.0,
            variance=0.0,
            stddev=0.0,
            mean_abs_delta=0.0,
            sample_count=0,
            packet_count=0,
            created_at=utc_now(),
        )

    variance = pvariance(all_amplitudes) if len(all_amplitudes) > 1 else 0.0
    deltas = [
        abs(per_packet_means[index] - per_packet_means[index - 1])
        for index in range(1, len(per_packet_means))
    ]

    return CsiFeatureWindow(
        mean_amplitude=mean(all_amplitudes),
        variance=variance,
        stddev=variance ** 0.5,
        mean_abs_delta=mean(deltas) if deltas else 0.0,
        sample_count=len(all_amplitudes),
        packet_count=len(per_packet_means),
        created_at=utc_now(),
    )
