"""Orders that bring the WInS account in line with the IPS (Final Report, WInS section).

Usage: python scripts/wins_rebalance.py [--refresh]
Reads the core weights from reports/report_numbers.json, the account from config/wins_account.yaml and
closes on the price date in config/asof.yaml (from the price cache unless --refresh); prints the
orders. It places nothing: the team enters orders in WInS itself.
"""
import json
import sys
from pathlib import Path

import pandas as pd
import yaml

from lgm.asof import PRICE_DATE
from lgm.data import yahoo
from lgm.growth.portfolio import whole_shares

ROOT = Path(__file__).resolve().parents[1]
COMMISSION = float(yaml.safe_load((ROOT / "config" / "wins_rules.yaml").read_text())["equities"]["commission"])


def main(refresh: bool = False):
    acct = yaml.safe_load((ROOT / "config" / "wins_account.yaml").read_text())
    held = acct["growth_funds_to_sell"]
    w = pd.Series(json.loads((ROOT / "reports" / "report_numbers.json").read_text())["core"]["weights"])
    tickers = list(w.index) + ["IBTM", *held]
    px = pd.Series({t: yahoo.close_on(t, PRICE_DATE, refresh) for t in tickers})
    cash = acct["cash"] + sum(n * px[t] for t, n in held.items()) - COMMISSION * len(held)
    invest = cash - acct["keep_cash"]
    shares = whole_shares(w, px[w.index], 0.6 * invest)
    ibtm = int(0.4 * invest // px["IBTM"])
    orders = [("Sell", t, n, n * px[t]) for t, n in held.items()]
    orders += [("Buy", t, int(n), n * px[t]) for t, n in shares.items() if n > 0] + [("Buy", "IBTM", ibtm, ibtm * px["IBTM"])]
    df = pd.DataFrame(orders, columns=["side", "symbol", "shares", "dollars"]).round(0)
    left = cash - df.loc[df.side == "Buy", "dollars"].sum() - COMMISSION * (len(df) - len(held))
    print(f"closes of {PRICE_DATE}; account as of {acct['as_of']}")
    print(df.to_string(index=False))
    print(f"{len(df)} orders, ${COMMISSION * len(df):,.0f} commissions, about ${left:,.0f} cash left")


if __name__ == "__main__":
    main(refresh="--refresh" in sys.argv)
