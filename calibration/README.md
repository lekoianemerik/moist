# Sensor Calibration

Interactive script that runs on the Raspberry Pi to calibrate a soil moisture sensor via MQTT.

## Prerequisites

- **Mosquitto** running on the Raspberry Pi (`sudo systemctl start mosquitto`)
- **ESP32** connected to your laptop, flashed with the sensor sketch set to fast output (`DEEP_SLEEP_MILISECONDS = 500` or `1000`), publishing to `esp32/test`
- The ESP32 sends JSON every ~1 second: `{"timestamp": ..., "moisture": 1234.5, "powerLevel": ..., "powerMode": "..."}`
- Both ESP32 and Raspberry Pi on the same Wi-Fi network

## Setup

```bash
cd calibration
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

```bash
# Interactive — prompts for sensor ID
python calibration.py

# Specify sensor ID and custom topic
python calibration.py --sensor-id 1 --topic esp32/test

# Collect more samples per condition (default: 10)
python calibration.py --sensor-id 1 --samples 20
```

The script walks through three conditions:

1. **Air** — hold sensor in open air (0% reference)
2. **Water** — submerge sensor in water up to the line (100% reference)
3. **Soil** — insert sensor in fresh potting soil from the bag (50% reference)

For each step, press Enter when the condition is set up. The script collects readings, computes the median, and at the end prints the three values to enter into the web dashboard (Manage Sensors page).

## How calibration works

The ESP32 counts how many charge/discharge cycles fit in a 10ms window (averaged over 64 samples). Higher count = drier (lower capacitance), lower count = wetter (higher capacitance).

The three reference values define a piecewise linear curve:

```
frequency count (high=dry)
  |
  |  air ────────── 0%
  |       \
  |        \  segment 1 (different slope)
  |         \
  |  soil ───────── 50%
  |           \
  |            \ segment 2 (different slope)
  |             \
  |  water ──────── 100%
  |
```

This accounts for the sensor's non-linear response -- the count-to-moisture relationship has a different slope in the dry range vs the wet range.
