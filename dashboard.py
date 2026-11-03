from html import escape

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

from ui_kit import (
    GHOST_GRAY,
    LIVERY_BY_TEAM,
    as_int,
    card_grid_markup,
    card_toolbar_markup,
    driver_card_markup,
    ordered_driver_records,
    page_shell,
    team_livery,
    unroll_champion_ledger,
)

_PANEL = "#15171d"
_HAIRLINE = "#2a2e39"
_INK = "#eceae4"
_INK_SOFT = "#b4b7c1"
_INK_FAINT = "#8a8f9c"
_STEEL_BLUE = "#3987e5"
_PLOTLY_FONT = "Hanken Grotesk, system-ui, -apple-system, Segoe UI, sans-serif"
_LADDER_TEAMS = ["Ferrari", "McLaren", "Mercedes", "Red Bull Racing", "Williams"]
_LABELED_LEGENDS = {
    "Lewis Hamilton", "Michael Schumacher", "Max Verstappen", "Sebastian Vettel", "Ayrton Senna", "Fernando Alonso",
}
_PLOT_CONFIG = {"displayModeBar": False, "responsive": True}


def _apply_pit_wall_theme(fig, height):
    # For _apply_pit_wall_theme responsible for giving every chart the same quiet broadcast look
    # using update_layout via shared tokens to do keep fonts, grid and tooltips consistent
    fig.update_layout(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=_PLOTLY_FONT, size=12, color=_INK_SOFT),
        margin=dict(l=10, r=24, t=16, b=40),
        hoverlabel=dict(bgcolor="#1b1e26", bordercolor=_HAIRLINE, font=dict(family=_PLOTLY_FONT, size=13, color=_INK)),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, font=dict(size=12, color=_INK_SOFT)),
    )
    fig.update_xaxes(gridcolor=_HAIRLINE, linecolor=_HAIRLINE, zerolinecolor=_HAIRLINE, tickfont=dict(color=_INK_FAINT))
    fig.update_yaxes(gridcolor=_HAIRLINE, linecolor=_HAIRLINE, zerolinecolor=_HAIRLINE, tickfont=dict(color=_INK_SOFT))
    return fig


def _soften_bar_ends(fig):
    # For _soften_bar_ends responsible for rounding the data end of each bar when plotly supports it
    # using update_traces inside try/except via marker_cornerradius to do stay compatible with older plotly
    try:
        fig.update_traces(marker_cornerradius=4, selector=dict(type="bar"))
    except ValueError:
        pass
    return fig


def _figure_title_ladder(ledger):
    # For _figure_title_ladder responsible for plotting every championship as one dot per driver per year
    # using go.Scatter grouped by constructor livery via hovertemplate to do show each team's era at a glance
    driver_order = ledger.groupby("driver")["year"].min().sort_values().index.tolist()
    fig = go.Figure()
    for team in _LADDER_TEAMS + ["Other constructors"]:
        if team == "Other constructors":
            chunk = ledger[~ledger["team"].isin(_LADDER_TEAMS)]
            livery = GHOST_GRAY
        else:
            chunk = ledger[ledger["team"] == team]
            livery = LIVERY_BY_TEAM[team]
        fig.add_trace(
            go.Scatter(
                x=chunk["year"],
                y=chunk["driver"],
                mode="markers",
                name=team,
                marker=dict(size=11, color=livery, line=dict(width=2, color=_PANEL)),
                customdata=chunk[["car", "team", "engineer"]].to_numpy(),
                hovertemplate=(
                    "<b>%{y}</b><br>%{x} world champion<br>"
                    "Car: %{customdata[0]}<br>Team: %{customdata[1]}<br>"
                    "Race engineer: %{customdata[2]}<extra></extra>"
                ),
            )
        )
    newest = ledger.iloc[-1]
    fig.add_annotation(
        x=int(newest["year"]), y=newest["driver"], text="Reigning champion", showarrow=False,
        xanchor="left", xshift=14, font=dict(size=12, color=_INK),
    )
    _apply_pit_wall_theme(fig, height=len(driver_order) * 24 + 110)
    fig.update_xaxes(range=[1947, 2040], dtick=10, showgrid=True, tickformat="d")
    fig.update_yaxes(categoryorder="array", categoryarray=driver_order, autorange="reversed", automargin=True)
    return fig


def _figure_titles_by_team(ledger):
    # For _figure_titles_by_team responsible for ranking constructors by drivers' titles won with them
    # using groupby size via livery colours to do show which teams built the title-winning cars
    tidy = ledger.assign(team=ledger["team"].replace({"Matra (Tyrrell-run)": "Matra"}))
    shared = tidy["team"].str.contains("&")
    tally = tidy[~shared].groupby("team").size().sort_values(ascending=False)
    top_tally = tally.head(8)
    folded = int(tally.iloc[8:].sum()) + int(shared.sum())
    if folded:
        top_tally = pd.concat([top_tally, pd.Series({"Other teams": folded})])
    bar_colors = [team_livery(name) if name != "Other teams" else GHOST_GRAY for name in top_tally.index]
    fig = go.Figure(
        go.Bar(
            x=top_tally.values, y=top_tally.index, orientation="h", marker=dict(color=bar_colors),
            text=top_tally.values, textposition="outside", cliponaxis=False, width=0.55,
            textfont=dict(color=_INK, size=13),
            hovertemplate="<b>%{y}</b><br>%{x} drivers' titles<extra></extra>",
        )
    )
    _apply_pit_wall_theme(fig, height=400)
    fig.update_xaxes(visible=False, range=[0, float(top_tally.max()) * 1.15])
    fig.update_yaxes(autorange="reversed", showgrid=False)
    return _soften_bar_ends(fig)


def _figure_podiums_vs_poles(df):
    # For _figure_podiums_vs_poles responsible for comparing podium and pole counts across drivers
    # using go.Scatter sized by championships via emphasis colouring to do spotlight the current grid against the legends
    drivers = df[df["role"].isin(["Driver", "World Champion"])].copy()
    drivers["podiums"] = drivers["podiums"].astype(float)
    drivers["poles"] = drivers["poles"].astype(float)
    drivers["wdc_count"] = drivers["wdc_count"].fillna(0).astype(float)
    fig = go.Figure()
    for label, mask, ink in (
        ("Retired legends", drivers["status"] != "Active", GHOST_GRAY),
        ("2026 grid", drivers["status"] == "Active", _INK),
    ):
        chunk = drivers[mask]
        shout = chunk["contact_name"].where(chunk["contact_name"].isin(_LABELED_LEGENDS), "")
        shout = shout.str.split().str[-1].fillna("")
        fig.add_trace(
            go.Scatter(
                x=chunk["poles"], y=chunk["podiums"], mode="markers+text", name=label,
                text=shout, textposition="top center", textfont=dict(size=11, color=_INK_SOFT),
                marker=dict(size=9 + chunk["wdc_count"] * 2.2, color=ink, opacity=0.92, line=dict(width=2, color=_PANEL)),
                customdata=chunk[["contact_name", "f1_team", "wdc_count"]].to_numpy(),
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>%{customdata[1]}<br>"
                    "%{y:.0f} podiums, %{x:.0f} poles<br>%{customdata[2]:.0f} titles<extra></extra>"
                ),
            )
        )
    _apply_pit_wall_theme(fig, height=400)
    fig.update_xaxes(title_text="Pole positions", title_font=dict(color=_INK_FAINT), rangemode="tozero")
    fig.update_yaxes(title_text="Podiums", title_font=dict(color=_INK_FAINT), rangemode="tozero")
    return fig


def _figure_ranked_bars(counts, hover_noun, height):
    # For _figure_ranked_bars responsible for drawing one-colour ranked horizontal bars
    # using go.Bar via value labels at the tip to do compare category sizes without a donut
    fig = go.Figure(
        go.Bar(
            x=counts.values, y=counts.index, orientation="h", marker=dict(color=_STEEL_BLUE),
            text=counts.values, textposition="outside", cliponaxis=False, width=0.55,
            textfont=dict(color=_INK, size=13),
            hovertemplate="<b>%{y}</b><br>%{x} " + hover_noun + "<extra></extra>",
        )
    )
    _apply_pit_wall_theme(fig, height=height)
    fig.update_xaxes(visible=False, range=[0, float(counts.max()) * 1.15])
    fig.update_yaxes(autorange="reversed", showgrid=False)
    return _soften_bar_ends(fig)


def _chart_markup(fig, include_plotlyjs):
    # For _chart_markup responsible for turning a figure into an embeddable HTML fragment
    # using pio.to_html via the shared config to do load plotly.js once and reuse it
    return pio.to_html(
        fig, full_html=False, include_plotlyjs="cdn" if include_plotlyjs else False,
        config=_PLOT_CONFIG, default_width="100%",
    )


def _markup_kpis(df):
    # For _markup_kpis responsible for rendering the headline number tiles
    # using data-count attributes via escape to do animate the numbers once on load
    grid_team_total = int(df.loc[df["role"] == "Driver", "f1_team"].nunique())
    tiles = [
        (len(df), "contacts in the directory"),
        (grid_team_total, "teams on the 2026 grid"),
        (int(df["country"].nunique()), "countries represented"),
        (int((df["is_world_champion"] == "Yes").sum()), "world champions"),
        (as_int(df["wdc_count"].sum()), "drivers' titles won"),
        (int((df["partnership_type"] == "Broadcast Partner").sum()), "Netflix production contacts"),
    ]
    return "".join(
        f'<div class="kpi"><b data-count="{value}">{value}</b><span>{escape(label)}</span></div>'
        for value, label in tiles
    )


def _markup_ledger_table(ledger):
    # For _markup_ledger_table responsible for a text version of the championship ladder
    # using escape over each ledger row to do give screen readers and print the same data
    body = "".join(
        f'<tr><td>{int(row.year)}</td><td><a href="/drivers/{int(row.id)}">{escape(row.driver)}</a></td>'
        f"<td>{escape(row.team)}</td><td>{escape(row.car)}</td><td>{escape(row.engineer)}</td></tr>"
        for row in ledger.sort_values("year", ascending=False).itertuples()
    )
    return (
        '<details class="table-view"><summary>View the championships as a table</summary>'
        '<div class="table-scroll"><table><thead><tr><th>Year</th><th>Driver</th><th>Team</th><th>Car</th>'
        f"<th>Race engineer</th></tr></thead><tbody>{body}</tbody></table></div></details>"
    )


_DASHBOARD_STYLES = """
header.hero { display: grid; grid-template-columns: minmax(0, 1fr) 280px; gap: 32px; align-items: end; padding: 44px 0 32px; }
h1 { font-family: var(--font-display); font-weight: 800; font-size: clamp(3rem, 8vw, 6rem); line-height: 0.92; letter-spacing: 0.005em; }
.hero p.lede { margin-top: 16px; max-width: 52ch; color: var(--ink-soft); font-size: 1.05rem; }
.hero-card { list-style: none; }
.kpis { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 12px; }
.kpi { background: var(--panel); border: 1px solid var(--hairline); border-top: 3px solid var(--wine); border-radius: 10px; padding: 16px 18px; }
.kpi b { display: block; font-family: var(--font-display); font-weight: 800; font-size: 2.8rem; line-height: 1; font-variant-numeric: tabular-nums; }
.kpi span { display: block; margin-top: 6px; color: var(--ink-faint); font-size: 0.88rem; line-height: 1.3; }
.more-link { display: inline-block; margin-top: 18px; color: var(--ink-soft); font-size: 0.95rem; }
.more-link:hover { color: var(--ink); }
.chart-card { background: var(--panel); border: 1px solid var(--hairline); border-radius: 12px; padding: 18px 18px 10px; min-width: 0; }
.chart-card h4 { font-weight: 600; font-size: 1.02rem; }
.chart-card p.note { color: var(--ink-faint); font-size: 0.88rem; margin: 2px 0 6px; }
.pair { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; margin-top: 16px; }
.pair.flush { margin-top: 0; }
details.table-view { margin-top: 8px; padding: 10px 0 8px; border-top: 1px solid var(--hairline); }
details.table-view summary { cursor: pointer; color: var(--ink-soft); font-size: 0.9rem; }
details.table-view summary:focus-visible { outline: 2px solid #8ab4ff; outline-offset: 2px; }
.table-scroll { overflow-x: auto; max-height: 420px; margin-top: 10px; }
table { border-collapse: collapse; width: 100%; font-size: 0.88rem; }
th, td { text-align: left; padding: 6px 12px 6px 0; border-bottom: 1px solid var(--hairline); white-space: nowrap; }
th { color: var(--ink-faint); font-weight: 500; position: sticky; top: 0; background: var(--panel); }
td a { text-decoration: none; }
td a:hover { text-decoration: underline; }
@media (max-width: 1000px) {
  header.hero { grid-template-columns: minmax(0, 1fr); padding-top: 32px; }
  .hero-card { max-width: 300px; }
  .kpis { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .pair { grid-template-columns: minmax(0, 1fr); }
}
@media (max-width: 760px) { .kpi b { font-size: 2.3rem; } }
@media (max-width: 480px) { .kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
"""

_DASHBOARD_SCRIPT = """
(function () {
  var calm = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  document.querySelectorAll('[data-count]').forEach(function (node) {
    var target = Number(node.dataset.count);
    if (calm || !target) { return; }
    var started = null;
    function tick(now) {
      if (started === null) { started = now; }
      var progress = Math.min((now - started) / 900, 1);
      node.textContent = Math.round(target * (1 - Math.pow(1 - progress, 3)));
      if (progress < 1) { requestAnimationFrame(tick); }
    }
    node.textContent = '0';
    requestAnimationFrame(tick);
  });
})();
"""


def render_dashboard(df):
    # For render_dashboard responsible for assembling the full analytics page from the contact dataframe
    # using the figure and markup helpers via page_shell to do serve one dashboard with the shared navigation
    ledger = unroll_champion_ledger(df)
    newest = ledger.iloc[-1]
    newest_record = df[df["id"] == newest["id"]].iloc[0]
    grid_records = [record for record in ordered_driver_records(df) if record["status"] == "Active"]
    driver_total = int(df["role"].isin(["Driver", "World Champion"]).sum())
    talent = df[df["role"].isin(["Driver", "World Champion"])]["country"].value_counts().head(10)
    partnership_counts = df["partnership_type"].value_counts()

    ladder_chart = _chart_markup(_figure_title_ladder(ledger), include_plotlyjs=True)
    team_chart = _chart_markup(_figure_titles_by_team(ledger), include_plotlyjs=False)
    scatter_chart = _chart_markup(_figure_podiums_vs_poles(df), include_plotlyjs=False)
    partnership_chart = _chart_markup(
        _figure_ranked_bars(partnership_counts, "contacts", 70 + 40 * len(partnership_counts)), include_plotlyjs=False
    )
    talent_chart = _chart_markup(
        _figure_ranked_bars(talent, "drivers and champions", 70 + 40 * len(talent)), include_plotlyjs=False
    )

    body = f"""
<header class="hero">
<div>
<h1>Dashboard</h1>
<p class="lede">Formula 1 in numbers: the 2026 grid, every world champion since 1950, and the teams, sponsors and broadcast partners around them.</p>
</div>
<ul class="hero-card">{driver_card_markup(newest_record, 0)}</ul>
</header>
<div class="kpis">{_markup_kpis(df)}</div>

<section>
<div class="section-head">
<div><h3>The 2026 grid</h3><p>Every current driver with their car number and career totals. Open a card for the full profile.</p></div>
</div>
{card_toolbar_markup(len(grid_records))}
{card_grid_markup(grid_records)}
<a class="more-link" href="/drivers">Browse all {driver_total} drivers, including every retired champion</a>
</section>

<section>
<div class="section-head"><div><h3>Every world champion</h3><p>One dot per title, coloured by the team that built the car. Hover a dot for the car and race engineer.</p></div></div>
<div class="chart-card">{ladder_chart}{_markup_ledger_table(ledger)}</div>
<div class="pair">
<div class="chart-card"><h4>Titles by team</h4><p class="note">Drivers' championships won in each team's cars.</p>{team_chart}</div>
<div class="chart-card"><h4>Podiums and poles</h4><p class="note">Bubble size grows with the number of titles. The 2026 grid is in white, retired legends in grey.</p>{scatter_chart}</div>
</div>
</section>

<section>
<div class="section-head"><div><h3>Inside the directory</h3><p>Who the {len(df)} contacts are and where the drivers come from.</p></div></div>
<div class="pair flush">
<div class="chart-card"><h4>Contacts by partnership type</h4>{partnership_chart}</div>
<div class="chart-card"><h4>Home countries of drivers and champions</h4>{talent_chart}</div>
</div>
</section>
"""
    return page_shell("Netflix F1 Nexus — Dashboard", body, "dashboard", _DASHBOARD_STYLES, _DASHBOARD_SCRIPT)