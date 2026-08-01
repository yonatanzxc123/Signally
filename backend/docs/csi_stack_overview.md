# Signally CSI — Stack, Tools & Code Overview

How Wi-Fi **Channel State Information (CSI)** presence detection is meant to work in
Signally: what generates CSI on the Raspberry Pi, what tools configure and test it,
and which code in our project consumes it. Also captures the verified Pi 5 status.

CSI is the fine-grained channel-response data a Wi-Fi radio computes for every frame
it receives. A person moving in the room perturbs the radio multipath, so CSI changes
over time — that's what lets us detect presence/motion without cameras.

---

## Part 1 — The nexmon stack on the Pi (all C)

The Pi's onboard Wi-Fi chip (Broadcom BCM43455c0) doesn't expose CSI normally. nexmon
patches the chip firmware to make it do so.

| Component | What it is | Language |
|---|---|---|
| **nexmon** | A *framework* for patching Broadcom Wi-Fi **firmware** — decompiles the chip firmware, injects C code, recompiles it. | C + ARM asm |
| **nexmon_csi** | A *patch* built with nexmon. Hooks the firmware's receive path to compute CSI per frame and emit it. | C + ucode asm |
| **modified `brcmfmac`** | nexmon's fork of the Linux Wi-Fi **driver** — required so the OS can put the chip in monitor mode and receive the CSI stream. | C (kernel module) |
| **`nexutil`** | CLI tool that talks to the patched firmware (ioctl / nl80211 vendor command) — sets monitor mode, loads the CSI config. | C |
| **`makecsiparams`** | Generates the base64 config string (channel, bandwidth, frame filter) fed to `nexutil -s500`. | C |

**In short:** the *framework* is nexmon; the *CSI logic* is the firmware patch + driver;
the *control tools* are `nexutil` + `makecsiparams`.

---

## Part 2 — How CSI is captured & tested

1. **Configure**
   ```bash
   CSIPARAMS=$(makecsiparams -c 8/20 -C 1 -N 1)      # channel 8, 20 MHz
   nexutil -Iwlan0 -s500 -b -l34 -v"$CSIPARAMS"      # arm CSI collection
   # + enable monitor mode (nexutil -m / mon0 interface, chip-dependent)
   ```
2. **Capture** — CSI is emitted as **UDP frames**:
   ```bash
   tcpdump -i wlan0 dst port 5500
   ```
   Each frame: `src 10.10.10.10 → 255.255.255.255:5500`, one per received Wi-Fi frame.
   Payload = a small header + interleaved `int16` real/imaginary pairs (the channel data),
   64 complex values for 20 MHz.
3. **Parse / analyze**
   - Official: **MATLAB** (`utils/matlab/csireader.m`).
   - Python: **`nexcsi`** or **CSIKit** — turn raw bytes → complex CSI → amplitude/phase.

---

## Part 3 — Our project's CSI code (Python, in `backend/`)

| File | Role | Status |
|---|---|---|
| `signally/sensors/csi_frame.py` | **Parser** — raw bytes → per-subcarrier amplitudes (our own, nexcsi-style). | Written for an assumed format; needs the real one |
| `signally/sensors/csi_detector.py` | **Detection brain** — Hampel outlier filter → temporal variance vs. adaptive empty-room baseline → `(present?, confidence)`. RuView-inspired classical DSP. | ✅ Done & proven on synthetic data |
| `signally/sensors/csi_provider.py` | **Transport** — UDP socket bound on all local interfaces so broadcast CSI frames from `wlan0` can be consumed. | ✅ Ready |
| `scripts/csi_replay.py` | Feeds synthetic frames for hardware-free testing. | ✅ Works |
| `signally/config.py` | CSI tunables (channel, window, thresholds). | ✅ |
| `tests/test_csi_frame.py`, `tests/test_csi_detector.py` | Unit tests. | ✅ Pass |

**Libraries our side uses:** `numpy` (DSP math), `scapy` (frame sniffing — already used for
Wi-Fi probing), `nexcsi` (validation), FastAPI (serves `/csi/status`).

---

## Part 4 — How it all connects

```
nexmon firmware (C, on the Wi-Fi chip)
   -> CSI UDP frames on wlan0
      -> scapy sniff            (csi_provider.py)
         -> parse bytes         (csi_frame.py)
            -> detect motion    (csi_detector.py  <- RuView logic)
               -> /csi/status + correlation engine (FastAPI)
                  -> React Native app
```

Everything from "scapy sniff" rightward is our code, and the **detector (the RuView part)
is built and tested** on synthetic data.

---

## Current status

Real CSI was verified on the Raspberry Pi 5 with kernel 6.12.87 on 2026-08-01.
The current upstream `Makefile.rpi` path uses vendor commands and does **not** need a
modified `brcmfmac` driver. The patched firmware is selected with
`update-alternatives`; `signally-csi.service` arms channel 8/20 MHz at boot.

Verification showed `nexutil -m` reporting monitor mode 1, `nexutil -k` reporting
channel 8, and real 274-byte UDP/5500 CSI datagrams on `wlan0`. Signally's parser now
uses the current 2-byte magic / 18-byte header format and its receiver binds to
`0.0.0.0:5500`.
