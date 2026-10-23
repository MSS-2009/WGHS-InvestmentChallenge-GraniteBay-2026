# Agent brief r1-taiwan: replace the assumed Taiwan building-cost inflation with data

**Read first, in order:** `docs/loop/COMMON.md` (standing rules; they apply to you in full, especially
rule 6 on data), `docs/MODEL.md` ("Market inputs"), `src/lgm/esg.py` (`tw_cost_growth`,
`tw_cost_vol`, how `tw_cost_log` is simulated), `src/lgm/engine.py` (`facility_real_tw2027`),
`src/lgm/data/fred.py` and `src/lgm/data/fed.py` (the house pattern for a cached, validated downloader).
**Your worktree:** branch `r1-taiwan`, based on `improve`. It already exists; you are in it.
Call its absolute path `WT`. Run everything as `PYTHONPATH=$WT/src PY ...` (see COMMON.md).

## 0. What is settled
The facility will pay for a building in Taiwan. The model converts the January 2033 dollar facility into
"2027 Taiwan building-cost terms" with the simulated USD/TWD rate (Federal Reserve H.10, from data) and
a Taiwan building-cost index that is **assumed**: 4% a year, 1.5% volatility, an i.i.d. random walk,
uncorrelated with anything. A previous session could not reach Taiwan's statistics sites. That
assumption drives the headline "real" median ($157k vs $198k nominal).

## 1. Task 1: get the data (research)
Find and download the longest available history of Taiwan's construction cost index. The official
series is the DGBAS (Directorate-General of Budget, Accounting and Statistics) 營造工程物價指數,
Construction Cost Index, monthly, with sub-indices including building construction (建築工程類).
Try, in roughly this order: DGBAS (`stat.gov.tw`, `nstatdb.dgbas.gov.tw`, `eng.stat.gov.tw`), Taiwan's
open data portal (`data.gov.tw`), any other official mirror you find. Third-party aggregators are
acceptable only as a cross-check, never as the only source.
- Save every raw file under `data/raw/taiwan/`. Record in `data/raw/taiwan/SOURCES.md`: the exact URL,
  download date, SHA-256, what the file contains (series, base year, frequency, first and last period)
  and the steps to reproduce the download.
- Cross-check: state at least three values (e.g. three year-end index levels) against an independent
  page or a second file, and record where they came from.
- If you also find Taiwan CPI from an official source, save it the same way (useful for Task 3).
- If every official source is unreachable or the data cannot be obtained, **stop and report
  `blocked`** with what you tried. Do not reconstruct the series from news articles, do not interpolate
  missing years, and do not type values in by hand.
Commit.

## 2. Task 2: loader `src/lgm/data/taiwan.py`
A function returning the monthly index as a pandas Series with a month-end DatetimeIndex, read from the
cached file, following the house pattern (a `refresh` flag; validate a downloaded response before it
replaces the cache; offline by default). Test in `tests/test_taiwan.py` that runs offline: shape, no
gaps, the cross-check values from Task 1. Commit.

## 3. Task 3: calibration `scripts/taiwan_costs.py`
Using the building-construction sub-index if available (else the total index; say which), report:
- mean and median annual growth (log and simple) over the full sample, the last 20 years and the last
  10 years;
- annual volatility of monthly log changes (x sqrt 12) and the standard deviation of 12-month changes;
  if they disagree a lot, the series is persistent and the i.i.d. model is wrong: say so;
- AR(1) persistence of monthly log changes, and of 12-month inflation;
- correlation of monthly log changes with USD/TWD monthly log changes (`lgm.data.fed.usd_twd`, cached)
  and with US CPI inflation (`lgm.data.fred.cpi`, cached), and with Taiwan CPI if you have it;
- **the quantity that matters**: the distribution of cumulative 72-month growth across every rolling
  window in history (p5, p50, p95), next to what the current assumption implies (4% drift, 1.5% vol,
  i.i.d.) and what your proposed calibration implies.
Write `reports/taiwan_costs.json` and a proposed `config/taiwan.yaml` (growth, vol, and, if the data
says so, a persistence parameter and correlations), each value commented with the script output it came
from. Commit.

## 4. Findings doc `docs/loop/r1_taiwan_findings.md`
What the data is, where it came from, the calibration tables, and a plain recommendation on what the
generator should use, including whether the i.i.d. random walk should be replaced by a persistent
process. Do NOT wire anything into `esg.py`, `backtest.py` or `scoring.py`: the planner will, after
checking your numbers. If you think a structural change is needed, describe it precisely.

## Verify
- `PYTHONPATH=$WT/src PY -m pytest -q` passes (paste the last line verbatim).
- `PYTHONPATH=$WT/src PY scripts/run_all.py` leaves every pre-existing `reports/` file byte-identical.

## Acceptance criteria
- [ ] raw files in `data/raw/taiwan/` with URL, date and SHA-256 in `SOURCES.md`, and three cross-checked values
- [ ] offline loader `src/lgm/data/taiwan.py` with a test
- [ ] `scripts/taiwan_costs.py`, `reports/taiwan_costs.json`, proposed `config/taiwan.yaml`
- [ ] `docs/loop/r1_taiwan_findings.md` with the 72-month comparison and a recommendation
- [ ] tests pass; pre-existing reports byte-identical
- [ ] one commit per task (or a `blocked` report after Task 1 if the data cannot be obtained)

## Files you own
`data/raw/taiwan/`, `src/lgm/data/taiwan.py`, `scripts/taiwan_costs.py`, `tests/test_taiwan.py`,
`config/taiwan.yaml`, `reports/taiwan_costs.json`, `docs/loop/r1_taiwan_findings.md`.
Two other workers are editing `esg.py`, `calibrate.py`, `engine.py` and `strategies.py`: do not touch them.

## Not yours to decide
The values the generator uses, and any structural change to it. Recommend.

## Budget
About 2 hours. Research that hits a wall after a real attempt should be reported as `blocked`, not
stretched to the timeout.
