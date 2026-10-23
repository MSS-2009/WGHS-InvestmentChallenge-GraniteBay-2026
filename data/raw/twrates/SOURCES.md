# Taiwan Short-Term Interest Rates Data Sources

## 1. Primary Source: Central Bank of the Republic of China (Taiwan) (CBC)

### Dataset: Money Market Interest Rates (Table 29.F)
- **Publisher:** Central Bank of the Republic of China (Taiwan) (中華民國中央銀行)
- **Department:** Department of Economic Research (經濟研究處)
- **Publication:** Financial Statistics Monthly (金融統計月報)
- **Primary Endpoint:** `https://cpx.cbc.gov.tw/API/DataAPI/Get?FileName=EG41M01en`
  - **Local Path:** `data/raw/twrates/cbc_money_market_rates.json`
  - **File Size:** 69,950 bytes
  - **Download Date:** 2026-10-22
  - **SHA-256:** `85eadc0925268b2c2b7448b8ca12a8b2bdd51ea54466283f5415d906a452e95c`
  - **Series Coverage:** 1987-05 to 2026-08 (472 monthly observations)
  - **Key Variables:**
    - `Commercial paper-Secondary market-31-90 days` (Market rate for 3-month commercial paper in secondary market, percent per annum)
    - `Interbank call loans` (Weighted average overnight call loan rate, percent per annum)

### Secondary Corroboration File: Financial Statistics Monthly Table 29.F CSV
- **URL:** `https://www.cbc.gov.tw/public/data/EBOOKXLS/149_EG41_A4L.csv`
- **Local Path:** `data/raw/twrates/149_EG41_A4L.csv`
- **File Size:** 8,373 bytes
- **Download Date:** 2026-10-22
- **SHA-256:** `8f640742ab4cf481346502c1fc2fa0a7f55f3ada542f924c51eaab111c6a4eec`

---

## 2. Cross-Checked Benchmark Values

The dataset values were independently verified across the CBC Statistical Database API (`EG41M01en`) and the official CBC Financial Statistics Monthly Table 29.F:

1. **August 2026 (2026M08 / 民國115年8月):**
   - 90-day Commercial Paper (Secondary market): **1.78%** p.a.
   - Overnight Interbank Call Loan Rate: **0.822%** p.a.
   - *Verification:* Verified identical between `cbc_money_market_rates.json` row `["2026M08", "0.822", ..., "1.78"]` and `149_EG41_A4L.csv` line 31 (`0.822 , 1.85 , 1.90 , 1.98 , 1.51 , 1.78`).

2. **December 2024 (2024M12 / 民國113年12月):**
   - 90-day Commercial Paper (Secondary market): **1.75%** p.a.
   - Overnight Interbank Call Loan Rate: **0.820%** p.a.
   - *Verification:* Verified identical between `cbc_money_market_rates.json` row `["2024M12", "0.820", ..., "1.75"]` and `149_EG41_A4L.csv` line 20 (`0.820 , 1.79 , 1.83 , 1.84 , 1.47 , 1.75`).

3. **July 2008 (2008M07 / 民國97年7月, GFC Commodity Peak):**
   - 90-day Commercial Paper (Secondary market): **2.07%** p.a.
   - Overnight Interbank Call Loan Rate: **2.166%** p.a.
   - *Verification:* Verified identical in `cbc_money_market_rates.json` row `["2008M07", "2.166", ..., "2.07"]` and CBC historical statistical archive.

---

## 3. FX Forward & NDF Research Note
- **Exchange Sources:** The Taiwan Futures Exchange (TAIFEX) launched USD/TWD FX Futures (contract code RTF) only in July 2015. Exchange-traded forwards/futures do not exist with historical depth prior to 2015.
- **OTC Forwards/NDF:** Interbank non-deliverable forwards (NDF) in USD/TWD trade predominantly offshore in Hong Kong/Singapore and are not published as a historical time series by CBC or Taiwan government agencies.
- **Covered Interest Parity (CIP):** The theoretical forward price is computed directly via Covered Interest Parity (CIP) using the official Taiwan 90-day commercial paper rate and the US 3-month Treasury par curve yield.

---

## 4. Forward exchange rates of the NT dollar against the US dollar (Table 31.C)
- **Publisher:** Central Bank of the Republic of China (Taiwan), Financial Statistics Monthly, Table 31.C
  ("Forward Exchange Rates of the N.T. Dollar against the U.S. Dollar By Period").
- **Endpoint:** `https://cpx.cbc.gov.tw/API/DataAPI/Get?FileName=EG55M01en`
- **Local Path:** `data/raw/twrates/cbc_forward_rates.json`
- **Download Date:** 2026-10-22
- **File Size:** 55,962 bytes
- **SHA-256:** `a1679dc8e2f25a7481e34244335311bcadd73bd58d6148f940b1f1caabaedbbc`
- **Content:** monthly period averages, buying and selling quotes, tenors 10/30/60/90/120/150/180 days,
  1991-01 to 2026-08 (418 months with data, first 1991-11). Some tenors are missing in some months.
- **Checks:** Aug 2026 180-day 31.243 / 31.403 and 10-day 31.595 / 31.721; Oct 2008 150-day missing (in
  `tests/test_twrates.py`). The annualised 180-day premium correlates 0.89 with the CIP drift computed
  from the CP and Treasury rates (2000-2026), with the gap explained mostly by CP being a credit rate.
- **Re-check:** `cbc_money_market_rates.json` was re-downloaded from the same endpoint on 2026-10-22:
  all 472 monthly rows identical.
