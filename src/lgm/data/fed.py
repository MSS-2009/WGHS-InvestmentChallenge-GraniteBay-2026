"""Federal Reserve data that needs no API key: the Kim-Wright term structure model (FEDS 2005-33)
and the H.10 daily USD/TWD rate. Raw files are cached in data/raw/fed/."""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import requests

RAW = Path(__file__).resolve().parents[3] / "data" / "raw" / "fed"
KW_URL = "https://www.federalreserve.gov/data/yield-curve-tables/feds200533.csv"
H10_TWD_URL = "https://www.federalreserve.gov/releases/h10/hist/dat00_ta.htm"


def _get(url: str, path: Path, refresh: bool) -> Path:
    if refresh or not path.exists():
        r = requests.get(url, timeout=120, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(r.content)
    return path


def kim_wright(refresh: bool = False) -> pd.DataFrame:
    """Daily Kim-Wright series in decimals. Columns like FF5 (5-year instantaneous forward),
    FFTP5 (its term premium), FY5 (5-year zero yield) and FYTP5 (its term premium)."""
    path = _get(KW_URL, RAW / "kim_wright_feds200533.csv", refresh)
    lines = path.read_text().splitlines()
    start = next(i for i, l in enumerate(lines) if l.startswith("Date,"))
    df = pd.read_csv(path, skiprows=start, index_col=0, parse_dates=True)
    rename = {}
    for c in df.columns:
        m = re.match(r"THREE(FFTP|FF|FYTP|FY)(\d\d)00\.B", c)
        if m:
            rename[c] = f"{m.group(1)}{int(m.group(2))}"
    return df.rename(columns=rename).apply(pd.to_numeric, errors="coerce") / 100.0


def usd_twd(refresh: bool = False) -> pd.Series:
    """Daily noon buying rate in New York, Taiwan dollars per US dollar (Fed H.10), from 2000."""
    path = _get(H10_TWD_URL, RAW / "h10_dat00_ta.htm", refresh)
    rows = re.findall(r'<th[^>]*>\s*([0-9]{1,2}-[A-Z]{3}-[0-9]{2})\s*</th>\s*<td[^>]*>\s*([0-9.]+|ND)\s*</td>',
                      path.read_text(), flags=re.I)
    s = pd.Series({pd.to_datetime(d, format="%d-%b-%y"): float(v) for d, v in rows if v != "ND"}).sort_index()
    return s.rename("USD_TWD")
