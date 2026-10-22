"""Loader for Treasury STRIPS and late-December notes from collected market quotes."""
from __future__ import annotations

import csv
import datetime as dt
from pathlib import Path

from ..instruments import TreasuryBond, TreasuryStrip

RAW_STRIPS_CSV = Path(__file__).resolve().parents[3] / "data" / "raw" / "strips" / "quotes_20261022.csv"


def load_quotes(path: Path | str | None = None) -> list[dict]:
    p = Path(path) if path else RAW_STRIPS_CSV
    with open(p, newline="") as f:
        return list(csv.DictReader(f))


def _quote(r: dict, side: str) -> float:
    """The collected quote: "mid" (the broker's last price) or "ask" (what a buyer pays)."""
    return float(r["ask_price"] if side == "ask" else r["price"])


def strips_universe(use_market_quotes: bool = True, path: Path | str | None = None,
                    side: str = "mid") -> list[TreasuryStrip]:
    """Treasury STRIPS maturing November 15 for 2032 through 2041.

    If use_market_quotes is True, the instruments use the real broker quotes collected
    on disk (the mid, or the ask with side="ask"). If False, price is None so they price off the zero curve.
    """
    rows = load_quotes(path)
    out = []
    for r in rows:
        if r["type"] in ("I-STRIP", "P-STRIP"):
            mat = dt.date.fromisoformat(r["maturity"])
            px = _quote(r, side) if use_market_quotes else None
            out.append(
                TreasuryStrip(
                    cusip=r["cusip"],
                    maturity=mat,
                    price=px,
                    label=r["description"],
                    strip_type=r["type"],
                )
            )
    return out


def december_notes_universe(use_market_quotes: bool = True, path: Path | str | None = None,
                            side: str = "mid") -> list[TreasuryBond]:
    """Treasury notes/bonds maturing in late December in 2032-2041.

    Specifically, the UST 3.875% note maturing 2032-12-31 (CUSIP 91282CPQ8).
    If use_market_quotes is True, clean_quote is set to the market clean price.
    """
    rows = load_quotes(path)
    out = []
    for r in rows:
        if r["type"] == "NOTE":
            mat = dt.date.fromisoformat(r["maturity"])
            c = float(r["coupon"]) / 100.0
            px = _quote(r, side) if use_market_quotes else None
            out.append(
                TreasuryBond(
                    cusip=r["cusip"],
                    coupon=c,
                    maturity=mat,
                    label=r["description"],
                    clean_quote=px,
                )
            )
    return out


def strips_plus_december_universe(use_market_quotes: bool = True, path: Path | str | None = None,
                                  side: str = "mid") -> list[TreasuryStrip | TreasuryBond]:
    """STRIPS plus the December-maturing Treasury notes/bonds."""
    return strips_universe(use_market_quotes, path, side) + december_notes_universe(use_market_quotes, path, side)
