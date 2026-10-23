"""Does scaling a short history's volatility by a longer-lived fund recover the long-window volatility?

Usage: python scripts/vol_proxy_check.py
EMXC (from 2017) and MCHI (from 2011) have their volatility scaled by EEM and FXI's full-window over
same-window ratio (`calibrate.VOL_PROXIES`). This tests the method on funds whose full 2005-2026 history
is known: pretend each started in April 2011 or August 2017, scale it by every other fund, and compare
with its true 2005-2026 volatility. Writes reports/vol_proxy_check.csv.
"""
import itertools
from pathlib import Path

import numpy as np
import pandas as pd

from lgm.asof import DATA_END
from lgm.data import yahoo

OUT = Path(__file__).resolve().parents[1] / "reports" / "vol_proxy_check.csv"
FUNDS = ("VUG", "VTV", "VB", "VGK", "EWJ", "EPP", "EWC", "EEM", "FXI")
EM_CHINA = ("EEM", "FXI")          # the pair behind the proxies the generator uses
STARTS = ("2011-04-30", "2017-08-31")


def main():
    r = {t: np.log1p(yahoo.monthly_returns([t], start="2000-01-01")[t]).dropna().loc["2005-05-01":DATA_END] for t in FUNDS}
    rows = []
    for start in STARTS:
        for fund, proxy in itertools.permutations(FUNDS, 2):
            full, short = r[fund].std(), r[fund].loc[start:].std()
            scaled = short * r[proxy].std() / r[proxy].loc[start:].std()
            rows.append({"start": start, "fund": fund, "proxy": proxy, "em_china_pair": fund in EM_CHINA and proxy in EM_CHINA,
                         "short_log_error": float(np.log(short / full)), "scaled_log_error": float(np.log(scaled / full))})
    d = pd.DataFrame(rows)
    d["scaled_closer"] = d.scaled_log_error.abs() < d.short_log_error.abs()
    d.round(4).to_csv(OUT, index=False)
    rms = lambda s: float(np.sqrt((s ** 2).mean()))
    for start, g in d.groupby("start"):
        print(f"start {start}: unscaled RMS {rms(g.short_log_error):.3f}, scaled RMS {rms(g.scaled_log_error):.3f}, "
              f"scaled closer in {int(g.scaled_closer.sum())} of {len(g)}")
    print(d[d.em_china_pair].round(3).to_string(index=False))
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
