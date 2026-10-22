"""FRED series via the public fredgraph CSV endpoint (no API key required)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import requests

URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={ids}"
RAW = Path(__file__).resolve().parents[3] / "data" / "raw"


def fetch(series: list[str], name: str, refresh: bool = False) -> pd.DataFrame:
    path = RAW / f"fred_{name}.csv"
    if refresh or not path.exists():
        import time
        for attempt in range(4):
            try:
                # FRED stalls on custom User-Agents and serves an HTML maintenance page with status 200
                r = requests.get(URL.format(ids=",".join(series)), timeout=60)
                r.raise_for_status()
                if not r.text.startswith(("observation_date,", "DATE,")):
                    raise requests.RequestException("FRED did not return CSV (maintenance page?)")
                break
            except requests.RequestException:
                if attempt == 3:
                    raise
                time.sleep(3 * (attempt + 1))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(r.text)
    df = pd.read_csv(path)
    date_col = df.columns[0]
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.set_index(date_col).sort_index()
    return df.apply(pd.to_numeric, errors="coerce")


TREASURY_CMT = {"DGS3MO": 0.25, "DGS6MO": 0.5, "DGS1": 1, "DGS2": 2, "DGS3": 3, "DGS5": 5,
                "DGS7": 7, "DGS10": 10, "DGS20": 20, "DGS30": 30}


def treasury_history(refresh: bool = False) -> pd.DataFrame:
    """Daily constant-maturity Treasury yields (percent); columns are tenors in years."""
    df = fetch(list(TREASURY_CMT), "treasury_cmt", refresh)
    return df.rename(columns=TREASURY_CMT)


def cpi(refresh: bool = False) -> pd.DataFrame:
    return fetch(["CPIAUCNS", "CPILFENS"], "cpi", refresh)
