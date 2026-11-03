"""r8-claims reproducer: evidence for contradicted claims in docs/VALIDATION.md and docs/MODEL.md.

Run with:
    PYTHONPATH=src /Users/whinz/WhartonComp/WGHS-InvestmentChallenge-GraniteBay-2026/.venv/bin/python docs/loop/r8_claims_repro.py
"""

from pathlib import Path
import pandas as pd


def check_bl_sensitivity():
    p = Path("reports/bl_sensitivity.csv")
    df = pd.read_csv(p)
    bbjp_min, bbjp_max = df["single_optimum_BBJP"].min(), df["single_optimum_BBJP"].max()
    bbca_min, bbca_max = df["single_optimum_BBCA"].min(), df["single_optimum_BBCA"].max()
    bbjp_resamp_min, bbjp_resamp_max = df["BBJP"].min(), df["BBJP"].max()
    bbca_resamp_min, bbca_resamp_max = df["BBCA"].min(), df["BBCA"].max()

    print("=== Claim 1: docs/VALIDATION.md:177 (Single Optimum BBJP Upper Bound) ===")
    print('Claimed text: "a single optimum swings them from 2.6% to 9.5% and 2.3% to 6.0%."')
    print(f"Evidence file: {p}")
    print(f"  Resampled BBJP range:      {bbjp_resamp_min * 100:.1f}% to {bbjp_resamp_max * 100:.1f}%")
    print(f"  Resampled BBCA range:      {bbca_resamp_min * 100:.1f}% to {bbca_resamp_max * 100:.1f}%")
    print(f"  Single optimum BBJP range: {bbjp_min * 100:.1f}% to {bbjp_max * 100:.1f}%  (min: {bbjp_min:.4f}, max: {bbjp_max:.4f})")
    print(f"  Single optimum BBCA range: {bbca_min * 100:.1f}% to {bbca_max * 100:.1f}%  (min: {bbca_min:.4f}, max: {bbca_max:.4f})")
    print("Contradiction: BBJP single optimum swings from 2.6% to 7.2%, NOT 9.5%.")
    print("Note: docs/MODEL.md:176-177 already quotes the correct figure: 'it moved BBJP between 2.6% and 7.2%'.")
    print()


def check_satellite_risk_sensitivity():
    p = Path("reports/satellite_risk_sensitivity.csv")
    df = pd.read_csv(p)

    as_est = df[df["reading"] == "as_estimated"].iloc[0]
    with_ret = df[df["reading"] == "with_return"].iloc[0]
    risk_only = df[df["reading"] == "risk_only"].iloc[0]

    print("=== Claim 2: docs/MODEL.md:414-415 (Satellite Beta Out-of-Sample Adjustment) ===")
    print('Claimed text: "raises the satellite\'s volatility from 15.1% to 16.9% and its beta from 0.89 to 0.99"')
    print(f"Evidence file: {p}")
    print(f"  as_estimated: satellite_vol = {as_est['satellite_vol']:.4f} ({as_est['satellite_vol']*100:.1f}%), satellite_beta = {as_est['satellite_beta']:.4f} ({as_est['satellite_beta']:.2f})")
    print(f"  with_return:  satellite_vol = {with_ret['satellite_vol']:.4f} ({with_ret['satellite_vol']*100:.1f}%), satellite_beta = {with_ret['satellite_beta']:.4f} ({with_ret['satellite_beta']:.2f})")
    print(f"  risk_only:    satellite_vol = {risk_only['satellite_vol']:.4f} ({risk_only['satellite_vol']*100:.1f}%), satellite_beta = {risk_only['satellite_beta']:.4f} ({risk_only['satellite_beta']:.2f})")
    print("Contradiction: satellite beta rises from 0.87 to 0.97, NOT 0.89 to 0.99.")
    print("Note: docs/MODEL.md:282 already quotes the unadjusted beta correctly: 'beta 0.87'.")
    print()


if __name__ == "__main__":
    check_bl_sensitivity()
    check_satellite_risk_sensitivity()
