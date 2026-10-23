"""Market-cap weights and look-through exposures from iShares holdings files.

- Region weights: iShares MSCI ACWI holdings (float-adjusted market cap, ~2,250 stocks).
- US style split: ratios of the same stock's weight in Russell 1000 vs Russell 1000 Growth/Value
  (a pure-growth stock's weight ratio equals the growth index's share of the Russell 1000).
- US large vs small: CRSP/Morningstar breakpoints used by Vanguard's VUG/VTV (top 85% of US market
  cap) and VB (85-98%).
- Look-through sector and country shares use the same holdings.
"""
from __future__ import annotations

import csv
import io
from pathlib import Path

import numpy as np
import requests

RAW = Path(__file__).resolve().parents[3] / "data" / "raw" / "ishares"
PRODUCTS = {"ACWI": 239600, "IWB": 239707, "IWF": 239706, "IWD": 239708, "IWM": 239710}
EUROPE = {"United Kingdom", "France", "Switzerland", "Germany", "Netherlands", "Sweden", "Denmark", "Italy",
          "Spain", "Finland", "Belgium", "Norway", "Ireland", "Austria", "Portugal", "Israel", "Poland"}
PACIFIC = {"Australia", "Hong Kong", "Singapore", "New Zealand"}
TECH = {"Information Technology", "Communication"}


def holdings(fund: str, refresh: bool = False) -> list[dict]:
    path = RAW / f"{fund}_holdings.csv"
    if refresh or not path.exists():
        url = f"https://www.ishares.com/us/products/{PRODUCTS[fund]}/fund/latest-holdings.csv"
        r = requests.get(url, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        if "\nTicker," not in r.text:
            raise ValueError(f"iShares returned no holdings table for {fund}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(r.text)
    lines = path.read_text(encoding="utf-8-sig", errors="ignore").splitlines()
    k = next(i for i, l in enumerate(lines) if l.startswith("Ticker,"))
    out = []
    for r in csv.DictReader(io.StringIO("\n".join(lines[k:]))):
        try:
            if r.get("Asset Class") == "Equity":
                out.append({"ticker": r["Ticker"], "w": float(r["Weight (%)"].replace(",", "")) / 100,
                            "loc": r.get("Location", ""), "sector": r.get("Sector", "")})
        except (ValueError, KeyError):
            continue
    return out


def region_of(loc: str) -> str:
    if loc == "United States":
        return "US"
    if loc in ("Japan", "Canada", "China"):
        return {"Japan": "Japan", "Canada": "Canada", "China": "China"}[loc]
    if loc in EUROPE:
        return "Europe"
    if loc in PACIFIC:
        return "PacificXJ"
    return "EMxChina"


def _style_share(big: list[dict], part: list[dict], min_w: float = 0.01) -> float:
    b = {h["ticker"]: h["w"] for h in big}
    ratios = [b[h["ticker"]] / h["w"] for h in part if h["ticker"] in b and h["w"] >= min_w and b[h["ticker"]] > 0]
    return float(min(ratios))


def market_weights_and_exposures(groups) -> dict:
    acwi = holdings("ACWI")
    tot = sum(h["w"] for h in acwi)
    region_w, region_tech, region_ct = {}, {}, {}
    for h in acwi:
        r = region_of(h["loc"])
        region_w[r] = region_w.get(r, 0) + h["w"] / tot
        region_tech[r] = region_tech.get(r, 0) + (h["w"] / tot if h["sector"] in TECH else 0)
        region_ct[r] = region_ct.get(r, 0) + (h["w"] / tot if h["loc"] in ("China", "Taiwan") else 0)
    iwb, iwf, iwd, iwm = (holdings(f) for f in ("IWB", "IWF", "IWD", "IWM"))
    g_share, v_share = _style_share(iwb, iwf), _style_share(iwb, iwd)
    g_share, v_share = g_share / (g_share + v_share), v_share / (g_share + v_share)
    large, small = 0.85 / 0.98, 0.13 / 0.98
    style_tech = {"growth": sum(h["w"] for h in iwf if h["sector"] in TECH) / sum(h["w"] for h in iwf),
                  "value": sum(h["w"] for h in iwd if h["sector"] in TECH) / sum(h["w"] for h in iwd),
                  "small": sum(h["w"] for h in iwm if h["sector"] in TECH) / sum(h["w"] for h in iwm)}
    w, tech, ct = [], [], []
    for g in groups:
        if g.region == "US":
            share = {"growth": large * g_share, "value": large * v_share, "small": small}[g.style]
            w.append(region_w["US"] * share)
            tech.append(style_tech[g.style])
            ct.append(0.0)
        else:
            w.append(region_w[g.region])
            tech.append(region_tech[g.region] / region_w[g.region])
            ct.append(region_ct[g.region] / region_w[g.region])
    w = np.array(w)
    return {"w_mkt": w / w.sum(), "tech": np.array(tech), "china_taiwan": np.array(ct),
            "us_growth_share": g_share, "region_w": region_w}
