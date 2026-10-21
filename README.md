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
- `simple.py` — exact re-implementation of the former team's guide (Steps 1-7).

**Part 2 — growth sleeve (in progress):** 10-15 ETF core allocated with Black-Litterman, plus a 30-50
stock satellite chosen by quantitative and qualitative screens, all scored with the Part 1 Monte Carlo.

## Data (no API keys)
Treasury par curves (home.treasury.gov), Treasury securities (TreasuryDirect), CPI (FRED CSV),
prices and FX (Yahoo Finance chart API). Raw downloads are cached in `data/raw/`.

## Quick start
```
python -m venv .venv && . .venv/bin/activate && pip install -e . pytest
python -m pytest
python scripts/validate_plans_v2.py
```

See `docs/VALIDATION.md` for the check of the former team's numbers.
