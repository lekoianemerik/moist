"""
Mock data for development -- matches the Supabase schema from project-overview.md.
Will be replaced with real Supabase queries once the database is wired up.
"""

import random
import math
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field


@dataclass
class Reading:
    moisture: float
    battery: int
    raw_value: int
    recorded_at: str


@dataclass
class Plant:
    id: str
    name: str
    location: str
    plant_type: str
    ideal_min: int
    ideal_max: int
    water_below: int
    avg_daily_drop: float
    latest: Reading = field(default=None)
    history: list[Reading] = field(default_factory=list)

    @property
    def status(self) -> dict:
        """Return status label, text color class, and bg color class."""
        m = self.latest.moisture
        if m <= self.water_below:
            return {"label": "Dry!", "text": "text-red-600 dark:text-red-400", "bg": "bg-red-100 dark:bg-red-950/60"}
        if m < self.ideal_min:
            return {"label": "Needs Water", "text": "text-amber-600 dark:text-amber-400", "bg": "bg-amber-100 dark:bg-amber-950/60"}
        if m > self.ideal_max:
            return {"label": "Overwatered", "text": "text-blue-600 dark:text-blue-400", "bg": "bg-blue-100 dark:bg-blue-950/60"}
        return {"label": "Healthy", "text": "text-emerald-600 dark:text-emerald-400", "bg": "bg-emerald-100 dark:bg-emerald-950/60"}

    @property
    def bar_color(self) -> str:
        m = self.latest.moisture
        if m <= self.water_below:
            return "bg-red-500"
        if m < self.ideal_min:
            return "bg-amber-500"
        return "bg-emerald-500"

    @property
    def sparkline_color(self) -> str:
        m = self.latest.moisture
        if m <= self.water_below:
            return "#ef4444"
        if m < self.ideal_min:
            return "#f59e0b"
        return "#22c55e"

    @property
    def battery_icon(self) -> str:
        b = self.latest.battery
        if b > 60:
            return "\U0001f50b"  # battery full
        if b > 20:
            return "\U0001faab"  # low battery
        return "\u26a0\ufe0f"    # warning

    @property
    def plant_emoji(self) -> str:
        emojis = {
            "basil": "\U0001f33f",
            "fern": "\U0001f331",
            "succulent": "\U0001fab4",
            "tomato": "\U0001f345",
        }
        return emojis.get(self.plant_type, "\U0001f33f")

    @property
    def time_ago(self) -> str:
        recorded = datetime.fromisoformat(self.latest.recorded_at)
        minutes = int((datetime.now(timezone.utc) - recorded).total_seconds() / 60)
        if minutes < 1:
            return "just now"
        if minutes < 60:
            return f"{minutes}m ago"
        return f"{minutes // 60}h ago"


def _generate_history(start_moisture: float, days: int = 7, per_day: int = 48) -> list[Reading]:
    """Generate fake 7-day history. Trends downward with noise and occasional watering spikes."""
    history = []
    total = days * per_day
    now = datetime.now(timezone.utc)
    moisture = start_moisture
    battery = 95.0

    random.seed(42)  # deterministic so the page looks the same on refresh

    for i in range(total, -1, -1):
        ts = now - timedelta(minutes=i * 30)

        # gradual drying with noise
        moisture -= random.uniform(0, 0.6) + 0.05
        moisture += random.uniform(-0.15, 0.15)

        # watering event roughly every 2.5 days
        if i > 0 and (i % int(per_day * 2.5)) < 1 and moisture < 50:
            moisture += random.uniform(30, 45)

        moisture = max(5.0, min(100.0, moisture))
        battery = max(0.0, battery - random.uniform(0, 0.02))

        history.append(Reading(
            moisture=round(moisture, 1),
            battery=round(battery),
            raw_value=round(3200 - (moisture / 100) * 1800),
            recorded_at=ts.isoformat(),
        ))

    random.seed()  # reset seed
    return history


def generate_sparkline_svg(readings: list[Reading], width: int = 140, height: int = 36, color: str = "#22c55e") -> str:
    """Generate an inline SVG sparkline from a list of readings. Pure Python, no JS."""
    if len(readings) < 2:
        return ""

    # sample down to ~50 points
    step = max(1, len(readings) // 50)
    sampled = readings[::step]

    moistures = [r.moisture for r in sampled]
    mn, mx = min(moistures), max(moistures)
    rng = mx - mn or 1.0

    pad = 2
    iw = width - pad * 2
    ih = height - pad * 2

    points = []
    for i, r in enumerate(sampled):
        x = pad + (i / (len(sampled) - 1)) * iw
        y = pad + ih - ((r.moisture - mn) / rng) * ih
        points.append(f"{x:.1f},{y:.1f}")

    pts = " ".join(points)
    return (
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" class="block">'
        f'<polyline fill="none" stroke="{color}" stroke-width="1.5" '
        f'stroke-linecap="round" stroke-linejoin="round" points="{pts}"/>'
        f'</svg>'
    )


def get_mock_plants() -> list[Plant]:
    """Return 4 fake plants with generated history."""
    configs = [
        ("sensor-01", "Kitchen Basil", "Kitchen windowsill", "basil", 40, 60, 30, 8.0, 72),
        ("sensor-02", "Bathroom Fern", "Bathroom shelf", "fern", 60, 80, 50, 6.0, 80),
        ("sensor-03", "Desk Succulent", "Office desk", "succulent", 10, 25, 10, 3.0, 35),
        ("sensor-04", "Balcony Tomato", "Balcony planter", "tomato", 50, 70, 35, 10.0, 65),
    ]

    plants = []
    for sid, name, loc, ptype, imin, imax, wbelow, drop, start_m in configs:
        history = _generate_history(start_m)
        plants.append(Plant(
            id=sid,
            name=name,
            location=loc,
            plant_type=ptype,
            ideal_min=imin,
            ideal_max=imax,
            water_below=wbelow,
            avg_daily_drop=drop,
            latest=history[-1],
            history=history,
        ))

    return plants
