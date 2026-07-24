"""
Hardware-free CSI dev/verify tool.

Sends nexmon-format CSI datagrams to the same UDP endpoint the real driver would
(default 127.0.0.1:5500), so the whole Signally CSI pipeline - parser, detector,
provider, /csi/status - can be exercised on a laptop with no Raspberry Pi and no
nexmon firmware.

Two modes:
  --synthetic   generate frames, alternating QUIET and MOTION phases, so you can
                watch /csi/status flip presence on and off.
  --pcap FILE   replay real CSI UDP payloads captured earlier with e.g.
                `tcpdump -i lo -w csi.pcap udp port 5500` (needs scapy).

Usage (from backend/):
  python scripts/csi_replay.py --synthetic
  python scripts/csi_replay.py --synthetic --rate 100 --subcarriers 64
  python scripts/csi_replay.py --pcap captures/walk.pcap
"""

from __future__ import annotations

import argparse
import socket
import sys
import time

import numpy as np

# Allow running as a plain script from backend/ without installing the package.
sys.path.insert(0, ".")
from signally.sensors.csi_frame import build_csi_frame  # noqa: E402


def _iq_from_amplitudes(amps: np.ndarray) -> list[tuple[int, int]]:
    """Turn a real amplitude vector into int16 (real, imag) pairs (phase=0)."""
    return [(int(round(a)), 0) for a in amps]


def run_synthetic(sock, addr, rate: float, subcarriers: int,
                  quiet_secs: float, motion_secs: float) -> None:
    period = 1.0 / rate
    base = np.full(subcarriers, 50.0)
    rng = np.random.default_rng()
    seq = 0
    print(f"[replay] synthetic -> {addr[0]}:{addr[1]}  {rate:.0f} Hz, "
          f"{subcarriers} subcarriers, quiet {quiet_secs}s / motion {motion_secs}s")
    while True:
        for phase, secs, noise in (("QUIET", quiet_secs, 0.5), ("MOTION", motion_secs, 15.0)):
            print(f"[replay] phase = {phase}")
            end = time.time() + secs
            while time.time() < end:
                amps = base + rng.normal(0, noise, subcarriers)
                frame = build_csi_frame(_iq_from_amplitudes(amps), sequence=seq & 0xFFFF)
                sock.sendto(frame, addr)
                seq += 1
                time.sleep(period)


def run_pcap(sock, addr, path: str, rate: float) -> None:
    try:
        from scapy.all import rdpcap, UDP  # type: ignore
    except ImportError:
        print("[replay] scapy is required for --pcap mode", file=sys.stderr)
        sys.exit(2)

    packets = rdpcap(path)
    payloads = [bytes(p[UDP].payload) for p in packets if p.haslayer(UDP)]
    if not payloads:
        print(f"[replay] no UDP payloads found in {path}", file=sys.stderr)
        sys.exit(1)

    period = 1.0 / rate
    print(f"[replay] pcap {path}: {len(payloads)} frames -> {addr[0]}:{addr[1]} looping")
    while True:
        for payload in payloads:
            sock.sendto(payload, addr)
            time.sleep(period)


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay CSI frames over UDP")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--synthetic", action="store_true", help="generate synthetic frames")
    src.add_argument("--pcap", metavar="FILE", help="replay UDP payloads from a pcap")
    parser.add_argument("--ip", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5500)
    parser.add_argument("--rate", type=float, default=100.0, help="frames per second")
    parser.add_argument("--subcarriers", type=int, default=64)
    parser.add_argument("--quiet-secs", type=float, default=8.0)
    parser.add_argument("--motion-secs", type=float, default=8.0)
    args = parser.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    addr = (args.ip, args.port)
    try:
        if args.synthetic:
            run_synthetic(sock, addr, args.rate, args.subcarriers,
                          args.quiet_secs, args.motion_secs)
        else:
            run_pcap(sock, addr, args.pcap, args.rate)
    except KeyboardInterrupt:
        print("\n[replay] stopped")
    finally:
        sock.close()


if __name__ == "__main__":
    main()
