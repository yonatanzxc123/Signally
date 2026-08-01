#!/usr/bin/env python3
"""Print the most common original transmitter MAC in a Nexmon CSI pcap."""

from __future__ import annotations

import sys

import numpy as np
from nexcsi import decoder


if len(sys.argv) != 2:
    raise SystemExit(f"Usage: {sys.argv[0]} CAPTURE.pcap")

samples = decoder("raspberrypi").read_pcap(sys.argv[1])
if samples.size == 0:
    raise SystemExit("No CSI frames found")

macs, counts = np.unique(samples["mac"], axis=0, return_counts=True)
valid = np.any(macs != 0, axis=1)
if not np.any(valid):
    raise SystemExit("No valid transmitter MAC found")

macs = macs[valid]
counts = counts[valid]
winner = macs[int(np.argmax(counts))]
print(":".join(f"{int(part):02x}" for part in winner))
