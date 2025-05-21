import json
import os

import pandas as pd
import yfinance as yf

HYPERPARAMS_PATH = "hyperparams.json"
DATA_DIR = "data"


def load_hyperparams(path=HYPERPARAMS_PATH):
    with open(path) as f:
        return json.load(f)


def save_hyperparams(ma_window, threshold, path=HYPERPARAMS_PATH):
    with open(path, "w") as f:
        json.dump(
            {"MA_WINDOW": int(ma_window), "THRESHOLD": float(threshold)}, f, indent=2
        )


def ensure_symbol_data(symbol, data_dir=DATA_DIR):
    os.makedirs(data_dir, exist_ok=True)
    fname = os.path.join(data_dir, symbol.replace("^", "").lower() + ".csv")

    if os.path.exists(fname):
        df = pd.read_csv(fname, parse_dates=["Date"], index_col="Date")
        today = pd.Timestamp.today().normalize()
        if not df.empty and df.index[-1].normalize() >= today:
            return df
    # download and cache
    df = yf.download(
        symbol, period="max", interval="1d", progress=False, auto_adjust=False
    )
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] for col in df.columns.values]
    df.index.name = "Date"
    df.to_csv(fname)
    df = pd.read_csv(fname, parse_dates=["Date"], index_col="Date")
    return df
