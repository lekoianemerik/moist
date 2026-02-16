# 🌱 Soil Humidity Monitor — Project Overview

**Status:** Web dashboard wired to Supabase, ready for Railway deploy. Fake sensor cron job ready for Raspberry Pi. Hardware on order.
**Location:** Ireland
**Last updated:** February 2026

---

## 1. Idea Overview

We're building an end-to-end plant monitoring system from scratch. A capacitive soil moisture sensor in each plant pot feeds an analog signal to a battery-powered ESP32 microcontroller, which wakes every 15–30 minutes, takes a reading, publishes it over Wi-Fi via MQTT, then goes back to deep sleep. A Raspberry Pi on the local network runs Mosquitto (MQTT broker) and a small Python service that processes incoming readings and pushes them to a cloud Postgres database (Supabase). A Python web app (FastAPI + HTMX) on Railway provides a login-protected dashboard where you can see each plant's current moisture level, historical trends, and a prediction of when it will next need watering.

```
┌──────────────┐    analog    ┌───────────┐    Wi-Fi/MQTT    ┌──────────────┐
│  Capacitive  │───────────▶  │   ESP32   │────────────────▶ │ Raspberry Pi │
│ Soil Sensor  │              │ (battery) │                  │  Mosquitto   │
└──────────────┘              └───────────┘                  │  + Python    │
                                                             └──────┬───────┘
                                                                    │ HTTPS
                                                                    ▼
                                                             ┌──────────────┐
                                                             │   Supabase   │
                                                             │  (Postgres)  │
                                                             └──────┬───────┘
                                                                    │ REST API
                                                                    ▼
                                                             ┌──────────────┐
                                                             │   FastAPI    │
                                                             │  on Railway  │
                                                             └──────────────┘
```

**Core features:**

- Per-plant moisture % with configurable thresholds
- 7-day sparkline history per sensor (server-rendered SVG)
- Watering prediction based on rolling average moisture decay rate (planned)
- Battery level monitoring per sensor node
- Automatic watering event detection (sudden moisture spike)
- Login-protected dashboard (Supabase Auth, asymmetric JWT via JWKS)
- Future: Telegram/email alerts when a plant drops below threshold

---

## 2. Hardware We Need

### Bill of Materials (4-plant setup)

| # | Component | Qty | Purpose | Est. Cost |
|---|-----------|-----|---------|-----------|
| 1 | **ESP32 DevKitC** | 4 | Microcontroller per sensor node. Wi-Fi, ADC, deep sleep (~10µA). | €16–40 |
| 2 | **Capacitive Soil Moisture Sensor v1.2** | 6 | Measures soil dielectric constant → moisture. Buy spares — QC varies. | €6–24 |
| 3 | **18650 Li-ion Battery (3000mAh)** | 4 | Powers each ESP32 node. Samsung 30Q or LG HG2 recommended. | €20–28 |
| 4 | **18650 Battery Holder** | 4 | Connects battery to ESP32. Single-cell, with wire leads. | €2–5 |
| 5 | **TP4056 USB Charge Module** | 4 | Charges 18650 via USB. Get the version with protection IC (2 chips). | €3–8 |
| 6 | **18650 Charger (Nitecore i2 or similar)** | 1 | Standalone charger for topping up batteries. | €15–18 |
| 7 | **Raspberry Pi Zero 2 W** | 1 | Local hub. Runs Mosquitto + Python ingest service. | €17 |
| 8 | **MicroSD Card (16GB+)** | 1 | OS storage for the Pi. | €8 |
| 9 | **Breadboard + Jumper Wires** | 1 set | Prototyping before permanent soldering. | €5–8 |
| 10 | **Micro-USB Cable** | 1 | Programming ESP32 boards. You probably own one already. | €0 |

**Estimated total: €72–156** depending on sourcing (AliExpress vs Irish/EU shops).

### Wiring Per Sensor Node

```
ESP32 GPIO 34 (ADC) ◄──── AOUT (Sensor)
ESP32 3.3V           ◄──── VCC  (Sensor)
ESP32 GND            ◄──── GND  (Sensor)

18650 (+) ──▶ TP4056 B+ ──▶ ESP32 VIN (or 3.3V via regulator)
18650 (−) ──▶ TP4056 B− ──▶ ESP32 GND
```

**Important notes:**

- Use GPIO 34, 35, 36, or 39 on the ESP32 for analog reads — these are input-only ADC pins and are the most reliable.
- The capacitive sensor outputs 0–3.0V analog, which maps nicely to the ESP32's 0–3.3V ADC range.
- Power the sensor from a GPIO pin (not VCC) so you can cut power between readings to save battery.

---

## 3. Path to Testing: Sensor → Cloud

This is the full data pipeline, broken into testable stages. Each stage can be built and verified independently.

### Stage 1 — Sensor → ESP32 (hardware required)

Flash the ESP32 with Arduino IDE or PlatformIO. Read the capacitive sensor's analog output and print over serial.

```cpp
// Minimal test sketch
const int SENSOR_PIN = 34;
const int SENSOR_POWER = 25;  // power sensor from GPIO to save battery

void setup() {
  Serial.begin(115200);
  pinMode(SENSOR_POWER, OUTPUT);
}

void loop() {
  digitalWrite(SENSOR_POWER, HIGH);
  delay(100);  // let sensor stabilise
  int raw = analogRead(SENSOR_PIN);
  digitalWrite(SENSOR_POWER, LOW);

  float moisture = map(raw, 3200, 1400, 0, 100);  // calibrate these values
  moisture = constrain(moisture, 0, 100);

  Serial.printf("Raw: %d | Moisture: %.1f%%\n", raw, moisture);
  delay(5000);
}
```

**Calibration:**

1. Record the raw ADC value with the sensor in air → this is your 0% (dry) reference.
2. Insert sensor into a glass of water (up to the line) → this is your 100% (saturated) reference.
3. Replace the `3200` and `1400` magic numbers above with your actual values.

### Stage 2 — ESP32 → MQTT → Raspberry Pi (hardware required)

Add Wi-Fi and MQTT to the ESP32 sketch. The ESP32 publishes a JSON payload to a topic like `home/plants/{sensor_id}/moisture`.

```cpp
// Pseudo-code for the full loop
void loop() {
  wakeFromDeepSleep();
  connectWiFi();
  readSensor();
  publishMQTT("home/plants/1/moisture", "{\"moisture\": 52.3, \"battery\": 87, \"raw\": 1842}");
  disconnectWiFi();
  enterDeepSleep(30 * 60);  // 30 minutes
}
```

**MQTT topic structure:**

```
home/plants/1/moisture  →  {"moisture": 52.3, "battery": 87, "raw": 1842}
home/plants/2/moisture  →  {"moisture": 38.1, "battery": 63, "raw": 2104}
...
```

### Stage 3 — Raspberry Pi → Supabase (DONE — fake cron)

**Before hardware arrives**, a simpler approach skips MQTT entirely: a cron job on the Raspberry Pi runs `fake_cron/send_reading.py` every 30 minutes, generating fake readings and inserting them directly into Supabase. This validates the full cloud pipeline (Pi → Supabase → dashboard) without needing Mosquitto or real sensors.

See `fake_cron/README.md` for setup and crontab instructions.

**When hardware arrives**, this will be replaced by the real MQTT ingest pipeline:

```python
# ingest.py — runs on the Raspberry Pi (future, replaces fake_cron)
import json, os
import paho.mqtt.client as mqtt
from supabase import create_client

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

def on_message(client, userdata, msg):
    sensor_id = int(msg.topic.split("/")[2])
    data = json.loads(msg.payload)
    supabase.table("readings").insert({
        "sensor_id": sensor_id,
        "moisture_raw": data["raw"],
        "moisture_pct": data["moisture"],
        "battery": data.get("battery"),
    }).execute()

client = mqtt.Client()
client.on_message = on_message
client.connect("localhost", 1883)
client.subscribe("home/plants/+/moisture")
client.loop_forever()
```

### Stage 4 — Supabase → FastAPI Dashboard (DONE)

The dashboard queries Supabase for the latest reading per plant and 7-day history. See `web/db.py` for the query implementation and [architecture.md](architecture.md) for the full data flow.

---

## 4. MQTT Testing (Faking Pub/Sub)

**You can test the entire pipeline right now on your laptop — no hardware needed.**

### Step 1 — Install Mosquitto locally

```bash
# macOS
brew install mosquitto
brew services start mosquitto

# Ubuntu / Debian / Raspberry Pi OS
sudo apt install mosquitto mosquitto-clients
sudo systemctl start mosquitto

# Verify it's running
mosquitto_sub -t "test" &
mosquitto_pub -t "test" -m "hello"
# You should see "hello" printed
```

### Step 2 — Fake sensor publisher (simulates 4 ESP32 nodes)

```python
# fake_sensors.py
import json, time, random
import paho.mqtt.client as mqtt

SENSORS = [
    {"id": 1, "name": "Kitchen Basil",    "moisture": 55, "battery": 87},
    {"id": 2, "name": "Bathroom Fern",    "moisture": 65, "battery": 63},
    {"id": 3, "name": "Desk Succulent",   "moisture": 20, "battery": 94},
    {"id": 4, "name": "Balcony Tomato",   "moisture": 48, "battery": 41},
]

client = mqtt.Client()
client.connect("localhost", 1883)

print("Publishing fake sensor data every 30s. Ctrl+C to stop.")

while True:
    for s in SENSORS:
        # Simulate gradual drying with some noise
        s["moisture"] = max(5, min(100, s["moisture"] - random.uniform(0, 0.5) + random.uniform(-0.1, 0.1)))
        s["battery"]  = max(0, s["battery"] - random.uniform(0, 0.01))

        # Randomly simulate a watering event (~2% chance per cycle)
        if random.random() < 0.02:
            s["moisture"] = min(95, s["moisture"] + random.uniform(30, 45))

        payload = json.dumps({
            "moisture": round(s["moisture"], 1),
            "battery": round(s["battery"]),
            "raw": int(3200 - (s["moisture"] / 100) * 1800),
        })

        topic = f"home/plants/{s['id']}/moisture"
        client.publish(topic, payload)
        print(f"  {topic} → {payload}")

    print(f"--- cycle complete, sleeping 30s ---")
    time.sleep(30)
```

### Step 3 — Subscriber / ingest service

```python
# ingest.py — subscribes and pushes to Supabase (or just prints for now)
import json
import paho.mqtt.client as mqtt

def on_message(client, userdata, msg):
    sensor_id = int(msg.topic.split("/")[2])
    data = json.loads(msg.payload)
    print(f"[sensor {sensor_id}] moisture={data['moisture']}% battery={data.get('battery')}%")
    # TODO: insert into Supabase here (see Section 3, Stage 3)

client = mqtt.Client()
client.on_message = on_message
client.connect("localhost", 1883)
client.subscribe("home/plants/+/moisture")
print("Listening for sensor data...")
client.loop_forever()
```

### Step 4 — Quick CLI test with mosquitto_pub

You can also test individual messages without the Python script:

```bash
# Terminal 1 — subscribe to everything
mosquitto_sub -t "home/plants/#" -v

# Terminal 2 — publish a single fake reading
mosquitto_pub -t "home/plants/1/moisture" \
  -m '{"moisture": 42.5, "battery": 91, "raw": 2435}'
```

### Python dependencies

```bash
pip install paho-mqtt supabase
```

---

## 5. Web Dashboard with FastAPI on Railway

### Tech stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Framework | **FastAPI** (Python) | Server-rendered HTML, API endpoints, familiar language |
| Templates | **Jinja2** | Server-side HTML rendering, included with FastAPI |
| Interactivity | **HTMX** | SPA-like dynamic updates without writing JavaScript |
| Styling | **Tailwind CSS** (CDN) | Fast iteration, zero build steps |
| Auth | **Supabase Auth** | Email/password login, asymmetric JWT verified via JWKS |
| Database | **Supabase (Postgres)** | Free tier: 500MB, REST API, realtime subscriptions |
| Charts | **Inline SVGs** (server-generated) | Sparklines built in Python, no JS charting library |
| Hosting | **Railway** | Auto-deploy from GitHub, env vars via dashboard |

### Why FastAPI + HTMX instead of Next.js?

- **100% Python** — same language as the Raspberry Pi ingest service, no JavaScript/TypeScript needed
- **Zero build steps** — no npm, no Node.js, no webpack. Just Python + HTML templates
- **HTMX for interactivity** — individual plant cards auto-refresh via server-rendered HTML fragments, no React/Vue needed
- **Railway over Vercel** — predictable free tier with no surprise billing, no cold starts

### Supabase schema

The full DDL (tables, indexes, views, seed data, dummy readings, RLS) is in `supabase/schema.sql`. See [architecture.md](architecture.md) for the data model design.

Key design decisions:

- **Sensor and plant are separate tables** — a sensor can be reassigned to a different plant without losing history.
- **Append-only with timestamps** — plants and sensors tables are never updated. A new row with a fresh timestamp represents the current config. Views (`current_plants`, `current_sensors`) always return the latest active row per ID. Removal is a soft-delete: append a row with `is_active = false`.
- **Both raw and calibrated readings** — `moisture_raw` (ADC value) and `moisture_pct` (0–100%) are stored so recalibration doesn't retroactively change historical data.
- **Integer IDs** — `plant_id` and `sensor_id` are integers (1, 2, 3, 4), not strings.

### HTMX auto-refresh pattern

Each plant card includes an HTMX attribute that polls its own endpoint every 30 seconds. The server returns a fresh HTML fragment and HTMX swaps it in — no full page reload, no JavaScript state management:

```html
<div hx-get="/api/plant/1" hx-trigger="every 30s" hx-swap="outerHTML">
  <!-- plant card content rendered by Jinja2 -->
</div>
```

### Watering prediction logic (planned)

```python
# predictions.py — to be added
from datetime import datetime, timezone

def predict_days_until_watering(
    recent_readings: list[dict],
    water_below: float,
    current_moisture: float,
) -> float:
    """Predict days until plant needs watering based on moisture decay rate."""
    if current_moisture <= water_below:
        return 0
    if len(recent_readings) < 2:
        return -1  # not enough data

    recent = recent_readings[-48:]  # ~24h of readings at 30-min intervals
    first = recent[0]
    last = recent[-1]

    t0 = datetime.fromisoformat(first["recorded_at"])
    t1 = datetime.fromisoformat(last["recorded_at"])
    hours_elapsed = (t1 - t0).total_seconds() / 3600

    if hours_elapsed < 1:
        return -1

    moisture_drop = first["moisture_pct"] - last["moisture_pct"]
    drop_per_hour = moisture_drop / hours_elapsed

    if drop_per_hour <= 0:
        return 99  # moisture is rising or stable

    hours_remaining = (current_moisture - water_below) / drop_per_hour
    return round(hours_remaining / 24, 1)
```

### Dashboard routes

| Route | Method | Auth | Purpose |
|-------|--------|------|---------|
| `/login` | GET | No | Login page |
| `/login` | POST | No | Authenticate, set session cookie |
| `/logout` | POST | No | Clear session, redirect to login |
| `/` | GET | Yes | Main dashboard — all plant cards |
| `/api/plant/{plant_id}` | GET | Yes | Single plant card partial (HTMX) |
| `/manage/plants` | GET | Yes | Plant management page (list, add, edit, remove) |
| `/manage/plants/add` | POST | Yes | Add a new plant |
| `/manage/plants/{plant_id}/edit` | POST | Yes | Update plant metadata |
| `/manage/plants/{plant_id}/delete` | POST | Yes | Deactivate a plant |
| `/manage/sensors` | GET | Yes | Sensor management page (list, add, edit, remove) |
| `/manage/sensors/add` | POST | Yes | Add a new sensor |
| `/manage/sensors/{sensor_id}/edit` | POST | Yes | Update sensor config |
| `/manage/sensors/{sensor_id}/delete` | POST | Yes | Deactivate a sensor |
| `/health` | GET | No | Healthcheck for Railway |

### Deploy to Railway

1. Push to GitHub
2. Go to railway.app, sign in with GitHub
3. New Project → Deploy from GitHub Repo → select "moist"
4. Set Root Directory to `web` in service settings
5. Settings → Networking → Generate Domain
6. Add environment variables in the Variables tab:
   - `SUPABASE_URL`
   - `SUPABASE_PUBLISHABLE_KEY`
   - `SUPABASE_SECRET_KEY`

The `.env` file is git-ignored. Railway injects env vars from its dashboard at runtime.

---

## What to Do Next

| Priority | Task | Status |
|----------|------|--------|
| ~~1~~ | ~~Build dashboard UI with mock data~~ | Done |
| ~~2~~ | ~~Create Supabase project, run the SQL schema~~ | Done (`supabase/schema.sql`) |
| ~~3~~ | ~~Wire dashboard to Supabase (replace mock data with real queries)~~ | Done (`web/db.py`) |
| ~~4~~ | ~~Add Supabase Auth for login-protected dashboard~~ | Done (email/password, JWKS) |
| ~~5~~ | ~~Fake sensor cron job for Pi → Supabase testing~~ | Done (`fake_cron/`) |
| 6 | Deploy to Railway | Ready — push to GitHub and configure |
| 7 | Set up fake cron on Raspberry Pi | Ready — see `fake_cron/README.md` |
| 8 | Add watering prediction logic and countdown display | Not started |
| 9 | **When hardware arrives:** flash ESP32s, calibrate sensors, replace fake cron with real MQTT pipeline | Waiting for delivery |
