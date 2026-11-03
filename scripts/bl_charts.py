"""Black-Litterman charts for the Final Report.

Usage: python scripts/bl_charts.py
Reads reports/core_bl.csv and config/cma.yaml; writes reports/figures/bl_return_estimates.png,
bl_firm_forecasts.png and bl_weights.png, and the numbers behind them to reports/bl_chart_data.csv.
Returns are geometric (compound) annual returns before fees, as the firms publish them.
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "reports" / "figures"
SURFACE, INK, INK2, GRID, RULE = "#fcfcfb", "#0b0b0b", "#52514e", "#e8e7e2", "#c3c2b7"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"     # categorical slots 1-3 (validated, light mode)
REGION = {"VUG": "us", "VTV": "us", "VB": "us", "VGK": "intl_dev", "BBJP": "intl_dev", "EPP": "intl_dev",
          "BBCA": "intl_dev", "EMXC": "em", "MCHI": "em"}
REGION_NAME = {"us": "US", "intl_dev": "Developed ex-US", "em": "Emerging"}

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": RULE, "axes.labelcolor": INK2,
                     "xtick.color": INK2, "ytick.color": INK, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
                     "savefig.facecolor": SURFACE})


def frame(fig, ax, title, subtitle, legend=False):
    fig.text(0.015, 0.975, title, fontsize=13, color=INK, fontweight="bold", va="top")
    fig.text(0.015, 0.925, subtitle, fontsize=9.5, color=INK2, va="top")
    if legend:
        fig.legend(*ax.get_legend_handles_labels(), loc="upper left", bbox_to_anchor=(0.008, 0.885), ncol=3,
                   frameon=False, fontsize=9, labelcolor=INK, handletextpad=0.3, columnspacing=1.4)
    fig.tight_layout(rect=(0, 0, 1, 0.83 if legend else 0.88))
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0)


def main():
    cfg = yaml.safe_load((ROOT / "config" / "cma.yaml").read_text())
    t = pd.read_csv(ROOT / "reports" / "core_bl.csv").set_index("etf")
    firms = pd.DataFrame(cfg["firms"]).T
    med = firms.median()
    var = t["vol"] ** 2
    d = pd.DataFrame({
        "group": t["group"],
        "market_implied": t["pi_excess"] + cfg["cash_long_run"] - 0.5 * var,
        "firm_median_region": [med[REGION[e]] for e in t.index],
        "black_litterman": t["bl_geo_total"],
        "w_market": t["w_mkt"], "w_black_litterman": t["w_bl"],
    })
    FIG.mkdir(parents=True, exist_ok=True)
    d.round(5).to_csv(ROOT / "reports" / "bl_chart_data.csv")

    # 1. Three return estimates per fund
    s = d.sort_values("black_litterman")
    y = np.arange(len(s))
    fig, ax = plt.subplots(figsize=(8.6, 5.8))
    for i, (_, r) in enumerate(s.iterrows()):
        ax.plot([r["market_implied"] * 100, r["black_litterman"] * 100], [i, i], color=RULE, linewidth=2, zorder=1)
    ax.scatter(s["firm_median_region"] * 100, y, marker="D", s=46, color=AQUA, edgecolor=SURFACE, linewidth=1.5,
               label="13-firm median forecast for its region", zorder=2)
    ax.scatter(s["market_implied"] * 100, y, marker="s", s=52, color=ORANGE, edgecolor=SURFACE, linewidth=1.5,
               label="Market-implied (prior)", zorder=3)
    ax.scatter(s["black_litterman"] * 100, y, marker="o", s=70, color=BLUE, edgecolor=SURFACE, linewidth=1.5,
               label="Black-Litterman (posterior)", zorder=4)
    for i, (_, r) in enumerate(s.iterrows()):
        ax.text(1.02, i, f"{r['black_litterman']:.1%}", transform=ax.get_yaxis_transform(), va="center",
                fontsize=9, color=INK)
    ax.text(1.02, len(s) - 0.35, "Black-\nLitterman", transform=ax.get_yaxis_transform(), va="bottom",
            fontsize=8, color=INK2)
    ax.set_yticks(y, [f"{e}  {g}" for e, g in zip(s.index, s["group"])])
    ax.set_xlabel("Expected return, % a year (10-year, compound, before fees)")
    ax.set_xlim(min(s[["market_implied", "black_litterman", "firm_median_region"]].min()) * 100 - 0.5,
                max(s[["market_implied", "black_litterman", "firm_median_region"]].max()) * 100 + 1.0)
    frame(fig, ax, "Three return estimates for each fund",
          "Our custom Black-Litterman model starts from the market-implied return and moves it toward 13 firms' forecasts",
          legend=True)
    fig.savefig(FIG / "bl_return_estimates.png", dpi=200)
    plt.close(fig)

    # 2. The firms' forecasts behind the views
    fig, ax = plt.subplots(figsize=(8.2, 4.6))
    regions = ["us", "intl_dev", "em"]
    rng = np.random.default_rng(3)
    for k, reg in enumerate(regions):
        v = firms[reg].astype(float) * 100
        ax.scatter(v, k + rng.uniform(-0.12, 0.12, len(v)), s=40, color=BLUE, edgecolor=SURFACE, linewidth=1.2, zorder=2)
        ax.plot([med[reg] * 100] * 2, [k - 0.3, k + 0.3], color=INK, linewidth=2, zorder=3)
        ax.text(med[reg] * 100, k + 0.36, f"median {med[reg]:.1%}", ha="center", fontsize=9, color=INK)
        lo, hi = v.idxmin(), v.idxmax()
        ax.text(v[lo] - 0.12, k - 0.2, lo, ha="right", fontsize=8, color=INK2)
        ax.text(v[hi] + 0.12, k - 0.2, hi, ha="left", fontsize=8, color=INK2)
    ax.set_yticks(range(3), [REGION_NAME[r] for r in regions])
    ax.set_ylim(-0.6, 2.75)
    ax.set_xlabel("10-year expected return, % a year (each dot is one firm)")
    frame(fig, ax, "What 13 firms expect from stocks over the next 10 years",
          "Their medians set the market level and the four views of our custom Black-Litterman model")
    fig.savefig(FIG / "bl_firm_forecasts.png", dpi=200)
    plt.close(fig)

    # 3. Market weights against Black-Litterman weights
    s = d.sort_values("w_black_litterman")
    y = np.arange(len(s))
    fig, ax = plt.subplots(figsize=(8.6, 5.6))
    for i, (_, r) in enumerate(s.iterrows()):
        ax.plot([r["w_market"] * 100, r["w_black_litterman"] * 100], [i, i], color=RULE, linewidth=2, zorder=1)
        ax.text(max(r["w_market"], r["w_black_litterman"]) * 100 + 0.8, i,
                f"{r['w_black_litterman']:.1%} vs {r['w_market']:.1%}", va="center", fontsize=9, color=INK)
    ax.scatter(s["w_market"] * 100, y, marker="s", s=52, color=ORANGE, edgecolor=SURFACE, linewidth=1.5,
               label="Market weight", zorder=2)
    ax.scatter(s["w_black_litterman"] * 100, y, marker="o", s=70, color=BLUE, edgecolor=SURFACE, linewidth=1.5,
               label="Black-Litterman weight", zorder=3)
    ax.set_yticks(y, [f"{e}  {g}" for e, g in zip(s.index, s["group"])])
    ax.set_xlim(0, 42)
    ax.set_xlabel("Share of the stock money, %")
    frame(fig, ax, "How our custom Black-Litterman model tilts the nine funds",
          "Less US growth (tech), more value, small companies and developed markets outside the US", legend=True)
    fig.savefig(FIG / "bl_weights.png", dpi=200)
    plt.close(fig)
    print(d.round(4).to_string())


if __name__ == "__main__":
    main()
