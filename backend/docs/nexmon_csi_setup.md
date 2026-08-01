# nexmon_csi setup on the Raspberry Pi 5 (BCM43455c0)

**The install/build is terminal-only over SSH** (the Pi is headless). Testing
afterwards can be done however you like — Swagger from your PC's browser at
`http://<pi-ip>:8000/docs`, or `curl` on the Pi itself; both are shown below.

This is the **hardware/firmware prerequisite** for live CSI. The Signally CSI
software layer (parser + detector + provider) is already built and testable
without any of this — see "Testing without hardware" at the bottom. This doc is
only needed to feed the pipeline **real** CSI instead of replayed frames.

> Signally consumes CSI as a UDP stream on `0.0.0.0:5500`. Everything below
> exists to make the Pi's onboard Wi-Fi produce that stream.

## Conventions used here

- All paths assume you are in the **`backend/` directory** of the repo on the Pi
  (the same place you launch uvicorn from). The virtualenv is one level up, so the
  interpreter is `../.venv/bin/python`.
- You need **two terminals at once** several times below. Over SSH the cleanest
  way is `tmux` (survives disconnects too):
  ```bash
  sudo apt-get install -y tmux    # once
  tmux                            # start; Ctrl-b " splits, Ctrl-b o switches panes
  ```
  Or just open a second SSH session to the Pi. `screen` works as well.
- Install `jq` once for readable JSON from curl (optional but nice):
  ```bash
  sudo apt-get install -y jq
  ```

## Why this is a separate track

nexmon_csi patches the Broadcom Wi-Fi **firmware** and puts the radio into a
CSI-extraction mode via `nexutil`. This is OS/firmware-level work, not Python —
none of it lives in this repo. Our code just reads the resulting UDP frames.

## Topology reminder

The Pi 5 has one onboard Wi-Fi radio (`wlan0`, BCM43455c0) and the Wavlink USB
adapter (`wlan1`). Once CSI capture starts, **both Wi-Fi radios are consumed**:

- `wlan0` → nexmon CSI monitor mode (this doc)
- `wlan1` → probe-request sniffing (existing wifi_probing)

So the Pi must reach the network — and your SSH session — over **Ethernet** while
capturing, since it has no Wi-Fi client interface left. SSH in over the Ethernet
IP before you touch `wlan0`, or you'll lock yourself out.

## One-time install (build nexmon_csi from source — Pi 5 / kernel 6.x)

> **This procedure follows nexmon_csi
> [discussion #395](https://github.com/seemoo-lab/nexmon_csi/discussions/395),**
> the authoritative source for Pi 5 + recent kernels. The maintainer confirmed
> **kernel 6.12 works** there. It is *not* the vanilla README flow — the Pi 5
> needs a 4k-page kernel, armhf cross-compile libs, Python 2.7, and a separate
> `Makefile.rpi`. If any command drifts from what you see on your OS image,
> #395 is the canonical reference. Budget ~60 min.

Everything runs over SSH. The nexmon build is smoothest as a normal user with
`sudo` where shown (the `-E`/`setcap` details below matter — don't "sudo su" the
whole thing, since some steps rely on your user environment).

### Step 0 — pre-flight & firmware backup

Confirm the chip is **bcm43455c0** and find which firmware file the driver
actually loads (the Pi 5 uses a *model-specific* file, not just the generic one):

```bash
cat /proc/device-tree/model ; echo          # -> "Raspberry Pi 5 Model B ..."
uname -r                                     # your kernel (6.12.x is fine)
uname -m                                     # aarch64
sudo dmesg | grep -i brcmfmac | grep -i firmware   # note the version + filename
```

Back up **both** the generic and the Pi-5 model-specific firmware so you can
always restore stock Wi-Fi:

```bash
cd /lib/firmware/brcm/
sudo cp brcmfmac43455-sdio.bin brcmfmac43455-sdio.bin.orig
sudo cp "brcmfmac43455-sdio.raspberrypi,5-model-b.bin" \
        "brcmfmac43455-sdio.raspberrypi,5-model-b.bin.orig"
```

### Step 1 — switch to the 4k-page kernel

The Pi 5 boots a 16k-page kernel by default; nexmon needs the 4k-page `kernel8`.
(`| sudo tee -a` — a bare `sudo echo >>` would write as your user and fail.)

```bash
echo 'kernel=kernel8.img' | sudo tee -a /boot/firmware/config.txt
sudo reboot
# after reconnecting, confirm the page size dropped to 4096:
getconf PAGESIZE      # -> 4096
```

### Step 2 — dependencies

```bash
sudo apt update && sudo apt full-upgrade -y
sudo apt install -y git libgmp3-dev gawk qpdf bison flex make autoconf libtool \
     texinfo xxd libnl-3-dev libnl-genl-3-dev bc libssl-dev tcpdump
```

### Step 3 — armhf cross-compile libraries (needed on aarch64)

```bash
sudo dpkg --add-architecture armhf
sudo apt update
sudo apt install -y libc6:armhf libisl23:armhf libmpfr6:armhf libmpc3:armhf libstdc++6:armhf
sudo ln -s /usr/lib/arm-linux-gnueabihf/libisl.so.23 /usr/lib/arm-linux-gnueabihf/libisl.so.10
sudo ln -s /usr/lib/arm-linux-gnueabihf/libmpfr.so.6 /usr/lib/arm-linux-gnueabihf/libmpfr.so.4
```

### Step 4 — Python 2.7 (nexmon's build tools need it)

```bash
sudo cp /etc/apt/sources.list /tmp/
echo 'deb http://archive.debian.org/debian/ stretch contrib main non-free' | sudo tee -a /etc/apt/sources.list
sudo apt update
sudo apt install -y python2.7
sudo mv /tmp/sources.list /etc/apt/     # restore your original sources
sudo apt update
```

### Step 5 — build the nexmon base

```bash
cd ~
git clone --depth=1 https://github.com/seemoo-lab/nexmon.git
cd nexmon
source setup_env.sh
sed -i '1 s/$/2.7/' $NEXMON_ROOT/buildtools/b43-v3/debug/b43-beautifier
make
```

### Step 6 — build & install nexutil

```bash
cd $NEXMON_ROOT/utilities/nexutil
sudo -E make install USE_VENDOR_CMD=1
sudo setcap cap_net_admin+ep /usr/bin/nexutil   # lets nexutil run without sudo later
```

### Step 7 — clone the CSI patch

```bash
cd $NEXMON_ROOT/patches/bcm43455c0/7_45_189/
git clone https://github.com/seemoo-lab/nexmon_csi.git
cd nexmon_csi
```

### Step 8 — build & load the patched firmware (Makefile.rpi)

```bash
make -f Makefile.rpi install-firmware   # build patch + write firmware
make -f Makefile.rpi unmanage           # take wlan0 away from NetworkManager
make -f Makefile.rpi reload-full        # reload the driver with the patch
```

> If the patch doesn't seem to take effect, it's usually the model-specific
> firmware file shadowing the generic one. Copy the patched firmware over the
> Pi-5 name, then reload:
> ```bash
> sudo cp /lib/firmware/brcm/brcmfmac43455-sdio.bin \
>         "/lib/firmware/brcm/brcmfmac43455-sdio.raspberrypi,5-model-b.bin"
> make -f Makefile.rpi reload-full
> ```

### Step 9 — confirm tools + Python dep

```bash
which nexutil makecsiparams               # both should resolve
../.venv/bin/python -m pip install numpy  # from backend/: CSI detector needs numpy
```

### Restoring stock Wi-Fi later

The patch lives in the running firmware; a reboot reverts it. If you overwrote the
firmware files, restore your backups and remove the 4k-page override:

```bash
cd /lib/firmware/brcm/
sudo cp brcmfmac43455-sdio.bin.orig brcmfmac43455-sdio.bin
sudo cp "brcmfmac43455-sdio.raspberrypi,5-model-b.bin.orig" \
        "brcmfmac43455-sdio.raspberrypi,5-model-b.bin"
# optionally remove the 'kernel=kernel8.img' line you added to config.txt
sudo reboot
```

## Each capture session

Pick the Wi-Fi channel you want to sense on — it must match the channel of the
AP/traffic in the room, since CSI is extracted from frames actually on that
channel. Find your AP's channel from the terminal with `iw dev` or `iwlist`.

```bash
# 1. Build a CSI parameter string for the target channel/bandwidth.
#    Example: channel 36, 80 MHz, first core/antenna. Base64 goes into nexutil -v.
CSIPARAMS=$(makecsiparams -c 36/80 -C 1 -N 1)

# 2. Load the params into the firmware and turn on CSI collection + monitor mode.
nexutil -Iwlan0 -s500 -b -l34 -v"$CSIPARAMS"
nexutil -Iwlan0 -m1          # monitor mode on
```

The nexmon_csi firmware now emits CSI as UDP frames (dst port 5500) on `wlan0`.

## Verify frames are actually flowing (the real wall we hit before)

Before touching Signally, confirm the firmware is producing frames — note the
interface is **`wlan0`**, not loopback:

```bash
sudo tcpdump -i wlan0 dst port 5500
```

If you see packets when there's Wi-Fi traffic near the Pi, capture works. **If
you see nothing, the problem is here, not in the Python** — recheck the channel
matches live traffic and `nexutil` succeeded. Stop tcpdump with `Ctrl-c`.

> **Integration note (likely first snag):** the CSI frames arrive on `wlan0`, but
> Signally's provider binds a UDP socket on `0.0.0.0:5500` by default. If
> `tcpdump` shows frames but `/csi/status` stays `null`, the socket isn't seeing
> them because they're on `wlan0`, not loopback. Set
> Keep `SIGNALLY_CSI_UDP_IP=0.0.0.0` so the socket listens on all interfaces, and make
> sure the frames' destination IP is the Pi (or broadcast). This is the one place
> the software↔firmware handoff may need a tweak once real capture is live.

## Point Signally at the live stream

In a terminal (from `backend/`):

```bash
export SIGNALLY_CSI_REAL_PROVIDER_ENABLED=true
sudo -E ../.venv/bin/python -m uvicorn signally.api.app:app --host 0.0.0.0 --port 8000
```

`sudo -E` preserves the exported env var through sudo; sudo is needed because the
full backend also drives the probing/ARP radios. Leave this running.

Check status either way:

- **Swagger from your PC:** open `http://<pi-ip>:8000/docs`, expand **GET
  `/csi/status`** → *Try it out* → *Execute*.
- **curl on the Pi** (second terminal; localhost = the Pi itself):
  ```bash
  curl -s localhost:8000/csi/status | jq       # drop "| jq" if not installed
  ```

Interpreting the result:

- `"presence_strength": null` → the listener is up but no frames are arriving
  (the `tcpdump` step confirms whether it's a capture problem). Signally
  auto-falls back to the mock provider in this state, so nothing crashes.
- a number → frames are parsed and the detector is running.

## Calibrate the threshold (terminal-only)

The detector learns an empty-room baseline automatically, but the sensitivity
factor needs tuning to your space. Watch the live value with `watch`:

```bash
# refreshes twice a second; leave it running while you move around
watch -n 0.5 "curl -s localhost:8000/csi/status | jq"
```

1. Leave the room empty ~30 s (this seeds the baseline; `CSI_BASELINE_WARMUP`).
   Note the resting `presence_strength`.
2. Walk in and out. Watch `presence_detected` flip to `true` and
   `presence_strength` rise while you move.
3. Adjust `SIGNALLY_CSI_BASELINE_FACTOR` (default 3.0): raise it if it
   false-triggers on an empty room, lower it if it misses real motion. Stop the
   backend (`Ctrl-c`), re-`export` the new value, restart with `sudo -E`.

## Testing without hardware (headless)

You do **not** need any nexmon setup to exercise the full software path — a
synthetic frame generator stands in for the firmware. Two terminals (use `tmux`
or two SSH sessions), both from `backend/`:

```bash
# terminal 1 - backend with the real listener on (no sudo needed: this only
# binds UDP 5500, and CSI needs no raw-socket privileges)
SIGNALLY_CSI_REAL_PROVIDER_ENABLED=true \
SIGNALLY_AUTO_START_MONITORING=false \
SIGNALLY_AUTO_START_WIFI_PROBING=false \
../.venv/bin/python -m uvicorn signally.api.app:app --host 0.0.0.0 --port 8000
```

```bash
# terminal 2 - feed synthetic nexmon frames to 127.0.0.1:5500
../.venv/bin/python scripts/csi_replay.py --synthetic
```

Then, in a third terminal (or a tmux pane), poll status while the replay prints
its alternating `phase = QUIET` / `phase = MOTION`:

```bash
watch -n 0.5 "curl -s localhost:8000/csi/status | jq"
```

`presence_detected` will flip `true`/`false` in step with the replay's MOTION and
QUIET phases — exercising the exact same parser + detector that real frames hit.
Stop each terminal with `Ctrl-c`.
