"""Yahoo Finance chart API (keyless). Used for ETF/stock price histories and FX."""
from __future__ import annotations

import datetime as dt
import time
from pathlib import Path

import pandas as pd
import requests

URL = "https://query1.finance.yahoo.com/v8/finance/chart/{sym}?period1={p1}&period2={p2}&interval={iv}&events=div%7Csplit"
RAW = Path(__file__).resolve().parents[3] / "data" / "raw" / "yahoo"


def _path(sym: str, interval: str) -> Path:
    return RAW / f"{sym.replace('^', '_').replace('=', '_')}_{interval}.csv"


def history(sym: str, start: str = "1990-01-01", end: str | None = None, interval: str = "1mo",
            refresh: bool = False) -> pd.DataFrame:
    """Columns: close, adjclose (total-return price). Cached as CSV."""
    end = end or dt.date.today().isoformat()
    path = _path(sym, interval)
    if path.exists() and not refresh:
        return pd.read_csv(path, index_col=0, parse_dates=True)
    p1 = int(dt.datetime.fromisoformat(start).replace(tzinfo=dt.timezone.utc).timestamp())
    p2 = int(dt.datetime.fromisoformat(end).replace(tzinfo=dt.timezone.utc).timestamp()) + 86400
    for attempt in range(3):
        r = requests.get(URL.format(sym=sym, p1=p1, p2=p2, iv=interval), timeout=60,
                         headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200:
            break
        time.sleep(2 + 2 * attempt)
    r.raise_for_status()
    res = r.json()["chart"]["result"][0]
    idx = pd.to_datetime(res["timestamp"], unit="s").normalize()
    q = res["indicators"]["quote"][0]
    adj = res["indicators"].get("adjclose", [{}])[0].get("adjclose", q["close"])
    df = pd.DataFrame({"close": q["close"], "adjclose": adj}, index=idx).dropna()
    df = df[~df.index.duplicated(keep="last")]
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path)
    return df


def monthly_returns(symbols: list[str], start: str = "2000-01-01") -> pd.DataFrame:
    """Simple monthly total returns, aligned on common months."""
    cols = {}
    for s in symbols:
        cached = _path(s, "1mo").exists()
        h = history(s, start=start, interval="1mo")
        px = h["adjclose"].resample("ME").last()
        cols[s] = px.pct_change()
        if not cached:
            time.sleep(0.3)
    return pd.DataFrame(cols).dropna()


def close_on(sym: str, date: str, refresh: bool = False) -> float:
    """Closing price on `date` from the daily cache; downloads only when the cache lacks that date."""
    day = pd.Timestamp(date)
    if not refresh and _path(sym, "1d").exists():
        h = pd.read_csv(_path(sym, "1d"), index_col=0, parse_dates=True)
        if day in h.index:
            return float(h.loc[day, "close"])
    start = (day - pd.Timedelta(days=30)).date().isoformat()
    h = history(sym, start=start, end=day.date().isoformat(), interval="1d", refresh=True)
    if day not in h.index:
        raise KeyError(f"no {sym} close on {date} (market holiday or not yet published?)")
    return float(h.loc[day, "close"])
