"""
moist -- Soil Humidity Monitor Dashboard
FastAPI + Jinja2 + HTMX, backed by Supabase.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Request, HTTPException, Form, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from db import (
    verify_token,
    authenticate,
    get_all_plants,
    get_plant_card,
    generate_sparkline_svg,
)

app = FastAPI(title="moist")

BASE_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

templates = Jinja2Templates(directory=BASE_DIR / "templates")

ACCESS_TOKEN_COOKIE = "access_token"


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------


def _get_user(request: Request) -> dict | None:
    """Extract and verify the JWT from the cookie. Returns payload or None."""
    token = request.cookies.get(ACCESS_TOKEN_COOKIE)
    if not token:
        return None
    return verify_token(token)


def _auth_failed_response(request: Request) -> Response:
    """Return an appropriate redirect for unauthenticated requests.

    Regular requests get a 302 redirect.
    HTMX requests get a 200 with HX-Redirect header so HTMX can handle it
    client-side without a full-page error.
    """
    if request.headers.get("HX-Request"):
        response = Response(status_code=200)
        response.headers["HX-Redirect"] = "/login"
        return response
    return RedirectResponse("/login", status_code=302)


# ---------------------------------------------------------------------------
# Public routes (no auth)
# ---------------------------------------------------------------------------


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = ""):
    """Render the login form."""
    if _get_user(request):
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse(
        "login.html", {"request": request, "error": error}
    )


@app.post("/login")
async def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
):
    """Authenticate with Supabase and set the session cookie."""
    try:
        access_token = authenticate(email, password)
    except Exception:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid email or password."},
            status_code=401,
        )

    response = RedirectResponse("/", status_code=302)
    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE,
        value=access_token,
        httponly=True,
        secure=os.environ.get("RAILWAY_ENVIRONMENT") is not None,
        samesite="lax",
        max_age=60 * 60 * 24 * 7,  # 7 days
    )
    return response


@app.post("/logout")
async def logout():
    """Clear the session cookie and redirect to login."""
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie(ACCESS_TOKEN_COOKIE)
    return response


@app.get("/health")
async def health():
    """Healthcheck endpoint for Railway."""
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Protected routes (require auth)
# ---------------------------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard -- renders all plant cards."""
    if not _get_user(request):
        return _auth_failed_response(request)

    plants = get_all_plants()
    healthy = sum(1 for p in plants if p.status["label"] == "Healthy")
    needs_attention = len(plants) - healthy

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "plants": plants,
            "healthy_count": healthy,
            "needs_attention": needs_attention,
            "generate_sparkline_svg": generate_sparkline_svg,
        },
    )


@app.get("/api/plant/{plant_id}", response_class=HTMLResponse)
async def plant_card_partial(request: Request, plant_id: int):
    """Single plant card HTML partial for HTMX polling."""
    if not _get_user(request):
        return _auth_failed_response(request)

    plant = get_plant_card(plant_id)
    if not plant:
        raise HTTPException(status_code=404, detail="Plant not found")

    return templates.TemplateResponse(
        "partials/plant_card.html",
        {
            "request": request,
            "plant": plant,
            "generate_sparkline_svg": generate_sparkline_svg,
        },
    )
