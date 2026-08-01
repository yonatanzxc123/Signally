#!/usr/bin/env python3
"""Validate a nexmon CSI pcap: report mean per-subcarrier amplitude variance.
Higher variance = more motion in the environment during capture.
Usage: csi_validate.py <file.pcap>"""
import sys
import numpy as np
from nexcsi import decoder

dev = "raspberrypi"
samples = decoder(dev).read_pcap(sys.argv[1])
csi = decoder(dev).unpack(samples["csi"])          # complex [frames, subcarriers]
amp = np.abs(csi).astype(float)
# drop null/pilot subcarriers that are always ~0
keep = amp.mean(axis=0) > 1e-6
amp = amp[:, keep]
motion = float(np.mean(np.var(amp, axis=0)))
print(f"frames={amp.shape[0]}  subcarriers={amp.shape[1]}  MOTION_METRIC={motion:.2f}")
