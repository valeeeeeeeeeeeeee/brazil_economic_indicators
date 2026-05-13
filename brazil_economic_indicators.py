"""
Brazil Economic Indicators — Central Bank of Brazil (BCB)
Data: IPCA (inflation), Selic (interest rate) and Dollar (exchange rate) via BCB public API
"""

import requests
import pandas as pd
import numpy as np
from datetime import datetime
import urllib3
import plotly.graph_objects as go
from plotly.subplots import make_subplots

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ─────────────────────────────────────────────
# 1. FETCH DATA FROM BCB API
# ─────────────────────────────────────────────

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

def fetch_series(code, name, start_date=None, end_date=None):
    url = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados?formato=json"

    if start_date:
        url += f"&dataInicial={start_date}"
    if end_date:
        url += f"&dataFinal={end_date}"

    print(f"Fetching {name}...")
    response = requests.get(url, headers=HEADERS, timeout=30, verify=False)
    response.raise_for_status()

    data = response.json()

    df = pd.DataFrame(data)
    df.columns = ["date", name]
    df["date"] = pd.to_datetime(df["date"], format="%d/%m/%Y")
    df[name] = df[name].astype(float)

    return df

ipca  = fetch_series(433, "IPCA")
selic = fetch_series(11,  "Selic", start_date="01/01/2017")
dolar = fetch_series(1,   "Dollar", start_date="01/01/2017")

# ─────────────────────────────────────────────
# 2. FILTER PERIOD (from 2017 onwards)
# ─────────────────────────────────────────────

start = datetime(2017, 1, 1)
ipca  = ipca[ipca["date"] >= start].reset_index(drop=True)

print(f"\nData loaded from {start.strftime('%m/%d/%Y')} to today.\n")

# ─────────────────────────────────────────────
# 3. STATISTICAL ANALYSIS
# ─────────────────────────────────────────────

current_year   = datetime.now().year
previous_year  = current_year - 1

ipca_year      = ipca[ipca["date"].dt.year == previous_year]
accumulated    = ipca_year["IPCA"].sum()
print(f"Accumulated IPCA in {previous_year}: {accumulated:.2f}%")

peak = dolar.loc[dolar["Dollar"].idxmax()]
print(f"Dollar peak: R$ {peak['Dollar']:.2f} on {peak['date'].strftime('%m/%d/%Y')}")

selic["year"]  = selic["date"].dt.year
selic_avg      = selic.groupby("year")["Selic"].mean().round(2)
print("\nAverage Selic rate by year:")
print(selic_avg.to_string())

# ─────────────────────────────────────────────
# 4. COMPUTE DOLLAR & IPCA MIN / MAX STATS
# ─────────────────────────────────────────────

dolar_max_val  = dolar["Dollar"].max()
dolar_max_date = dolar.loc[dolar["Dollar"].idxmax(), "date"].strftime("%m/%d/%Y")
dolar_min_val  = dolar["Dollar"].min()
dolar_min_date = dolar.loc[dolar["Dollar"].idxmin(), "date"].strftime("%m/%d/%Y")

ipca_max_val   = ipca["IPCA"].max()
ipca_max_date  = ipca.loc[ipca["IPCA"].idxmax(), "date"].strftime("%m/%d/%Y")
ipca_min_val   = ipca["IPCA"].min()
ipca_min_date  = ipca.loc[ipca["IPCA"].idxmin(), "date"].strftime("%m/%d/%Y")

# ─────────────────────────────────────────────
# 5. COMPUTE SELIC CUMULATIVE RATE
# ─────────────────────────────────────────────

selic = selic.sort_values("date").reset_index(drop=True)
selic["Selic_Cumulative"] = (
    selic.groupby("year")["Selic"]
         .transform(lambda x: ((1 + x / 100).cumprod() - 1) * 100)
)

# ─────────────────────────────────────────────
# 6. IPCA ACCUMULATED OVER 12 MONTHS (rolling compound)
#    Each point answers: "What was the total inflation over the
#    past 12 months?"  Uses compound formula: ∏(1 + r_i/100) - 1.
#    The BCB uses exactly this to assess the inflation target.
# ─────────────────────────────────────────────

ipca = ipca.sort_values("date").reset_index(drop=True)

ipca["IPCA_12m"] = (
    (1 + ipca["IPCA"] / 100)
    .rolling(window=12, min_periods=12)
    .apply(lambda x: (x.prod() - 1) * 100, raw=True)
)

ipca_12m_valid    = ipca.dropna(subset=["IPCA_12m"])
ipca_12m_max_val  = ipca["IPCA_12m"].max()
ipca_12m_max_date = ipca.loc[ipca["IPCA_12m"].idxmax(), "date"].strftime("%m/%d/%Y")
ipca_12m_min_val  = ipca["IPCA_12m"].min()
ipca_12m_min_date = ipca.loc[ipca["IPCA_12m"].idxmin(), "date"].strftime("%m/%d/%Y")

print(f"\nIPCA 12-month peak: {ipca_12m_max_val:.2f}% on {ipca_12m_max_date}")
print(f"IPCA 12-month low:  {ipca_12m_min_val:.2f}% on {ipca_12m_min_date}")

# ─────────────────────────────────────────────
# 7. CORRELATION MATRIX
#    Merge all three series by month (inner join) and compute
#    pairwise Pearson correlations.
# ─────────────────────────────────────────────

dolar_monthly = (
    dolar.set_index("date")["Dollar"]
    .resample("ME")
    .last()
    .reset_index()
)
dolar_monthly.columns = ["date", "Dollar"]

for df in [ipca, selic, dolar_monthly]:
    df["month"] = df["date"].dt.to_period("M")

merged = (
    ipca[["month", "IPCA"]]
    .merge(selic[["month", "Selic"]], on="month", how="inner")
    .merge(dolar_monthly[["month", "Dollar"]], on="month", how="inner")
)

corr = merged[["IPCA", "Selic", "Dollar"]].corr()

print("\nCorrelation matrix:")
print(corr.round(3).to_string())

# ─────────────────────────────────────────────
# 8. INTERACTIVE CHARTS WITH PLOTLY
#    Layout — 4 rows:
#      Row 1 — IPCA monthly + IPCA 12-month accumulated (overlay)
#      Row 2 — Selic
#      Row 3 — Dollar
#      Row 4 — Correlation view: Z-score normalized, toggle via legend
# ─────────────────────────────────────────────

print("\nGenerating interactive chart...")

fig = make_subplots(
    rows=4, cols=1,
    shared_xaxes=False,
    vertical_spacing=0.12,
    subplot_titles=(
        "IPCA — Monthly Inflation (%) & 12-Month Accumulated",
        "Selic Rate (%)",
        "Exchange Rate — Dollar (BRL)",
        "Correlation View — Normalized Series  ·  click legend to toggle"
    ),
    row_heights=[0.27, 0.23, 0.23, 0.27]
)

# ── Row 1a: IPCA monthly ─────────────────────────────────────────────
ipca_customdata = np.column_stack([
    np.full(len(ipca), ipca_max_val),
    np.full(len(ipca), ipca_max_date),
    np.full(len(ipca), ipca_min_val),
    np.full(len(ipca), ipca_min_date),
])
fig.add_trace(
    go.Scatter(
        x=ipca["date"], y=ipca["IPCA"],
        mode="lines", name="IPCA Monthly",
        line=dict(color="tomato", width=1.5),
        fill="tozeroy", fillcolor="rgba(255, 99, 71, 0.10)",
        customdata=ipca_customdata,
        hovertemplate=(
            "<b>Date:</b> %{x|%m/%d/%Y}<br>"
            "<b>Monthly:</b> %{y:.2f}%<br>"
            "<b>All-time High:</b> %{customdata[0]:.2f}% on %{customdata[1]}<br>"
            "<b>All-time Low:</b> %{customdata[2]:.2f}% on %{customdata[3]}"
            "<extra></extra>"
        )
    ),
    row=1, col=1
)

# ── Row 1b: IPCA 12-month accumulated (overlay) ──────────────────────
ipca_12m_custom = np.column_stack([
    np.full(len(ipca_12m_valid), ipca_12m_max_val),
    np.full(len(ipca_12m_valid), ipca_12m_max_date),
    np.full(len(ipca_12m_valid), ipca_12m_min_val),
    np.full(len(ipca_12m_valid), ipca_12m_min_date),
])
fig.add_trace(
    go.Scatter(
        x=ipca_12m_valid["date"], y=ipca_12m_valid["IPCA_12m"],
        mode="lines", name="IPCA 12m Accum.",
        line=dict(color="#8B0000", width=2.5, dash="dot"),
        customdata=ipca_12m_custom,
        hovertemplate=(
            "<b>12m Accumulated:</b> %{y:.2f}%<br>"
            "<b>12m Peak:</b> %{customdata[0]:.2f}% on %{customdata[1]}<br>"
            "<b>12m Low:</b> %{customdata[2]:.2f}% on %{customdata[3]}"
            "<extra></extra>"
        )
    ),
    row=1, col=1
)

# BCB inflation target band (3.0 % ± 1.5 pp = 1.5 %–4.5 %)
# Shaded in green so the viewer instantly sees when inflation was on target
fig.add_hrect(
    y0=1.5, y1=4.5,
    fillcolor="rgba(0,180,0,0.07)", line_width=0,
    annotation_text="BCB target band",
    annotation_position="top right",
    annotation_font_size=10,
    annotation_font_color="green",
    row=1, col=1
)
fig.add_hline(y=0, line_dash="dash", line_color="black",
              line_width=0.8, opacity=0.4, row=1, col=1)

# ── Row 2: Selic ─────────────────────────────────────────────────────
fig.add_trace(
    go.Scatter(
        x=selic["date"], y=selic["Selic"],
        mode="lines", name="Selic",
        line=dict(color="steelblue", width=2),
        fill="tozeroy", fillcolor="rgba(70, 130, 180, 0.15)",
        customdata=selic["Selic_Cumulative"],
        hovertemplate=(
            "<b>Date:</b> %{x|%m/%d/%Y}<br>"
            "<b>Rate:</b> %{y:.2f}%<br>"
            "<b>YTD Accumulated:</b> %{customdata:.2f}%"
            "<extra></extra>"
        )
    ),
    row=2, col=1
)

# ── Row 3: Dollar ─────────────────────────────────────────────────────
dolar_customdata = np.column_stack([
    np.full(len(dolar), dolar_max_val),
    np.full(len(dolar), dolar_max_date),
    np.full(len(dolar), dolar_min_val),
    np.full(len(dolar), dolar_min_date),
])
fig.add_trace(
    go.Scatter(
        x=dolar["date"], y=dolar["Dollar"],
        mode="lines", name="Dollar",
        line=dict(color="seagreen", width=2),
        fill="tozeroy", fillcolor="rgba(46, 139, 87, 0.15)",
        customdata=dolar_customdata,
        hovertemplate=(
            "<b>Date:</b> %{x|%m/%d/%Y}<br>"
            "<b>Value:</b> R$ %{y:.2f}<br>"
            "<b>All-time High:</b> R$ %{customdata[0]:.2f} on %{customdata[1]}<br>"
            "<b>All-time Low:</b> R$ %{customdata[2]:.2f} on %{customdata[3]}"
            "<extra></extra>"
        )
    ),
    row=3, col=1
)

# ── Row 4: Correlation view — Z-score normalized series ───────────────
# Z-score normalization ((x - mean) / std) puts all three on one axis.
# The user can click any legend item to hide/show that variable.

def zscore(s):
    return (s - s.mean()) / s.std()

merged_sorted = merged.sort_values("month").copy()
dates_corr    = merged_sorted["month"].dt.to_timestamp()

fig.add_trace(
    go.Scatter(
        x=dates_corr, y=zscore(merged_sorted["IPCA"]),
        mode="lines", name="IPCA (norm.)",
        line=dict(color="tomato", width=2),
        hovertemplate="<b>IPCA (z-score):</b> %{y:.2f}<extra></extra>"
    ),
    row=4, col=1
)
fig.add_trace(
    go.Scatter(
        x=dates_corr, y=zscore(merged_sorted["Selic"]),
        mode="lines", name="Selic (norm.)",
        line=dict(color="steelblue", width=2),
        hovertemplate="<b>Selic (z-score):</b> %{y:.2f}<extra></extra>"
    ),
    row=4, col=1
)
fig.add_trace(
    go.Scatter(
        x=dates_corr, y=zscore(merged_sorted["Dollar"]),
        mode="lines", name="Dollar (norm.)",
        line=dict(color="seagreen", width=2),
        hovertemplate="<b>Dollar (z-score):</b> %{y:.2f}<extra></extra>"
    ),
    row=4, col=1
)
fig.add_hline(y=0, line_dash="dash", line_color="grey",
              line_width=0.8, opacity=0.5, row=4, col=1)

# Pearson r annotations — embedded directly on the chart
r_ipca_selic   = corr.loc["IPCA",  "Selic"]
r_ipca_dollar  = corr.loc["IPCA",  "Dollar"]
r_selic_dollar = corr.loc["Selic", "Dollar"]

fig.add_annotation(
    text=(
        f"r(IPCA × Selic) = {r_ipca_selic:.2f}   "
        f"r(IPCA × Dollar) = {r_ipca_dollar:.2f}   "
        f"r(Selic × Dollar) = {r_selic_dollar:.2f}"
    ),
    xref="paper", yref="paper",
    x=0.01, y=0.01,
    showarrow=False,
    font=dict(size=11, color="#444"),
    bgcolor="rgba(255,255,255,0.80)",
    bordercolor="#ccc",
    borderwidth=1,
    xanchor="left", yanchor="bottom"
)

# ── General layout ────────────────────────────────────────────────────
fig.update_layout(
    title=dict(
        text="Brazil Economic Indicators (2017 – present)",
        font=dict(size=20),
        x=0.5
    ),
    height=1350,
    showlegend=True,
    legend=dict(
        orientation="h",
        yanchor="bottom", y=1.01,
        xanchor="right",  x=1,
        font=dict(size=12),
    ),
    hovermode="x unified",
    plot_bgcolor="white"
)

fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor="rgba(200,200,200,0.3)")
fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor="rgba(200,200,200,0.3)")

# ── Export with injected per-chart range filters ──────────────────────
# Plotly's native rangeselector always attaches to the top-left of the
# entire figure, ignoring subplot position.  The reliable fix is to
# inject plain HTML buttons after the chart is rendered and wire them
# to Plotly.relayout() via JavaScript.
#
# Strategy:
#   1. Render the figure normally (no rangeselector on any axis).
#   2. Inject a <script> block that:
#        a. Reads the subplot bounding boxes from the live layout.
#        b. Creates a <div> of buttons for each subplot.
#        c. Positions each <div> directly below its subplot's x-axis.
#        d. On click, calls Plotly.relayout() targeting only that subplot's
#           xaxis (xaxis, xaxis2, xaxis3, xaxis4).

POST_SCRIPT = """
(function() {
  // Map subplot row → Plotly xaxis key
  var axisKeys = ['xaxis', 'xaxis2', 'xaxis3', 'xaxis4'];
  var labels   = ['1Y', '3Y', '5Y', 'All'];
  var years    = [1, 3, 5, null];   // null = show all

  var gd = document.querySelector('.plotly-graph-div');

  function buildFilters() {
    // Remove any previously injected bars (e.g. on window resize)
    document.querySelectorAll('.custom-range-bar').forEach(function(el) {
      el.remove();
    });

    var layout = gd._fullLayout;
    var wrapper = gd.parentElement;
    var wrapperRect = wrapper.getBoundingClientRect();
    var gdRect     = gd.getBoundingClientRect();

    axisKeys.forEach(function(axKey, idx) {
      var ax = layout[axKey];
      if (!ax || ax.domain === undefined) return;

      // domain is [0..1] fraction of the plot area height
      // _offset and _length are pixel values within the SVG
      var plotTop    = layout._margin.t;
      var plotHeight = layout.height - layout._margin.t - layout._margin.b;
      var domainBottom = ax.domain[0];   // lower fraction = closer to bottom

      // pixel y of the bottom of this subplot's x-axis, relative to the <div>
      var yPx = plotTop + plotHeight * (1 - domainBottom) + 6;

      // x boundaries of the plot area
      var xLeft  = layout._margin.l;
      var xRight = layout.width - layout._margin.r;

      var bar = document.createElement('div');
      bar.className = 'custom-range-bar';
      bar.style.cssText = [
        'position:absolute',
        'display:flex',
        'gap:4px',
        'top:'  + yPx  + 'px',
        'left:' + xLeft + 'px',
        'z-index:10',
      ].join(';');

      var activeBtn = null;

      labels.forEach(function(label, i) {
        var btn = document.createElement('button');
        btn.textContent = label;
        btn.style.cssText = [
          'padding:2px 10px',
          'font-size:11px',
          'font-family:sans-serif',
          'background:white',
          'border:1px solid #ccc',
          'border-radius:3px',
          'cursor:pointer',
          'color:#444',
          'transition:background 0.15s',
        ].join(';');

        btn.addEventListener('mouseenter', function() {
          if (btn !== activeBtn) btn.style.background = '#f0f0f0';
        });
        btn.addEventListener('mouseleave', function() {
          if (btn !== activeBtn) btn.style.background = 'white';
        });

        btn.addEventListener('click', function() {
          // Reset all buttons in this bar
          bar.querySelectorAll('button').forEach(function(b) {
            b.style.background = 'white';
            b.style.fontWeight = 'normal';
            b.style.borderColor = '#ccc';
          });
          btn.style.background   = 'rgba(70,130,180,0.18)';
          btn.style.fontWeight   = '600';
          btn.style.borderColor  = 'steelblue';
          activeBtn = btn;

          var update = {};
          if (years[i] === null) {
            update[axKey + '.autorange'] = true;
            update[axKey + '.range']     = undefined;
          } else {
            var now   = new Date();
            var start = new Date(now.getFullYear() - years[i],
                                 now.getMonth(), now.getDate());
            update[axKey + '.range']     = [start.toISOString(), now.toISOString()];
            update[axKey + '.autorange'] = false;
          }
          Plotly.relayout(gd, update);
        });

        bar.appendChild(btn);
      });

      gd.parentElement.style.position = 'relative';
      gd.parentElement.appendChild(bar);
    });
  }

  // Build after Plotly finishes rendering
  gd.on('plotly_afterplot', function() { buildFilters(); });
  // Rebuild on resize so positions stay correct
  window.addEventListener('resize', function() { buildFilters(); });
  // Initial build (in case afterplot already fired)
  if (gd._fullLayout) buildFilters();
})();
"""

from pathlib import Path
output_html = Path(__file__).parent / "brazil_indicators_interactive.html"
fig.write_html(output_html, post_script=POST_SCRIPT)
print(f"\nInteractive chart saved as '{output_html}'")
fig.show()