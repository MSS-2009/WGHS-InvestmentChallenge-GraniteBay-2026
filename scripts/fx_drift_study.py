"""Study of USD/TWD exchange rate forecast rules and Fama regressions on historical data.

Evaluates four forecast rules at 12, 36, and 72-month horizons:
(a) Random walk (no change)
(b) Interest-differential drift (Covered Interest Parity forward)
(c) Half of CIP drift
(d) Trailing 10-year average drift

Performs Fama-style regressions of realized k-month log changes on CIP forward differentials
using Newey-West overlap-robust standard errors.

Outputs:
- reports/fx_drift_study.csv
"""
from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd

from lgm.calibrate import usd_twd_monthly
from lgm.data import treasury, twrates

ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "reports" / "fx_drift_study.csv"

HORIZONS = [12, 36, 72]


def newey_west_ols(x: np.ndarray, y: np.ndarray, max_lag: int) -> tuple[np.ndarray, np.ndarray]:
    """OLS regression with Newey-West (HAC) overlap-robust standard errors."""
    N = len(y)
    X = np.column_stack([np.ones(N), x])
    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    resid = y - X @ beta

    xe = X * resid[:, None]
    S = xe.T @ xe
    for lag in range(1, max_lag + 1):
        w = 1.0 - lag / (max_lag + 1.0)
        gamma = xe[lag:].T @ xe[:-lag]
        S += w * (gamma + gamma.T)

    x_inv = np.linalg.inv(X.T @ X)
    cov = x_inv @ S @ x_inv
    se = np.sqrt(np.diag(cov))
    return beta, se


def main():
    print("=" * 80)
    print("USD/TWD FX DRIFT FORECAST STUDY & FAMA REGRESSION")
    print("=" * 80)

    # 1. Load Data
    fx = usd_twd_monthly()  # month-end USD/TWD spot rate (Fed H.10)
    th = treasury.history(1990, 2026)
    us_3m = (th[0.25].resample("ME").last() / 100.0).dropna()
    tw_cp90 = twrates.cp_90d(decimal=True)

    df = pd.concat([fx.rename("spot"), us_3m.rename("r_us"), tw_cp90.rename("r_tw")], axis=1, sort=True).dropna()
    print(f"Dataset range: {df.index[0].strftime('%Y-%m')} to {df.index[-1].strftime('%Y-%m')} ({len(df)} months)")

    # Annualized CIP drift = ln(1 + r_tw) - ln(1 + r_us)
    # When r_us > r_tw, cip_drift < 0, meaning the dollar is priced to depreciate against TWD.
    df["cip_drift"] = np.log1p(df["r_tw"]) - np.log1p(df["r_us"])
    df["log_spot"] = np.log(df["spot"])
    # Trailing 10-year drift (120 months)
    df["trail_10y_drift"] = (df["log_spot"] - df["log_spot"].shift(120)) / 10.0

    records = []

    for k in HORIZONS:
        print("\n" + "-" * 80)
        print(f"HORIZON k = {k} MONTHS ({k//12} YEARS)")
        print("-" * 80)

        sub = df.copy()
        sub["realized_k"] = sub["log_spot"].shift(-k) - sub["log_spot"]
        valid = sub.dropna(subset=["realized_k"])
        n_obs = len(valid)
        n_indep = n_obs // k

        # Forecasts
        # (a) Random walk
        f_rw = np.zeros(n_obs)
        # (b) CIP forward
        f_cip = valid["cip_drift"].values * (k / 12.0)
        # (c) Half CIP
        f_half = 0.5 * f_cip
        # (d) Trailing 10-year average drift
        valid_10y = valid.dropna(subset=["trail_10y_drift"])
        f_10y = valid_10y["trail_10y_drift"].values * (k / 12.0)
        act_10y = valid_10y["realized_k"].values

        act = valid["realized_k"].values

        def eval_rule(f, a):
            err = f - a
            bias = float(np.mean(err))
            rmse = float(np.sqrt(np.mean(err**2)))
            mae = float(np.mean(np.abs(err)))
            return bias, rmse, mae

        b_rw, r_rw, m_rw = eval_rule(f_rw, act)
        b_cip, r_cip, m_cip = eval_rule(f_cip, act)
        b_half, r_half, m_half = eval_rule(f_half, act)
        b_10y, r_10y, m_10y = eval_rule(f_10y, act_10y)

        # Fama Regression: realized_k = alpha + beta * f_cip + eps
        beta_fama, se_fama = newey_west_ols(f_cip, act, max_lag=k)
        t_stat_0 = float(beta_fama[1] / se_fama[1])
        t_stat_1 = float((beta_fama[1] - 1.0) / se_fama[1])

        rules_data = [
            ("random_walk", b_rw, r_rw, m_rw, n_obs, n_indep, "No change (fx_drift = 0); baseline random walk"),
            ("cip_forward", b_cip, r_cip, m_cip, n_obs, n_indep, "Full Covered Interest Parity forward rate differential"),
            ("half_cip", b_half, r_half, m_half, n_obs, n_indep, "Half CIP forward rate differential"),
            ("trailing_10y_drift", b_10y, r_10y, m_10y, len(valid_10y), len(valid_10y) // k, "Trailing 10-year (120-month) annualized historical drift"),
        ]

        for r_name, bias, rmse, mae, n_w, n_i, note in rules_data:
            records.append({
                "horizon_months": k,
                "rule": r_name,
                "bias": round(bias, 6),
                "rmse": round(rmse, 6),
                "mae": round(mae, 6),
                "n_windows": n_w,
                "n_independent_windows": n_i,
                "fama_beta": np.nan,
                "fama_se": np.nan,
                "fama_t_stat_0": np.nan,
                "fama_t_stat_1": np.nan,
                "notes": note,
            })
            print(f"  {r_name:<20s} | Bias: {bias*100:>+6.2f}% | RMSE: {rmse*100:>5.2f}% | MAE: {mae*100:>5.2f}% | N: {n_w:3d} (Indep: {n_i:2d})")

        # Fama regression record
        records.append({
            "horizon_months": k,
            "rule": "fama_regression",
            "bias": round(float(beta_fama[0]), 6),  # alpha intercept
            "rmse": np.nan,
            "mae": np.nan,
            "n_windows": n_obs,
            "n_independent_windows": n_indep,
            "fama_beta": round(float(beta_fama[1]), 4),
            "fama_se": round(float(se_fama[1]), 4),
            "fama_t_stat_0": round(t_stat_0, 2),
            "fama_t_stat_1": round(t_stat_1, 2),
            "notes": f"Fama OLS: realized = {beta_fama[0]:.4f} + {beta_fama[1]:.4f} * f_cip (NW SE: {se_fama[1]:.4f}, lag={k})",
        })
        print(f"  Fama Regression: slope beta = {beta_fama[1]:.4f} (SE: {se_fama[1]:.4f}) | t(beta=0) = {t_stat_0:>+5.2f} | t(beta=1) = {t_stat_1:>+5.2f}")

    df_out = pd.DataFrame(records)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df_out.to_csv(REPORT_PATH, index=False)
    print(f"\nWrote {REPORT_PATH} with {len(df_out)} rows.")


if __name__ == "__main__":
    main()
