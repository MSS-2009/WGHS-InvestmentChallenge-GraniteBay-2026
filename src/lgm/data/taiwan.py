"""Taiwan price statistics from the Directorate-General of Budget, Accounting and Statistics (DGBAS).

All data is cached under data/raw/taiwan/ for offline reproducibility. No API key required.
Official series:
- Construction Cost Index (營造工程物價指數 - 總指數), monthly from 1991, 2021=100.
- Consumer Price Index (消費者物價指數 - 總指數), monthly from 1959, 2021=100.
- Sub-indices: Materials (材料類) and Labor & Equipment Services (勞務類).
"""
from __future__ import annotations

import io
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

import pandas as pd
import requests

RAW = Path(__file__).resolve().parents[3] / "data" / "raw" / "taiwan"
CCI_URL = "https://ws.dgbas.gov.tw/001/Upload/463/relfile/10315/2703/ccispl.ods"
CPI_URL = "https://ws.dgbas.gov.tw/001/Upload/463/relfile/10315/2703/cpispl.ods"
MATERIALS_URL = "https://ws.dgbas.gov.tw/001/Upload/463/relfile/10315/2702/ccimaterials.ods"
SERVICES_URL = "https://ws.dgbas.gov.tw/001/Upload/463/relfile/10315/2702/cciservices.ods"

NS_TABLE = "{urn:oasis:names:tc:opendocument:xmlns:table:1.0}"


def _get(url: str, path: Path, refresh: bool, marker: bytes) -> Path:
    """Download unless cached; validates the response before overwriting the cache file."""
    if refresh or not path.exists():
        # DGBAS servers use certificates from the Taiwan Government Root CA.
        # Fall back gracefully if local certificate stores lack Taiwan GRCA.
        try:
            r = requests.get(url, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
        except requests.exceptions.SSLError:
            r = requests.get(url, timeout=60, headers={"User-Agent": "Mozilla/5.0"}, verify=False)
        r.raise_for_status()
        if marker not in r.content:
            raise ValueError(f"unexpected response from {url}: marker {marker!r} not found")
        # Validate that the downloaded payload is a valid zip containing content.xml
        try:
            with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                if "content.xml" not in z.namelist():
                    raise ValueError(f"invalid ODS archive from {url}: content.xml missing")
        except zipfile.BadZipFile as e:
            raise ValueError(f"invalid zip archive from {url}") from e

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(r.content)
    return path


def _parse_ods_monthly(path: Path, table_prefix: str, series_name: str) -> pd.Series:
    """Parse a monthly spliced series from a DGBAS ODS file.

    Returns a pandas Series with a month-end DatetimeIndex, sorted chronologically.
    """
    with zipfile.ZipFile(path) as z:
        tree = ET.fromstring(z.read("content.xml"))

    table = None
    for t in tree.findall(f".//{NS_TABLE}table"):
        tname = t.get(f"{NS_TABLE}name", "")
        if table_prefix in tname:
            table = t
            break
    if table is None:
        raise ValueError(f"table matching prefix {table_prefix!r} not found in {path}")

    records: dict[pd.Timestamp, float] = {}
    for r in table.findall(f".//{NS_TABLE}table-row"):
        cells: list[str] = []
        for c in r.findall(f".//{NS_TABLE}table-cell"):
            rep = int(c.get(f"{NS_TABLE}number-columns-repeated", "1"))
            txt = "".join(c.itertext()).strip()
            cells.extend([txt] * rep)
        if cells and cells[0].isdigit():
            roc_year = int(cells[0])
            year = roc_year + 1911
            for m in range(1, 13):
                if m < len(cells) and cells[m]:
                    try:
                        val = float(cells[m].replace(",", ""))
                        # Month-end timestamp
                        dt = pd.Timestamp(year, m, 1) + pd.offsets.MonthEnd(1)
                        records[dt] = val
                    except ValueError:
                        pass

    s = pd.Series(records, name=series_name).sort_index()
    if s.empty:
        raise ValueError(f"no observations parsed from {path}")
    return s


def construction_cost(refresh: bool = False) -> pd.Series:
    """Monthly Taiwan Construction Cost Index (營造工程物價指數 - 總指數), 2021=100.

    Longest available spliced series (1991-01 to present) from DGBAS.
    Returns a Series indexed by month-end Timestamps.
    """
    path = _get(CCI_URL, RAW / "ccispl.ods", refresh, marker=b"content.xml")
    return _parse_ods_monthly(path, table_prefix="營造工程", series_name="TW_CCI")


def cci(refresh: bool = False) -> pd.Series:
    """Alias for construction_cost()."""
    return construction_cost(refresh=refresh)


def cpi(refresh: bool = False) -> pd.Series:
    """Monthly Taiwan Consumer Price Index (消費者物價指數 - 總指數), 2021=100.

    Longest available spliced series (1959-01 to present) from DGBAS.
    Returns a Series indexed by month-end Timestamps.
    """
    path = _get(CPI_URL, RAW / "cpispl.ods", refresh, marker=b"content.xml")
    return _parse_ods_monthly(path, table_prefix="CPI", series_name="TW_CPI")


def materials(refresh: bool = False) -> pd.Series:
    """Monthly Taiwan Construction Cost Materials Sub-Index (材料類), 2021=100."""
    path = _get(MATERIALS_URL, RAW / "ccimaterials.ods", refresh, marker=b"content.xml")
    return _parse_ods_monthly(path, table_prefix="材料類", series_name="TW_CCI_MATERIALS")


def services(refresh: bool = False) -> pd.Series:
    """Monthly Taiwan Construction Cost Labor & Services Sub-Index (勞務類), 2021=100."""
    path = _get(SERVICES_URL, RAW / "cciservices.ods", refresh, marker=b"content.xml")
    return _parse_ods_monthly(path, table_prefix="勞務類", series_name="TW_CCI_SERVICES")
