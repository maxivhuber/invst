import os

import dash
import pandas as pd
import pandas_market_calendars as mcal
import plotly.graph_objs as go
from dash import Input, Output, callback, dcc, html

from chart import fetch_and_process_symbol, process_signals
from helpers import csv_symbol_name, load_hyperparams

app = dash.Dash(__name__)
app.title = "S&P 500 SMA Trading Demo"

FORM_STYLE = {"marginRight": "1em"}


def serve_layout():
    hyperparams = load_hyperparams()
    return html.Div(
        [
            html.H2(
                "S&P 500 Adj Close, SMA & Trend Signals",
                style={"textAlign": "center", "marginBottom": "1.5em"},
            ),
            dcc.Graph(
                id="price-chart",
                style=dict(
                    width="100vw", height="56.25vw", maxHeight="80vh", maxWidth="100vw"
                ),
            ),
            dcc.Interval(id="refresh", interval=60_000, n_intervals=0),
            html.Div(
                [
                    html.Label("MA Window:", style=FORM_STYLE),
                    dcc.Input(
                        id="ma-window",
                        type="number",
                        value=hyperparams["MA_WINDOW"],
                        min=1,
                        style=FORM_STYLE,
                    ),
                    html.Label("Threshold:", style=FORM_STYLE),
                    dcc.Input(
                        id="threshold",
                        type="number",
                        value=hyperparams["THRESHOLD"],
                        min=0,
                        step=0.0001,
                        style=FORM_STYLE,
                    ),
                    html.Label("Months to show:", style=FORM_STYLE),
                    dcc.Input(
                        id="months-show",
                        type="number",
                        value=hyperparams["DEFAULT_MONTHS_SHOW"],
                        min=1,
                        max=960,
                        step=1,
                        style=FORM_STYLE,
                    ),
                    dcc.Checklist(
                        id="log-scale",
                        options=[{"label": "Log scale", "value": "log"}],
                        value=[],
                        style={"display": "flex", "alignItems": "center", **FORM_STYLE},
                    ),
                    html.Label("Overwrite Latest Value:", style=FORM_STYLE),
                    dcc.Input(
                        id="overwrite-value",
                        type="number",
                        placeholder="Optional",
                        debounce=True,
                        style=FORM_STYLE,
                    ),
                    html.Label("Symbol:", style=FORM_STYLE),
                    dcc.Dropdown(
                        id="symbol-dropdown",
                        options=[
                            {"label": "S&P 500 (^GSPC)", "value": "^GSPC"},
                            {"label": "Nasdaq 100 (^NDX)", "value": "^NDX"},
                        ],
                        value="^GSPC",
                        clearable=False,
                        style={"width": "200px", **FORM_STYLE},
                    ),
                ],
                style={
                    "display": "flex",
                    "justifyContent": "center",
                    "alignItems": "center",
                    "marginTop": "2em",
                    "marginBottom": "1em",
                },
            ),
        ]
    )


app.layout = serve_layout


@callback(
    Output("price-chart", "figure"),
    [
        Input("refresh", "n_intervals"),
        Input("symbol-dropdown", "value"),
        Input("ma-window", "value"),
        Input("threshold", "value"),
        Input("months-show", "value"),
        Input("log-scale", "value"),
        Input("overwrite-value", "value"),
    ],
)
def update_plot(
    _, symbol, ma_window, threshold, months_show, log_scale, overwrite_value
):
    params = load_hyperparams()
    ma_window = ma_window or params["MA_WINDOW"]
    threshold = threshold if threshold is not None else params["THRESHOLD"]
    months_show = (
        months_show
        if isinstance(months_show, int) and months_show > 0
        else params["DEFAULT_MONTHS_SHOW"]
    )

    warning_msgs = []
    try:
        df = fetch_and_process_symbol(
            symbol, symbol, ma_window, threshold, overwrite_value=overwrite_value
        )
    except Exception as e:
        warning_msgs.append(
            "Only historical data is displayed (live fetch failed, check market hours)."
        )
        csv_path = f"./data/base_{csv_symbol_name(symbol)}.csv"
        if not os.path.exists(csv_path):
            return go.Figure(layout=dict(title=f"Error: {e} (no fallback data)"))
        try:
            data = pd.read_csv(csv_path, index_col=0, parse_dates=True)
        except Exception as e2:
            return go.Figure(layout=dict(title=f"Error loading fallback: {e2}"))
        # Normalize columns/index
        data = data.rename(columns={c: c.replace(" ", "_") for c in data.columns})
        data.index = pd.to_datetime(data.index)
        latest_dt = data.index.max().date()
        today = pd.Timestamp.now(tz="US/Eastern").date()
        if today == latest_dt:
            df = process_signals(data, ma_window, threshold, overwrite_value)
        elif today > latest_dt:
            nyse = mcal.get_calendar("NYSE")
            sched = nyse.schedule(
                start_date=latest_dt + pd.Timedelta(days=1), end_date=today
            )
            if not sched.empty:
                next_trading_date = sched.index[0].date()
                if next_trading_date <= today:
                    # Add row for today if not present
                    new_row = data.iloc[-1].copy()
                    new_idx = pd.Timestamp(next_trading_date)
                    data.loc[new_idx] = new_row
                    warning_msgs.append(f"Added placeholder for {next_trading_date}.")
            df = process_signals(data, ma_window, threshold, overwrite_value)

    end = df.index.max()
    start = end - pd.DateOffset(months=int(months_show))
    df = df.loc[start:]
    base_title = "S&P 500 with SMA, Threshold Area and Buy/Sell Signals"
    full_title = base_title
    if warning_msgs:
        full_title += "<br><span style='color:#e67e22'>[{}]</span>".format(
            " ".join(warning_msgs)
        )

    fig = go.Figure(
        [
            go.Scatter(
                x=df.index,
                y=df["Adj_Close"],
                mode="lines",
                name="Adj Close",
                line=dict(color="#222", width=2),
            ),
            go.Scatter(
                x=df.index,
                y=df["SMA"],
                mode="lines",
                name="SMA",
                line=dict(color="#A020F0", width=2, dash="dash"),
            ),
            go.Scatter(
                x=df.index,
                y=df["upp"],
                mode="lines",
                line=dict(width=0),
                showlegend=False,
                hoverinfo="skip",
            ),
            go.Scatter(
                x=df.index,
                y=df["low"],
                mode="lines",
                fill="tonexty",
                fillcolor="rgba(112,128,144,0.18)",
                line=dict(width=0),
                name="Threshold Band",
                showlegend=True,
                hoverinfo="skip",
            ),
            go.Scatter(
                x=df[df.signal == "BUY"].index,
                y=df[df.signal == "BUY"]["Adj_Close"],
                mode="markers",
                marker=dict(
                    symbol="triangle-up",
                    color="#27AE60",
                    size=12,
                    line=dict(width=2, color="#155d27"),
                ),
                name="Buy",
            ),
            go.Scatter(
                x=df[df.signal == "SELL"].index,
                y=df[df.signal == "SELL"]["Adj_Close"],
                mode="markers",
                marker=dict(
                    symbol="triangle-down",
                    color="#C0392B",
                    size=12,
                    line=dict(width=2, color="#7f1d1d"),
                ),
                name="Sell",
            ),
        ]
    )
    fig.update_layout(
        margin=dict(l=30, r=20, b=40, t=40),
        template="plotly_white",
        title=full_title,
        xaxis_title="Date",
        yaxis_title="Price",
        legend=dict(orientation="h", y=1.05, x=1, xanchor="right"),
        yaxis_type="log" if "log" in (log_scale or []) else "linear",
        uirevision="spx-chart-1",
    )
    return fig


server = app.server

if __name__ == "__main__":
    app.run(debug=True)
