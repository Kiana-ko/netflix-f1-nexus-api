import unicodedata
from html import escape

import pandas as pd

# ─────────── Palette ───────────
INK_DARK = "#0e0f13"
INK_LIGHT = "#ffffff"
GHOST_GRAY = "#6c7488"

LIVERY_BY_TEAM = {
    "McLaren": "#ff8000",
    "Mercedes": "#27f4d2",
    "Red Bull Racing": "#3671c6",
    "Ferrari": "#e8002d",
    "Williams": "#64c4ff",
    "Racing Bulls": "#6692ff",
    "Aston Martin": "#229971",
    "Haas": "#e4e4e7",
    "Audi": "#8f98a3",
    "Alpine": "#ff87bc",
    "Cadillac": "#d1a54a",
}
GRID_TEAM_ORDER = list(LIVERY_BY_TEAM)

# Decorative colours for constructors that no longer race, used only for legend cards
HISTORIC_LIVERY_BY_TEAM = {
    "Alfa Romeo": "#a4172b",
    "Maserati": "#2b4b8f",
    "Maserati & Mercedes": "#8fa3b5",
    "Cooper": "#1f6b45",
    "Brabham": "#2a6f8f",
    "BRM": "#3b7a57",
    "Lotus": "#d8b21f",
    "Matra (Tyrrell-run)": "#2c5aa0",
    "Matra": "#2c5aa0",
    "Tyrrell": "#2c5aa0",
    "Benetton": "#1aa7d9",
    "Brawn GP": "#c8e61a",
    "Renault": "#ffd60a",
}

# Public three-letter timing-screen codes for the 2026 grid
DRIVER_CODES = {
    "Lando Norris": "NOR", "Oscar Piastri": "PIA", "Kimi Antonelli": "ANT", "George Russell": "RUS",
    "Max Verstappen": "VER", "Isack Hadjar": "HAD", "Charles Leclerc": "LEC", "Lewis Hamilton": "HAM",
    "Alex Albon": "ALB", "Carlos Sainz": "SAI", "Liam Lawson": "LAW", "Arvid Lindblad": "LIN",
    "Fernando Alonso": "ALO", "Lance Stroll": "STR", "Esteban Ocon": "OCO", "Oliver Bearman": "BEA",
    "Nico Hülkenberg": "HUL", "Gabriel Bortoleto": "BOR", "Pierre Gasly": "GAS", "Franco Colapinto": "COL",
    "Sergio Pérez": "PER", "Valtteri Bottas": "BOT",
}

# Legends whose first three surname letters would collide
LEGEND_CODES = {
    "Michael Schumacher": "MSC", "Graham Hill": "GHI", "Phil Hill": "PHI", "Damon Hill": "DHI",
    "Nico Rosberg": "NRO", "Keke Rosberg": "KRO", "Denny Hulme": "DHU",
}

SORT_LABELS = [
    ("order", "Default"),
    ("number", "Car number"),
    ("titles", "Titles"),
    ("podiums", "Podiums"),
    ("poles", "Poles"),
    ("seasons", "Seasons"),
]

NAV_PAGES = [
    ("Home", "/", "home"), ("Dashboard", "/dashboard", "dashboard"),
    ("Drivers", "/drivers", "drivers"), ("Races", "/races", "races"),
]
NAV_API = [
    ("Contacts", "/contacts", "JSON"),
    ("Random", "/contacts/random", "JSON"),
    ("Circuits", "/circuits", "JSON"),
    ("Analysis", "/analysis", "JSON"),
    ("Docs", "/docs", "Swagger"),
]


def _checkered_flag_svg():
    # For _checkered_flag_svg responsible for the small checkered flag beside the brand name
    # using a 5 by 3 grid of rects via a pole line to do replace the old striped block
    squares = []
    for row in range(3):
        for col in range(5):
            fill = "#f4f3ef" if (row + col) % 2 == 0 else "#15171d"
            squares.append(f'<rect x="{6 + col * 5}" y="{2 + row * 5}" width="5" height="5" fill="{fill}"/>')
    return (
        '<svg class="brand-flag" viewBox="0 0 32 26" width="32" height="26" aria-hidden="true">'
        '<rect x="2" y="1" width="2" height="24" rx="1" fill="#b4b7c1"/>'
        f'<g transform="skewY(-6)" transform-origin="6 2">{"".join(squares)}</g>'
        '<rect x="6" y="2" width="25" height="15" fill="none" stroke="#f4f3ef" stroke-width="0.8" transform="skewY(-6)" transform-origin="6 2"/>'
        "</svg>"
    )


# ─────────── Small value helpers ───────────
def as_int(value, fallback=0):
    # For as_int responsible for turning nullable pandas numbers into plain ints
    # using pd.isna via int() to do keep HTML and hover text free of NaN
    return fallback if pd.isna(value) else int(value)


def as_text(value, fallback=""):
    # For as_text responsible for turning nullable CSV cells into plain strings
    # using pd.isna via str() to do keep blank cells from printing as nan
    return fallback if pd.isna(value) else str(value)


def unroll_champion_ledger(df):
    # For unroll_champion_ledger responsible for exploding pipe-joined title columns into one row per championship
    # using str.split via zip over the four title columns to do feed the ladder, team chart, table and profiles
    ledger_rows = []
    for record in df[df["is_world_champion"] == "Yes"].itertuples():
        years = str(record.championship_years).split(" | ")
        cars = str(record.title_cars).split(" | ")
        teams = str(record.title_teams).split(" | ")
        engineers = str(record.title_engineers).split(" | ")
        for year, car, team, engineer in zip(years, cars, teams, engineers):
            ledger_rows.append(
                {"id": int(record.id), "driver": record.contact_name, "year": int(year),
                 "car": car, "team": team, "engineer": engineer}
            )
    return pd.DataFrame(ledger_rows).sort_values("year").reset_index(drop=True)


# ─────────── Colour maths ───────────
def _channel(hex_pair):
    value = int(hex_pair, 16) / 255
    return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4


def _luminance(hex_color):
    red, green, blue = (_channel(hex_color[i:i + 2]) for i in (1, 3, 5))
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_ratio(color_a, color_b):
    # For contrast_ratio responsible for the WCAG contrast between two hex colours
    # using relative luminance via the 4.5:1 body-text rule to do pick readable card text
    light, dark = sorted((_luminance(color_a), _luminance(color_b)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def _shade(hex_color, keep):
    # For _shade responsible for darkening a hex colour toward black
    # using a channel multiplier to do build the deep end of each card gradient
    channels = [int(int(hex_color[i:i + 2], 16) * keep) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(channels)


def _tint(hex_color, amount):
    # For _tint responsible for lightening a hex colour toward white
    # using a channel blend to do give light liveries a visible gradient without hurting ink contrast
    channels = [int(int(hex_color[i:i + 2], 16) + (255 - int(hex_color[i:i + 2], 16)) * amount) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(channels)


def card_palette(livery):
    # For card_palette responsible for choosing the gradient end and text colour for one livery
    # using contrast_ratio via white-versus-ink to do keep every name readable on its card
    if contrast_ratio(INK_LIGHT, livery) >= contrast_ratio(INK_DARK, livery):
        return livery, _shade(livery, 0.6), INK_LIGHT
    return _tint(livery, 0.3), livery, INK_DARK


def team_livery(team_name):
    # For team_livery responsible for looking up the colour of any constructor
    # using the current and historic dictionaries via a gray fallback to do colour every title consistently
    return LIVERY_BY_TEAM.get(team_name) or HISTORIC_LIVERY_BY_TEAM.get(team_name) or GHOST_GRAY


def driver_livery(record):
    # For driver_livery responsible for picking the colour behind one driver's card
    # using the current team, or the last title team for retired legends, to do tie colour to the car they drove
    if as_text(record["f1_team"]) in LIVERY_BY_TEAM:
        return LIVERY_BY_TEAM[record["f1_team"]]
    last_title_team = as_text(record["title_teams"]).split(" | ")[-1]
    return team_livery(last_title_team)


def driver_code(record):
    # For driver_code responsible for the three-letter timing-screen code
    # using DRIVER_CODES, or the first three letters of the surname, to do label legends the same way
    name = record["contact_name"]
    if name in LEGEND_CODES:
        return LEGEND_CODES[name]
    if name in DRIVER_CODES:
        return DRIVER_CODES[name]
    surname = name.split()[-1]
    plain = unicodedata.normalize("NFKD", surname).encode("ascii", "ignore").decode("ascii")
    return plain[:3].upper()


def ordered_driver_records(df):
    # For ordered_driver_records responsible for the default card order of every driver
    # using team order, car number and first title year to do show the 2026 grid first and legends by era
    drivers = df[df["role"].isin(["Driver", "World Champion"])].copy()
    grid = drivers[drivers["status"] == "Active"].copy()
    grid["team_rank"] = grid["f1_team"].map({name: slot for slot, name in enumerate(GRID_TEAM_ORDER)})
    grid = grid.sort_values(["team_rank", "car_number"])
    legends = drivers[drivers["status"] != "Active"].copy()
    legends["first_title"] = legends["championship_years"].astype(str).str.split(" | ", regex=False).str[0].astype(int)
    legends = legends.sort_values("first_title")
    return [record for _, record in pd.concat([grid, legends]).iterrows()]


# ─────────── Markup pieces ───────────
def team_label_for(record):
    # For team_label_for responsible for the team name shown on a card
    # using the status column via as_text to do label retired drivers as Retired instead of a team
    return as_text(record["f1_team"]) if as_text(record["status"]) == "Active" else "Retired"


def figure_parts(record):
    # For figure_parts responsible for the big number and its caption on a card or profile
    # using the status column via as_int to do show the car number for the grid and title count for legends
    if as_text(record["status"]) == "Active":
        return str(as_int(record["car_number"])), "car number"
    titles = as_int(record["wdc_count"])
    return str(titles), "world title" if titles == 1 else "world titles"


def tags_markup(record):
    # For tags_markup responsible for the small outlined chips under a driver's name
    # using wdc_count and is_rookie via escape to do flag champions and rookies the same way everywhere
    titles = as_int(record["wdc_count"])
    tags = []
    if titles == 1:
        tags.append(f'<span class="tag">World champion {escape(as_text(record["championship_years"]))}</span>')
    elif titles > 1:
        tags.append(f'<span class="tag">{titles}× world champion</span>')
    if as_text(record["is_rookie"]) == "Yes":
        tags.append('<span class="tag">Rookie</span>')
    return "".join(tags)


def driver_card_markup(record, slot):
    # For driver_card_markup responsible for one team-coloured driver card
    # using livery colours and data attributes via escape to do link every card to its profile and let the browser sort it
    livery = driver_livery(record)
    start, end, on_color = card_palette(livery)
    is_grid = as_text(record["status"]) == "Active"
    titles = as_int(record["wdc_count"])
    seasons = as_int(record["f1_seasons"])
    podiums = as_int(record["podiums"])
    poles = as_int(record["poles"])
    car_number = as_int(record["car_number"], fallback=999)
    code = driver_code(record)
    nickname = as_text(record["nickname"])
    team_label = team_label_for(record)
    figure_value, figure_caption = figure_parts(record)
    tags = tags_markup(record)

    search_text = " ".join([record["contact_name"], nickname, team_label, as_text(record["country"]), code]).lower()
    nickname_markup = f'<p class="card-nick">{escape(nickname)}</p>' if nickname else ""
    return (
        f'<li class="driver-card" style="--from:{start};--to:{end};--on:{on_color}" '
        f'data-order="{slot}" data-number="{car_number}" data-titles="{titles}" data-podiums="{podiums}" '
        f'data-poles="{poles}" data-seasons="{seasons}" data-group="{"grid" if is_grid else "legend"}" '
        f'data-champ="{1 if titles else 0}" data-search="{escape(search_text)}">'
        f'<a class="driver-link" href="/drivers/{as_int(record["id"])}" '
        f'aria-label="Open the profile of {escape(record["contact_name"])}">'
        f'<div class="card-top">'
        f'<div class="card-meta"><span>{escape(code)}</span><span>{escape(team_label)}</span></div>'
        f'<div class="card-figure"><b>{figure_value}</b><small>{figure_caption}</small></div>'
        f'<h4 class="card-name">{escape(record["contact_name"])}</h4>{nickname_markup}'
        f'<div class="card-tags">{tags}</div>'
        "</div>"
        '<dl class="card-stats">'
        f"<div><dt>Podiums</dt><dd>{podiums}</dd></div>"
        f"<div><dt>Poles</dt><dd>{poles}</dd></div>"
        f"<div><dt>Seasons</dt><dd>{seasons}</dd></div>"
        "</dl></a></li>"
    )


def card_grid_markup(records):
    # For card_grid_markup responsible for the full grid of driver cards
    # using driver_card_markup via enumerate to do give each card its default sort slot
    cards = "".join(driver_card_markup(record, slot) for slot, record in enumerate(records))
    return f'<ul class="card-grid" id="card-grid">{cards}</ul>'


def card_toolbar_markup(total, show_filters=False, show_search=False):
    # For card_toolbar_markup responsible for the sort, filter and search controls above a card grid
    # using data attributes via aria-pressed buttons to do drive CARD_TOOLS_SCRIPT without any server round trip
    sort_buttons = "".join(
        f'<button type="button" data-sort="{key}" aria-pressed="{"true" if key == "order" else "false"}">{label}</button>'
        for key, label in SORT_LABELS
    )
    filter_markup = ""
    if show_filters:
        filter_buttons = "".join(
            f'<button type="button" data-filter="{key}" aria-pressed="{"true" if key == "all" else "false"}">{label}</button>'
            for key, label in (("all", "All drivers"), ("grid", "2026 grid"), ("champ", "World champions"), ("legend", "Retired"))
        )
        filter_markup = f'<div class="pills" role="group" aria-label="Filter drivers">{filter_buttons}</div>'
    search_markup = ""
    if show_search:
        search_markup = (
            '<label class="search"><span class="visually-hidden">Search drivers</span>'
            '<input type="search" data-search placeholder="Search name, team or country" autocomplete="off"></label>'
        )
    return (
        '<div class="toolbar">'
        f"{filter_markup}{search_markup}"
        f'<div class="pills" role="group" aria-label="Sort drivers"><span class="pill-label">Sort by</span>{sort_buttons}</div>'
        f'<p class="count" id="card-count" aria-live="polite">Showing {total} of {total}</p>'
        "</div>"
    )


def nav_markup(active):
    # For nav_markup responsible for the top navigation bar shared by every page
    # using NAV_PAGES and NAV_API via aria-current to do mark the open page and open JSON in a new tab
    current_attribute = ' aria-current="page"'
    pages = "".join(
        f'<li><a href="{href}"{current_attribute if key == active else ""}>{label}</a></li>'
        for label, href, key in NAV_PAGES
    )
    api = "".join(
        f'<li><a href="{href}" target="_blank" rel="noopener">{label}<span class="badge">{badge}</span></a></li>'
        for label, href, badge in NAV_API
    )
    return (
        '<header class="topbar"><nav aria-label="Main">'
        f'<a class="brand" href="/">{_checkered_flag_svg()}Netflix <span class="f1">F1</span> Nexus</a>'
        f'<ul class="nav-links">{pages}</ul>'
        f'<ul class="nav-links nav-api" aria-label="API endpoints"><li class="nav-label">API</li>{api}</ul>'
        "</nav></header>"
    )


# ─────────── Styles and script ───────────
BASE_STYLES = """
:root {
  color-scheme: dark;
  --asphalt: #0e0f13; --panel: #15171d; --panel-raise: #1b1e26; --hairline: #2a2e39;
  --ink: #eceae4; --ink-soft: #b4b7c1; --ink-faint: #8a8f9c; --signal: #e10600; --f1-red: #e10600;
  --wine: #b01438; --wine-bright: #d11a45;
  --font-display: "Big Shoulders Display", "Arial Narrow", "Roboto Condensed", sans-serif;
  --font-body: "Hanken Grotesk", system-ui, -apple-system, "Segoe UI", sans-serif;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
html { background: var(--asphalt); }
body { background: radial-gradient(900px 380px at 12% -6%, rgba(176, 20, 56, 0.32), transparent 70%), radial-gradient(700px 320px at 92% 0%, rgba(225, 6, 0, 0.14), transparent 70%), var(--asphalt); background-repeat: no-repeat; color: var(--ink); font-family: var(--font-body); font-size: 16px; line-height: 1.5; -webkit-font-smoothing: antialiased; }
a { color: inherit; }
.visually-hidden { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
.topbar { background: var(--asphalt); border-bottom: 1px solid var(--hairline); position: sticky; top: 0; z-index: 20; }
.topbar nav { max-width: 1280px; margin: 0 auto; padding: 4px 16px; display: flex; flex-wrap: wrap; align-items: center; gap: 0 18px; min-height: 56px; }
.brand { display: flex; align-items: center; gap: 10px; font-family: var(--font-display); font-weight: 800; font-size: 1.5rem; letter-spacing: 0.01em; text-decoration: none; }
.brand-flag { flex: none; }
.f1 { color: var(--f1-red); }
.nav-links { display: flex; flex-wrap: wrap; align-items: center; gap: 0 4px; list-style: none; }
.nav-links a { display: flex; align-items: center; gap: 6px; padding: 14px 9px 12px; color: var(--ink-soft); font-size: 0.95rem; text-decoration: none; border-bottom: 2px solid transparent; }
.nav-links a:hover { color: var(--ink); }
.nav-links a[aria-current="page"] { color: var(--ink); border-bottom-color: var(--f1-red); }
.nav-links a:focus-visible, .brand:focus-visible { outline: 2px solid #8ab4ff; outline-offset: -2px; }
.nav-api { margin-left: auto; }
.nav-label { color: var(--ink-faint); font-size: 0.85rem; padding-right: 6px; }
.badge { font-size: 0.7rem; line-height: 1.5; color: var(--ink-faint); border: 1px solid var(--hairline); border-radius: 999px; padding: 0 7px; }
.page { max-width: 1280px; margin: 0 auto; padding: 0 16px 56px; }
section { margin-top: 56px; }
.section-head { display: flex; flex-wrap: wrap; align-items: end; justify-content: space-between; gap: 12px 24px; margin-bottom: 16px; }
h3 { font-family: var(--font-display); font-weight: 700; font-size: 2rem; line-height: 1.05; }
.section-head p { color: var(--ink-faint); max-width: 60ch; font-size: 0.95rem; margin-top: 4px; }
.button { display: inline-block; font: inherit; font-weight: 600; font-size: 0.95rem; text-decoration: none; cursor: pointer; border-radius: 999px; padding: 10px 20px; border: 1px solid var(--ink); }
.button.solid { background: var(--wine); border-color: var(--wine); color: #fff; }
.button.ghost { background: transparent; color: var(--ink); }
.button:hover { background: var(--wine-bright); border-color: var(--wine-bright); color: #fff; }
.button:focus-visible { outline: 2px solid #8ab4ff; outline-offset: 2px; }
footer.page-foot { margin-top: 56px; color: var(--ink-faint); font-size: 0.86rem; }
@media (max-width: 900px) {
  .topbar { position: static; }
  .nav-api { margin-left: 0; }
  .nav-links a { padding: 10px 10px 8px; }
}
@media (max-width: 760px) { h3 { font-size: 1.7rem; } }
@media (prefers-reduced-motion: reduce) { * { transition: none !important; } }
"""

CARD_STYLES = """
.toolbar { display: flex; flex-wrap: wrap; align-items: center; gap: 10px 20px; margin-bottom: 16px; }
.pills { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
.pill-label { color: var(--ink-faint); font-size: 0.88rem; padding-right: 4px; }
.pills button { font: inherit; font-size: 0.88rem; color: var(--ink-soft); background: transparent; border: 1px solid var(--hairline); border-radius: 999px; padding: 6px 14px; cursor: pointer; }
.pills button:hover { color: var(--ink); border-color: var(--wine-bright); }
.pills button[aria-pressed="true"] { color: #fff; background: var(--wine); border-color: var(--wine); }
.pills button:focus-visible, .search input:focus-visible { outline: 2px solid #8ab4ff; outline-offset: 2px; }
.search input { font: inherit; font-size: 0.92rem; color: var(--ink); background: var(--panel); border: 1px solid var(--hairline); border-radius: 999px; padding: 7px 16px; width: min(320px, 100%); }
.search input::placeholder { color: var(--ink-faint); }
.count { color: var(--ink-faint); font-size: 0.88rem; margin-left: auto; }
.card-grid { list-style: none; display: grid; grid-template-columns: repeat(auto-fill, minmax(236px, 1fr)); gap: 14px; }
.driver-card { border-radius: 14px; overflow: hidden; background: var(--panel); border: 1px solid var(--hairline); box-shadow: 0 16px 32px -20px var(--from); }
.driver-card[hidden] { display: none; }
.driver-card:hover { border-color: var(--ink); }
.driver-link { display: flex; flex-direction: column; height: 100%; color: inherit; text-decoration: none; border-radius: inherit; }
.driver-link:focus-visible { outline: 2px solid #8ab4ff; outline-offset: 3px; }
.card-top { position: relative; flex: 1; min-height: 216px; display: flex; flex-direction: column; overflow: hidden; padding: 14px 16px 16px; background: linear-gradient(145deg, var(--from) 0%, var(--to) 100%); color: var(--on); }
.card-meta { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; font-weight: 600; font-size: 0.88rem; }
.card-figure { display: flex; align-items: baseline; gap: 8px; margin: 6px 0 auto; }
.card-figure b { font-family: var(--font-display); font-weight: 800; font-size: 4.6rem; line-height: 0.95; font-variant-numeric: tabular-nums; }
.card-figure small { font-size: 0.82rem; font-weight: 500; }
.card-name { position: relative; margin-top: 12px; font-family: var(--font-display); font-weight: 800; font-size: 1.9rem; line-height: 1; }
.card-nick { position: relative; margin-top: 3px; font-size: 0.92rem; font-weight: 500; }
.card-tags { position: relative; display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
.card-tags:empty { display: none; }
.tag { font-size: 0.78rem; font-weight: 600; line-height: 1.5; padding: 1px 9px; border: 1.5px solid var(--on); border-radius: 999px; }
.card-stats { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); background: var(--panel); }
.card-stats div { padding: 10px 14px 11px; border-left: 1px solid var(--hairline); }
.card-stats div:first-child { border-left: 0; }
.card-stats dt { color: var(--ink-faint); font-size: 0.78rem; }
.card-stats dd { font-family: var(--font-display); font-weight: 700; font-size: 1.6rem; line-height: 1.1; font-variant-numeric: tabular-nums; }
.empty-note { color: var(--ink-faint); padding: 24px 0; }
@media (max-width: 480px) { .card-grid { grid-template-columns: minmax(0, 1fr); } .count { margin-left: 0; } }
"""

CARD_TOOLS_SCRIPT = """
(function () {
  var grid = document.getElementById('card-grid');
  if (!grid) { return; }
  var cards = Array.prototype.slice.call(grid.children);
  var state = { sort: 'order', filter: 'all', query: '' };
  var countNode = document.getElementById('card-count');
  var sortButtons = document.querySelectorAll('[data-sort]');
  var filterButtons = document.querySelectorAll('[data-filter]');
  var searchBox = document.querySelector('[data-search]');

  function passesFilter(card) {
    if (state.filter === 'grid') { return card.dataset.group === 'grid'; }
    if (state.filter === 'legend') { return card.dataset.group === 'legend'; }
    if (state.filter === 'champ') { return card.dataset.champ === '1'; }
    return true;
  }

  function refresh() {
    var ascending = state.sort === 'order' || state.sort === 'number';
    var ordered = cards.slice().sort(function (a, b) {
      var gap = Number(a.dataset[state.sort]) - Number(b.dataset[state.sort]);
      if (gap === 0) { return Number(a.dataset.order) - Number(b.dataset.order); }
      return ascending ? gap : -gap;
    });
    var shown = 0;
    ordered.forEach(function (card) {
      var visible = passesFilter(card) && card.dataset.search.indexOf(state.query) !== -1;
      card.hidden = !visible;
      if (visible) { shown += 1; }
      grid.appendChild(card);
    });
    if (countNode) { countNode.textContent = 'Showing ' + shown + ' of ' + cards.length; }
    var emptyNode = document.getElementById('card-empty');
    if (emptyNode) { emptyNode.hidden = shown !== 0; }
  }

  function press(buttons, chosen) {
    buttons.forEach(function (other) { other.setAttribute('aria-pressed', other === chosen ? 'true' : 'false'); });
  }

  sortButtons.forEach(function (button) {
    button.addEventListener('click', function () { state.sort = button.dataset.sort; press(sortButtons, button); refresh(); });
  });
  filterButtons.forEach(function (button) {
    button.addEventListener('click', function () { state.filter = button.dataset.filter; press(filterButtons, button); refresh(); });
  });
  if (searchBox) {
    searchBox.addEventListener('input', function () { state.query = searchBox.value.trim().toLowerCase(); refresh(); });
  }
})();
"""


def page_shell(title, body, active, styles="", script=""):
    # For page_shell responsible for wrapping any page body in the shared head, nav and fonts
    # using BASE_STYLES and CARD_STYLES via one f-string to do give every page the same look and navigation
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Big+Shoulders+Display:wght@700;800&family=Hanken+Grotesk:wght@400;500;600&display=swap" rel="stylesheet">
<style>{BASE_STYLES}{CARD_STYLES}{styles}</style>
</head>
<body>
{nav_markup(active)}
<main class="page">
{body}
</main>
<script>{CARD_TOOLS_SCRIPT}{script}</script>
</body>
</html>"""