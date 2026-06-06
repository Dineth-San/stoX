"""
build_prices_live.py — Fetch today's CSE prices via the live API and
append them to the cleaned price panel.

Run this once per trading day (after market close ~4:30 PM Sri Lanka time).
It reads today's OHLCV from the CSE tradeSummary API, filters to the 20
SL20 tickers, and appends to master_prices.parquet.

After running this, also run:
    python build_alignment.py     # re-aligns panel with macro data
    python build_features.py      # re-engineers features
This updates the feature panel so predict.py uses today's close.

Usage
-----
    python build_prices_live.py              # append today
    python build_prices_live.py --dry-run    # preview without saving
    python build_prices_live.py --date 2026-05-21   # backfill a specific date
"""

import argparse
import logging
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ML_DIR = Path(__file__).parent
sys.path.insert(0, str(ML_DIR / "src"))

import numpy as np
import pandas as pd
import requests

from sl20_ml.utils.config import load_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

CSE_API = "https://www.cse.lk/api"
SL20_TICKERS = [
    "JKH", "COMB", "DIAL", "SAMP", "HAYL", "CTC", "HNB", "LIOC",
    "SPEN", "DFCC", "NTB", "BUKI", "CARG", "CCS", "HHL", "LION",
    "MELS", "TKYO", "VONE", "AEL",
]

# CSE symbol → our ticker (strip .N0000 suffix)
def _symbol_to_ticker(symbol: str) -> str:
    return symbol.split(".")[0]


def fetch_today_prices() -> pd.DataFrame:
    """
    Call CSE tradeSummary API and return a DataFrame with today's OHLCV
    for all traded securities.

    Returns columns: ticker, date, open, high, low, close, volume, turnover, trades
    """
    logger.info("Fetching prices from CSE tradeSummary API ...")
    resp = requests.post(
        f"{CSE_API}/tradeSummary",
        headers={"User-Agent": "stoX/1.0", "Accept": "application/json"},
        data={},
        timeout=20,
    )
    resp.raise_for_status()
    payload = resp.json()

    # Response: {"reqTradeSummery": [...]}
    raw: list[dict] = []
    if isinstance(payload, dict):
        for v in payload.values():
            if isinstance(v, list):
                raw = v
                break
    elif isinstance(payload, list):
        raw = payload

    if not raw:
        raise ValueError("tradeSummary returned empty payload")

    rows = []
    for item in raw:
        symbol = item.get("symbol", "")
        ticker = _symbol_to_ticker(symbol)

        # Derive trade date from lastTradedTime (Unix ms) or use today
        ts_ms = item.get("lastTradedTime") or item.get("tradesTime")
        if ts_ms:
            trade_date = pd.Timestamp(int(ts_ms), unit="ms", tz="UTC").normalize()
        else:
            trade_date = pd.Timestamp(date.today())

        open_  = item.get("open")
        high   = item.get("high")
        low    = item.get("low")
        close  = item.get("closingPrice") or item.get("lastTradedPrice")
        vol    = item.get("sharevolume") or item.get("quantity", 0)
        turn   = item.get("turnover", np.nan)
        trades = item.get("tradevolume") or item.get("trades", np.nan)

        # Skip rows with no meaningful trade data
        if not close or close == 0:
            continue

        rows.append({
            "ticker":   ticker,
            "date":     trade_date,
            "open":     float(open_)  if open_  else float(close),
            "high":     float(high)   if high   else float(close),
            "low":      float(low)    if low    else float(close),
            "close":    float(close),
            "volume":   float(vol)    if vol    else 0.0,
            "turnover": float(turn)   if turn   else np.nan,
            "trades":   float(trades) if trades else np.nan,
        })

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)  # strip tz for parquet
    logger.info(f"  API returned {len(df)} securities for {df['date'].iloc[0].date() if len(df) else 'N/A'}")
    return df


def append_to_panel(
    new_rows: pd.DataFrame,
    prices_path: Path,
    dry_run: bool = False,
) -> pd.DataFrame:
    """
    Load existing master_prices.parquet, remove any rows for the same
    date (idempotent re-run), append new rows, and save.
    """
    if prices_path.exists():
        existing = pd.read_parquet(prices_path)
    else:
        logger.warning(f"  {prices_path} not found — creating fresh file")
        existing = pd.DataFrame(columns=new_rows.columns)

    # Filter to SL20 tickers only
    sl20_rows = new_rows[new_rows["ticker"].isin(SL20_TICKERS)].copy()

    # Deduplicate: some tickers have multiple share classes (ordinary + preference).
    # Keep the row with the highest volume per ticker — that's always the main class.
    sl20_rows = (
        sl20_rows.sort_values("volume", ascending=False)
        .drop_duplicates(subset=["ticker", "date"], keep="first")
    )
    logger.info(f"  SL20 rows in today's fetch: {len(sl20_rows)} / {len(SL20_TICKERS)} tickers")

    missing = set(SL20_TICKERS) - set(sl20_rows["ticker"].unique())
    if missing:
        logger.warning(f"  Tickers not traded today: {sorted(missing)}")

    # Idempotent: remove existing rows for the same date before appending
    new_date = sl20_rows["date"].iloc[0] if len(sl20_rows) else None
    if new_date is not None:
        before = len(existing)
        existing = existing[existing["date"] != new_date]
        removed = before - len(existing)
        if removed:
            logger.info(f"  Replaced {removed} existing rows for {new_date.date()}")

    # Carry over columns from existing panel that the API doesn't provide
    # (adj_close, daily_return, year, ohlc_inconsistent, suspicious_move)
    for col in ["trades", "year", "daily_return", "ohlc_inconsistent",
                "suspicious_move", "adj_close"]:
        if col not in sl20_rows.columns:
            sl20_rows[col] = np.nan

    sl20_rows["year"] = sl20_rows["date"].dt.year

    combined = pd.concat([existing, sl20_rows], ignore_index=True)
    combined = combined.sort_values(["ticker", "date"]).reset_index(drop=True)

    if dry_run:
        logger.info(f"  DRY RUN — would save {len(combined)} rows (not writing)")
        return combined

    combined.to_parquet(prices_path, index=False)
    logger.info(f"  Saved {len(combined)} total rows to {prices_path}")
    return combined


def main():
    parser = argparse.ArgumentParser(description="Fetch today's CSE prices and update panel")
    parser.add_argument("--dry-run", action="store_true", help="Preview without saving")
    parser.add_argument("--date",    default=None, help="Override date (YYYY-MM-DD)")
    args = parser.parse_args()

    cfg        = load_config()
    ml_dir     = ML_DIR
    prices_path = ml_dir / cfg["paths"]["cleaned"]["prices"]

    logger.info("=" * 60)
    logger.info("stoX — Live Price Update")
    logger.info("=" * 60)

    # Fetch from API
    df = fetch_today_prices()

    # Override date if requested (useful for backfill testing)
    if args.date:
        df["date"] = pd.Timestamp(args.date)
        logger.info(f"  Date overridden to {args.date}")

    # Append
    result = append_to_panel(df, prices_path, dry_run=args.dry_run)

    # Summary
    latest = result[result["ticker"].isin(SL20_TICKERS)]["date"].max()
    logger.info("\n" + "=" * 60)
    logger.info(f"  Panel now covers up to: {latest.date()}")
    if not args.dry_run:
        logger.info("  Next steps:")
        logger.info("    python build_alignment.py")
        logger.info("    python build_features.py")
        logger.info("    python predict.py")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
