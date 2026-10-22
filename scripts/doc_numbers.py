"""Check that the figures docs/MODEL.md and docs/VALIDATION.md quote match the reports they come from.

Usage: python scripts/doc_numbers.py [--fix]
Each check reads one figure from a committed report, formats it the way the docs write it, and looks
for that text in the doc. A model change that moves a number then fails tests/test_doc_numbers.py
until the doc is updated, instead of leaving a stale figure behind. Run scripts/run_all.py first.
Exit status 1 if any figure is missing. With --fix, each missing figure whose old version (the same
text with any numbers) appears exactly once in its doc is rewritten in place; the rest are listed.
"""
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / "reports"


def k(x: float) -> str:
    """$197.6k style."""
    return f"${x / 1000:,.1f}k"


def rng(a: float, b: float) -> str:
    return f"{k(a)}-{k(b)}"


def checks() -> list[tuple[str, str, str]]:
    """(doc, what, text that must appear)."""
    rn = json.loads((R / "report_numbers.json").read_text())
    ps = json.loads((R / "policy_study.json").read_text())
    plan, stress, q = rn["plan"], rn["stress"], rn["quotes_2031"]["median"]
    sl = rn["sleeves"]
    fx = pd.read_csv(R / "fx_variants.csv").set_index("variant")
    out = [
        ("MODEL", "rate stress, base to -75bp", f"the IPS median falls from\n{k(plan['median'])} to "
                                              f"{k(stress['rates_minus_75bp_at_lock']['median'])}"),
        ("MODEL", "rate stress, +75bp", f"0.75 points higher: {k(stress['rates_plus_75bp_at_lock']['median'])}"),
        ("MODEL", "3-fund sleeve medians",
         f"| VTI/VEA/VWO 60/30/10 (3 funds) | {k(sl['bl|wins_commissions|VTI/VEA/VWO 60/30/10']['median'])} | "
         f"{k(sl['bl|no_commissions|VTI/VEA/VWO 60/30/10']['median'])} | "
         f"{k(sl['equilibrium|wins_commissions|VTI/VEA/VWO 60/30/10']['median'])} |"),
        ("MODEL", "BL core medians",
         f"| Black-Litterman core (9 funds) | {k(sl['bl|wins_commissions|Black-Litterman core']['median'])} | "
         f"{k(sl['bl|no_commissions|Black-Litterman core']['median'])} | "
         f"{k(sl['equilibrium|wins_commissions|Black-Litterman core']['median'])} |"),
        ("MODEL", "secured in 2031 (typical)", f"above the {k(q['guaranteed_contribution'])}"),
        ("MODEL", "10-90 contribution range", f"| Model 10th-90th percentile (historically ~98% of outcomes) | "
                                             f"{rng(*q['contribution_range'])} |"),
        ("MODEL", "calibrated 20-80 contribution range", f"| 20th-80th percentile (historically ~80% of outcomes) | "
                                                        f"{rng(*q['contribution_range_calibrated'])} |"),
        ("MODEL", "reverse stress, worst 1% mean", f"average a {k(ps['reverse_stress']['worst_1pct']['facility_mean'])} facility"),
        ("MODEL", "real median, hedged vs not", f"real median of {k(fx.loc['forward_latest', 'real_median'])} "
                                              f"instead of {k(plan['real_median'])}"),
        ("MODEL", "real median, loop summary", f"(real median $156.8k -> {k(plan['real_median'])})"),
    ]
    for row in ps["floor_frontier"]:
        f = row["floor_share"]
        if abs(f - 0.2) < 1e-9:
            continue                     # the doc's table shows the 0, 40, 60, 80 and 100% floors
        label = f"{f:.0%}" + (" (IPS)" if abs(f - 0.6) < 1e-9 else "")
        lo, hi = row["range_2031_typical"]
        range_txt = k(lo) if lo == hi else rng(lo, hi)
        secured = "$0" if row["secured_2031_typical"] == 0 else k(row["secured_2031_typical"])
        out.append(("MODEL", f"floor frontier {label}",
                    f"| {label} | {k(row['median'])} | {k(row['p5'])} | {k(row['p95'])} | {secured} | {range_txt} |"))
    sat = pd.read_csv(R / "satellite_scoring.csv")
    piv = sat.pivot_table(index=["beliefs", "commissions"], columns="candidate", values="median_vs_core")
    for beliefs, comm, label in (("Equilibrium (no alpha)", "$25 (WInS)", "Equilibrium (no alpha) | $25 per trade (WInS)"),
                                 ("Black-Litterman posterior", "$25 (WInS)", "BL posterior (+0.22%) | $25 per trade (WInS)"),
                                 ("Black-Litterman posterior", "none", "BL posterior (+0.22%) | none"),
                                 ("Satellite alpha as hoped (+0.82%)", "$25 (WInS)", "Alpha as hoped (+0.82%) | $25 per trade (WInS)")):
        cells = [piv.loc[(beliefs, comm), f"Core + {s}% satellite"] / 1000 for s in (10, 20, 30)]
        txt = " | ".join(("+" if c >= 0 else "−") + f"${abs(c):.1f}k" for c in cells)
        out.append(("MODEL", f"satellite verdict: {label}", f"| {label} | {txt} |"))
    conv = pd.read_csv(R / "validation_convergence.csv")
    se = conv.std() / np.sqrt(len(conv))
    out.append(("VALIDATION", "convergence",
                f"the median facility is ${conv['median'].mean():,.0f} with a standard\n  error of ${se['median']:,.0f}; "
                f"the 5th percentile's is ${se['p5']:,.0f}."))
    bt = pd.read_csv(R / "backtest.csv")
    ips = bt[(bt.paths.str.startswith("History re-centred")) & (bt.strategy == "IPS, Black-Litterman core")].iloc[0]
    out.append(("VALIDATION", "replay vs simulation",
                f"the IPS median is {k(ips['median'])} against {k(plan['median'])}\n  simulated; its 5th percentile is "
                f"{k(ips['p5'])} against {k(plan['p5'])} simulated"))
    pv = pd.read_csv(R / "plans_v2_validation.csv").set_index("strategy")
    for short, full in (("S8 hybrid", "S8 Hybrid, half-hedged"), ("S6 lock, stock surplus", "S6 Bond-first, equity surplus"),
                        ("S9 lock, 60/40, floor", "S9 Bond-first, 60/40 surplus, 60% floor")):
        r = pv.loc[full]
        out.append(("VALIDATION", f"Plans v2 table: {short}",
                    f"/ {r.p5_k:.1f} | {r.v2_median_k:.1f} / {r.median_k:.1f} | {r.v2_p95_k:.1f} / {r.p95_k:.1f} |"))
    esg = pd.read_csv(R / "validation_esg.csv").set_index("check")
    lo, hi = (esg.loc[f"10-year yield change to Jan 2033, {p}"] for p in ("p5", "p95"))
    pt = lambda x: f"{x * 100:+.1f}"
    out.append(("VALIDATION", "10-year yield change spread",
                f"spans {pt(lo.model)} to {pt(hi.model)} points (5th-95th\n  percentile), against "
                f"{pt(lo.history_2005_2026)} to {pt(hi.history_2005_2026)} points"))
    rp = json.loads((R / "rate_path_scenario.json").read_text())
    out.append(("MODEL", "Kim-Wright path", f"the median facility is\n  ${(rp['unchanged']['median'] - rp['kim_wright']['median']) / 1000:.1f}k lower"))
    v2 = json.loads((R / "plans_v2_rate_stress.json").read_text())
    out.append(("VALIDATION", "Plans v2 rate stress",
                f"{k(v2['base_median'])} -> {k(v2['minus_75bp_median'])}"))
    return out


NUMBER = r"[−+-]?\$?\d[\d,]*(?:\.\d+)?k?%?"


def pattern(text: str) -> re.Pattern:
    """The expected text with every number generalised, to find the stale version of it."""
    head = ""
    if text.startswith("| "):                      # a table row: its first cell is the row's label, keep it
        cut = text.index(" | ", 2) + 3
        head, text = text[:cut], text[cut:]
    parts = re.split(f"({NUMBER})", text)
    return re.compile(re.escape(head) + "".join(NUMBER if i % 2 else re.escape(x) for i, x in enumerate(parts)))


def fix() -> list[tuple[str, str, str]]:
    """Rewrite each stale figure found exactly once; return the ones that could not be placed."""
    paths = {"MODEL": ROOT / "docs" / "MODEL.md", "VALIDATION": ROOT / "docs" / "VALIDATION.md"}
    texts = {d: p.read_text() for d, p in paths.items()}
    left = []
    for doc, what, text in missing():
        hits = pattern(text).findall(texts[doc])
        if len(hits) == 1:
            texts[doc] = texts[doc].replace(hits[0], text)
        else:
            left.append((doc, what, text))
    for d, p in paths.items():
        p.write_text(texts[d])
    return left


def missing() -> list[tuple[str, str, str]]:
    docs = {"MODEL": (ROOT / "docs" / "MODEL.md").read_text(), "VALIDATION": (ROOT / "docs" / "VALIDATION.md").read_text()}
    return [c for c in checks() if c[2] not in docs[c[0]]]


def main() -> int:
    if "--fix" in sys.argv:
        for doc, what, text in fix():
            print(f"could not place: {doc} {what}: {text!r}")
    bad = missing()
    for doc, what, text in checks():
        print(f"{'MISSING' if (doc, what, text) in bad else 'ok':8s} {doc:10s} {what}: {text!r}")
    print(f"\n{len(bad)} of {len(checks())} figures missing from the docs")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
