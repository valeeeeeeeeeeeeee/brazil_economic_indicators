"""
Brazil Economic Indicators — Central Bank of Brazil (BCB)
Data: IPCA (inflation), Selic (interest rate) and Dollar (exchange rate) via BCB public API
"""

import requests
import pandas as pd
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
# 4. COMPUTE SELIC CUMULATIVE RATE
#    Uses compound formula: (1 + r/100) multiplied across all periods,
#    then converted back to percentage.  Reset is per calendar year so
#    the tooltip always shows the year-to-date accumulated figure.
# ─────────────────────────────────────────────

selic = selic.sort_values("date").reset_index(drop=True)
selic["Selic_Cumulative"] = (
    selic.groupby("year")["Selic"]
         .transform(lambda x: ((1 + x / 100).cumprod() - 1) * 100)
)

# ─────────────────────────────────────────────
# 5. INTERACTIVE CHARTS WITH PLOTLY
# ─────────────────────────────────────────────

print("\nGenerating interactive chart...")

fig = make_subplots(
    rows=3, cols=1,
    shared_xaxes=True,          # Syncs zoom on the X axis across all 3 charts
    vertical_spacing=0.08,
    subplot_titles=(
        "IPCA — Monthly Inflation (%)",
        "Selic Rate (%)",
        "Exchange Rate — Dollar (BRL)"
    )
)

hover_template = "<b>Date:</b> %{x|%m/%d/%Y}<br><b>Value:</b> %{y:.2f}"

# --- Chart 1: IPCA ---
fig.add_trace(
    go.Scatter(
        x=ipca["date"], y=ipca["IPCA"],
        mode="lines", name="IPCA",
        line=dict(color="tomato", width=2),
        fill="tozeroy", fillcolor="rgba(255, 99, 71, 0.15)",
        hovertemplate=hover_template + "%<extra></extra>"
    ),
    row=1, col=1
)
# Zero reference line on IPCA
fig.add_hline(y=0, line_dash="dash", line_color="black", line_width=1, opacity=0.5, row=1, col=1)

# --- Chart 2: Selic ---
# customdata carries the cumulative rate so we can show it in the hover tooltip
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

# --- Chart 3: Dollar ---
fig.add_trace(
    go.Scatter(
        x=dolar["date"], y=dolar["Dollar"],
        mode="lines", name="Dollar",
        line=dict(color="seagreen", width=2),
        fill="tozeroy", fillcolor="rgba(46, 139, 87, 0.15)",
        hovertemplate=(
            "<b>Date:</b> %{x|%m/%d/%Y}<br>"
            "<b>Value:</b> R$ %{y:.2f}"
            "<extra></extra>"
        )
    ),
    row=3, col=1
)

# --- General Layout ---
fig.update_layout(
    title=dict(
        text="Brazil Economic Indicators (2017 – present)",
        font=dict(size=20),
        x=0.5                   # Center the title
    ),
    height=900,
    showlegend=False,
    hovermode="x unified",      # Vertical crosshair aligned across all subplots
    plot_bgcolor="white"
)

# Grid lines
fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor="rgba(200, 200, 200, 0.3)")
fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor="rgba(200, 200, 200, 0.3)")

# Save as HTML (open in any browser)
output_html = "brazil_indicators_interactive.html"
fig.write_html(output_html)
print(f"Interactive chart saved as '{output_html}'")

# Open automatically in the default browser
fig.show()