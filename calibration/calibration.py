"""
3-point sensor calibration via MQTT.

Run on the Raspberry Pi while an ESP32 (connected to your laptop) publishes
readings every ~1 second to the MQTT broker.

The ESP32 sends JSON like:
    {"timestamp": 1740000000, "moisture": 1234.5, "powerLevel": 2100.0, "powerMode": "USB"}

The "moisture" field is a raw frequency count (charge/discharge cycles in a
10ms window, averaged over 64 samples).  Higher = drier, lower = wetter.

Walks through three conditions:
  1. Air   — sensor held in open air (0% moisture reference)
  2. Water — sensor submerged in water (100% moisture reference)
  3. Soil  — sensor inserted in fresh potting soil (50% moisture reference)

Collects multiple readings for each, takes the median, and prints the
calibration values to enter into the web dashboard.

Usage:
    python calibration.py                           # interactive prompts
    python calibration.py --sensor-id 1             # specify sensor ID
    python calibration.py --topic esp32/sensor2     # custom MQTT topic
    python calibration.py --samples 20              # collect 20 samples per condition
"""

import argparse
import json
import statistics
import sys
import threading

import paho.mqtt.client as mqtt

MQTT_HOST = "localhost"
MQTT_PORT = 1883
DEFAULT_TOPIC = "esp32/test"
DEFAULT_SAMPLES = 10


def collect_readings(
    host: str,
    port: int,
    topic: str,
    num_samples: int,
) -> list[float]:
    """Subscribe to an MQTT topic and collect num_samples moisture values."""
    readings: list[float] = []
    done = threading.Event()

    def on_connect(client, userdata, flags, rc, properties=None):
        if rc != 0:
            print(f"  MQTT connection failed (rc={rc}). Is Mosquitto running?")
            done.set()
            return
        client.subscribe(topic)

    def on_message(client, userdata, msg):
        try:
            payload = json.loads(msg.payload)
            moisture = float(payload["moisture"])
        except (json.JSONDecodeError, KeyError, ValueError):
            return

        readings.append(moisture)
        power_info = ""
        if "powerLevel" in payload:
            power_info = f"  power={payload['powerLevel']:.0f} ({payload.get('powerMode', '?')})"
        print(f"  [{len(readings)}/{num_samples}] moisture = {moisture:.1f}{power_info}")
        if len(readings) >= num_samples:
            done.set()

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(host, port)
    except ConnectionRefusedError:
        print(f"  ERROR: Cannot connect to MQTT broker at {host}:{port}")
        print("  Is Mosquitto running? Try: sudo systemctl start mosquitto")
        sys.exit(1)

    client.loop_start()

    timeout = num_samples * 10
    done.wait(timeout=timeout)
    client.loop_stop()
    client.disconnect()

    if not readings:
        print("  No readings received. Is the ESP32 publishing to this topic?")
        sys.exit(1)

    return readings


def median_reading(readings: list[float]) -> float:
    return round(statistics.median(readings), 1)


def raw_to_pct(raw: float, cal_air: float, cal_soil: float, cal_water: float) -> float:
    """Convert a raw frequency count to moisture % using piecewise linear interpolation.

    Higher raw value = drier (more charge cycles fit in the measurement window).
    """
    if raw >= cal_air:
        return 0.0
    elif raw >= cal_soil:
        return 50.0 * (cal_air - raw) / (cal_air - cal_soil)
    elif raw >= cal_water:
        return 50.0 + 50.0 * (cal_soil - raw) / (cal_soil - cal_water)
    else:
        return 100.0


def main():
    parser = argparse.ArgumentParser(description="Calibrate a soil moisture sensor via MQTT")
    parser.add_argument("--sensor-id", type=int, help="Sensor ID (for display only, used in output instructions)")
    parser.add_argument("--topic", default=DEFAULT_TOPIC, help=f"MQTT topic to subscribe to (default: {DEFAULT_TOPIC})")
    parser.add_argument("--samples", type=int, default=DEFAULT_SAMPLES, help=f"Samples per condition (default: {DEFAULT_SAMPLES})")
    parser.add_argument("--host", default=MQTT_HOST, help=f"MQTT broker host (default: {MQTT_HOST})")
    parser.add_argument("--port", type=int, default=MQTT_PORT, help=f"MQTT broker port (default: {MQTT_PORT})")
    args = parser.parse_args()

    sensor_id = args.sensor_id
    if sensor_id is None:
        try:
            sensor_id = int(input("Sensor ID to calibrate: "))
        except (ValueError, EOFError):
            print("Invalid sensor ID.")
            sys.exit(1)

    topic = args.topic
    n = args.samples

    print()
    print(f"=== Calibrating sensor #{sensor_id} ===")
    print(f"Listening on: {topic}")
    print(f"Samples per condition: {n}")
    print()

    # --- Step 1: Air ---
    print("STEP 1/3 — AIR")
    print("Hold the sensor in open air (not touching anything).")
    input("Press Enter when ready...")
    print(f"  Collecting {n} readings...")
    air_readings = collect_readings(args.host, args.port, topic, n)
    cal_air = median_reading(air_readings)
    print(f"  -> Air median: {cal_air}")
    print()

    # --- Step 2: Water ---
    print("STEP 2/3 — WATER")
    print("Submerge the sensor in water (up to the marked line).")
    input("Press Enter when ready...")
    print(f"  Collecting {n} readings...")
    water_readings = collect_readings(args.host, args.port, topic, n)
    cal_water = median_reading(water_readings)
    print(f"  -> Water median: {cal_water}")
    print()

    # --- Step 3: Soil ---
    print("STEP 3/3 — SOIL")
    print("Insert the sensor into fresh potting soil (straight from the bag).")
    input("Press Enter when ready...")
    print(f"  Collecting {n} readings...")
    soil_readings = collect_readings(args.host, args.port, topic, n)
    cal_soil = median_reading(soil_readings)
    print(f"  -> Soil median: {cal_soil}")
    print()

    # --- Sanity checks ---
    ok = True
    if not (cal_air > cal_soil > cal_water):
        print("WARNING: Expected air > soil > water (higher count = drier).")
        print(f"  Got: air={cal_air}, soil={cal_soil}, water={cal_water}")
        print("  The sensor may not be working correctly, or conditions were wrong.")
        print()
        ok = False

    # --- Summary ---
    print("=" * 50)
    print("CALIBRATION RESULTS")
    print("=" * 50)
    print(f"  Sensor:      #{sensor_id}")
    print(f"  Air   (0%):  {cal_air}")
    print(f"  Soil  (50%): {cal_soil}")
    print(f"  Water (100%):{cal_water}")
    print()

    if ok:
        print("Mapping check (piecewise linear):")
        for label, raw in [("Air", cal_air), ("Soil", cal_soil), ("Water", cal_water)]:
            pct = raw_to_pct(raw, cal_air, cal_soil, cal_water)
            print(f"  {label:6s} raw={raw:8.1f} -> {pct:5.1f}%")
        print()

    print("Enter these values in the web dashboard:")
    print(f"  Manage Sensors -> Sensor #{sensor_id} -> Edit")
    print(f"    Cal. air:   {cal_air}")
    print(f"    Cal. water: {cal_water}")
    print(f"    Cal. soil:  {cal_soil}")
    print()


if __name__ == "__main__":
    main()
