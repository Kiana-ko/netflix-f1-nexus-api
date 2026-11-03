from html import escape

import pandas as pd

from ui_kit import (
    as_int,
    as_text,
    card_grid_markup,
    card_palette,
    card_toolbar_markup,
    driver_card_markup,
    driver_code,
    driver_livery,
    figure_parts,
    ordered_driver_records,
    page_shell,
    tags_markup,
    team_label_for,
    team_livery,
    unroll_champion_ledger,
)

_DRIVER_ROLES = ["Driver", "World Champion"]

# method, path shown, link to open, description, badge
_ENDPOINT_ROWS = [
    ("GET", "/contacts", "/contacts", "Every contact in the directory. Add ?partnership_type= or ?country= to filter.", "JSON"),
    ("GET", "/contacts/random", "/contacts/random", "One random contact. This is the Lab 4 endpoint.", "JSON"),
    ("GET", "/circuits", "/circuits", "The 2026 race calendar: circuit, city, date, winner and race time.", "JSON"),
    ("GET", "/contacts/1", "/contacts/1", "One contact by its id. Id 1 is Lando Norris.", "JSON"),
    ("GET", "/contacts/team/McLaren", "/contacts/team/McLaren", "Everyone linked to one team. Try Ferrari, Mercedes or Retired.", "JSON"),
    ("GET", "/analysis", "/analysis", "Totals for teams, countries, partnerships and world titles.", "JSON"),
]


# ─────────── Home ───────────
_HOME_STYLES = """
header.hero { display: grid; grid-template-columns: minmax(0, 1fr) 280px; gap: 32px; align-items: end; padding: 48px 0 8px; }
h1 { font-family: var(--font-display); font-weight: 800; font-size: clamp(3.4rem, 10vw, 7rem); line-height: 0.9; letter-spacing: 0.005em; }
.status { display: inline-flex; align-items: center; gap: 8px; margin-bottom: 18px; color: var(--ink-soft); font-size: 0.92rem; border: 1px solid var(--hairline); border-radius: 999px; padding: 4px 14px 4px 10px; }
.status i { width: 9px; height: 9px; border-radius: 50%; background: #3ddc84; }
.hero p.lede { margin-top: 18px; max-width: 50ch; color: var(--ink-soft); font-size: 1.08rem; }
.hero-actions { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 24px; }
.hero-card { list-style: none; }
.tiles { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; }
.tile { display: flex; flex-direction: column; gap: 6px; padding: 20px 22px; background: var(--panel); border: 1px solid var(--hairline); border-radius: 12px; text-decoration: none; }
.tile { border-top: 3px solid var(--wine); }
.tile:hover { border-color: var(--wine-bright); }
.tile:focus-visible, .endpoint:focus-visible { outline: 2px solid #8ab4ff; outline-offset: 2px; }
.tile strong { font-family: var(--font-display); font-weight: 800; font-size: 2rem; line-height: 1; display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.tile .badge { font-family: var(--font-body); font-weight: 400; font-size: 0.7rem; }
.tile span { color: var(--ink-faint); font-size: 0.95rem; }
.endpoints { list-style: none; border: 1px solid var(--hairline); border-radius: 12px; overflow: hidden; background: var(--panel); }
.endpoints li + li { border-top: 1px solid var(--hairline); }
.endpoint { display: grid; grid-template-columns: 52px minmax(0, 17rem) minmax(0, 1fr) auto; gap: 6px 18px; align-items: baseline; padding: 14px 20px; text-decoration: none; }
.endpoint:hover { background: var(--panel-raise); }
.method { color: var(--ink-faint); font-size: 0.82rem; font-weight: 600; }
.endpoint code { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.92rem; color: var(--ink); overflow-wrap: anywhere; }
.endpoint .what { color: var(--ink-soft); font-size: 0.93rem; }
.demo { display: grid; grid-template-columns: minmax(0, 320px) minmax(0, 1fr); gap: 24px; align-items: start; background: var(--panel); border: 1px solid var(--hairline); border-radius: 12px; padding: 22px; }
.demo p { color: var(--ink-soft); font-size: 0.95rem; margin: 8px 0 18px; }
.demo pre { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.84rem; line-height: 1.55; color: var(--ink-soft); background: var(--asphalt); border: 1px solid var(--hairline); border-radius: 10px; padding: 14px 16px; max-height: 340px; overflow: auto; white-space: pre-wrap; overflow-wrap: anywhere; }
@media (max-width: 1000px) {
  header.hero { grid-template-columns: minmax(0, 1fr); padding-top: 32px; }
  .hero-card { max-width: 300px; }
  .tiles { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .endpoint { grid-template-columns: 44px minmax(0, 1fr) auto; }
  .endpoint .what { grid-column: 1 / -1; }
  .demo { grid-template-columns: minmax(0, 1fr); }
}
"""

_HOME_SCRIPT = """
(function () {
  var button = document.getElementById('draw-contact');
  var output = document.getElementById('draw-output');
  if (!button || !output) { return; }
  button.addEventListener('click', function () {
    button.disabled = true;
    output.textContent = 'Calling GET /contacts/random ...';
    fetch('/contacts/random', { headers: { Accept: 'application/json' } })
      .then(function (reply) {
        if (reply.status === 429) { throw new Error('Too many requests. Wait a minute and try again.'); }
        if (!reply.ok) { throw new Error('The API answered with status ' + reply.status + '.'); }
        return reply.json();
      })
      .then(function (data) { output.textContent = JSON.stringify(data, null, 2); })
      .catch(function (problem) { output.textContent = problem.message; })
      .then(function () { button.disabled = false; });
  });
})();
"""


def _markup_endpoint_rows():
    # For _markup_endpoint_rows responsible for the clickable list of JSON endpoints
    # using _ENDPOINT_ROWS via escape to do open each endpoint in a new tab
    return "".join(
        f'<li><a class="endpoint" href="{escape(link)}" target="_blank" rel="noopener">'
        f'<span class="method">{method}</span><code>{escape(path)}</code>'
        f'<span class="what">{escape(what)}</span><span class="badge">{badge}</span></a></li>'
        for method, path, link, what, badge in _ENDPOINT_ROWS
    )


def render_home(df):
    # For render_home responsible for the landing page that links to every other page
    # using page_shell via the newest champion card to do let a browser reach the whole API from one place
    ledger = unroll_champion_ledger(df)
    newest_record = df[df["id"] == ledger.iloc[-1]["id"]].iloc[0]
    driver_total = int(df["role"].isin(_DRIVER_ROLES).sum())
    body = f"""
<header class="hero">
<div>
<p class="status"><i aria-hidden="true"></i>API online. Green flag.</p>
<h1>Netflix <span class="f1">F1</span> Nexus</h1>
<p class="lede">A Formula 1 directory: the 2026 grid, every world champion since 1950, and the teams, sponsors and broadcast partners around them.</p>
<div class="hero-actions">
<a class="button solid" href="/dashboard">Open the dashboard</a>
<a class="button ghost" href="/drivers">Browse the drivers</a>
</div>
</div>
<ul class="hero-card">{driver_card_markup(newest_record, 0)}</ul>
</header>

<section>
<div class="section-head"><div><h3>Pages</h3><p>The visual side of the project.</p></div></div>
<div class="tiles">
<a class="tile" href="/dashboard"><strong>Dashboard</strong><span>KPIs, the 2026 grid and charts for every world title.</span></a>
<a class="tile" href="/drivers"><strong>Drivers</strong><span>A profile card for each of the {driver_total} drivers and champions.</span></a>
<a class="tile" href="/races"><strong>Races</strong><span>All 23 Grands Prix of 2026 with circuits, winners and race times.</span></a>
<a class="tile" href="/docs" target="_blank" rel="noopener"><strong>API docs <span class="badge">Swagger</span></strong><span>Try every endpoint from the browser.</span></a>
</div>
</section>

<section>
<div class="section-head"><div><h3>API endpoints</h3><p>Each one opens in a new tab as raw JSON, so this page stays open.</p></div></div>
<ul class="endpoints">{_markup_endpoint_rows()}</ul>
</section>

<section>
<div class="section-head"><div><h3>Try the random contact</h3></div></div>
<div class="demo">
<div>
<strong>GET /contacts/random</strong>
<p>Draws one contact from the directory and shows the JSON the API returns.</p>
<button class="button solid" type="button" id="draw-contact">Draw a random contact</button>
</div>
<pre id="draw-output" aria-live="polite">Press the button to call the endpoint.</pre>
</div>
</section>
"""
    return page_shell("Netflix F1 Nexus", body, "home", _HOME_STYLES, _HOME_SCRIPT)


# ─────────── Races ───────────
_RACES_STYLES = """
.page-head { padding: 44px 0 20px; }
h1 { font-family: var(--font-display); font-weight: 800; font-size: clamp(3rem, 8vw, 6rem); line-height: 0.92; }
.page-head p { margin-top: 14px; max-width: 58ch; color: var(--ink-soft); font-size: 1.05rem; }
.stat { background: var(--panel); border: 1px solid var(--hairline); border-top: 3px solid var(--wine); border-radius: 10px; padding: 16px 18px; }
.stat b { display: block; font-family: var(--font-display); font-weight: 800; line-height: 1; }
.stat span { display: block; margin-top: 6px; color: var(--ink-faint); font-size: 0.9rem; }
.season-strip { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.season-strip .stat b { font-size: 2.2rem; }
.wins { list-style: none; margin-top: 14px; display: grid; gap: 8px; background: var(--panel); border: 1px solid var(--hairline); border-radius: 12px; padding: 16px 20px; }
.wins li { display: grid; grid-template-columns: 150px minmax(0, 1fr) 28px; align-items: center; gap: 14px; font-size: 0.95rem; }
.wins a { text-decoration: none; }
.wins a:hover { text-decoration: underline; }
.wins span.bar { height: 10px; border-radius: 5px; background: var(--stripe); }
.wins b { font-family: var(--font-display); font-size: 1.3rem; text-align: right; }
.race-grid { list-style: none; display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 14px; }
.race-card { display: flex; flex-direction: column; background: var(--panel); border: 1px solid var(--hairline); border-left: 5px solid var(--stripe); border-radius: 12px; padding: 16px 18px; }
.race-card[hidden] { display: none; }
.race-card.next { border-color: var(--wine-bright); border-left-color: var(--wine-bright); }
.race-top { display: flex; justify-content: space-between; align-items: baseline; gap: 10px; color: var(--ink-faint); font-size: 0.9rem; }
.race-top b { font-family: var(--font-display); font-weight: 800; font-size: 2.3rem; line-height: 1; color: var(--ink); }
.race-card h4 { font-family: var(--font-display); font-weight: 800; font-size: 1.7rem; line-height: 1.05; margin-top: 6px; }
.race-track { color: var(--ink-soft); font-size: 0.95rem; margin-top: 4px; }
.race-place { color: var(--ink-faint); font-size: 0.88rem; }
.race-result { margin-top: auto; padding-top: 14px; }
.race-result div { border-top: 1px solid var(--hairline); padding-top: 10px; }
.race-result small { display: block; color: var(--ink-faint); font-size: 0.8rem; }
.race-result a { font-weight: 600; text-decoration: none; }
.race-result a:hover { text-decoration: underline; }
.race-result span { color: var(--ink-soft); font-size: 0.88rem; }
.race-note { margin-top: 24px; color: var(--ink-faint); font-size: 0.88rem; max-width: 80ch; }
@media (max-width: 760px) { .season-strip { grid-template-columns: minmax(0, 1fr); } .wins li { grid-template-columns: 110px minmax(0, 1fr) 24px; } }
"""

_RACES_SCRIPT = """
(function () {
  var buttons = document.querySelectorAll('[data-race-filter]');
  var cards = document.querySelectorAll('.race-card');
  buttons.forEach(function (button) {
    button.addEventListener('click', function () {
      var wanted = button.dataset.raceFilter;
      buttons.forEach(function (other) { other.setAttribute('aria-pressed', other === button ? 'true' : 'false'); });
      cards.forEach(function (card) { card.hidden = wanted !== 'all' && card.dataset.state !== wanted; });
    });
  });
})();
"""


def _race_day(iso_date):
    # For _race_day responsible for turning an ISO date into a short day and month
    # using pd.Timestamp via strftime to do show dates like 1 Nov on the race cards
    stamp = pd.Timestamp(iso_date)
    return f"{stamp.day} {stamp.strftime('%b')}"


def render_races(races, df):
    # For render_races responsible for the 2026 Grand Prix calendar page
    # using the races dataframe via the driver ids to do link winners to their profiles and colour each race by team
    ids_by_name = dict(zip(df["contact_name"], df["id"]))
    finished = races[races["winner"].notna()]
    upcoming = races[races["winner"].isna()]
    next_round = int(upcoming.iloc[0]["round"]) if not upcoming.empty else None
    win_counts = finished["winner"].value_counts()
    team_by_winner = finished.groupby("winner")["winner_team"].first()

    cards = []
    for race in races.itertuples():
        is_done = pd.notna(race.winner)
        stripe = team_livery(race.winner_team) if is_done else "#2a2e39"
        if is_done:
            winner_link = f'<a href="/drivers/{int(ids_by_name[race.winner])}">{escape(race.winner)}</a>' if race.winner in ids_by_name else escape(race.winner)
            result = (
                f"<div><small>Winner</small>{winner_link} <span>{escape(race.winner_team)}</span>"
                f"<small>{int(race.laps)} laps, {escape(race.race_time)}</small></div>"
            )
        else:
            label = "Next race" if race.round == next_round else "Upcoming"
            result = f"<div><small>{label}</small><span>Lights out on {_race_day(race.race_date)}</span></div>"
        next_class = " next" if race.round == next_round else ""
        cards.append(
            f'<li class="race-card{next_class}" style="--stripe:{stripe}" data-state="{"done" if is_done else "upcoming"}">'
            f'<div class="race-top"><b>{int(race.round)}</b><span>{_race_day(race.race_date)}</span></div>'
            f"<h4>{escape(race.grand_prix)}</h4>"
            f'<p class="race-track">{escape(race.circuit)}</p>'
            f'<p class="race-place">{escape(race.city)}, {escape(race.country)}</p>'
            f'<div class="race-result">{result}</div></li>'
        )

    top_wins = int(win_counts.iloc[0])
    win_rows = "".join(
        f'<li style="--stripe:{team_livery(team_by_winner[name])}">'
        + (f'<a href="/drivers/{int(ids_by_name[name])}">{escape(name)}</a>' if name in ids_by_name else escape(name))
        + f'<span class="bar" style="width:{count / top_wins * 100:.0f}%"></span><b>{int(count)}</b></li>'
        for name, count in win_counts.items()
    )
    next_text = "Season complete"
    if next_round is not None:
        next_row = upcoming.iloc[0]
        next_text = f"{next_row['grand_prix'].replace(' Grand Prix', '')}, {_race_day(next_row['race_date'])}"
    leader = win_counts.index[0]

    body = f"""
<div class="page-head">
<h1>Races</h1>
<p>The 2026 calendar with every circuit, the winner of each Grand Prix and the time it took.</p>
</div>
<div class="season-strip">
<div class="stat"><b>{len(finished)} of {len(races)}</b><span>races completed</span></div>
<div class="stat"><b>{escape(next_text)}</b><span>next race</span></div>
<div class="stat"><b>{escape(leader)}</b><span>most wins, {top_wins}</span></div>
</div>
<section>
<div class="section-head"><div><h3>Wins this season</h3></div></div>
<ul class="wins">{win_rows}</ul>
</section>
<section>
<div class="section-head"><div><h3>Calendar</h3></div>
<div class="pills" role="group" aria-label="Filter races">
<button type="button" data-race-filter="all" aria-pressed="true">All races</button>
<button type="button" data-race-filter="done" aria-pressed="false">Completed</button>
<button type="button" data-race-filter="upcoming" aria-pressed="false">Upcoming</button>
</div></div>
<ul class="race-grid">{"".join(cards)}</ul>
<p class="race-note">The Bahrain and Saudi Arabian rounds planned for April were cancelled. The Bahrain Grand Prix was rescheduled and held at Sepang in Malaysia on 4 October. Race winners and times come from F1.com results.</p>
</section>
"""
    return page_shell("Netflix F1 Nexus — Races", body, "races", _RACES_STYLES, _RACES_SCRIPT)


# ─────────── Drivers gallery ───────────
_DRIVERS_STYLES = """
.page-head { padding: 44px 0 24px; }
h1 { font-family: var(--font-display); font-weight: 800; font-size: clamp(3rem, 8vw, 6rem); line-height: 0.92; }
.page-head p { margin-top: 14px; max-width: 56ch; color: var(--ink-soft); font-size: 1.05rem; }
"""


def render_drivers(df):
    # For render_drivers responsible for the gallery of every driver card
    # using ordered_driver_records via the toolbar to do filter, search and sort without reloading
    records = ordered_driver_records(df)
    body = f"""
<div class="page-head">
<h1>Drivers</h1>
<p>The {sum(1 for record in records if record["status"] == "Active")} drivers on the 2026 grid and every world champion since 1950. Open a card for the full profile.</p>
</div>
{card_toolbar_markup(len(records), show_filters=True, show_search=True)}
{card_grid_markup(records)}
<p class="empty-note" id="card-empty" hidden>No driver matches. Clear the search or pick another filter.</p>
"""
    return page_shell("Netflix F1 Nexus — Drivers", body, "drivers", _DRIVERS_STYLES)


# ─────────── Driver profile ───────────
_PROFILE_STYLES = """
.profile-hero { position: relative; overflow: hidden; margin-top: 24px; padding: 22px 28px 30px; border-radius: 16px; color: var(--on); background: linear-gradient(145deg, var(--from) 0%, var(--to) 100%); display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 8px 32px; align-items: end; }
.crumbs { grid-column: 1 / -1; font-size: 0.92rem; font-weight: 500; position: relative; }
.crumbs a { color: var(--on); }
.profile-meta { display: flex; flex-wrap: wrap; gap: 0 18px; font-weight: 600; font-size: 0.98rem; margin-top: 28px; position: relative; }
.profile-hero h1 { font-family: var(--font-display); font-weight: 800; font-size: clamp(2.8rem, 9vw, 5.6rem); line-height: 0.92; position: relative; }
.profile-nick { font-size: 1.1rem; font-weight: 500; margin-top: 6px; position: relative; }
.profile-hero .card-tags { margin-top: 16px; }
.profile-figure { position: relative; text-align: right; }
.profile-figure b { display: block; font-family: var(--font-display); font-weight: 800; font-size: clamp(5rem, 16vw, 10rem); line-height: 0.85; font-variant-numeric: tabular-nums; }
.profile-figure span { font-weight: 600; font-size: 0.95rem; }
.stat-row { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-top: 14px; }
.stat { background: var(--panel); border: 1px solid var(--hairline); border-top: 3px solid var(--wine); border-radius: 10px; padding: 16px 18px; }
.stat b { display: block; font-family: var(--font-display); font-weight: 800; font-size: 2.8rem; line-height: 1; font-variant-numeric: tabular-nums; }
.stat span { display: block; margin-top: 6px; color: var(--ink-faint); font-size: 0.9rem; }
.columns { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.2fr); gap: 16px; margin-top: 16px; }
.panel { background: var(--panel); border: 1px solid var(--hairline); border-radius: 12px; padding: 20px 22px; }
.panel h3 { font-size: 1.6rem; margin-bottom: 10px; }
.facts div { display: flex; justify-content: space-between; gap: 20px; padding: 9px 0; border-top: 1px solid var(--hairline); }
.facts dt { color: var(--ink-faint); font-size: 0.93rem; }
.facts dd { font-weight: 600; text-align: right; }
.record { list-style: none; }
.record li { display: grid; grid-template-columns: 78px minmax(0, 1fr); gap: 14px; align-items: center; padding: 11px 0 11px 14px; border-top: 1px solid var(--hairline); border-left: 4px solid var(--stripe); }
.record b { font-family: var(--font-display); font-weight: 800; font-size: 2rem; line-height: 1; font-variant-numeric: tabular-nums; }
.record strong { display: block; font-weight: 600; }
.record small { color: var(--ink-faint); font-size: 0.88rem; }
.panel p.quiet { color: var(--ink-soft); }
.sub-head { margin-top: 40px; }
.teammates { max-width: 520px; }
.pager { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 40px; }
@media (max-width: 760px) {
  .profile-hero { grid-template-columns: minmax(0, 1fr); padding: 18px 20px 24px; }
    .profile-figure { text-align: left; }
  .profile-figure b { display: inline; font-size: 4.4rem; }
  .profile-figure span { margin-left: 10px; }
  .stat-row { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .columns { grid-template-columns: minmax(0, 1fr); }
}
"""


def _markup_facts(record):
    # For _markup_facts responsible for the car and crew facts list on a profile
    # using as_text via escape to do show only the facts this driver actually has
    is_grid = as_text(record["status"]) == "Active"
    facts = [("Country", as_text(record["country"])), ("Status", as_text(record["status"]))]
    if is_grid:
        facts = [
            ("Team", as_text(record["company"])),
            ("Car", as_text(record["current_car"])),
            ("Race engineer", as_text(record["race_engineer"])),
        ] + facts
    else:
        facts.append(("Contact via", as_text(record["company"])))
    facts.append(("Directory type", as_text(record["partnership_type"])))
    return "".join(
        f"<div><dt>{label}</dt><dd>{escape(value)}</dd></div>" for label, value in facts if value
    )


def _markup_record(record, ledger):
    # For _markup_record responsible for the championship record list on a profile
    # using the title ledger via team_livery to do list each title with its car, team and race engineer
    own_titles = ledger[ledger["id"] == as_int(record["id"])].sort_values("year", ascending=False)
    if own_titles.empty:
        return (
            '<p class="quiet">No world championships yet. '
            f'{as_int(record["podiums"])} podiums and {as_int(record["poles"])} pole positions '
            f'in {as_int(record["f1_seasons"])} {"season" if as_int(record["f1_seasons"]) == 1 else "seasons"}.</p>'
        )
    items = "".join(
        f'<li style="--stripe:{team_livery(row.team)}"><b>{int(row.year)}</b>'
        f"<div><strong>{escape(row.car)}</strong>"
        f"<small>{escape(row.team)}, race engineer {escape(row.engineer)}</small></div></li>"
        for row in own_titles.itertuples()
    )
    return f'<ul class="record">{items}</ul>'


def find_driver(df, contact_id):
    # For find_driver responsible for locating one driver or champion by id
    # using a boolean mask via the role column to do return None for sponsors and staff
    matches = df[(df["id"] == contact_id) & df["role"].isin(_DRIVER_ROLES)]
    return None if matches.empty else matches.iloc[0]


def render_driver_profile(df, contact_id):
    # For render_driver_profile responsible for the full profile page of one driver
    # using the card palette via the title ledger to do show car, crew, titles and teammate in one place
    record = find_driver(df, contact_id)
    if record is None:
        return None
    ledger = unroll_champion_ledger(df)
    livery = driver_livery(record)
    start, end, on_color = card_palette(livery)
    figure_value, figure_caption = figure_parts(record)
    is_grid = as_text(record["status"]) == "Active"
    titles = as_int(record["wdc_count"])
    nickname = as_text(record["nickname"])
    meta_bits = [driver_code(record), team_label_for(record), as_text(record["country"])]
    meta_markup = "".join(f"<span>{escape(bit)}</span>" for bit in meta_bits if bit)

    records = ordered_driver_records(df)
    position = next(slot for slot, other in enumerate(records) if other["id"] == record["id"])
    pager_links = []
    if position > 0:
        before = records[position - 1]
        pager_links.append(f'<a class="button ghost" href="/drivers/{as_int(before["id"])}">Previous: {escape(before["contact_name"])}</a>')
    if position < len(records) - 1:
        after = records[position + 1]
        pager_links.append(f'<a class="button ghost" href="/drivers/{as_int(after["id"])}">Next: {escape(after["contact_name"])}</a>')
    pager_links.append(
        f'<a class="button ghost" href="/contacts/{as_int(record["id"])}" target="_blank" rel="noopener">Open this record as JSON</a>'
    )

    teammates_markup = ""
    if is_grid:
        teammates = [
            other for other in records
            if other["f1_team"] == record["f1_team"] and other["id"] != record["id"] and other["status"] == "Active"
        ]
        if teammates:
            cards = "".join(driver_card_markup(other, slot) for slot, other in enumerate(teammates))
            teammates_markup = (
                '<div class="section-head sub-head"><div><h3>Teammate</h3></div></div>'
                f'<ul class="card-grid teammates">{cards}</ul>'
            )

    nickname_markup = f'<p class="profile-nick">{escape(nickname)}</p>' if nickname else ""
    body = f"""
<div class="profile-hero" style="--from:{start};--to:{end};--on:{on_color}">
<p class="crumbs"><a href="/drivers">Drivers</a> / {escape(record["contact_name"])}</p>
<div>
<p class="profile-meta">{meta_markup}</p>
<h1>{escape(record["contact_name"])}</h1>
{nickname_markup}
<div class="card-tags">{tags_markup(record)}</div>
</div>
<div class="profile-figure"><b>{figure_value}</b><span>{figure_caption}</span></div>
</div>

<div class="stat-row">
<div class="stat"><b>{as_int(record["podiums"])}</b><span>podiums</span></div>
<div class="stat"><b>{as_int(record["poles"])}</b><span>pole positions</span></div>
<div class="stat"><b>{as_int(record["f1_seasons"])}</b><span>seasons in F1</span></div>
<div class="stat"><b>{titles}</b><span>world {"title" if titles == 1 else "titles"}</span></div>
</div>

<div class="columns">
<div class="panel"><h3>{"Car and crew" if is_grid else "Profile"}</h3><dl class="facts">{_markup_facts(record)}</dl></div>
<div class="panel"><h3>Championship record</h3>{_markup_record(record, ledger)}</div>
</div>
{teammates_markup}
<nav class="pager" aria-label="More drivers">{"".join(pager_links)}</nav>
"""
    return page_shell(f"{record['contact_name']} — Netflix F1 Nexus", body, "drivers", _PROFILE_STYLES)