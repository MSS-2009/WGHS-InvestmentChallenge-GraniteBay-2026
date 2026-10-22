"""Which Taiwan building-cost drift forecasts six-year cost growth best? Evidence for the drift choice.

Usage: python scripts/taiwan_drift_study.py
The headline uses the 1991-2026 average drift (2.85% a year); the last ten years averaged 3.78%
(config/taiwan.yaml). At every month-end from Jan 2001 (ten years of history) to Jul 2020 (the last
origin with 74 months of outcome), each rule forecasts the next 74 months' log change of the DGBAS
construction cost index using only data to that month:
  expanding     average since Jan 1991 (what the headline's full-sample choice is, in real time)
  trailing_20y  average of the last 20 years (expanding until 20 years exist)
  trailing_10y  average of the last 10 years
  trailing_5y   average of the last 5 years
  zero          no growth
Errors are reported overall and for each five-year block of origins, because 235 overlapping origins
hold only about three independent six-year windows. Writes reports/taiwan_drift_study.csv.
"""
from pathlib import Path

import numpy as np
import pandas as pd

from lgm.data import taiwan

OUT = Path(__file__).resolve().parents[1] / "reports" / "taiwan_drift_study.csv"
H = 74


def main():
    x = np.log(taiwan.construction_cost())
    d = x.diff().dropna()
    origins = [t for t in x.index if t >= pd.Timestamp("2001-01-31") and x.index.get_loc(t) + H < len(x)]
    rules = {"expanding": None, "trailing_20y": 240, "trailing_10y": 120, "trailing_5y": 60, "zero": 0}
    rows = []
    for t in origins:
        i = x.index.get_loc(t)
        actual = float(x.iloc[i + H] - x.iloc[i])
        hist = d.loc[:t]
        for name, w in rules.items():
            mu = 0.0 if w == 0 else float(hist.mean() if w is None else hist.iloc[-w:].mean())
            rows.append({"origin": t, "rule": name, "forecast": H * mu, "actual": actual, "error": actual - H * mu})
    df = pd.DataFrame(rows)
    df["block"] = (df.origin.dt.year - 2001) // 5 * 5 + 2001
    out = []
    for (block, rule), g in [*((("all", r), g) for r, g in df.groupby("rule")), *df.groupby(["block", "rule"])]:
        out.append({"origins": block if block == "all" else f"{block}-{min(block + 4, 2020)}", "rule": rule,
                    "n": len(g), "rmse": float(np.sqrt((g.error ** 2).mean())), "mean_error": float(g.error.mean()),
                    "mean_forecast_annual": float(g.forecast.mean() / H * 12)})
    res = pd.DataFrame(out)
    res.round(5).to_csv(OUT, index=False)
    piv = res.pivot(index="origins", columns="rule", values="rmse")[list(rules)]
    print("RMSE of the 74-month log change (0.10 = about 10% of cost), by block of origins:")
    print(piv.round(3).to_string())
    print("\nMean error (actual - forecast):")
    print(res.pivot(index="origins", columns="rule", values="mean_error")[list(rules)].round(3).to_string())
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
