"""
Fake sensor reading sender for the moist project.

Run via cron every 30 minutes on a Raspberry Pi.
Inserts one fake reading per active sensor into Supabase,
simulating gradual drying, battery drain, and occasional watering events.

Sensors are discovered dynamically from the current_sensors view,
so newly added sensors automatically get readings and removed sensors
are skipped.

State (current moisture/battery per sensor) is persisted to a JSON file
so values drift realistically across cron runs.
"""

import json
import os
import random
import sys
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
STATE_FILE = SCRIPT_DIR / "state.json"

load_dotenv(SCRIPT_DIR / ".env")

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SECRET_KEY = os.environ.get("SUPABASE_SECRET_KEY")

if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
    print("ERROR: SUPABASE_URL and SUPABASE_SECRET_KEY must be set in .env or environment")
    sys.exit(1)

# Defaults for newly discovered sensors
DEFAULT_INIT_MOISTURE = 50.0
DEFAULT_INIT_BATTERY = 90.0

# ---------------------------------------------------------------------------
# Sensor discovery
# ---------------------------------------------------------------------------

def get_active_sensors(supabase) -> list[dict]:
    """Fetch active sensors from the current_sensors view.

    Returns a list of dicts with sensor_id, calibration_air, calibration_water,
    calibration_soil.  The view already filters is_active = true.
    """
    res = supabase.table("current_sensors").select("*").order("sensor_id").execute()
    return res.data

# ---------------------------------------------------------------------------
# State management
# ---------------------------------------------------------------------------

def load_state(active_sensor_ids: list[int]) -> dict:
    """Load persisted sensor state, initialise new sensors, prune removed ones."""
    state = {}
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            state = json.load(f)

    active_keys = {str(sid) for sid in active_sensor_ids}

    # Initialise state for any newly discovered sensors
    for sid in active_sensor_ids:
        key = str(sid)
        if key not in state:
            state[key] = {
                "moisture": DEFAULT_INIT_MOISTURE,
                "battery": DEFAULT_INIT_BATTERY,
            }

    # Prune sensors that are no longer active
    pruned = {k: v for k, v in state.items() if k in active_keys}
    return pruned


def save_state(state: dict) -> None:
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

# ---------------------------------------------------------------------------
# Reading generation
# ---------------------------------------------------------------------------

def next_reading(sensor_id: int, sensor_cfg: dict, state: dict) -> dict:
    """
    Advance the simulation by one 30-minute tick and return a reading dict
    ready for Supabase insertion.
    """
    key = str(sensor_id)
    s = state[key]

    moisture = s["moisture"]
    battery = s["battery"]

    # Gradual drying: lose 0.2-0.8 % per tick (= 0.4-1.6 %/hr)
    moisture -= random.uniform(0.2, 0.8)

    # Add noise (+/-0.3 %)
    moisture += random.uniform(-0.3, 0.3)

    # Occasional watering event (~3 % chance per tick = once per ~17 hours)
    if random.random() < 0.03:
        moisture += random.uniform(30, 45)

    moisture = round(max(5.0, min(100.0, moisture)), 1)

    # Battery drain: ~0.01 % per tick (= 0.5 %/day)
    battery -= random.uniform(0.005, 0.015)
    battery = round(max(5.0, min(100.0, battery)), 0)

    # Compute raw ADC from moisture % (piecewise linear, inverse of 3-point calibration)
    cal_air = sensor_cfg["calibration_air"]
    cal_water = sensor_cfg["calibration_water"]
    cal_soil = sensor_cfg["calibration_soil"]
    if moisture <= 50:
        raw = int(cal_air - (moisture / 50.0) * (cal_air - cal_soil))
    else:
        raw = int(cal_soil - ((moisture - 50) / 50.0) * (cal_soil - cal_water))

    # Persist new state
    s["moisture"] = moisture
    s["battery"] = battery

    return {
        "sensor_id": sensor_id,
        "moisture_raw": raw,
        "moisture_pct": moisture,
        "battery": battery,
    }

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    supabase = create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)

    sensors = get_active_sensors(supabase)
    if not sensors:
        print("No active sensors found. Nothing to do.")
        return

    sensor_map = {s["sensor_id"]: s for s in sensors}
    state = load_state(list(sensor_map.keys()))

    rows = []
    for sensor_id, sensor_cfg in sensor_map.items():
        reading = next_reading(sensor_id, sensor_cfg, state)
        rows.append(reading)

    result = supabase.table("readings").insert(rows).execute()
    print(f"Inserted {len(result.data)} readings:")
    for r in rows:
        print(f"  sensor {r['sensor_id']}: moisture={r['moisture_pct']}%  battery={r['battery']}%  raw={r['moisture_raw']}")

    save_state(state)


if __name__ == "__main__":
    main()
