from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from contextlib import asynccontextmanager
from collections import defaultdict
from typing import Optional
import plotly.express as px
import plotly.io as pio
import pandas as pd
import logging
import time
import re

# ─────────── Logging ───────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("netflix_f1_nexus")

# ───────────Constants ──────────
CSV_TELEMETRY_PATH = "f1_nexus_contacts.csv"
RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_MAX_REQUESTS = 30
SAFE_STRING_PATTERN = re.compile(r"^[a-zA-Z0-9\s\-]+$")

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


def _load_telemetry() -> pd.DataFrame:
    # For _load_telemetry responsible for reading and validating the contact CSV
    # using pandas via CSV_TELEMETRY_PATH to do hydrate the in-memory pit wall dataframe
    required_columns = {
        "id", "contact_name", "company", "phone",
        "email", "f1_team", "role", "partnership_type", "country"
    }
    try:
        frame = pd.read_csv(CSV_TELEMETRY_PATH)
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


# ─────────── Lifespan ───────────
@asynccontextmanager
async def _lifespan(app: FastAPI):
    # For _lifespan responsible for startup and shutdown lifecycle management
    # using asynccontextmanager via FastAPI lifespan to do load data before first request
    global _pit_wall_dataframe
    _pit_wall_dataframe = _load_telemetry()
    yield
    logger.info("Netflix F1 Nexus API — shutting down. Lights out.")


# ─────────── App ───────────
app = FastAPI(
    title="Netflix F1 Nexus API",
    description=(
        "Internal contact directory for the Netflix × F1 Drive to Survive "
        "production partnership. Manages drivers, team principals, sponsors, "
        "and Netflix production staff across the full grid."
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
def root():
    # For root responsible for API health check
    # using static response via FastAPI GET to do confirm service is live
    return {
        "status": "green flag",
        "api": "Netflix F1 Nexus",
        "version": "1.0.0",
        "docs": "/docs",
    }


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
        "teams_on_the_grid": df["f1_team"].nunique(),
        "countries_represented": df["country"].nunique(),
        "contacts_per_team": df["f1_team"].value_counts().to_dict(),
        "partnership_type_breakdown": df["partnership_type"].value_counts().to_dict(),
        "most_represented_team": top_team,
        "dominant_partnership_type": dominant_partnership,
        "netflix_production_staff": int(
            df[df["company"] == "Netflix Inc"]["contact_name"].count()
        ),
    }


@app.get("/dashboard", response_class=HTMLResponse, tags=["Dashboard"])
def get_dashboard():
    # For get_dashboard responsible for rendering a visual analytics dashboard
    # using plotly via pandas groupby to do serve interactive charts as HTML
    df = _pit_wall_dataframe

    fig_teams = px.bar(
        df["f1_team"].value_counts().reset_index(),
        x="f1_team", y="count",
        title="Contacts per F1 Team",
        color="f1_team",
        color_discrete_sequence=px.colors.qualitative.Bold,
        template="plotly_dark",
    )
    fig_teams.update_layout(showlegend=False, xaxis_title="Team", yaxis_title="Contacts")

    fig_partnership = px.pie(
        df["partnership_type"].value_counts().reset_index(),
        names="partnership_type", values="count",
        title="Partnership Type Breakdown",
        color_discrete_sequence=px.colors.qualitative.Bold,
        template="plotly_dark",
        hole=0.4,
    )

    fig_country = px.bar(
        df["country"].value_counts().reset_index(),
        x="country", y="count",
        title="Contacts by Country",
        color="country",
        color_discrete_sequence=px.colors.qualitative.Pastel,
        template="plotly_dark",
    )
    fig_country.update_layout(showlegend=False, xaxis_title="Country", yaxis_title="Contacts")

    chart_teams = pio.to_html(fig_teams, full_html=False, include_plotlyjs="cdn")
    chart_partnership = pio.to_html(fig_partnership, full_html=False, include_plotlyjs=False)
    chart_country = pio.to_html(fig_country, full_html=False, include_plotlyjs=False)

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Netflix F1 Nexus — Dashboard</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{ background: #0a0a0a; color: #fff; font-family: 'SF Pro Display', -apple-system, sans-serif; padding: 2rem; }}
            h1 {{ font-size: 1.8rem; font-weight: 700; margin-bottom: 0.25rem; letter-spacing: -0.5px; }}
            p.subtitle {{ color: #888; font-size: 0.95rem; margin-bottom: 2rem; }}
            .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; }}
            .card {{ background: #111; border: 1px solid #222; border-radius: 12px; padding: 1.5rem; }}
            .card.full {{ grid-column: 1 / -1; }}
            .stat-row {{ display: flex; gap: 1rem; margin-bottom: 1.5rem; }}
            .stat {{ background: #111; border: 1px solid #222; border-radius: 10px; padding: 1rem 1.5rem; flex: 1; }}
            .stat h2 {{ font-size: 2rem; font-weight: 800; color: #e10600; }}
            .stat p {{ color: #888; font-size: 0.8rem; margin-top: 0.2rem; text-transform: uppercase; letter-spacing: 0.5px; }}
        </style>
    </head>
    <body>
        <h1>Netflix F1 Nexus</h1>
        <p class="subtitle">Drive to Survive — Internal Contact Intelligence Dashboard</p>

        <div class="stat-row">
            <div class="stat"><h2>{len(df)}</h2><p>Total Contacts</p></div>
            <div class="stat"><h2>{df["f1_team"].nunique()}</h2><p>Teams on the Grid</p></div>
            <div class="stat"><h2>{df["country"].nunique()}</h2><p>Countries</p></div>
            <div class="stat"><h2>{int(df[df["company"] == "Netflix Inc"]["contact_name"].count())}</h2><p>Netflix Staff</p></div>
        </div>

        <div class="grid">
            <div class="card full">{chart_teams}</div>
            <div class="card">{chart_partnership}</div>
            <div class="card">{chart_country}</div>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


# ─────────── Serialization helpers ───────────
def _clean_row(row: pd.Series) -> dict:
    # For _clean_row responsible for converting a pandas Series to a clean JSON-safe dict
    # using dict comprehension via row.to_dict to do strip internal normalized columns
    return {k: v for k, v in row.to_dict().items() if not k.endswith("_normalized")}


def _serialize(frame: pd.DataFrame) -> list[dict]:
    # For _serialize responsible for converting a filtered DataFrame to a JSON-safe list
    # using _clean_row via iterrows to do strip all internal columns before response
    return [_clean_row(row) for _, row in frame.iterrows()]