# moist

Soil humidity monitoring system for houseplants. Tracks moisture levels, battery status, and predicts when each plant needs watering.

See [project-overview.md](project-overview.md) for the full aspirational design (hardware, MQTT pipeline, Supabase schema, deployment plan).

## Current status

**Hardware:** Ordered, awaiting delivery (ESP32s, capacitive sensors, Raspberry Pi, batteries).

**Web dashboard:** Built and running locally with mock data. Not yet deployed.

| Component | Status |
|-----------|--------|
| Web dashboard (FastAPI + HTMX) | Working locally with mock data |
| Supabase database | Not set up yet |
| Supabase Auth (login) | Not started |
| MQTT pipeline (fake sensors) | Not started |
| Raspberry Pi ingest service | Not started |
| Railway deployment | Not deployed yet |
| ESP32 firmware | Waiting for hardware |

## Tech stack

| Layer | Technology |
|-------|-----------|
| Web framework | FastAPI (Python) |
| Templates | Jinja2 |
| Interactivity | HTMX (auto-refreshing plant cards) |
| Styling | Tailwind CSS (CDN) |
| Database | Supabase (Postgres) — not wired up yet |
| Hosting | Railway (free tier) — not deployed yet |

## Project structure

```
moist/
├── README.md                  # You are here
├── project-overview.md        # Full project design and aspirational plan
└── web/                       # FastAPI web dashboard
    ├── main.py                # App entry point (3 routes)
    ├── mock_data.py           # 4 fake plants with 7-day generated history
    ├── requirements.txt       # Python dependencies
    ├── Procfile               # Railway start command
    ├── railway.toml           # Railway config
    ├── .env                   # Supabase credentials (git-ignored)
    ├── templates/
    │   ├── base.html          # Layout with Tailwind + HTMX CDN
    │   ├── dashboard.html     # Main dashboard page
    │   └── partials/
    │       └── plant_card.html  # Individual plant card
    └── static/
        └── favicon.ico
```

## Running locally

```bash
cd web
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Open http://localhost:8000 to see the dashboard with 4 mock plants.

## What's next

1. Create Supabase project and run the database schema (see project-overview.md Section 5)
2. Wire the dashboard to Supabase (replace mock data with real queries)
3. Add login with Supabase Auth
4. Deploy to Railway
5. Set up MQTT pipeline with fake sensors for end-to-end testing
6. When hardware arrives: flash ESP32s, calibrate sensors, go live
