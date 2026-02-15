"""
Supabase client, data models, and query functions.
Replaces mock_data.py with real database queries.
"""

import os
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field

import jwt
from jwt import PyJWKClient
from supabase import create_client, Client

# ---------------------------------------------------------------------------
# Supabase clients (lazy-initialised)
# ---------------------------------------------------------------------------

SUPABASE_URL: str = os.environ.get("SUPABASE_URL", "")
SUPABASE_PUBLISHABLE_KEY: str = os.environ.get("SUPABASE_PUBLISHABLE_KEY", "")
SUPABASE_SECRET_KEY: str = os.environ.get("SUPABASE_SECRET_KEY", "")

_auth_client: Client | None = None
_data_client: Client | None = None
_jwks_client: PyJWKClient | None = None


def _get_auth_client() -> Client:
    """Publishable-key client used only for auth calls."""
    global _auth_client
    if _auth_client is None:
        _auth_client = create_client(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY)
    return _auth_client


def _get_data_client() -> Client:
    """Secret-key client used for data queries (bypasses RLS)."""
    global _data_client
    if _data_client is None:
        _data_client = create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)
    return _data_client


def _get_jwks_client() -> PyJWKClient:
    """JWKS client for asymmetric JWT verification (cached internally)."""
    global _jwks_client
    if _jwks_client is None:
        jwks_url = f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json"
        _jwks_client = PyJWKClient(jwks_url, cache_keys=True, lifespan=600)
    return _jwks_client


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class Reading:
    moisture_pct: float
    battery: float
    moisture_raw: int
    recorded_at: str


@dataclass
class Plant:
    plant_id: int
    sensor_id: int
    plant_name: str
    plant_position: str
    ideal_min: int
    ideal_max: int
    water_below: int
    latest: Reading | None = None
    history: list[Reading] = field(default_factory=list)

    @property
    def status(self) -> dict:
        """Status label, text colour class, and bg colour class."""
        if not self.latest:
            return {
                "label": "No Data",
                "text": "text-stone-500",
                "bg": "bg-stone-100 dark:bg-stone-800",
            }
        m = self.latest.moisture_pct
        if m <= self.water_below:
            return {
                "label": "Dry!",
                "text": "text-red-600 dark:text-red-400",
                "bg": "bg-red-100 dark:bg-red-950/60",
            }
        if m < self.ideal_min:
            return {
                "label": "Needs Water",
                "text": "text-amber-600 dark:text-amber-400",
                "bg": "bg-amber-100 dark:bg-amber-950/60",
            }
        if m > self.ideal_max:
            return {
                "label": "Overwatered",
                "text": "text-blue-600 dark:text-blue-400",
                "bg": "bg-blue-100 dark:bg-blue-950/60",
            }
        return {
            "label": "Healthy",
            "text": "text-emerald-600 dark:text-emerald-400",
            "bg": "bg-emerald-100 dark:bg-emerald-950/60",
        }

    @property
    def bar_color(self) -> str:
        if not self.latest:
            return "bg-stone-400"
        m = self.latest.moisture_pct
        if m <= self.water_below:
            return "bg-red-500"
        if m < self.ideal_min:
            return "bg-amber-500"
        return "bg-emerald-500"

    @property
    def sparkline_color(self) -> str:
        if not self.latest:
            return "#a8a29e"
        m = self.latest.moisture_pct
        if m <= self.water_below:
            return "#ef4444"
        if m < self.ideal_min:
            return "#f59e0b"
        return "#22c55e"

    @property
    def battery_icon(self) -> str:
        if not self.latest:
            return "\u2753"
        b = self.latest.battery
        if b > 60:
            return "\U0001f50b"
        if b > 20:
            return "\U0001faab"
        return "\u26a0\ufe0f"

    @property
    def time_ago(self) -> str:
        if not self.latest:
            return "no data"
        recorded = datetime.fromisoformat(self.latest.recorded_at)
        minutes = int((datetime.now(timezone.utc) - recorded).total_seconds() / 60)
        if minutes < 1:
            return "just now"
        if minutes < 60:
            return f"{minutes}m ago"
        hours = minutes // 60
        if hours < 24:
            return f"{hours}h ago"
        return f"{hours // 24}d ago"


# ---------------------------------------------------------------------------
# Sparkline SVG generator
# ---------------------------------------------------------------------------


def generate_sparkline_svg(
    readings: list[Reading],
    width: int = 140,
    height: int = 36,
    color: str = "#22c55e",
) -> str:
    """Generate an inline SVG sparkline from a list of readings."""
    if len(readings) < 2:
        return ""

    step = max(1, len(readings) // 50)
    sampled = readings[::step]

    moistures = [r.moisture_pct for r in sampled]
    mn, mx = min(moistures), max(moistures)
    rng = mx - mn or 1.0

    pad = 2
    iw = width - pad * 2
    ih = height - pad * 2

    points = []
    for i, r in enumerate(sampled):
        x = pad + (i / (len(sampled) - 1)) * iw
        y = pad + ih - ((r.moisture_pct - mn) / rng) * ih
        points.append(f"{x:.1f},{y:.1f}")

    pts = " ".join(points)
    return (
        f'<svg width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" class="block">'
        f'<polyline fill="none" stroke="{color}" stroke-width="1.5" '
        f'stroke-linecap="round" stroke-linejoin="round" points="{pts}"/>'
        f"</svg>"
    )


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------


def authenticate(email: str, password: str) -> str:
    """Sign in with email + password via Supabase Auth.

    Returns the access_token JWT on success.
    Raises on invalid credentials or network error.
    """
    client = _get_auth_client()
    response = client.auth.sign_in_with_password(
        {"email": email, "password": password}
    )
    return response.session.access_token


def verify_token(token: str) -> dict | None:
    """Verify a Supabase JWT using the JWKS discovery endpoint.

    Uses asymmetric key verification (ES256/RS256) with the public key
    fetched from Supabase's .well-known/jwks.json endpoint.  The JWKS
    client caches keys for 10 minutes.

    Returns the payload dict on success, or None if the token is
    invalid / expired.
    """
    try:
        jwks_client = _get_jwks_client()
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256", "RS256"],
            audience="authenticated",
        )
        return payload
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Database queries
# ---------------------------------------------------------------------------


def _row_to_reading(row: dict) -> Reading:
    return Reading(
        moisture_pct=row["moisture_pct"],
        battery=row.get("battery") or 0,
        moisture_raw=row.get("moisture_raw") or 0,
        recorded_at=row["recorded_at"],
    )


def get_all_plants() -> list[Plant]:
    """All plants with current sensor, latest reading, and 7-day history.

    Issues 3 queries: current_plants, current_sensors, readings (7 days).
    """
    client = _get_data_client()

    plants_res = (
        client.table("current_plants").select("*").order("plant_id").execute()
    )

    sensors_res = (
        client.table("current_sensors").select("*").order("sensor_id").execute()
    )
    sensor_by_plant: dict[int, dict] = {
        s["plant_id"]: s for s in sensors_res.data
    }

    since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    readings_res = (
        client.table("readings")
        .select("sensor_id, moisture_pct, battery, moisture_raw, recorded_at")
        .gte("recorded_at", since)
        .order("recorded_at")
        .limit(5000)
        .execute()
    )

    readings_by_sensor: dict[int, list[Reading]] = {}
    for row in readings_res.data:
        sid = row["sensor_id"]
        readings_by_sensor.setdefault(sid, []).append(_row_to_reading(row))

    plants: list[Plant] = []
    for p in plants_res.data:
        sensor = sensor_by_plant.get(p["plant_id"])
        sensor_id = sensor["sensor_id"] if sensor else 0
        history = readings_by_sensor.get(sensor_id, [])

        plants.append(
            Plant(
                plant_id=p["plant_id"],
                sensor_id=sensor_id,
                plant_name=p["plant_name"],
                plant_position=p.get("plant_position") or "",
                ideal_min=p["ideal_min"],
                ideal_max=p["ideal_max"],
                water_below=p["water_below"],
                latest=history[-1] if history else None,
                history=history,
            )
        )

    return plants


def get_plant_card(plant_id: int) -> Plant | None:
    """Single plant with sensor, latest reading, and 7-day history.

    Used by the HTMX card-refresh endpoint.
    """
    client = _get_data_client()

    plant_res = (
        client.table("current_plants")
        .select("*")
        .eq("plant_id", plant_id)
        .execute()
    )
    if not plant_res.data:
        return None
    p = plant_res.data[0]

    sensor_res = (
        client.table("current_sensors")
        .select("*")
        .eq("plant_id", plant_id)
        .limit(1)
        .execute()
    )
    sensor_id = sensor_res.data[0]["sensor_id"] if sensor_res.data else 0

    since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    readings_res = (
        client.table("readings")
        .select("sensor_id, moisture_pct, battery, moisture_raw, recorded_at")
        .eq("sensor_id", sensor_id)
        .gte("recorded_at", since)
        .order("recorded_at")
        .execute()
    )
    history = [_row_to_reading(r) for r in readings_res.data]

    return Plant(
        plant_id=p["plant_id"],
        sensor_id=sensor_id,
        plant_name=p["plant_name"],
        plant_position=p.get("plant_position") or "",
        ideal_min=p["ideal_min"],
        ideal_max=p["ideal_max"],
        water_below=p["water_below"],
        latest=history[-1] if history else None,
        history=history,
    )
