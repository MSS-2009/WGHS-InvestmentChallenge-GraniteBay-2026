"""Do US stocks mean-revert over Laura's horizon? Checks the generator's i.i.d. monthly equity shocks.

Usage: python scripts/equity_horizon.py [n_null]
Variance ratios of the US market's monthly log returns (Kenneth French, Jul 1926-) at 12, 36 and 74
months, nominal and in excess of T-bills, from three start dates, each against an i.i.d. null built by
resampling the same months (`calibrate.variance_ratio_test`). If stocks mean-reverted, the model's
i.i.d. shocks would overstate the spread of six-year returns. Writes reports/equity_horizon.csv, and
reports/equity_vol_history.csv: the market's annual volatility by period, against the 2005-2026 window
the generator's equity volatilities come from; and reports/equity_vol_forecast.csv: how well trailing
windows of 3, 9 and 21 years (the generator uses about 21) and the whole history since 1926 forecast the
next 3 or 6 years' volatility, from every half-year end since 1946.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from lgm.calibrate import variance_ratio_test
from lgm.data import french

OUT = Path(__file__).resolve().parents[1] / "reports" / "equity_horizon.csv"
VOL_OUT = OUT.with_name("equity_vol_history.csv")
FORECAST_OUT = OUT.with_name("equity_vol_forecast.csv")
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
    fc = vol_forecast(m)
    fc.round(4).to_csv(FORECAST_OUT, index=False)
    print(fc.to_string(index=False))
    print(f"Wrote {OUT}, {VOL_OUT} and {FORECAST_OUT}")


def vol_forecast(m: pd.Series) -> pd.DataFrame:
    """Log error of each trailing-window volatility against the next `horizon` months' volatility."""
    windows = {"3 years": 36, "9 years": 108, "21 years": 252, "since 1926": None}
    rows = []
    for horizon in (36, 72):
        for end in pd.date_range("1946-12-31", m.index[-1] - pd.DateOffset(months=horizon), freq="6ME"):
            past, future = m.loc[:end], m.loc[end + pd.offsets.MonthEnd(1):].iloc[:horizon]
            for name, n in windows.items():
                est = past if n is None else past.iloc[-n:]
                rows.append({"horizon_m": horizon, "est_end": end, "window": name,
                             "log_error": float(np.log(est.std() / future.std()))})
    d = pd.DataFrame(rows)
    d["period"] = np.where(d.est_end.dt.year <= 1980, "1946-1980", "1981 on")
    rms = lambda s: float(np.sqrt((s ** 2).mean()))
    return (d.groupby(["horizon_m", "period", "window"], sort=False).log_error
            .agg(origins="size", bias="mean", rms=rms).reset_index())


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 20_000)
