import dash
import pandas as pd
import plotly.graph_objs as go
from dash import Input, Output, callback, dcc, html

from chart import fetch_and_process_spx
from helpers import load_hyperparams

app = dash.Dash(__name__)
app.title = "S&P 500 SMA Trading Demo"


def serve_layout():
    hyperparams = load_hyperparams()
    return html.Div(
        [
            html.Div(
                html.H2("S&P 500 Adj Close, SMA & Trend Signals"),
                style={"textAlign": "center", "marginBottom": "1.5em"},
            ),
            dcc.Graph(
                id="price-chart",
                style={
                    "width": "100vw",
                    "height": "56.25vw",
                    "maxHeight": "85vh",
                    "maxWidth": "100vw",
                },
            ),
            dcc.Interval(id="refresh", interval=60 * 1000, n_intervals=0),
            html.Div(
                [
                    html.Label("MA Window:", style={"marginRight": "0.5em"}),
                    dcc.Input(
                        id="ma-window",
                        type="number",
                        value=hyperparams["MA_WINDOW"],
                        min=1,
                        style={"marginRight": "1em"},
                    ),
                    html.Label("Threshold:", style={"marginRight": "0.5em"}),
                    dcc.Input(
                        id="threshold",
                        type="number",
                        value=hyperparams["THRESHOLD"],
                        min=0,
                        step=0.001,
                        style={"marginRight": "1em"},
                    ),
                    html.Label("Months to show:", style={"marginRight": "0.5em"}),
                    dcc.Input(
                        id="months-show",
                        type="number",
                        value=hyperparams["DEFAULT_MONTHS_SHOW"],
                        min=1,
                        max=12 * 80,
                        step=1,
                        style={"marginRight": "1em"},
                    ),
                    dcc.Checklist(
                        id="log-scale",
                        options=[{"label": "Log scale", "value": "log"}],
                        value=[],
                        style={
                            "marginRight": "1em",
                            "display": "flex",
                            "alignItems": "center",
                        },
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


app.layout = serve_layout()


@callback(
    Output("price-chart", "figure"),
    [
        Input("refresh", "n_intervals"),
        Input("ma-window", "value"),
        Input("threshold", "value"),
        Input("months-show", "value"),
        Input("log-scale", "value"),
    ],
)
def update_plot(_, ma_window, threshold, months_show, log_scale):
    # Load defaults if any parameter is missing
    hyperparams = load_hyperparams()
    if ma_window is None:
        ma_window = hyperparams["MA_WINDOW"]
    if threshold is None:
        threshold = hyperparams["THRESHOLD"]
    if months_show is None or not isinstance(months_show, int) or months_show < 1:
        months_show = hyperparams["DEFAULT_MONTHS_SHOW"]

    try:
        gspc = fetch_and_process_spx(ma_window, threshold)
    except Exception as e:
        fig = go.Figure()
        fig.update_layout(title=f"Error: {e}")
        return fig

    end = gspc.index.max()
    start = end - pd.DateOffset(months=int(months_show))
    data = gspc.loc[start:]

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=data.index,
            y=data["Adj_Close"],
            mode="lines",
            name="Adj Close",
            line=dict(color="#222", width=2),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=data.index,
            y=data["SMA"],
            mode="lines",
            name="SMA",
            line=dict(color="#A020F0", width=2, dash="dash"),
        )
    )
    fig.add_traces(
        [
            go.Scatter(
                x=data.index,
                y=data["upp"],
                mode="lines",
                line=dict(width=0),
                showlegend=False,
                hoverinfo="skip",
            ),
            go.Scatter(
                x=data.index,
                y=data["low"],
                mode="lines",
                fill="tonexty",
                fillcolor="rgba(112, 128, 144, 0.18)",
                line=dict(width=0),
                name="Threshold Band",
                showlegend=True,
                hoverinfo="skip",
            ),
        ]
    )
    buys = data[data.signal == "BUY"]
    sells = data[data.signal == "SELL"]
    fig.add_trace(
        go.Scatter(
            x=buys.index,
            y=buys["Adj_Close"],
            mode="markers",
            marker=dict(
                symbol="triangle-up",
                color="#27AE60",
                size=12,
                line=dict(width=2, color="#155d27"),
            ),
            name="Buy",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=sells.index,
            y=sells["Adj_Close"],
            mode="markers",
            marker=dict(
                symbol="triangle-down",
                color="#C0392B",
                size=12,
                line=dict(width=2, color="#7f1d1d"),
            ),
            name="Sell",
        )
    )
    fig.update_layout(
        margin={"l": 30, "r": 20, "b": 40, "t": 40},
        template="plotly_white",
        title="S&P 500 Adj Close with SMA, Threshold Area, Buy/Sell Signals",
        xaxis_title="Date",
        yaxis_title="Price",
        legend=dict(orientation="h", y=1.05, x=1, xanchor="right"),
        yaxis_type="log" if "log" in log_scale else "linear",
        uirevision="spx-chart-1",
    )
    return fig


server = app.server

if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=False)

