# Taiwan Price & Construction Cost Data Sources

This directory contains official time series data from the Directorate-General of Budget, Accounting and Statistics (DGBAS), Executive Yuan, Republic of China (Taiwan) (中華民國行政院主計總處).

## Primary Data Files

### 1. `ccispl.ods`
- **Series:** Taiwan Construction Cost Index (Total Index) / 營造工程物價指數 ( 總指數 ) 銜接表
- **Publisher:** DGBAS (行政院主計總處)
- **Portal Page:** https://www.stat.gov.tw/cp.aspx?n=2665
- **Exact Download URL:** https://ws.dgbas.gov.tw/001/Upload/463/relfile/10315/2703/ccispl.ods
- **Download Date:** 2026-10-21
- **File Size:** 36,944 bytes
- **SHA-256:** `478ed82674b781b8acafd87aaba98b81a857c3671d289255298333c51b56076a`
- **Base Year:** 2021 = 100 (民國110年=100, updated from 105=100 in February 2023)
- **Frequency:** Monthly
- **First Period:** 1991-01 (民國80年1月)
- **Last Period:** 2026-09 (民國115年9月)
- **Observations:** 429 consecutive months, zero gaps.
- **Sheets:**
  - `營造工程物價`: Monthly index levels from 1991-01 to 2026-09.
  - `年增率`: Year-over-year percentage change for each month.

### 2. `cpispl.ods`
- **Series:** Taiwan Consumer Price Index (Total Index) / 消費者物價指數 ( 總指數 ) 銜接表
- **Publisher:** DGBAS (行政院主計總處)
- **Portal Page:** https://www.stat.gov.tw/cp.aspx?n=2665
- **Exact Download URL:** https://ws.dgbas.gov.tw/001/Upload/463/relfile/10315/2703/cpispl.ods
- **Download Date:** 2026-10-21
- **File Size:** 53,165 bytes
- **SHA-256:** `2ef241f542b3bd4e0da596b4d305044c71e9b0003ccc7fb0031983bcbb17bb70`
- **Base Year:** 2021 = 100 (民國110年=100)
- **Frequency:** Monthly
- **First Period:** 1959-01 (民國48年1月)
- **Last Period:** 2026-09 (民國115年9月)
- **Observations:** 813 consecutive months.

### 3. `ccimaterials.ods`
- **Series:** Taiwan Construction Cost Materials Sub-Index / 營造工程物價指數-材料類 銜接表
- **Publisher:** DGBAS (行政院主計總處)
- **Portal Page:** https://www.stat.gov.tw/cp.aspx?n=2665
- **Exact Download URL:** https://ws.dgbas.gov.tw/001/Upload/463/relfile/10315/2702/ccimaterials.ods
- **Download Date:** 2026-10-21
- **File Size:** 36,804 bytes
- **SHA-256:** `e1a7c22924dd6e51c0b6d36ba2ef75e00f5c59d981bf1cb94021e3f9fe346353`
- **Base Year:** 2021 = 100 (民國110年=100)
- **Frequency:** Monthly
- **Coverage:** 1991-01 through 2026-09.

### 4. `cciservices.ods`
- **Series:** Taiwan Construction Cost Labor & Services Sub-Index / 營造工程物價指數-勞務類 銜接表
- **Publisher:** DGBAS (行政院主計總處)
- **Portal Page:** https://www.stat.gov.tw/cp.aspx?n=2665
- **Exact Download URL:** https://ws.dgbas.gov.tw/001/Upload/463/relfile/10315/2702/cciservices.ods
- **Download Date:** 2026-10-21
- **File Size:** 36,726 bytes
- **SHA-256:** `dd403f052443d5034c3058165c4ba3358f0fbf2139ec998aed9419ac2eba22e4`
- **Base Year:** 2021 = 100 (民國110年=100)
- **Frequency:** Monthly
- **Coverage:** 1991-01 through 2026-09.

---

## Steps to Reproduce the Download

1. Note on SSL certificates: Taiwan government web servers (`stat.gov.tw`, `ws.dgbas.gov.tw`) use TLS certificates signed by the Taiwan Government Root Certification Authority (GRCA), which lacks Subject Key Identifier (SKI) metadata under RFC 5280. On macOS Python 3.13 / LibreSSL, standard TLS certificate validation will report `Missing Subject Key Identifier (_ssl.c:1028)`. An unverified SSL context (`ssl._create_unverified_context()`) or adding the Taiwan Government Root CA to the certificate store is required when connecting via Python.
2. The official DGBAS price statistics portal is located at `https://www.stat.gov.tw/cp.aspx?n=2665`.
3. Under the statistical tables section (`統計表`), click on the ODF download links:
   - `ccispl.ods`: `https://ws.dgbas.gov.tw/001/Upload/463/relfile/10315/2703/ccispl.ods`
   - `cpispl.ods`: `https://ws.dgbas.gov.tw/001/Upload/463/relfile/10315/2703/cpispl.ods`
   - `ccimaterials.ods`: `https://ws.dgbas.gov.tw/001/Upload/463/relfile/10315/2702/ccimaterials.ods`
   - `cciservices.ods`: `https://ws.dgbas.gov.tw/001/Upload/463/relfile/10315/2702/cciservices.ods`
4. The files can be downloaded using `python3` or `curl -k -O <URL>`.

---

## Cross-Checks

We verified values against multiple independent sources:

### Cross-Check 1: Official New Taipei City Government Report
- **Source:** New Taipei City Government Economic Development Department (新北市政府經濟發展局)
- **Document URL:** `https://www.newtaipeimarket.ntpc.gov.tw/tc/includes/GetFile.ashx?mid=33&id=2571&chk=fd4a37eb-4eca-4af3-8bf0-049f1c880400`
- **Reference Table:** Table 1 ("表一 營造工程物價指數（總指數）銜接表 指數基期：民國 110 年=100", explicitly citing DGBAS Department of Comprehensive Statistics / 行政院主計總處綜合統計處).
- **Verified Values:**
  - December 2021 (ROC 110/12): **103.25** (2021 annual average: 100.00)
  - December 2022 (ROC 111/12): **107.92** (2022 annual average: 107.36)
  - December 2023 (ROC 112/12): **109.88** (2023 annual average: 109.23)
  - December 2024 (ROC 113/12): **111.84** (2024 annual average: 111.40)
  - December 2025 (ROC 114/12): **112.86** (2025 annual average: 112.27)
  All 5 year-end levels and annual averages match `ccispl.ods` exactly to two decimal places.

### Cross-Check 2: Latest Release (September 2026)
- **Source:** DGBAS Monthly Press Notice (中華民國統計資訊網 11509統計表)
- **URL:** `https://www.stat.gov.tw/cp.aspx?n=2665`
- **Verified Value:**
  - September 2026 (ROC 115/09): **120.26**
  - September 2025 (ROC 114/09): **112.09**
  - YoY Change: `(120.26 / 112.09 - 1) * 100 = +7.29%`
  Matches the official published release for the month.

### Cross-Check 3: Internal Multi-Sheet Consistency Check
- In `ccispl.ods`, Sheet 1 (`營造工程物價`) contains monthly index levels $I_{t}$, while Sheet 2 (`年增率`) independently publishes the YoY percentage change $g_{t} = (I_{t} / I_{t-12} - 1) \times 100$.
- Recomputing YoY inflation from Sheet 1 matches Sheet 2 across all test points:
  - 2026-09: $120.26 / 112.09 - 1 = 7.29\%$ (Sheet 2: 7.29)
  - 2025-12: $112.86 / 111.84 - 1 = 0.91\%$ (Sheet 2: 0.91)
  - 2024-12: $111.84 / 109.88 - 1 = 1.78\%$ (Sheet 2: 1.78)
  - 2023-12: $109.88 / 107.92 - 1 = 1.82\%$ (Sheet 2: 1.82)
  - 2022-12: $107.92 / 103.25 - 1 = 4.52\%$ (Sheet 2: 4.52)
  - 2021-12: $103.25 / 92.76 - 1 = 11.31\%$ (Sheet 2: 11.31)
