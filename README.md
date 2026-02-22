# moist

Soil humidity monitoring system for houseplants. Tracks moisture levels, battery status, and predicts when each plant needs watering.

## Current status

**Hardware:** Ordered, awaiting delivery (ESP32s, capacitive sensors, Raspberry Pi, batteries).

**Web dashboard:** Wired to Supabase with auth. Ready to deploy to Railway.

| Component | Status |
|-----------|--------|
| Web dashboard (FastAPI + HTMX) | Done -- reads from Supabase, login-protected |
| Plant/sensor management pages | Done -- add, edit, remove plants and sensors from the UI |
| Supabase database (schema + seed data) | Done -- `supabase/schema.sql` ready to run |
| Supabase Auth (email/password login) | Done -- cookie-based sessions, JWKS verification |
| Railway deployment | Ready -- `railway.toml` configured, needs env vars |
| Fake sensor cron job (Raspberry Pi) | Done -- `fake_cron/` discovers sensors dynamically from Supabase |
| MQTT pipeline (real sensors) | Not started |
| Sensor calibration script (Raspberry Pi) | Done -- `calibration/` 3-point calibration via MQTT |
| ESP32 firmware | Waiting for hardware |

## Tech stack

| Layer | Technology |
|-------|-----------|
| Web framework | FastAPI (Python) |
| Templates | Jinja2 |
| Interactivity | HTMX (auto-refreshing plant cards every 30s) |
| Styling | Tailwind CSS (CDN) |
| Database | Supabase (Postgres) |
| Auth | Supabase Auth (email/password, asymmetric JWT) |
| Hosting | Railway (auto-deploy from GitHub) |

## Project structure

```
moist/
├── README.md                  # You are here
├── project-overview.md        # Full aspirational design (hardware, MQTT, predictions)
├── architecture.md            # Data model, auth flow, deployment architecture
├── supabase/
│   └── schema.sql             # DDL + seed data + dummy readings (run in SQL Editor)
├── calibration/               # Sensor calibration tool (runs on Raspberry Pi)
│   ├── calibration.py         # Interactive 3-point calibration via MQTT
│   ├── requirements.txt       # Python dependencies (paho-mqtt)
│   └── README.md              # Setup + usage instructions
├── fake_cron/                 # Fake sensor cron job (runs on Raspberry Pi)
│   ├── send_reading.py        # Discovers active sensors from Supabase, inserts fake readings
│   ├── requirements.txt       # Python dependencies (supabase, python-dotenv)
│   ├── .env.example           # Template for Supabase credentials
│   └── README.md              # Setup + crontab instructions
└── web/                       # FastAPI web dashboard
    ├── main.py                # Routes + auth middleware (14 endpoints)
    ├── db.py                  # Supabase clients, data models, queries, CRUD
    ├── requirements.txt       # Python dependencies
    ├── railway.toml           # Railway deployment config
    ├── runtime.txt            # Python 3.12
    ├── .env                   # Supabase credentials (git-ignored)
    ├── .env.example           # Documents required env vars
    ├── templates/
    │   ├── base.html          # Layout: Tailwind CDN, HTMX CDN, dark mode
    │   ├── login.html         # Login page (pre-auth screen)
    │   ├── dashboard.html     # Main page: summary bar + plant card grid
    │   ├── manage_plants.html # Plant management: add, edit, remove plants
    │   ├── manage_sensors.html # Sensor management: add, edit, remove, link to plants
    │   └── partials/
    │       └── plant_card.html  # Individual plant card (HTMX-swappable)
    └── static/
        └── favicon.ico
```

## Running locally

```bash
cd web
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in your Supabase credentials:

```bash
cp .env.example .env
# Edit .env with your SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY, SUPABASE_SECRET_KEY
```

Before the first run, go to the Supabase SQL Editor and run `supabase/schema.sql` to create tables and seed data. Then create one user in the Supabase dashboard (Authentication > Users > Add User).

```bash
uvicorn main:app --reload
```

Open http://localhost:8000 -- you'll be redirected to the login page.

## Deploying to Railway

1. Push to GitHub
2. Go to [railway.app](https://railway.app), sign in with GitHub
3. New Project > Deploy from GitHub Repo > select "moist"
4. Set Root Directory to `web` in service settings
5. Settings > Networking > Generate Domain
6. Add environment variables in the Variables tab:
   - `SUPABASE_URL`
   - `SUPABASE_PUBLISHABLE_KEY`
   - `SUPABASE_SECRET_KEY`

Railway auto-deploys on every push to `main`. The `.env` file is git-ignored; Railway uses its own Variables tab instead.

## What's next

1. Deploy to Railway
2. Set up fake cron job on Raspberry Pi (see `fake_cron/README.md`)
3. Add watering prediction logic and countdown display
4. When hardware arrives: flash ESP32s, calibrate sensors, replace fake cron with real MQTT pipeline

See [project-overview.md](project-overview.md) for the full aspirational design and [architecture.md](architecture.md) for technical details.
