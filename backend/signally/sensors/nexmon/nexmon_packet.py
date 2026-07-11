"""Minimal Nexmon CSI UDP payload parser.

Signally treats Nexmon CSI as an external producer. The parser here validates a
small Signally-supported UDP payload shape and extracts bcm43455c0-style
interleaved int16 real/imaginary CSI values.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import struct
from typing import Optional

from signally.utils.time_utils import utc_now


NEXMON_CSI_MAGIC = b"\x11\x11\x11\x11"
NEXMON_HEADER_SIZE = 16


class NexmonPacketParseError(ValueError):
    """Raised when a UDP payload cannot be parsed as supported Nexmon CSI."""


@dataclass
class NexmonCsiPacket:
    source_mac: Optional[str]
    sequence_number: Optional[int]
    core: Optional[int]
    spatial_stream: Optional[int]
    channel: Optional[int]
    csi_samples: list[complex]
    received_at: datetime
    raw_size: int

    @property
    def sample_count(self) -> int:
        return len(self.csi_samples)


def parse_nexmon_udp_payload(
    payload: bytes,
    received_at: Optional[datetime] = None,
) -> NexmonCsiPacket:
    if len(payload) < NEXMON_HEADER_SIZE + 4:
        raise NexmonPacketParseError("Nexmon CSI payload is too short.")

    if payload[:4] != NEXMON_CSI_MAGIC:
        raise NexmonPacketParseError("Nexmon CSI magic bytes are missing.")

    csi_bytes = payload[NEXMON_HEADER_SIZE:]
    if len(csi_bytes) % 4 != 0:
        raise NexmonPacketParseError("CSI sample payload must be int16 real/imag pairs.")

    samples: list[complex] = []
    for offset in range(0, len(csi_bytes), 4):
        real, imag = struct.unpack_from("<hh", csi_bytes, offset)
        samples.append(complex(real, imag))

    if not samples:
        raise NexmonPacketParseError("Nexmon CSI payload did not contain CSI samples.")

    source_mac = ":".join("{0:02X}".format(part) for part in payload[4:10])
    sequence_number = struct.unpack_from("<H", payload, 10)[0]
    core = payload[12]
    spatial_stream = payload[13]
    channel = struct.unpack_from("<H", payload, 14)[0]

    return NexmonCsiPacket(
        source_mac=source_mac,
        sequence_number=sequence_number,
        core=core,
        spatial_stream=spatial_stream,
        channel=channel,
        csi_samples=samples,
        received_at=received_at or utc_now(),
        raw_size=len(payload),
    )
