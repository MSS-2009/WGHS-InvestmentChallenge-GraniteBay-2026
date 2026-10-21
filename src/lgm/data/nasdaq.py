"""Nasdaq public API (keyless): company profile, analyst ratings and 4 years of financials."""
from __future__ import annotations

import json
import time
from pathlib import Path

import requests

RAW = Path(__file__).resolve().parents[3] / "data" / "raw" / "nasdaq"
H = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 Chrome/130.0 Safari/537.36",
     "Accept": "application/json"}
ENDPOINTS = {"profile": "company/{s}/company-profile", "ratings": "analyst/{s}/ratings",
             "financials": "company/{s}/financials?frequency=1"}


def fetch(symbol: str, kind: str, refresh: bool = False) -> dict:
    path = RAW / f"{symbol}_{kind}.json"
    if path.exists() and not refresh:
        return json.loads(path.read_text())
    for attempt in range(3):
        try:
            r = requests.get("https://api.nasdaq.com/api/" + ENDPOINTS[kind].format(s=symbol), headers=H, timeout=30)
            data = r.json().get("data") or {}
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data))
            time.sleep(0.3)
            return data
        except (requests.RequestException, ValueError):
            time.sleep(2 * (attempt + 1))
    return {}


def _num(x):
    if x in (None, "", "--"):
        return None
    s = str(x).replace("$", "").replace(",", "").replace("%", "").strip()
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()")
    try:
        v = float(s)
    except ValueError:
        return None
    return -v if neg else v


def _rows(table: dict) -> dict[str, list]:
    out = {}
    for r in (table or {}).get("rows") or []:
        out[r.get("value1")] = [_num(r.get(f"value{i}")) for i in range(2, 6)]
    return out


def evidence(symbol: str) -> dict:
    prof = fetch(symbol, "profile")
    rat = fetch(symbol, "ratings")
    fin = fetch(symbol, "financials")
    inc, bal, cf, ratio = (_rows(fin.get(k)) for k in ("incomeStatementTable", "balanceSheetTable",
                                                         "cashFlowTable", "financialRatiosTable"))
    g = lambda d, k, i=0: (d.get(k) or [None] * 4)[i]
    rev = [g(inc, "Total Revenue", i) for i in range(4)]
    debt = (g(bal, "Short-Term Debt / Current Portion of Long-Term Debt") or 0) + (g(bal, "Long-Term Debt") or 0)
    equity = g(bal, "Total Equity") or g(bal, "Stock Holders Equity")
    ocf = g(cf, "Net Cash Flow-Operating")
    capex = g(cf, "Capital Expenditures")
    ni = g(inc, "Net Income")
    rd = g(inc, "Research and Development")
    out = {
        "industry": (prof.get("Industry") or {}).get("value"),
        "description": ((prof.get("CompanyDescription") or {}).get("value") or "")[:600],
        "analyst_rating": rat.get("meanRatingType"),
        "n_analysts": len(rat.get("brokerNames") or []),
        "revenue": rev[0],
        "rev_cagr_3y": (rev[0] / rev[3]) ** (1 / 3) - 1 if rev[0] and rev[3] and rev[3] > 0 and rev[0] > 0 else None,
        "op_margin": g(ratio, "Operating Margin"),
        "op_margin_avg4": None,
        "net_margin": g(ratio, "Profit Margin"),
        "roe": g(ratio, "After Tax ROE"),
        "rd_to_revenue": (rd / rev[0]) if rd and rev[0] else 0.0,
        "debt_to_equity": (debt / equity) if equity and equity > 0 else None,
        "fcf_conversion": ((ocf + (capex or 0)) / ni) if ocf is not None and ni and ni > 0 else None,
        "current_ratio": g(ratio, "Current Ratio"),
    }
    oms = [x for x in (ratio.get("Operating Margin") or []) if x is not None]
    out["op_margin_avg4"] = sum(oms) / len(oms) if oms else None
    return out
