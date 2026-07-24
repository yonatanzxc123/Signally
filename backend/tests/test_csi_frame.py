"""Unit tests for the pure nexmon CSI frame parser."""

import math

import numpy as np

from signally.sensors.csi_frame import build_csi_frame, parse_csi_frame


def test_parse_round_trip_amplitudes():
    # (3,4)->5, (6,8)->10, (1,0)->1, (0,5)->5
    frame = build_csi_frame([(3, 4), (6, 8), (1, 0), (0, 5)], sequence=7)
    parsed = parse_csi_frame(frame)

    assert parsed is not None
    assert parsed.subcarrier_count == 4
    assert parsed.sequence == 7
    assert np.allclose(parsed.amplitudes, [5.0, 10.0, 1.0, 5.0])


def test_parse_decodes_header_fields():
    frame = build_csi_frame(
        [(1, 1)],
        source_mac=b"\x11\x22\x33\x44\x55\x66",
        sequence=42,
        core_spatial=(2 << 3) | 1,  # spatial=2, core=1
        chanspec=0xABCD,
        chip=0x1234,
    )
    parsed = parse_csi_frame(frame)

    assert parsed.source_mac == "11:22:33:44:55:66"
    assert parsed.sequence == 42
    assert parsed.core == 1
    assert parsed.spatial_stream == 2
    assert parsed.chanspec == 0xABCD
    assert parsed.chip == 0x1234


def test_bad_magic_returns_none():
    junk = b"\x00\x00\x00\x00" + b"x" * 40
    assert parse_csi_frame(junk) is None


def test_too_short_returns_none():
    assert parse_csi_frame(b"short") is None


def test_empty_payload_returns_none():
    # Valid 20-byte header but zero CSI values.
    header_only = build_csi_frame([])
    assert parse_csi_frame(header_only) is None


def test_negative_iq_amplitude():
    frame = build_csi_frame([(-3, -4)])  # amplitude 5
    parsed = parse_csi_frame(frame)
    assert math.isclose(parsed.amplitudes[0], 5.0)
