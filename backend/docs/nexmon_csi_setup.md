# nexmon_csi setup on the Raspberry Pi 5 (BCM43455c0)

This is the **hardware/firmware prerequisite** for live CSI. The Signally CSI
software layer (parser + detector + provider) is already built and testable
without any of this — see "Testing without hardware" at the bottom. This doc is
only needed to feed the pipeline **real** CSI instead of replayed frames.

> Signally consumes CSI as a UDP stream on `127.0.0.1:5500`. Everything below
> exists to make the Pi's onboard Wi-Fi produce that stream.

## Why this is a separate track

nexmon_csi patches the Broadcom Wi-Fi **firmware** and puts the radio into a
CSI-extraction mode via `nexutil`. This is OS/firmware-level work, not Python —
none of it lives in this repo. Our code just reads the resulting UDP frames.

## Topology reminder

The Pi 5 has one onboard Wi-Fi radio (`wlan0`, BCM43455c0) and the Wavlink USB
adapter (`wlan1`). Once CSI capture starts, **both Wi-Fi radios are consumed**:

- `wlan0` → nexmon CSI monitor mode (this doc)
- `wlan1` → probe-request sniffing (existing wifi_probing)

So the Pi must reach the network over **Ethernet** while capturing — it has no
Wi-Fi client interface left.

## One-time install

1. Flash/patch nexmon + nexmon_csi for the Pi 5 / BCM43455c0, following the
   upstream project: <https://github.com/seemoo-lab/nexmon_csi>. This produces a
   patched firmware and the `nexutil` / `makecsiparams` tools.
2. Confirm the tools are on PATH: `which nexutil makecsiparams`.

## Each capture session

Pick the Wi-Fi channel you want to sense on (it must match the channel of the
AP/traffic in the room — CSI is extracted from frames actually on that channel).

```bash
# 1. Build a CSI parameter string for the target channel/bandwidth.
#    Example: channel 36, 80 MHz, first core/antenna.
CSIPARAMS=$(makecsiparams -c 36/80 -C 1 -N 1)

# 2. Put wlan0 up in monitor mode and load the params into the firmware.
sudo ifconfig wlan0 up
sudo nexutil -Iwlan0 -s500 -b -l34 -v"$CSIPARAMS"

# 3. Enable monitor mode framing so CSI frames are emitted.
sudo iw dev wlan0 interface add mon0 type monitor 2>/dev/null || true
sudo ifconfig mon0 up
```

The nexmon_csi firmware emits CSI as UDP to `5500`. Point Signally at it with the
defaults already in `config.py` (`SIGNALLY_CSI_UDP_IP=127.0.0.1`,
`SIGNALLY_CSI_UDP_PORT=5500`).

## Verify frames are actually flowing (the real wall we hit before)

Before touching Signally, confirm the firmware is producing frames:

```bash
sudo tcpdump -i lo -n udp port 5500
```

If you see packets when there's Wi-Fi traffic near the Pi, capture works. **If
you see nothing, the problem is here, not in the Python** — recheck the channel
matches live traffic, `wlan0` is up, and `nexutil` succeeded.

## Point Signally at the live stream

```bash
export SIGNALLY_CSI_REAL_PROVIDER_ENABLED=true
sudo -E ../.venv/bin/python -m uvicorn signally.api.app:app --host 0.0.0.0 --port 8000
```

Then watch `GET /csi/status`:

- `presence_strength: null` → the listener is up but no frames are arriving
  (`tcpdump` above will confirm whether it's a capture problem). Signally
  auto-falls back to the mock provider in this state, so nothing crashes.
- a number → frames are parsed and the detector is running.

## Calibrate the threshold

The detector learns an empty-room baseline automatically, but the sensitivity
factor needs tuning to your space:

1. Leave the room empty ~30 s (this seeds the baseline; `CSI_BASELINE_WARMUP`).
2. Walk in and out, watching `presence_strength` in `/csi/status`.
3. Adjust `SIGNALLY_CSI_BASELINE_FACTOR` (default 3.0) up if it false-triggers,
   down if it misses real motion. Restart with `-E` to apply.

## Testing without hardware

You do **not** need any of the above to develop or demo the software path:

```bash
# terminal 1 - backend with the real listener on
SIGNALLY_CSI_REAL_PROVIDER_ENABLED=true python -m uvicorn signally.api.app:app --port 8000

# terminal 2 - feed synthetic nexmon frames to 127.0.0.1:5500
python scripts/csi_replay.py --synthetic
```

`/csi/status` will flip `presence_detected` true/false as the replay alternates
its QUIET and MOTION phases — exercising the exact same parser + detector that
real frames hit.
```
