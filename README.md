# Laura Gao investment model

Liability-driven investment model for the 2026-27 Laura Gao case: fund ten fixed $50,000 payments
(2033-2042) with certainty, then build the largest responsible facility contribution for 2033.

**Part 1 — core funding model (built)**
- `curve.py` — Treasury par curve to zero-coupon curve (bootstrapping).
- `instruments.py`, `ladder.py` — WInS-permitted Treasuries and iBonds ETFs; cheapest cash-flow-matched
  reserve as a linear program (HiGHS).
- `calibrate.py`, `esg.py` — monthly scenario generator calibrated to 1994-2026 data: three-factor
  Nelson-Siegel yield curve, US / developed / emerging stocks with fat tails (Student-t), inflation,
  USD/TWD and Taiwan building costs.
- `strategies.py`, `engine.py` — strategy rules (lock schedule, mix, rebalancing band, 2031 floor,
  contribution rule) simulated month by month; Monte Carlo scoring against Laura's goals; nested
  2031 simulation for the co-sponsor range.
- `backtest.py` — historical replay: 184 real six-year paths (2005-2026) applied to today's curve.
- `simple.py` — exact re-implementation of the former team's guide (Steps 1-7).

**Part 2 — growth sleeve (built)**
- `growth/core.py`, `black_litterman.py`, `lookthrough.py` — nine-ETF core: market-cap prior, views from
  13 firms' published capital-market assumptions, constrained optimiser (no tech/communication or
  China+Taiwan overweight), resampled over 500 posterior draws for stable weights.
- `growth/satellite.py`, `qualitative.py` — 35-stock satellite: S&P 500 risk and return-quality screens,
  then the values (Laura fit) and company-strength model with yes/no gates; HRP weights.
- `growth/portfolio.py`, `scoring.py` — the satellite as one more Black-Litterman asset (alpha view over
  its style benchmark), sized and judged with the Part 1 Monte Carlo, including commissions and WInS
  whole-share orders.

See `docs/MODEL.md` for the design and results.

## Data (no API keys)
Treasury par curves (home.treasury.gov), Treasury securities (TreasuryDirect), CPI (FRED CSV),
prices and FX (Yahoo Finance chart API), ETF holdings (iShares), company financials and analyst
ratings (Nasdaq). Raw downloads are cached in `data/raw/`. The October 2026 news check on the selected
stocks used Bigdata.com (https://bigdata.com); its effect is recorded in `config/qualitative_judgments.csv`.

## Quick start
```
python -m venv .venv && . .venv/bin/activate && pip install -e . pytest
python -m pytest
python scripts/validate_plans_v2.py
python scripts/build_core.py
python scripts/build_satellite.py
python scripts/validate_model.py    # how good is the model: generator checks, convergence, replay, BL sensitivity
python scripts/report_numbers.py    # headline numbers for the IPS and Final Report
```

See `docs/VALIDATION.md` for the check of the former team's numbers.
