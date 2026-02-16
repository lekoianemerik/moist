"""
Fake sensor reading sender for the moist project.

Run via cron every 30 minutes on a Raspberry Pi.
Inserts one fake reading per sensor into Supabase,
simulating gradual drying, battery drain, and occasional watering events.

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

# Sensor definitions matching supabase/schema.sql seed data
SENSORS = {
    1: {"name": "Kitchen Basil",  "cal_dry": 3200, "cal_wet": 1400, "init_moisture": 55, "init_battery": 87},
    2: {"name": "Bathroom Fern",  "cal_dry": 3100, "cal_wet": 1350, "init_moisture": 65, "init_battery": 63},
    3: {"name": "Desk Succulent", "cal_dry": 3250, "cal_wet": 1450, "init_moisture": 20, "init_battery": 94},
    4: {"name": "Balcony Tomato", "cal_dry": 3150, "cal_wet": 1380, "init_moisture": 48, "init_battery": 41},
}

# ---------------------------------------------------------------------------
# State management
# ---------------------------------------------------------------------------

def load_state() -> dict:
    """Load persisted sensor state, or initialise from defaults."""
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)

    # First run — seed from SENSORS defaults
    state = {}
    for sid, cfg in SENSORS.items():
        state[str(sid)] = {
            "moisture": cfg["init_moisture"],
            "battery": cfg["init_battery"],
        }
    return state


def save_state(state: dict) -> None:
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

# ---------------------------------------------------------------------------
# Reading generation
# ---------------------------------------------------------------------------

def next_reading(sensor_id: int, state: dict) -> dict:
    """
    Advance the simulation by one 30-minute tick and return a reading dict
    ready for Supabase insertion.
    """
    key = str(sensor_id)
    cfg = SENSORS[sensor_id]
    s = state[key]

    moisture = s["moisture"]
    battery = s["battery"]

    # Gradual drying: lose 0.2–0.8 % per tick (≈ 0.4–1.6 %/hr)
    moisture -= random.uniform(0.2, 0.8)

    # Add noise (±0.3 %)
    moisture += random.uniform(-0.3, 0.3)

    # Occasional watering event (~3 % chance per tick ≈ once per ~17 hours)
    if random.random() < 0.03:
        moisture += random.uniform(30, 45)

    moisture = round(max(5.0, min(100.0, moisture)), 1)

    # Battery drain: ~0.01 % per tick (≈ 0.5 %/day)
    battery -= random.uniform(0.005, 0.015)
    battery = round(max(5.0, min(100.0, battery)), 0)

    # Compute raw ADC from moisture %
    cal_dry = cfg["cal_dry"]
    cal_wet = cfg["cal_wet"]
    raw = int(cal_dry - (moisture / 100.0) * (cal_dry - cal_wet))

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
    state = load_state()
    supabase = create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)

    rows = []
    for sensor_id in SENSORS:
        reading = next_reading(sensor_id, state)
        rows.append(reading)

    # Batch insert all 4 readings at once
    result = supabase.table("readings").insert(rows).execute()
    print(f"Inserted {len(result.data)} readings:")
    for r in rows:
        print(f"  sensor {r['sensor_id']}: moisture={r['moisture_pct']}%  battery={r['battery']}%  raw={r['moisture_raw']}")

    save_state(state)


if __name__ == "__main__":
    main()
