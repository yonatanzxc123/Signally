"""
Pure parser for nexmon_csi UDP frames.

No sockets, no threads, no state - just bytes in, parsed CSI out - so it can be
unit-tested against synthetic frames without any hardware.

Frame layout (seemoo-lab/nexmon_csi) for BCM43455c0 / BCM4339 chips. Those chips
emit plain interleaved int16 I/Q pairs; the bcm4358 / bcm4366c0 family uses a
different compressed-float encoding that this parser deliberately does NOT handle
(the Raspberry Pi 5 / Pi 4 / Pi 3B+ onboard radio is BCM43455c0, which is what we
target):

    offset  size  field
    0       2     magic bytes, always 0x1111
    2       6     source MAC address
    8       2     Wi-Fi frame sequence number
    10      2     core (low 3 bits) / spatial stream (next 3 bits)
    12      2     chanspec
    14      2     chip version identifier
    16      2     frame control (currently ignored)
    18      ...   CSI payload: N subcarriers x (int16 real, int16 imag) = N*4 bytes
                  N is 64 / 128 / 256 for 20 / 40 / 80 MHz capture bandwidth.

Byte order is assumed little-endian (ARM/Broadcom). This is the single assumption
we could not validate without a live capture: if amplitudes come out looking like
noise once real hardware is connected, flip _BYTE_ORDER to ">" and re-test. It is
isolated here on purpose so that is a one-line change.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

_BYTE_ORDER = "<"  # little-endian; see module docstring before changing

_MAGIC = 0x1111
import struct

_HEADER_STRUCT = struct.Struct(_BYTE_ORDER + "H6sHHHHH")
_HEADER_SIZE = _HEADER_STRUCT.size  # 18 bytes in the current nexmon_csi format
_BYTES_PER_SUBCARRIER = 4  # int16 real + int16 imag


@dataclass(frozen=True)
class CsiFrame:
    """One decoded nexmon CSI frame."""

    source_mac: str
    sequence: int
    core: int
    spatial_stream: int
    chanspec: int
    chip: int
    amplitudes: np.ndarray  # float64, one value per subcarrier

    @property
    def subcarrier_count(self) -> int:
        return int(self.amplitudes.shape[0])


def parse_csi_frame(data: bytes) -> Optional[CsiFrame]:
    """
    Parse one nexmon_csi UDP datagram.

    Returns a CsiFrame, or None if the datagram is not a well-formed CSI frame
    (bad magic, too short, or empty payload) - callers should just skip None.
    """
    if len(data) < _HEADER_SIZE:
        return None

    magic, mac, seq, core_spatial, chanspec, chip, _frame_control = (
        _HEADER_STRUCT.unpack_from(data)
    )
    if magic != _MAGIC:
        return None

    payload = data[_HEADER_SIZE:]
    subcarrier_count = len(payload) // _BYTES_PER_SUBCARRIER
    if subcarrier_count == 0:
        return None

    # Trim any trailing bytes that don't complete a full I/Q pair, then read the
    # payload as int16 pairs -> complex -> amplitude, all vectorised.
    usable = subcarrier_count * _BYTES_PER_SUBCARRIER
    iq = np.frombuffer(payload[:usable], dtype=_BYTE_ORDER + "i2").astype(np.float64)
    real = iq[0::2]
    imag = iq[1::2]
    amplitudes = np.hypot(real, imag)

    return CsiFrame(
        source_mac=":".join("%02x" % b for b in mac),
        sequence=seq,
        core=core_spatial & 0x07,
        spatial_stream=(core_spatial >> 3) & 0x07,
        chanspec=chanspec,
        chip=chip,
        amplitudes=amplitudes,
    )


def build_csi_frame(amplitudes_iq, *, source_mac=b"\xaa\xbb\xcc\xdd\xee\xff",
                    sequence: int = 0, core_spatial: int = 0,
                    chanspec: int = 0, chip: int = 0) -> bytes:
    """
    Build a synthetic nexmon CSI datagram from a list of (real, imag) int pairs.

    Test/replay helper only - the inverse of parse_csi_frame - so unit tests and
    the replay script can produce byte-accurate frames without real hardware.
    """
    header = _HEADER_STRUCT.pack(
        _MAGIC, source_mac, sequence, core_spatial, chanspec, chip, 0
    )
    body = b"".join(
        struct.pack(_BYTE_ORDER + "hh", int(r), int(i)) for r, i in amplitudes_iq
    )
    return header + body
