"""US Treasury daily par yield curve (home.treasury.gov), keyless CSV download."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import pandas as pd
import requests

from ..curve import TREASURY_TENORS, ParCurve
from ..dates import as_date

URL = ("https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
       "daily-treasury-rates.csv/{year}/all?type=daily_treasury_yield_curve"
       "&field_tdr_date_value={year}&page&_format=csv")
RAW = Path(__file__).resolve().parents[3] / "data" / "raw"


def fetch_year(year: int, refresh: bool = False) -> Path:
    path = RAW / f"treasury_par_{year}.csv"
    if path.exists() and not refresh:
        return path
    r = requests.get(URL.format(year=year), timeout=60, headers={"User-Agent": "lgm-research"})
    r.raise_for_status()
    _check_csv(r.text, URL)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(r.text)
    return path


def _check_csv(text: str, url: str):
    """Refuse to cache anything but Treasury's CSV (an error page would overwrite good data)."""
    if not text.startswith("Date,"):
        raise ValueError(f"unexpected response from {url.split('?')[0]}: {text[:60]!r}")


def load_year(year: int) -> pd.DataFrame:
    """Rows indexed by date; columns are tenors in years; values in percent."""
    df = pd.read_csv(fetch_year(year))
    df["Date"] = pd.to_datetime(df["Date"], format="%m/%d/%Y").dt.date
    df = df.set_index("Date").sort_index()
    cols = {c: TREASURY_TENORS[c] for c in df.columns if c in TREASURY_TENORS}
    return df[list(cols)].rename(columns=cols).astype(float)


def par_curve(date: dt.date | str) -> ParCurve:
    d = as_date(date)
    row = load_year(d.year).loc[d].dropna()
    return ParCurve.from_points(d, {float(k): float(v) for k, v in row.items()})


def history(start_year: int = 1990, end_year: int = 2026) -> "pd.DataFrame":
    """Daily par yields (percent) for a range of years from Treasury's yearly CSV files."""
    import time
    frames = []
    for y in range(start_year, end_year + 1):
        new = not (RAW / f"treasury_par_{y}.csv").exists()
        frames.append(load_year(y))
        if new:
            time.sleep(0.3)
    df = pd.concat(frames).sort_index()
    df.index = pd.to_datetime(df.index)
    return df[sorted(df.columns)]


REAL_URL = URL.replace("type=daily_treasury_yield_curve", "type=daily_treasury_real_yield_curve")


def real_year(year: int, refresh: bool = False) -> pd.DataFrame:
    """Daily par real (TIPS) yield curve for one year; columns are tenors in years, values in percent."""
    path = RAW / f"treasury_real_{year}.csv"
    if refresh or not path.exists():
        r = requests.get(REAL_URL.format(year=year), timeout=60, headers={"User-Agent": "lgm-research"})
        r.raise_for_status()
        _check_csv(r.text, REAL_URL)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(r.text)
    df = pd.read_csv(path)
    df["Date"] = pd.to_datetime(df["Date"], format="%m/%d/%Y")
    df = df.set_index("Date").sort_index()
    cols = {c: float(c.split()[0]) for c in df.columns if c.endswith("YR")}
    return df[list(cols)].rename(columns=cols).astype(float)


def breakevens(start: int = 2003, end: int = 2026) -> pd.DataFrame:
    """Daily breakeven inflation (nominal par minus real par yield, decimals) at 5, 7, 10, 20 and 30 years,
    plus the 5-year rate 5 years ahead. TIPS are used only as a market inflation gauge, never held."""
    nominal = pd.concat([load_year(y) for y in range(start, end + 1)])
    nominal.index = pd.to_datetime(nominal.index)
    real = pd.concat([real_year(y) for y in range(start, end + 1)])
    be = (nominal[[5.0, 7.0, 10.0, 20.0, 30.0]] - real[[5.0, 7.0, 10.0, 20.0, 30.0]]).dropna(how="all") / 100
    be["5y5y"] = ((1 + be[10.0]) ** 10 / (1 + be[5.0]) ** 5) ** (1 / 5) - 1
    return be
