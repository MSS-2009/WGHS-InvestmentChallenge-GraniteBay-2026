"""Values evidence from each company's latest 10-K (SEC EDGAR): the exemplar report's Scouting Report method.

Usage: SEC_CONTACT="<name> <email>" python scripts/tenk_values.py
The SEC asks automated clients to identify themselves with a contact in the User-Agent; it is read from the
SEC_CONTACT environment variable and never stored. Requests stay under the SEC's 10-per-second limit.

For every company in reports/universe_pass2_qual.csv: find its latest 10-K, take Item 1 (Business, which since
2020 includes the human-capital disclosure; the whole filing if Item 1 cannot be found), and count words tied to
Laura's values parameters (V1-V25) for each of the qualitative model's five values dimensions. Only the counts
are kept, in data/raw/sec/<ticker>.json; scripts/universe_rank.py turns them into scores.
"""
import html
import json
import os
import re
import sys
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "sec"
KEYWORDS = {   # regex stems per values dimension, from the parameters each dimension maps to
    "innovation_creativity": r"innovat|research and development|patent|invent|creativ|new products?|breakthrough|"
                             r"pioneer|intellectual property|experiment|design",
    "societal_utility": r"patients?\b|health ?care|public health|safety|clean energy|renewable|sustainab|drinking water|"
                        r"food security|nutrition|infrastructure|essential services|affordab|underserved|communit",
    "people_inclusion": r"diversity|inclusion|inclusive|belonging|equal opportunity|human capital|employee engagement|"
                        r"well-?being|pay equity|employee resource group|career development|training and development",
    "trust_integrity": r"privacy|data protection|ethic|code of (business )?conduct|integrity|transparen|"
                       r"anti-corruption|human rights|responsible (sourcing|use|ai)|customer trust",
    "access_education_creators": r"educat|learning|students|scholarship|small business|entrepreneur|creators?\b|"
                                 r"developers?\b|accessib|philanthrop|volunteer|nonprofit|financial inclusion",
}
TAG = re.compile(r"<[^>]+>")
SPACE = re.compile(r"\s+")


def session() -> requests.Session:
    contact = os.environ.get("SEC_CONTACT", "").strip()
    if "@" not in contact:
        sys.exit("set SEC_CONTACT to a name and contact email (the SEC requires it in the User-Agent)")
    s = requests.Session()
    s.headers.update({"User-Agent": contact, "Accept-Encoding": "gzip, deflate"})
    return s


def get(s: requests.Session, url: str) -> requests.Response:
    for attempt in range(4):
        r = s.get(url, timeout=120)
        time.sleep(0.15)
        if r.status_code == 200:
            return r
        time.sleep(2 * (attempt + 1))
    r.raise_for_status()
    return r


def business_section(text: str) -> tuple[str, str]:
    """Item 1 (Business) up to Item 1A; the longest such span skips the table of contents."""
    low = text.lower()
    starts = [m.start() for m in re.finditer(r"item\s*1\s*[.:\-]?\s*business", low)]
    ends = [m.start() for m in re.finditer(r"item\s*1a\s*[.:\-]?\s*risk\s*factors", low)]
    best = (0, 0)
    for a in starts:
        b = next((e for e in ends if e > a), None)
        if b and b - a > best[1] - best[0]:
            best = (a, b)
    if best[1] - best[0] > 5000:
        return text[best[0]:best[1]], "Item 1"
    return text, "whole filing"


def main():
    s = session()
    RAW.mkdir(parents=True, exist_ok=True)
    tick = get(s, "https://www.sec.gov/files/company_tickers.json").json()
    cik = {re.sub(r"[^A-Z0-9]", "", v["ticker"].upper()): int(v["cik_str"]) for v in tick.values()}
    names = pd.read_csv(ROOT / "reports" / "universe_pass2_qual.csv")["ticker"].astype(str)
    done = missing = 0
    for t in names:
        path = RAW / f"{t}.json"
        if path.exists():
            done += 1
            continue
        c = cik.get(re.sub(r"[^A-Z0-9]", "", t.upper()))
        if c is None:
            missing += 1
            continue
        try:
            sub = get(s, f"https://data.sec.gov/submissions/CIK{c:010d}.json").json()["filings"]["recent"]
            k = next((i for i, f in enumerate(sub["form"]) if f in ("10-K", "10-K/A")), None)
            if k is None:
                path.write_text(json.dumps({"ticker": t, "cik": c, "form": None}))
                continue
            acc = sub["accessionNumber"][k].replace("-", "")
            url = f"https://www.sec.gov/Archives/edgar/data/{c}/{acc}/{sub['primaryDocument'][k]}"
            raw = get(s, url).text
            text = SPACE.sub(" ", html.unescape(TAG.sub(" ", raw)))
            section, where = business_section(text)
            out = {"ticker": t, "cik": c, "form": sub["form"][k], "filing_date": sub["filingDate"][k], "url": url,
                   "section": where, "words": len(section.split()),
                   "hits": {d: len(re.findall(p, section, re.I)) for d, p in KEYWORDS.items()}}
            path.write_text(json.dumps(out))
            done += 1
        except (requests.RequestException, ValueError, KeyError) as e:
            print(f"{t}: {type(e).__name__}", flush=True)
        if done % 50 == 0:
            print(f"{done} done", flush=True)
    print(f"finished: {done} with counts, {missing} without an SEC ticker match", flush=True)


if __name__ == "__main__":
    main()
