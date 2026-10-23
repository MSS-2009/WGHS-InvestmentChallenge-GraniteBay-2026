"""Taiwan short-term money market interest rates from the Central Bank of the Republic of China (CBC).

All data is cached under data/raw/twrates/ for offline reproducibility. No API key required.
Official series:
- Commercial paper 31-90 days secondary market rate (primary 3-month Taiwan market rate).
- Interbank overnight call loan rate.
- Forward exchange rates of the NT dollar against the US dollar, 10-180 days (Table 31.C).
"""
from __future__ import annotations

import json
from pathlib import Path
import ssl
import urllib.request

import numpy as np
import pandas as pd

RAW = Path(__file__).resolve().parents[3] / "data" / "raw" / "twrates"
API_URL = "https://cpx.cbc.gov.tw/API/DataAPI/Get?FileName=EG41M01en"
JSON_PATH = RAW / "cbc_money_market_rates.json"
FWD_API_URL = "https://cpx.cbc.gov.tw/API/DataAPI/Get?FileName=EG55M01en"
FWD_JSON_PATH = RAW / "cbc_forward_rates.json"


def _fetch_rates(refresh: bool = False, url: str = API_URL, path: Path = JSON_PATH) -> dict:
    if refresh or not path.exists():
        ctx = ssl.create_default_context()           # certificate checks stay on (see taiwan._get)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, context=ctx, timeout=60) as r:
            content = r.read()
        # Validate that it is valid JSON with expected structure
        data = json.loads(content)
        if "data" not in data or "dataSets" not in data["data"]:
            raise ValueError("unexpected API payload from CBC")
        RAW.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return data

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def money_market_rates(refresh: bool = False, decimal: bool = True) -> pd.DataFrame:
    """Monthly money market interest rates from CBC Table 29.F (1987 to present).

    Returns a DataFrame indexed by month-end DatetimeIndex, sorted chronologically.
    By default, returns rates as decimals (e.g. 0.0178 for 1.78%). If decimal=False, returns percent.
    """
    raw = _fetch_rates(refresh=refresh)
    cols = [x["data"] for x in raw["data"]["structure"]["Table1"]]
    rows = raw["data"]["dataSets"]

    records = []
    dates = []
    for r in rows:
        d_str = r[0]  # e.g. "1987M05"
        year = int(d_str[:4])
        month = int(d_str[5:])
        dt = pd.Timestamp(year, month, 1) + pd.offsets.MonthEnd(1)
        dates.append(dt)

        vals = []
        for val_str in r[1:]:
            val_clean = val_str.strip()
            if val_clean == "-" or not val_clean:
                vals.append(np.nan)
            else:
                try:
                    v = float(val_clean.replace(",", ""))
                    vals.append(v / 100.0 if decimal else v)
                except ValueError:
                    vals.append(np.nan)
        records.append(vals)

    df = pd.DataFrame(records, index=dates, columns=cols).sort_index()
    return df


def cp_90d(refresh: bool = False, decimal: bool = True) -> pd.Series:
    """Monthly Taiwan 90-day Commercial Paper secondary market rate (3-month rate).

    Returns a Series indexed by month-end DatetimeIndex.
    """
    df = money_market_rates(refresh=refresh, decimal=decimal)
    col = "Commercial paper-Secondary market-31-90 days"
    s = df[col].dropna()
    return s.rename("TW_CP_90D")


def interbank_call(refresh: bool = False, decimal: bool = True) -> pd.Series:
    """Monthly Taiwan weighted average overnight interbank call loan rate.

    Returns a Series indexed by month-end DatetimeIndex.
    """
    df = money_market_rates(refresh=refresh, decimal=decimal)
    col = "Interbank call loans"
    s = df[col].dropna()
    return s.rename("TW_INTERBANK_CALL")


def forward_rates(refresh: bool = False) -> pd.DataFrame:
    """Monthly USD/TWD forward rates (TWD per USD) from CBC Table 31.C, 1991-11 to present: the mid
    of the buying and selling quotes for each tenor. Columns are tenors in days (10 ... 180).
    Values are period averages, as published."""
    raw = _fetch_rates(refresh=refresh, url=FWD_API_URL, path=FWD_JSON_PATH)
    tenors = [int(x["data"].split()[0]) for x in raw["data"]["structure"]["Table1"]]
    dates, rows = [], []
    for r in raw["data"]["dataSets"]:
        vals = [np.nan if v.strip() in ("-", "") else float(v.replace(",", "")) for v in r[1:]]
        rows.append([(vals[2 * i] + vals[2 * i + 1]) / 2 for i in range(len(tenors))])
        dates.append(pd.Timestamp(int(r[0][:4]), int(r[0][5:]), 1) + pd.offsets.MonthEnd(1))
    return pd.DataFrame(rows, index=dates, columns=tenors).sort_index().dropna(how="all")
