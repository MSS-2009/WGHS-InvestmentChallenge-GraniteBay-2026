"""Do US stocks mean-revert over Laura's horizon? Checks the generator's i.i.d. monthly equity shocks.

Usage: python scripts/equity_horizon.py [n_null]
Variance ratios of the US market's monthly log returns (Kenneth French, Jul 1926-) at 12, 36 and 74
months, nominal and in excess of T-bills, from three start dates, each against an i.i.d. null built by
resampling the same months (`calibrate.variance_ratio_test`). If stocks mean-reverted, the model's
i.i.d. shocks would overstate the spread of six-year returns. Writes reports/equity_horizon.csv, and
reports/equity_vol_history.csv: the market's annual volatility by period, against the 2005-2026 window
the generator's equity volatilities come from.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from lgm.calibrate import variance_ratio_test
from lgm.data import french

OUT = Path(__file__).resolve().parents[1] / "reports" / "equity_horizon.csv"
VOL_OUT = OUT.with_name("equity_vol_history.csv")
PERIODS = (("1926", "2026"), ("1946", "2026"), ("1946", "2004"), ("2005", "2026"))


def main(n_null: int = 20_000):
    ff = french.monthly("F-F_Research_Data_Factors")
    series = {"nominal": np.log1p(ff["Mkt-RF"] + ff["RF"]), "excess of T-bills": np.log1p(ff["Mkt-RF"] + ff["RF"]) - np.log1p(ff["RF"])}
    rows = []
    for label, s in series.items():
        for start in ("1926", "1946", "1990"):
            r = s.loc[start:].dropna().values
            for h in (12, 36, 74):
                t = variance_ratio_test(r, h, n_null)
                rows.append({"returns": label, "start": start, "months": len(r), "horizon_m": h, **t})
                print(f"{label:17s} from {start} (n={len(r)}) h={h:2d}: VR {t['variance_ratio']:.2f} "
                      f"(i.i.d. median {t['null_median']:.2f}, p {t['p_mean_reversion']:.2f})")
    pd.DataFrame(rows).round(4).to_csv(OUT, index=False)
    m = series["nominal"]
    vol = pd.DataFrame([{"period": f"{a}-{b}", "annual_vol": float(m.loc[a:b].std() * np.sqrt(12))} for a, b in PERIODS])
    vol.round(4).to_csv(VOL_OUT, index=False)
    print(vol.to_string(index=False))
    print(f"Wrote {OUT} and {VOL_OUT}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 20_000)
