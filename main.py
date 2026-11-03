from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, Response
from contextlib import asynccontextmanager
from collections import defaultdict
from typing import Optional
import pandas as pd
import logging
import time
import re

from dashboard import render_dashboard
from pages import render_driver_profile, render_drivers, render_home, render_races

# ─────────── Logging ───────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("netflix_f1_nexus")

# ───────────Constants ──────────
CSV_TELEMETRY_PATH = "f1_nexus_contacts.csv"
CSV_RACES_PATH = "f1_nexus_races.csv"
RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_MAX_REQUESTS = 30
SAFE_STRING_PATTERN = re.compile(r"^[a-zA-Z0-9\s\-]+$")
INTEGER_TELEMETRY_COLUMNS = {
    "car_number": "Int64", "wdc_count": "Int64", "f1_seasons": "Int64",
    "podiums": "Int64", "poles": "Int64",
}

# ─────────── Rate limiter (in-memory, per IP) ───────────

# For rate limiter responsible for per-IP request throttling
# using defaultdict via in-memory store to do prevent API abuse
_throttle_registry: dict[str, list[float]] = defaultdict(list)


def _is_throttled(client_ip: str) -> bool:
    # For _is_throttled responsible for sliding window rate limit check
    # using timestamp list via _throttle_registry to do enforce request ceiling
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW_SECONDS
    _throttle_registry[client_ip] = [
        ts for ts in _throttle_registry[client_ip] if ts > window_start
    ]
    if len(_throttle_registry[client_ip]) >= RATE_LIMIT_MAX_REQUESTS:
        return True
    _throttle_registry[client_ip].append(now)
    return False


def _sanitize_param(value: str) -> str:
    # For _sanitize_param responsible for stripping unsafe characters from path params
    # using regex via SAFE_STRING_PATTERN to do prevent injection via URL
    stripped = value.strip()
    if not SAFE_STRING_PATTERN.match(stripped):
        raise HTTPException(
            status_code=400,
            detail="Invalid characters detected in parameter."
        )
    return stripped


# ─────────── Data layer ───────────
_pit_wall_dataframe: pd.DataFrame = pd.DataFrame()
_race_calendar_dataframe: pd.DataFrame = pd.DataFrame()


def _load_telemetry() -> pd.DataFrame:
    # For _load_telemetry responsible for reading and validating the contact CSV
    # using pandas via CSV_TELEMETRY_PATH to do hydrate the in-memory pit wall dataframe
    required_columns = {
        "id", "contact_name", "company",
        "f1_team", "role", "partnership_type", "country"
    }
    try:
        frame = pd.read_csv(CSV_TELEMETRY_PATH, dtype=INTEGER_TELEMETRY_COLUMNS)
        missing = required_columns - set(frame.columns)
        if missing:
            raise ValueError(f"CSV is missing required columns: {missing}")
        frame["f1_team_normalized"] = frame["f1_team"].str.lower().str.strip()
        frame["partnership_type_normalized"] = frame["partnership_type"].str.lower().str.strip()
        logger.info(f"Pit wall loaded — {len(frame)} contacts across {frame['f1_team'].nunique()} teams.")
        return frame
    except FileNotFoundError:
        logger.critical(f"Telemetry feed offline — {CSV_TELEMETRY_PATH} not found.")
        raise


def _load_race_calendar() -> pd.DataFrame:
    # For _load_race_calendar responsible for reading the 2026 Grand Prix calendar CSV
    # using pandas via CSV_RACES_PATH to do hydrate the in-memory race calendar dataframe
    try:
        frame = pd.read_csv(CSV_RACES_PATH, dtype={"laps": "Int64"})
        logger.info(f"Race calendar loaded — {len(frame)} Grands Prix.")
        return frame
    except FileNotFoundError:
        logger.critical(f"Race calendar offline — {CSV_RACES_PATH} not found.")
        raise


# ─────────── Lifespan ───────────
@asynccontextmanager
async def _lifespan(app: FastAPI):
    # For _lifespan responsible for startup and shutdown lifecycle management
    # using asynccontextmanager via FastAPI lifespan to do load data before first request
    global _pit_wall_dataframe, _race_calendar_dataframe
    _pit_wall_dataframe = _load_telemetry()
    _race_calendar_dataframe = _load_race_calendar()
    yield
    logger.info("Netflix F1 Nexus API — shutting down. Lights out.")


# ─────────── App ───────────
app = FastAPI(
    title="Netflix F1 Nexus API",
    description=(
        "A Formula 1 contact directory covering the 2026 grid, every world "
        "champion, team leadership, sponsors and broadcast partners, "
        "including Netflix."
    ),
    version="1.0.0",
    lifespan=_lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ─────────── Middleware ───────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost", "127.0.0.1"],
)


@app.middleware("http")
async def _throttle_gate(request: Request, call_next):
    # For _throttle_gate responsible for enforcing rate limits on every inbound request
    # using client IP via _is_throttled to do reject over-limit callers with 429
    client_ip = request.client.host
    if _is_throttled(client_ip):
        logger.warning(f"Rate limit triggered — IP: {client_ip}")
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests. Pit stop required."},
        )
    response = await call_next(request)
    return response


# ─────────── Routes ───────────
@app.get("/", tags=["Health"])
def root(request: Request):
    # For root responsible for API health check and the browser home page
    # using the Accept header via FastAPI GET to do show the home page to browsers and JSON to Postman
    if "text/html" in request.headers.get("accept", ""):
        return HTMLResponse(content=render_home(_pit_wall_dataframe))
    return {
        "status": "green flag",
        "api": "Netflix F1 Nexus",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/favicon.ico", include_in_schema=False)
@app.get("/apple-touch-icon.png", include_in_schema=False)
@app.get("/apple-touch-icon-precomposed.png", include_in_schema=False)
def _silence_icon_probes():
    # For _silence_icon_probes responsible for answering automatic browser icon requests
    # using an empty 204 response via FastAPI GET to do keep the server log free of 404 noise
    return Response(status_code=204)


@app.get("/contacts", tags=["Contacts"])
def get_all_contacts(
    partnership_type: Optional[str] = Query(None, description="Filter by partnership type"),
    country: Optional[str] = Query(None, description="Filter by country"),
):
    # For get_all_contacts responsible for returning the full contact roster
    # using pandas query filters via optional query params to do support flexible lookups
    frame = _pit_wall_dataframe.copy()

    if partnership_type:
        safe_type = _sanitize_param(partnership_type)
        frame = frame[frame["partnership_type_normalized"] == safe_type.lower()]

    if country:
        safe_country = _sanitize_param(country)
        frame = frame[frame["country"].str.lower() == safe_country.lower()]

    if frame.empty:
        raise HTTPException(status_code=404, detail="No contacts matched your filters.")

    return _serialize(frame)


@app.get("/contacts/random", tags=["Contacts"])
def get_random_contact():
    # For get_random_contact responsible for surfacing a single randomized contact
    # using pandas sample via _pit_wall_dataframe to do satisfy the lab random requirement
    sampled_row = _pit_wall_dataframe.sample(1).iloc[0]
    logger.info(f"Random contact served — {sampled_row['contact_name']} @ {sampled_row['company']}")
    return _clean_row(sampled_row)


@app.get("/contacts/{contact_id}", tags=["Contacts"])
def get_contact_by_id(contact_id: int):
    # For get_contact_by_id responsible for precise single-record lookup
    # using integer ID filter via pandas boolean mask to do return one contact or 404
    if contact_id < 1:
        raise HTTPException(status_code=400, detail="Contact ID must be a positive integer.")
    result = _pit_wall_dataframe[_pit_wall_dataframe["id"] == contact_id]
    if result.empty:
        raise HTTPException(status_code=404, detail=f"No contact found with ID {contact_id}.")
    return _clean_row(result.iloc[0])


@app.get("/contacts/team/{team_name}", tags=["Contacts"])
def get_contacts_by_team(team_name: str):
    # For get_contacts_by_team responsible for filtering contacts by F1 constructor
    # using normalized team name via pandas string match to do return full team roster
    safe_team = _sanitize_param(team_name)
    result = _pit_wall_dataframe[
        _pit_wall_dataframe["f1_team_normalized"] == safe_team.lower()
    ]
    if result.empty:
        raise HTTPException(
            status_code=404,
            detail=f"No contacts found for team '{team_name}'. Check the constructor name."
        )
    return _serialize(result)


@app.get("/analysis", tags=["Analysis"])
def get_analysis():
    # For get_analysis responsible for returning aggregate intelligence on the contact grid
    # using pandas groupby and value_counts via _pit_wall_dataframe to do surface partnership metrics
    df = _pit_wall_dataframe
    top_team = df["f1_team"].value_counts().idxmax()
    dominant_partnership = df["partnership_type"].value_counts().idxmax()

    return {
        "total_contacts": len(df),
        "teams_on_the_grid": int(df.loc[df["role"] == "Driver", "f1_team"].nunique()),
        "countries_represented": df["country"].nunique(),
        "contacts_per_team": df["f1_team"].value_counts().to_dict(),
        "partnership_type_breakdown": df["partnership_type"].value_counts().to_dict(),
        "most_represented_team": top_team,
        "dominant_partnership_type": dominant_partnership,
        "netflix_production_staff": int(
            (df["partnership_type"] == "Broadcast Partner").sum()
        ),
        "world_champions": int((df["is_world_champion"] == "Yes").sum()),
        "total_titles": int(df["wdc_count"].sum()),
        "status_breakdown": df["status"].value_counts().to_dict(),
    }


@app.get("/dashboard", response_class=HTMLResponse, tags=["Dashboard"])
def get_dashboard():
    # For get_dashboard responsible for rendering a visual analytics dashboard
    # using render_dashboard via _pit_wall_dataframe to do serve driver cards and interactive charts as HTML
    return HTMLResponse(content=render_dashboard(_pit_wall_dataframe))


@app.get("/races", response_class=HTMLResponse, tags=["Races"])
def get_race_calendar():
    # For get_race_calendar responsible for the page listing every 2026 Grand Prix
    # using render_races via the race dataframe to do show circuits, winners and race times
    return HTMLResponse(content=render_races(_race_calendar_dataframe, _pit_wall_dataframe))


@app.get("/circuits", tags=["Races"])
def get_circuits():
    # For get_circuits responsible for returning the race calendar as JSON
    # using _serialize via the race dataframe to do expose circuit, city, date and winner per round
    return _serialize(_race_calendar_dataframe)


@app.get("/drivers", response_class=HTMLResponse, tags=["Drivers"])
def get_driver_gallery():
    # For get_driver_gallery responsible for the page with a profile card for every driver
    # using render_drivers via _pit_wall_dataframe to do let the browser filter, search and sort the cards
    return HTMLResponse(content=render_drivers(_pit_wall_dataframe))


@app.get("/drivers/{contact_id}", response_class=HTMLResponse, tags=["Drivers"])
def get_driver_profile(contact_id: int):
    # For get_driver_profile responsible for the profile page of one driver or champion
    # using render_driver_profile via the contact id to do return the page or a 404 for non-drivers
    profile_html = render_driver_profile(_pit_wall_dataframe, contact_id)
    if profile_html is None:
        raise HTTPException(
            status_code=404,
            detail=f"Contact {contact_id} is not a driver. Use /contacts/{contact_id} for the JSON record.",
        )
    return HTMLResponse(content=profile_html)


# ─────────── Serialization helpers ───────────
def _clean_row(row: pd.Series) -> dict:
    # For _clean_row responsible for converting a pandas Series to a clean JSON-safe dict
    # using dict comprehension via row.to_dict to do strip internal normalized columns
    return {
        k: None if pd.isna(v) else (v.item() if hasattr(v, "item") else v)
        for k, v in row.to_dict().items()
        if not k.endswith("_normalized")
    }


def _serialize(frame: pd.DataFrame) -> list[dict]:
    # For _serialize responsible for converting a filtered DataFrame to a JSON-safe list
    # using _clean_row via iterrows to do strip all internal columns before response
    return [_clean_row(row) for _, row in frame.iterrows()]