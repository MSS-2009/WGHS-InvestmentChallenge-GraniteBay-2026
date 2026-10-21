"""Yahoo Finance chart API (keyless). Used for ETF/stock price histories and FX."""
from __future__ import annotations

import datetime as dt
import json
import time
from pathlib import Path

import pandas as pd
import requests

URL = "https://query1.finance.yahoo.com/v8/finance/chart/{sym}?period1={p1}&period2={p2}&interval={iv}&events=div%7Csplit"
RAW = Path(__file__).resolve().parents[3] / "data" / "raw" / "yahoo"


def history(sym: str, start: str = "1990-01-01", end: str | None = None, interval: str = "1mo",
            refresh: bool = False) -> pd.DataFrame:
    """Columns: close, adjclose (total-return price). Cached as CSV."""
    end = end or dt.date.today().isoformat()
    path = RAW / f"{sym.replace('^', '_').replace('=', '_')}_{interval}.csv"
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
        h = history(s, start=start, interval="1mo")
        px = h["adjclose"].resample("ME").last()
        cols[s] = px.pct_change()
        time.sleep(0.3)
    return pd.DataFrame(cols).dropna()
