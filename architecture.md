# Architecture

Technical reference for the moist system. For the aspirational vision (hardware, MQTT, predictions), see [project-overview.md](project-overview.md).

---

## System overview

```
                              ┌──────────────────────────────────────────┐
                              │         Supabase (cloud)                 │
                              │                                          │
    ┌──────────────┐  HTTPS   │  ┌──────────┐  ┌───────────┐            │
    │ Raspberry Pi │─────────▶│  │ Postgres │  │   Auth    │            │
    │  fake cron   │  insert  │  │ 3 tables │  │ JWKS keys │            │
    │  (or MQTT    │          │  │ 2 views  │  └─────┬─────┘            │
    │   ingest)    │          │  └────┬─────┘        │                  │
    └──────────────┘          │       │ REST API     │ .well-known/jwks │
                              └───────┼──────────────┼──────────────────┘
                                      │              │
                                      ▼              ▼
                              ┌──────────────────────────────────────────┐
                              │     Railway (FastAPI + HTMX)             │
                              │                                          │
                              │  main.py ─── db.py ─── Supabase SDK     │
                              │     │                                    │
                              │     ├── GET /login   (public)            │
                              │     ├── POST /login  (public)            │
                              │     ├── POST /logout (public)            │
                              │     ├── GET /        (auth required)     │
                              │     ├── GET /api/plant/{id} (auth, HTMX) │
                              │     └── GET /health  (public)            │
                              └──────────────────────────────────────────┘
                                      ▲
                                      │ HTTPS
                                      │
                                  ┌───────┐
                                  │Browser│
                                  └───────┘
```

---

## Data model

Three tables with an append-only temporal pattern for plants and sensors, and pure time-series for readings.

### Why append-only?

Records are never updated or deleted. To change a plant's config or recalibrate a sensor, insert a new row with a fresh timestamp. The current state is always the most recent row per ID. This preserves full history for debugging and auditing.

Two Postgres views (`current_plants`, `current_sensors`) encapsulate the `DISTINCT ON (...) ORDER BY created_at DESC` logic so application queries stay simple.

### Tables

```
plants (append-only config)
├── id              bigint identity PK
├── plant_id        integer             -- logical identifier (1, 2, 3, 4)
├── plant_name      text
├── plant_position  text
├── ideal_min       integer             -- ideal moisture range lower bound
├── ideal_max       integer             -- ideal moisture range upper bound
├── water_below     integer             -- flag as needing water below this %
└── created_at      timestamptz         -- version timestamp

sensors (append-only config)
├── id              bigint identity PK
├── sensor_id       integer             -- logical identifier (1, 2, 3, 4)
├── plant_id        integer             -- which plant this sensor is assigned to
├── calibration_dry integer             -- raw ADC value at 0% (air, ~3200)
├── calibration_wet integer             -- raw ADC value at 100% (water, ~1400)
└── created_at      timestamptz         -- version timestamp

readings (time-series)
├── id              bigint identity PK
├── sensor_id       integer             -- which sensor took this reading
├── moisture_raw    integer             -- raw ADC value from the sensor
├── moisture_pct    real                -- calibrated 0-100%
├── battery         real                -- battery level 0-100%
└── recorded_at     timestamptz         -- when the reading was taken
```

### Views

- `current_plants` -- latest row per `plant_id`
- `current_sensors` -- latest row per `sensor_id`

### Relationships

```
current_plants.plant_id  <──  current_sensors.plant_id  <──  readings.sensor_id
      (1:1 currently)              (sensor assigned to plant)    (many readings per sensor)
```

No foreign key constraints between the temporal tables (Postgres can't FK to a non-unique column). Referential integrity is maintained at the application layer.

### Indexes

- `plants (plant_id, created_at DESC)` -- fast current-config lookup
- `sensors (sensor_id, created_at DESC)` -- fast current-config lookup
- `readings (sensor_id, recorded_at DESC)` -- fast dashboard and history queries

### Growth estimate

At 48 readings/day (every 30 min) with 4 sensors: ~192 rows/day, ~70K/year. Well within Supabase's 500MB free tier for years.

---

## Auth flow

Authentication uses Supabase Auth with email/password. JWTs are signed with asymmetric keys (ES256/RS256) and verified locally using the JWKS discovery endpoint.

### Login

```
Browser                        FastAPI                         Supabase Auth
   │                              │                                 │
   │  POST /login (email, pass)   │                                 │
   │─────────────────────────────▶│                                 │
   │                              │  sign_in_with_password()        │
   │                              │────────────────────────────────▶│
   │                              │                                 │
   │                              │◀─── access_token (JWT) ────────│
   │                              │                                 │
   │◀── 302 / + Set-Cookie ──────│                                 │
   │    (httponly, samesite=lax)   │                                 │
```

### Authenticated request

```
Browser                        FastAPI                         Supabase (JWKS)
   │                              │                                 │
   │  GET / (Cookie: access_token)│                                 │
   │─────────────────────────────▶│                                 │
   │                              │  fetch public key (cached 10m)  │
   │                              │────────────────────────────────▶│
   │                              │◀─── JWKS (public keys) ────────│
   │                              │                                 │
   │                              │  verify JWT signature locally   │
   │                              │  (no Auth server in hot path)   │
   │                              │                                 │
   │◀── 200 dashboard.html ──────│                                 │
```

### HTMX polling with expired token

```
Browser (HTMX)                 FastAPI
   │                              │
   │  GET /api/plant/1            │
   │  (Cookie: expired JWT)       │
   │─────────────────────────────▶│
   │                              │  verify_token() → None
   │                              │
   │◀── 200 + HX-Redirect ──────│
   │    header: /login            │
   │                              │
   │  (HTMX handles redirect     │
   │   client-side, no broken UI) │
```

### Environment variables

| Variable | Where | Purpose |
|----------|-------|---------|
| `SUPABASE_URL` | Railway Variables tab | Project URL |
| `SUPABASE_PUBLISHABLE_KEY` | Railway Variables tab | Auth calls (replaces legacy anon key) |
| `SUPABASE_SECRET_KEY` | Railway Variables tab | Data queries, bypasses RLS (replaces legacy service_role key) |

The `.env` file is used for local development only and is git-ignored. Railway injects variables at runtime from its dashboard.

### Cookie settings

| Setting | Local | Railway |
|---------|-------|---------|
| `httponly` | true | true |
| `secure` | false | true (auto-detected via `RAILWAY_ENVIRONMENT`) |
| `samesite` | lax | lax |
| `max_age` | 7 days | 7 days |

---

## Request flow (dashboard)

When a user loads the dashboard, `db.py` issues 2 + N Supabase queries (where N = number of plants):

1. `SELECT * FROM current_plants ORDER BY plant_id` -- all plant configs
2. `SELECT * FROM current_sensors ORDER BY sensor_id` -- all sensor configs (to map sensor → plant)
3. For **each** sensor: `SELECT ... FROM readings WHERE sensor_id = ? AND recorded_at >= (now - 7 days) ORDER BY recorded_at` -- 7-day history for that sensor

Readings are fetched per-sensor rather than in one bulk query to avoid hitting the Supabase PostgREST default row limit (1 000 rows). A single query across all sensors can silently truncate results when the total exceeds the cap.

Results are assembled into `Plant` dataclass objects in Python. Each plant gets its latest reading (last item in history) and full 7-day history (for the sparkline SVG). The Jinja2 templates render server-side HTML.

For HTMX card refreshes (every 30s per card), `get_plant_card(plant_id)` runs 3 queries scoped to a single plant/sensor.

All dashboard and HTMX partial responses include `Cache-Control: no-store` headers to prevent browsers and proxies from serving stale HTML.

---

## File reference

```
fake_cron/                       # Fake sensor cron job (runs on Raspberry Pi)
├── send_reading.py              # Generates fake readings, inserts into Supabase
│                                #   Persists state to state.json between runs
│                                #   Simulates drying, battery drain, watering events
├── requirements.txt             # supabase, python-dotenv
├── .env.example                 # SUPABASE_URL + SUPABASE_SECRET_KEY
└── README.md                    # Setup + crontab instructions

web/
├── main.py              # FastAPI routes + auth middleware
│                        #   _get_user() -- verify JWT from cookie
│                        #   _auth_failed_response() -- HTMX-aware redirect
│                        #   6 route handlers
│
├── db.py                # Supabase clients + data layer
│                        #   _get_auth_client() -- publishable key, for auth
│                        #   _get_data_client() -- secret key, for queries
│                        #   _get_jwks_client() -- JWKS endpoint, for JWT verification
│                        #   Plant / Reading dataclasses with computed properties
│                        #   generate_sparkline_svg() -- server-rendered SVG
│                        #   authenticate() / verify_token()
│                        #   get_all_plants() / get_plant_card()
│
├── requirements.txt     # fastapi, uvicorn, jinja2, python-dotenv,
│                        # python-multipart, supabase, PyJWT[crypto]
│
├── railway.toml         # start command + healthcheck path
├── runtime.txt          # Python 3.12
├── .env.example         # documents the 3 required env vars
│
├── templates/
│   ├── base.html        # <html> shell: Tailwind CDN, HTMX CDN, 401 handler
│   ├── login.html       # centered login card (extends base)
│   ├── dashboard.html   # header + summary bar + card grid (extends base)
│   └── partials/
│       └── plant_card.html  # single card: moisture bar, sparkline, battery
│
└── static/
    └── favicon.ico
```

---

## Row-level security (RLS)

All three tables have RLS enabled.

| Role | plants | sensors | readings |
|------|--------|---------|----------|
| `authenticated` | SELECT | SELECT | SELECT |
| `service_role` | INSERT | INSERT | INSERT |
| `anon` | -- | -- | -- |

The web dashboard uses the secret key (bypasses RLS) for simplicity. The Raspberry Pi ingest service will also use the secret key for inserts. RLS policies are in place for defense-in-depth if the publishable key is ever used for direct client queries.
