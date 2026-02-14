# 🌱 Soil Humidity Monitor — Project Overview

**Status:** Hardware ordered, awaiting delivery
**Location:** Ireland
**Last updated:** February 2026

---

## 1. Idea Overview

We're building an end-to-end plant monitoring system from scratch. A capacitive soil moisture sensor in each plant pot feeds an analog signal to a battery-powered ESP32 microcontroller, which wakes every 15–30 minutes, takes a reading, publishes it over Wi-Fi via MQTT, then goes back to deep sleep. A Raspberry Pi on the local network runs Mosquitto (MQTT broker) and a small Python service that processes incoming readings and pushes them to a cloud Postgres database (Supabase). A Next.js web app on Vercel provides a login-protected dashboard where you can see each plant's current moisture level, historical trends, and a prediction of when it will next need watering.

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
                                                             │   Next.js    │
                                                             │  on Vercel   │
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

### Stage 4 — Supabase → Next.js Dashboard (can test NOW)

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

## 5. UI with Next.js on Vercel

### Tech stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Framework | **Next.js 14+ (App Router)** | Server components, API routes, easy Vercel deploy |
| Styling | **Tailwind CSS** | Fast iteration, no CSS files to manage |
| Auth | **Supabase Auth** | Free, handles email/password + magic links, JWT tokens |
| Database | **Supabase (Postgres)** | Free tier: 500MB, REST API, realtime subscriptions |
| Charts | **Recharts** or lightweight inline SVGs | Sparklines, moisture history |
| Hosting | **Vercel** (free tier) | Zero-config Next.js deploys from GitHub |

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
plant-monitor/
├── app/
│   ├── layout.tsx              # Root layout, fonts, Supabase provider
│   ├── page.tsx                # Redirect to /dashboard or /login
│   ├── login/
│   │   └── page.tsx            # Login form (Supabase Auth)
│   └── dashboard/
│       ├── page.tsx            # Main dashboard (server component)
│       ├── plant-card.tsx      # Individual plant card (client component)
│       ├── detail-panel.tsx    # Selected plant detail view
│       ├── sparkline.tsx       # SVG sparkline chart
│       └── moisture-gauge.tsx  # Semi-circle gauge
├── lib/
│   ├── supabase-server.ts      # Server-side Supabase client
│   ├── supabase-browser.ts     # Browser-side Supabase client
│   ├── plant-profiles.ts       # Plant type definitions & thresholds
│   └── predictions.ts          # Watering prediction logic
├── middleware.ts                # Auth redirect (protect /dashboard)
├── tailwind.config.ts
├── package.json
└── .env.local                  # NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY
```

### Key dashboard queries

```typescript
// lib/queries.ts
import { supabase } from './supabase-browser'

// Get all plants with their latest reading
export async function getPlantsWithLatestReading() {
  const { data } = await supabase
    .from('plants')
    .select(`
      *,
      readings (
        moisture, battery, raw_value, recorded_at
      )
    `)
    .order('recorded_at', { referencedTable: 'readings', ascending: false })
    .limit(1, { referencedTable: 'readings' })

  return data
}

// Get 7-day history for a specific plant
export async function getPlantHistory(sensorId: string, days: number = 7) {
  const since = new Date(Date.now() - days * 24 * 60 * 60 * 1000).toISOString()

  const { data } = await supabase
    .from('readings')
    .select('moisture, battery, recorded_at')
    .eq('sensor_id', sensorId)
    .gte('recorded_at', since)
    .order('recorded_at', { ascending: true })

  return data
}
```

### Watering prediction logic

```typescript
// lib/predictions.ts

interface PredictionInput {
  recentReadings: { moisture: number; recorded_at: string }[]
  waterBelow: number
  currentMoisture: number
}

export function predictDaysUntilWatering(input: PredictionInput): number {
  const { recentReadings, waterBelow, currentMoisture } = input

  if (currentMoisture <= waterBelow) return 0
  if (recentReadings.length < 2) return -1  // not enough data

  // Calculate average hourly moisture drop from last 48h of readings
  const recent = recentReadings.slice(-48)  // assuming ~1 reading per 30 min
  const first = recent[0]
  const last = recent[recent.length - 1]

  const hoursElapsed =
    (new Date(last.recorded_at).getTime() - new Date(first.recorded_at).getTime()) / 3600000

  if (hoursElapsed < 1) return -1

  const moistureDrop = first.moisture - last.moisture
  const dropPerHour = moistureDrop / hoursElapsed

  if (dropPerHour <= 0) return 99  // moisture is rising or stable

  const hoursRemaining = (currentMoisture - waterBelow) / dropPerHour
  return Math.round((hoursRemaining / 24) * 10) / 10
}
```

### Deploy to Vercel

```bash
# 1. Create the project
npx create-next-app@latest plant-monitor --typescript --tailwind --app
cd plant-monitor

# 2. Install dependencies
npm install @supabase/supabase-js @supabase/ssr recharts

# 3. Add environment variables to .env.local
#    NEXT_PUBLIC_SUPABASE_URL=https://xxxxx.supabase.co
#    NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbG...

# 4. Build and test locally
npm run dev

# 5. Deploy
npx vercel
```

Add the same env vars in Vercel's project settings under **Settings → Environment Variables**.

### Dashboard pages to build

1. **`/login`** — email + password form, calls `supabase.auth.signInWithPassword()`
2. **`/dashboard`** — grid of plant cards on the left, detail panel on the right
3. **`/dashboard/settings`** (later) — add/remove plants, edit thresholds, manage sensors
4. **`/api/health`** (optional) — endpoint the Pi can ping to verify cloud connectivity

### Realtime updates (optional, nice-to-have)

Supabase supports Postgres realtime — the dashboard can subscribe to new readings and update without polling:

```typescript
supabase
  .channel('readings')
  .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'readings' },
    (payload) => {
      // Update the relevant plant card in state
    }
  )
  .subscribe()
```

---

## What to Do Right Now (No Hardware Needed)

| Priority | Task | Time Est. |
|----------|------|-----------|
| 1 | Create Supabase project, run the SQL schema above | 15 min |
| 2 | Install Mosquitto locally, run `fake_sensors.py` and `ingest.py` | 30 min |
| 3 | Connect `ingest.py` to Supabase so fake readings flow into the DB | 30 min |
| 4 | Scaffold Next.js project, wire up Supabase Auth for login | 1–2 hrs |
| 5 | Build dashboard UI (plant cards, sparklines, detail panel) | 2–3 hrs |
| 6 | Add prediction logic and watering countdown | 1 hr |
| 7 | Deploy to Vercel | 15 min |
| 8 | **When hardware arrives:** flash ESP32s, calibrate sensors, swap fake publisher for real nodes | 1–2 hrs |
