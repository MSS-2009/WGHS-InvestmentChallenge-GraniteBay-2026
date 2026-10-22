# Agent brief r4-fx: what should the generator assume about the US dollar against the Taiwan dollar?

**Read first, in order:** `docs/loop/COMMON.md` (standing rules, in full; rule 6 on data matters
here), `docs/MODEL.md` ("Market inputs"), `src/lgm/esg.py` (`fx_drift`, `fx_log`),
`src/lgm/calibrate.py` (`usd_twd_monthly`), `src/lgm/data/fed.py`, `scripts/rate_path_study.py`
(the house pattern for testing a forecast rule on history), `src/lgm/engine.py` (`facility_real_tw2027`).
**Your worktree:** branch `r4-fx`, based on `improve`. Already created; you are in it.
Run everything as `PYTHONPATH=$WT/src PY ...`.

## 0. What landed (verified by the planner)
Your r3-taiwan branch is merged. The planner checked that the AR(2) coefficients reproduce the data's
lag-1 and lag-2 autocorrelations (0.598, 0.298) and that the variance-ratio table matches. Your
conclusion stands: today's starting state moves the real median by about $0.2k, and the drift
choice moves it by up to $11k. Well done on the refit.

## 1. The question
The real (Taiwan building-cost) value of the 2033 facility depends just as much on USD/TWD, which the
generator models as a driftless random walk (`fx_drift = 0`). US short rates are around 4.3% and
Taiwan's are far lower, so covered interest parity prices the dollar to weaken against TWD by
roughly the rate differential each year. The forward rate is the market's hedged price. It is
known to be a poor forecast of the future spot rate in many currencies (the forward premium
puzzle), but that is a claim to test on TWD, not to assume. Which drift should the generator use,
and how much does it change the real median?

## 2. Task 1: data (research)
Get, as month-end series back as far as available:
- Taiwan short-term interest rates from an official source, e.g. the Central Bank of the Republic of
  China (Taiwan) (`cbc.gov.tw`): interbank overnight call rate, 90-day commercial paper or bill
  rates, or the central bank discount rate. Prefer a market rate with a tenor near 3 months.
- If you can find them from an official or exchange source, USD/TWD forward or NDF points. Do not
  use a forum or blog as a source for these.
- The US 3-month rate is already cached (Treasury par curves in `data/raw/`).
Raw files under `data/raw/twrates/`, with URL, date and SHA-256 in `SOURCES.md` and three
cross-checked values. If no official Taiwan rate series can be obtained, report `blocked` with what
you tried. Loader in `src/lgm/data/twrates.py`, offline by default, with a test. Commit.

## 3. Task 2: which forecast rule works for TWD? (`scripts/fx_drift_study.py`)
From every month-end with data, forecast USD/TWD 72 months ahead (also 12 and 36) with:
(a) random walk (no change); (b) interest-differential drift (CIP forward, or the forward points if
you have them); (c) half of (b); (d) the trailing 10-year average drift. Report for each rule and
horizon: mean error (bias), RMSE and mean absolute error of the log forecast, and the number of
independent windows. Then a Fama-style regression of the realised k-month change on the
interest differential (slope and its standard error, with overlap-robust errors); a slope of 1
means the forward is unbiased, and 0 means a random walk. Write `reports/fx_drift_study.csv`. Commit.

## 4. Task 3: what it changes (`scripts/fx_variants.py`)
Headline IPS parameters as `scripts/report_numbers.py` builds them. The Taiwan cost process is the
fitted AR(2) from your round-3 work at the full-sample drift (`config/taiwan.yaml`); state the exact
settings. Variants: `fx_drift` = 0, the current interest differential, half of it, and whatever
rule your Task 2 favours. For each: median, p5, p95 of `facility_real_tw2027`, and the nominal median
(must not change). Write `reports/fx_variants.csv`. Commit.

## 5. Findings `docs/loop/r4_fx_findings.md`
Data and sources, the forecast-rule table, the regression, the variants, and a recommendation.

## Verify / acceptance
- [ ] official Taiwan rate series on disk with URL, date, SHA-256, three cross-checks; loader and test (or `blocked`)
- [ ] `reports/fx_drift_study.csv` with every rule x horizon, and the regression
- [ ] `reports/fx_variants.csv`
- [ ] `docs/loop/r4_fx_findings.md` with a recommendation
- [ ] `PYTHONPATH=$WT/src PY -m pytest -q` passes; `scripts/run_all.py` leaves every pre-existing `reports/` file byte-identical
- [ ] one commit per task

## Files you own
`data/raw/twrates/`, `src/lgm/data/twrates.py`, `scripts/fx_drift_study.py`, `scripts/fx_variants.py`,
`tests/test_twrates.py`, `reports/fx_*`, `docs/loop/r4_fx_findings.md`. **Do not edit `esg.py`**:
another worker is changing its shock block right now, and `fx_drift` already exists as a parameter.

## Not yours to decide
The FX drift used for headline numbers.

## Budget
About 2 hours. Keep peak memory low (COMMON.md rule 11).
