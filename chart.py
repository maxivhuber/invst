from datetime import datetime, timedelta, timezone

import pandas as pd
import pandas_market_calendars as mcal
import pytz
import yfinance as yf

from helpers import ensure_symbol_data


def market_is_open():
    eastern = pytz.timezone("US/Eastern")
    now = datetime.now(eastern)
    nyse = mcal.get_calendar("NYSE")
    # Get today's trading schedule
    schedule = nyse.schedule(start_date=now.date(), end_date=now.date())

    if schedule.empty:
        return False

    open_dt = schedule.iloc[0]["market_open"].tz_convert(eastern)
    close_dt = schedule.iloc[0]["market_close"].tz_convert(eastern)
    return open_dt <= now <= close_dt


def fetch_base_history(symbol):
    """Fetches and formats daily historical data for the given symbol."""
    data = ensure_symbol_data(symbol)
    data = data.rename(columns={c: c.replace(" ", "_") for c in data.columns})
    data.index = pd.to_datetime(data.index)
    return data


def fetch_recent_intraday_close(symbol):
    """Fetches the latest 1m close value from the last 30mins for the symbol."""
    now_utc = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    start = now_utc - timedelta(minutes=30)
    df = yf.download(
        symbol,
        start=start,
        end=now_utc,
        interval="1m",
        progress=False,
        auto_adjust=False,
    )
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] for col in df.columns.values]
    close = pd.to_numeric(df["Adj Close"], errors="coerce")
    last_val = close.dropna().iloc[-1] if not close.dropna().empty else None
    return last_val, now_utc.date()


def update_latest_close(data, last_val, today):
    """Update or insert the last close for today into the daily data."""
    if last_val is not None:
        if data.index[-1].date() == today:
            data.iloc[-1, data.columns.get_loc("Adj_Close")] = last_val
        elif data.index[-1].date() < today:
            new_idx = pd.Timestamp(today)
            new_row = [None] * (data.shape[1] - 1) + [last_val]
            data.loc[new_idx] = new_row
    return data


def process_signals(data, ma_window, threshold, overwrite_value=None):
    """Calculate SMA, threshold bands, trading signals."""
    # Ensure no missing dates
    data = (
        data.reindex(pd.date_range(data.index.min(), data.index.max(), freq="D"))
        .ffill()
        .bfill()
    )
    # Overwrite close value (UI entry)
    if overwrite_value is not None:
        data.at[data.index.max(), "Adj_Close"] = overwrite_value
    data["SMA"] = data["Adj_Close"].rolling(window=ma_window).mean()
    data = data.dropna(subset=["SMA"])
    data["upp"] = data["SMA"] * (1 + threshold)
    data["low"] = data["SMA"] * (1 - threshold)
    data["signal"] = None
    invested = False
    for idx, row in enumerate(data.itertuples(), 0):
        if not invested and row.Adj_Close >= row.upp:
            data.iat[idx, data.columns.get_loc("signal")] = "BUY"
            invested = True
        elif invested and row.Adj_Close < row.low:
            data.iat[idx, data.columns.get_loc("signal")] = "SELL"
            invested = False
    return data


def fetch_and_process_symbol(
    base_symbol, intraday_symbol, ma_window, threshold, overwrite_value=None
):
    if not market_is_open():
        raise RuntimeError("US stock market is closed.")
    base = fetch_base_history(base_symbol)
    last_val, today = fetch_recent_intraday_close(intraday_symbol)
    base = update_latest_close(base, last_val, today)
    result = process_signals(base, ma_window, threshold, overwrite_value)
    return result
