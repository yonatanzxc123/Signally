# Nexmon CSI Setup For Signally

Signally treats Nexmon CSI as an external hardware dependency. The Signally backend does not install, build, vendor, or manage the Nexmon CSI project.

Reference project:

https://github.com/seemoo-lab/nexmon_csi

## What Nexmon Provides

Nexmon CSI can extract Channel State Information from supported Broadcom Wi-Fi chips, including the `bcm43455c0` family used by Raspberry Pi 3B+/4B/5 devices. Nexmon emits CSI as UDP packets, commonly to broadcast address `255.255.255.255` on port `5500`.

For `bcm43455c0`, Signally expects CSI samples as interleaved `int16` real/imaginary values after the Nexmon metadata header.

## What Signally Provides

Signally provides the receiving and decision layer:

- UDP listener on `SIGNALLY_CSI_UDP_HOST:SIGNALLY_CSI_UDP_PORT`
- Nexmon packet parser
- CSI amplitude feature extraction
- baseline calibration
- baseline deviation and confidence scoring
- normalized sensing snapshot for correlation
- API endpoints for status and calibration

The correlation engine consumes only normalized sensing data. It does not consume raw CSI arrays.

## Backend Configuration

Useful environment variables:

```bash
SIGNALLY_CSI_REAL_PROVIDER_ENABLED=true
SIGNALLY_CSI_UDP_HOST=0.0.0.0
SIGNALLY_CSI_UDP_PORT=5500
SIGNALLY_CSI_PACKET_STALE_AFTER_SECONDS=3.0
SIGNALLY_CSI_FEATURE_WINDOW_SECONDS=3.0
SIGNALLY_CSI_BASELINE_MIN_PACKETS=5
SIGNALLY_CSI_BASELINE_THRESHOLD_MULTIPLIER=3.0
SIGNALLY_CSI_BASELINE_MIN_THRESHOLD=5.0
```

When `SIGNALLY_CSI_REAL_PROVIDER_ENABLED=false`, the backend uses the clearly labeled mock CSI provider. Mock/fallback CSI is not presented as real Nexmon data.

## Expected Nexmon Runtime Shape

On the Raspberry Pi, Nexmon should be configured separately so CSI UDP packets reach the Signally backend machine on port `5500`.

Traffic is required. CSI is extracted from received Wi-Fi frames, so an idle environment may produce little or no CSI data. For a classroom demo, a phone hotspot can act as a controlled AP/transmitter. In a real deployment, the home router/AP and normal Wi-Fi clients provide traffic.

## API Endpoints

- `GET /csi/status`
- `GET /csi/snapshot`
- `POST /csi/calibration/start`
- `POST /csi/calibration/stop`
- `GET /csi/baseline`
- `DELETE /csi/baseline`

Provider statuses:

- `OK`: packets are arriving, a baseline exists, and confidence/deviation are computed
- `NO_DATA`: no recent Nexmon CSI packets have arrived
- `NO_BASELINE`: packets are arriving, but calibration has not been saved
- `ERROR`: repeated parsing or receiver errors occurred
- `MOCK`: mock CSI provider is active
- `FALLBACK`: mock CSI is being used because real CSI is not ready

## Calibration Flow

1. Start the backend with real CSI enabled.
2. Confirm `/csi/status` shows `NO_BASELINE` rather than `NO_DATA`.
3. Keep the monitored area in the intended baseline state.
4. Call `POST /csi/calibration/start`.
5. Wait several seconds while packets arrive.
6. Call `POST /csi/calibration/stop`.
7. Confirm `/csi/status` changes to `OK`.

If calibration fails with "not enough CSI packets", generate more Wi-Fi traffic and try again.

## Current Scope

This is a proof-of-concept sensing layer. It detects presence/movement by comparing simple CSI amplitude features against a baseline. It does not implement activity recognition, identity recognition, gait analysis, multi-zone sensing, or machine learning.
