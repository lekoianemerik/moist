# 🌱 Soil Humidity Monitor — Project Overview

**Status:** Hardware ordered, awaiting delivery
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

- Per-plant moisture % with configurable thresholds per plant type
- 7-day sparkline history per sensor
- Watering prediction based on rolling average moisture decay rate
- Battery level monitoring per sensor node
- Automatic watering event detection (sudden moisture spike)
- Login-protected dashboard (Supabase Auth)
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

Add Wi-Fi and MQTT to the ESP32 sketch. The ESP32 publishes a JSON payload to a topic like `home/plants/{sensor-id}/moisture`.

```cpp
// Pseudo-code for the full loop
void loop() {
  wakeFromDeepSleep();
  connectWiFi();
  readSensor();
  publishMQTT("home/plants/sensor-01/moisture", "{\"moisture\": 52.3, \"battery\": 87, \"raw\": 1842}");
  disconnectWiFi();
  enterDeepSleep(30 * 60);  // 30 minutes
}
```

**MQTT topic structure:**

```
home/plants/sensor-01/moisture  →  {"moisture": 52.3, "battery": 87, "raw": 1842}
home/plants/sensor-02/moisture  →  {"moisture": 38.1, "battery": 63, "raw": 2104}
...
```

### Stage 3 — Raspberry Pi → Supabase (can test NOW)

A Python service on the Pi subscribes to `home/plants/+/moisture`, processes each message, and inserts it into Supabase via its REST API.

```python
# ingest.py — runs on the Raspberry Pi
import json, os
import paho.mqtt.client as mqtt
from supabase import create_client

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

def on_message(client, userdata, msg):
    sensor_id = msg.topic.split("/")[2]
    data = json.loads(msg.payload)
    supabase.table("readings").insert({
        "sensor_id": sensor_id,
        "moisture": data["moisture"],
        "battery": data.get("battery"),
        "raw_value": data.get("raw"),
    }).execute()

client = mqtt.Client()
client.on_message = on_message
client.connect("localhost", 1883)
client.subscribe("home/plants/+/moisture")
client.loop_forever()
```

### Stage 4 — Supabase → FastAPI Dashboard (can test NOW)

The dashboard queries Supabase for the latest reading per plant and recent history. See Section 5 for full details.

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
    {"id": "sensor-01", "name": "Kitchen Basil",    "type": "basil",     "moisture": 55, "battery": 87},
    {"id": "sensor-02", "name": "Bathroom Fern",    "type": "fern",      "moisture": 65, "battery": 63},
    {"id": "sensor-03", "name": "Desk Succulent",   "type": "succulent", "moisture": 20, "battery": 94},
    {"id": "sensor-04", "name": "Balcony Tomato",   "type": "tomato",    "moisture": 48, "battery": 41},
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
    sensor_id = msg.topic.split("/")[2]
    data = json.loads(msg.payload)
    print(f"[{sensor_id}] moisture={data['moisture']}% battery={data.get('battery')}%")
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
mosquitto_pub -t "home/plants/sensor-01/moisture" \
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
| Auth | **Supabase Auth** (future) | Free, handles email/password + magic links |
| Database | **Supabase (Postgres)** | Free tier: 500MB, REST API, realtime subscriptions |
| Charts | **Inline SVGs** (server-generated) | Sparklines built in Python, no JS charting library |
| Hosting | **Railway** (free tier) | $0/month with $1 credit, no cold starts, auto-deploy from GitHub |

### Why FastAPI + HTMX instead of Next.js?

- **100% Python** — same language as the Raspberry Pi ingest service, no JavaScript/TypeScript needed
- **Zero build steps** — no npm, no Node.js, no webpack. Just Python + HTML templates
- **HTMX for interactivity** — individual plant cards auto-refresh via server-rendered HTML fragments, no React/Vue needed
- **Railway over Vercel** — predictable free tier with no surprise billing, no cold starts

### Supabase schema

```sql
-- Run this in Supabase SQL Editor

create table plants (
  id            text primary key,           -- matches sensor_id e.g. 'sensor-01'
  name          text not null,              -- 'Kitchen Basil'
  location      text,                       -- 'Kitchen windowsill'
  plant_type    text not null,              -- 'basil', 'fern', 'succulent', 'tomato'
  ideal_min     integer not null default 40,
  ideal_max     integer not null default 60,
  water_below   integer not null default 30,
  avg_daily_drop real not null default 8.0,
  created_at    timestamptz default now()
);

create table readings (
  id          bigint generated always as identity primary key,
  sensor_id   text references plants(id) not null,
  moisture    real not null,
  battery     real,
  raw_value   integer,
  recorded_at timestamptz default now()
);

-- Index for fast dashboard queries
create index idx_readings_sensor_time on readings (sensor_id, recorded_at desc);

-- Seed with our 4 test plants
insert into plants (id, name, location, plant_type, ideal_min, ideal_max, water_below, avg_daily_drop) values
  ('sensor-01', 'Kitchen Basil',    'Kitchen windowsill', 'basil',     40, 60, 30, 8.0),
  ('sensor-02', 'Bathroom Fern',    'Bathroom shelf',     'fern',      60, 80, 50, 6.0),
  ('sensor-03', 'Desk Succulent',   'Office desk',        'succulent', 10, 25, 10, 3.0),
  ('sensor-04', 'Balcony Tomato',   'Balcony planter',    'tomato',    50, 70, 35, 10.0);

-- Row-level security (RLS) — lock it down
alter table plants enable row level security;
alter table readings enable row level security;

create policy "Authenticated users can read plants"
  on plants for select
  to authenticated
  using (true);

create policy "Authenticated users can read readings"
  on readings for select
  to authenticated
  using (true);

create policy "Service role can insert readings"
  on readings for insert
  to service_role
  with check (true);
```

### Project structure

```
web/
├── main.py                    # FastAPI app, routes, startup
├── mock_data.py               # Fake plants & readings (replaced by Supabase later)
├── requirements.txt           # fastapi, uvicorn, jinja2, python-dotenv
├── Procfile                   # Start command for Railway
├── railway.toml               # Railway deployment config
├── .env                       # SUPABASE_URL, SUPABASE_KEY (git-ignored)
├── templates/
│   ├── base.html              # Layout: Tailwind CDN, HTMX CDN, dark mode
│   ├── dashboard.html         # Main page: summary bar + plant card grid
│   └── partials/
│       └── plant_card.html    # Single plant card (HTMX-swappable)
└── static/
    └── favicon.ico
```

### Key dashboard queries (Python + Supabase SDK)

```python
# queries.py — to be added when Supabase is wired up
from supabase import create_client
import os

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

def get_plants_with_latest_reading():
    """Get all plants with their most recent reading."""
    result = supabase.table("plants").select(
        "*, readings(moisture, battery, raw_value, recorded_at)"
    ).order(
        "recorded_at", desc=True, foreign_table="readings"
    ).limit(1, foreign_table="readings").execute()
    return result.data

def get_plant_history(sensor_id: str, days: int = 7):
    """Get 7-day reading history for a specific plant."""
    from datetime import datetime, timedelta, timezone
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    result = supabase.table("readings").select(
        "moisture, battery, recorded_at"
    ).eq("sensor_id", sensor_id).gte(
        "recorded_at", since
    ).order("recorded_at", desc=False).execute()
    return result.data
```

### Watering prediction logic

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

    moisture_drop = first["moisture"] - last["moisture"]
    drop_per_hour = moisture_drop / hours_elapsed

    if drop_per_hour <= 0:
        return 99  # moisture is rising or stable

    hours_remaining = (current_moisture - water_below) / drop_per_hour
    return round(hours_remaining / 24, 1)
```

### HTMX auto-refresh pattern

Each plant card includes an HTMX attribute that polls its own endpoint every 30 seconds. The server returns a fresh HTML fragment and HTMX swaps it in — no full page reload, no JavaScript state management:

```html
<div hx-get="/api/plant/sensor-01" hx-trigger="every 30s" hx-swap="outerHTML">
  <!-- plant card content rendered by Jinja2 -->
</div>
```

### Deploy to Railway

```bash
# 1. Push to GitHub
cd moist
git remote add origin https://github.com/YOU/moist.git
git push -u origin main

# 2. Go to railway.app, sign in with GitHub
# 3. New Project → Deploy from GitHub Repo → select "moist"
# 4. Set Root Directory to "web" in service settings
# 5. Settings → Networking → Generate Domain
# 6. Add env vars SUPABASE_URL and SUPABASE_KEY (when ready)
```

### Dashboard routes

| Route | Method | Purpose |
|-------|--------|---------|
| `/` | GET | Main dashboard — renders all plant cards |
| `/api/plant/{id}` | GET | Single plant card partial (HTMX refresh) |
| `/health` | GET | Healthcheck for Railway |
| `/login` | GET/POST | Login form with Supabase Auth (future) |
| `/settings` | GET/POST | Manage plants, thresholds, sensors (future) |

---

## What to Do Next (No Hardware Needed)

| Priority | Task | Time Est. |
|----------|------|-----------|
| ~~1~~ | ~~Build dashboard UI with mock data~~ | ~~done~~ |
| 2 | Create Supabase project, run the SQL schema above | 15 min |
| 3 | Wire dashboard to Supabase (replace mock_data.py with real queries) | 1–2 hrs |
| 4 | Add Supabase Auth for login-protected dashboard | 1–2 hrs |
| 5 | Install Mosquitto locally, run `fake_sensors.py` and `ingest.py` | 30 min |
| 6 | Connect `ingest.py` to Supabase so fake readings flow into the DB | 30 min |
| 7 | Add watering prediction logic and countdown display | 1 hr |
| 8 | Deploy to Railway | 15 min |
| 9 | **When hardware arrives:** flash ESP32s, calibrate sensors, swap fake publisher for real nodes | 1–2 hrs |
