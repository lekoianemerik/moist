"""
moist -- Soil Humidity Monitor Dashboard
FastAPI + Jinja2 + HTMX
"""

import os
from pathlib import Path

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from mock_data import get_mock_plants, generate_sparkline_svg

app = FastAPI(title="moist")

BASE_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

templates = Jinja2Templates(directory=BASE_DIR / "templates")

# Load mock plants once at startup
plants = get_mock_plants()
plants_by_id = {p.id: p for p in plants}


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard -- renders all plant cards."""
    healthy = sum(1 for p in plants if p.status["label"] == "Healthy")
    needs_attention = len(plants) - healthy

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "plants": plants,
        "healthy_count": healthy,
        "needs_attention": needs_attention,
        "generate_sparkline_svg": generate_sparkline_svg,
    })


@app.get("/api/plant/{plant_id}", response_class=HTMLResponse)
async def plant_card(request: Request, plant_id: str):
    """Return a single plant card HTML partial (for HTMX polling)."""
    plant = plants_by_id.get(plant_id)
    if not plant:
        raise HTTPException(status_code=404, detail="Plant not found")

    return templates.TemplateResponse("partials/plant_card.html", {
        "request": request,
        "plant": plant,
        "generate_sparkline_svg": generate_sparkline_svg,
    })


@app.get("/health")
async def health():
    """Healthcheck endpoint for Railway."""
    return {"status": "ok"}
