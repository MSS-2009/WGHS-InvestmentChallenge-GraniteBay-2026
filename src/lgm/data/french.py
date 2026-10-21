"""Kenneth R. French Data Library (Tuck/Dartmouth), keyless CSV zips cached in data/raw/french/."""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pandas as pd
import requests

RAW = Path(__file__).resolve().parents[3] / "data" / "raw" / "french"
URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/{name}_CSV.zip"


def monthly(name: str, refresh: bool = False) -> pd.DataFrame:
    """First monthly table of a library file (value-weighted returns), in decimals, month-end index."""
    path = RAW / f"{name}.csv"
    if refresh or not path.exists():
        r = requests.get(URL.format(name=name), timeout=120, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(z.read(z.namelist()[0]))
    lines = path.read_text(errors="ignore").splitlines()
    head = next(i for i, l in enumerate(lines) if l.startswith(",") and i + 1 < len(lines) and lines[i + 1].strip()[:6].isdigit())
    rows = []
    for l in lines[head + 1:]:
        cells = [c.strip() for c in l.split(",")]
        if not (cells[0].isdigit() and len(cells[0]) == 6):
            break
        rows.append(cells)
    cols = [c.strip() for c in lines[head].split(",")][1:]
    df = pd.DataFrame([r[1:] for r in rows], columns=cols, index=pd.to_datetime([r[0] for r in rows], format="%Y%m"))
    df.index = df.index + pd.offsets.MonthEnd(0)
    return df.astype(float).replace([-99.99, -999.0], float("nan")) / 100
