from datetime import datetime, timedelta, timezone

import pandas as pd
import pytz
import yfinance as yf

from helpers import ensure_symbol_data


def fetch_and_process_spx(ma_window, threshold):
    # --- Current US trading hours ---
    eastern = pytz.timezone("US/Eastern")
    now_et = datetime.now(eastern)
    is_weekday = now_et.weekday() < 5
    after_open = now_et.hour > 9 or (now_et.hour == 9 and now_et.minute >= 30)
    before_close = now_et.hour < 16
    if not (is_weekday and after_open and before_close):
        raise RuntimeError("US stock market is closed.")

    # --- Most up-to-date today value: 1m data last 30min
    now_utc = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    end = now_utc
    start = end - timedelta(minutes=30)
    intraday = yf.download(
        "^GSPC", start=start, end=end, interval="1m", progress=False, auto_adjust=False
    )
    if isinstance(intraday.columns, pd.MultiIndex):
        intraday.columns = [col[0] for col in intraday.columns.values]
    intraday.index.name = "Date"
    tail_close = pd.to_numeric(intraday["Adj Close"], errors="coerce")
    last_val = tail_close.dropna().iloc[-1] if not tail_close.dropna().empty else None

    # --- Base historical daily data
    gspc = ensure_symbol_data("^GSPC")
    gspc = gspc.rename(columns={c: c.replace(" ", "_") for c in gspc.columns})
    today = now_utc.date()
    if last_val is not None:
        if gspc.index[-1].date() == today:
            gspc.iloc[-1, gspc.columns.get_loc("Adj_Close")] = last_val
        elif gspc.index[-1].date() < today:
            new_idx = pd.Timestamp(today)
            new_row = [None] * (gspc.shape[1] - 1) + [last_val]
            gspc.loc[new_idx] = new_row

    # fill missing dates, calculate SMA, bands, signals
    full_idx = pd.date_range(gspc.index.min(), gspc.index.max(), freq="D")
    gspc = gspc.reindex(full_idx).ffill().bfill()

    gspc["SMA"] = gspc["Adj_Close"].rolling(window=ma_window).mean()
    gspc = gspc.dropna(subset=["SMA"])
    gspc["upp"] = gspc["SMA"] * (1 + threshold)
    gspc["low"] = gspc["SMA"] * (1 - threshold)
    gspc["signal"] = None

    # trading signals generation, simple loop
    invested = False
    for idx, row in enumerate(gspc.itertuples(), 0):
        if not invested and row.Adj_Close >= row.upp:
            gspc.iat[idx, gspc.columns.get_loc("signal")] = "BUY"
            invested = True
        elif invested and row.Adj_Close < row.low:
            gspc.iat[idx, gspc.columns.get_loc("signal")] = "SELL"
            invested = False
    return gspc
