"""Orders that bring the WInS account in line with the IPS (Final Report, WInS section).

Usage: python scripts/wins_rebalance.py
Reads the core weights from reports/report_numbers.json and October 20, 2026 closes; prints the
orders. It places nothing: the team enters orders in WInS itself.
"""
import json
from pathlib import Path

import pandas as pd

from lgm.data import yahoo
from lgm.growth.portfolio import whole_shares

ROOT = Path(__file__).resolve().parents[1]
PRICE_DATE = "2026-10-20"
HELD = {"ESGV": 252, "VSGX": 290}          # growth funds bought on Oct 21 that the IPS excludes
CASH = 38_813.97                           # WInS cash after the Oct 21 trades
KEEP_CASH, COMMISSION = 6_000.0, 25.0


def main():
    w = pd.Series(json.loads((ROOT / "reports" / "report_numbers.json").read_text())["core"]["weights"])
    tickers = list(w.index) + ["IBTM", *HELD]
    px = pd.Series({t: float(yahoo.history(t, start="2026-10-01", end=PRICE_DATE, interval="1d", refresh=True)
                              .loc[PRICE_DATE, "close"]) for t in tickers})
    cash = CASH + sum(n * px[t] for t, n in HELD.items()) - COMMISSION * len(HELD)
    invest = cash - KEEP_CASH
    shares = whole_shares(w, px[w.index], 0.6 * invest)
    ibtm = int(0.4 * invest // px["IBTM"])
    orders = [("Sell", t, n, n * px[t]) for t, n in HELD.items()]
    orders += [("Buy", t, int(n), n * px[t]) for t, n in shares.items()] + [("Buy", "IBTM", ibtm, ibtm * px["IBTM"])]
    df = pd.DataFrame(orders, columns=["side", "symbol", "shares", "dollars"]).round(0)
    left = cash - df.loc[df.side == "Buy", "dollars"].sum() - COMMISSION * (len(df) - len(HELD))
    print(df.to_string(index=False))
    print(f"{len(df)} orders, ${COMMISSION * len(df):,.0f} commissions, about ${left:,.0f} cash left")


if __name__ == "__main__":
    main()
