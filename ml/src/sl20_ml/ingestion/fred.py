"""
fred.py — Fetch global macro data from FRED or yfinance.

Series fetched (configured in pipeline.yaml under `fred_series`):

  oil_wti       : WTI crude oil spot price (USD/barrel)    FRED: DCOILWTICO  / yf: CL=F
  sp500         : S&P 500 index level                      FRED: SP500        / yf: ^GSPC
  vix           : CBOE VIX volatility index                FRED: VIXCLS       / yf: ^VIX
  us_10y_yield  : US 10-year treasury yield (%)            FRED: DGS10        / yf: ^TNX
  dxy           : USD index (broad, goods & services)      FRED: DTWEXBGS     / yf: DX-Y.NYB
  gold          : Gold price, London AM fix (USD/troy oz)  FRED: GOLDAMGBD228NLBM / yf: GC=F

Strategy
--------
1. If a cached CSV exists in data/raw/fred/<name>.csv, load that.
2. Otherwise try FRED API (requires FRED_API_KEY in environment / .env).
3. If no API key, fall back to yfinance for series that have a yf ticker.
4. Save fetched data to the raw cache CSV for reproducibility.

The raw CSVs are git-ignored (large data files); add them to DVC after build.
"""

import logging
import os
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

_DATE_FMT = "%Y-%m-%d"


# ── Public API ─────────────────────────────────────────────────────────────────

def load_all_fred(
    fred_dir: Path,
    series_cfg: dict[str, list],
    start: str,
    end: str,
) -> pd.DataFrame:
    """
    Load (or fetch and cache) all configured FRED series.

    Parameters
    ----------
    fred_dir : Path
        Directory for raw cache CSVs (data/raw/fred/).
    series_cfg : dict[str, list]
        From pipeline.yaml `fred_series`. Key = column name,
        value = [fred_id, yf_ticker].  yf_ticker may be null/None.
    start : str  — e.g. "2010-01-01"  (fetch a year before ML start for coverage)
    end   : str  — e.g. "2025-12-31"

    Returns
    -------
    pd.DataFrame with columns: date + one column per series.
    Index is a continuous calendar range; missing dates have NaN.
    """
    fred_dir.mkdir(parents=True, exist_ok=True)
    api_key = _get_api_key()

    series_frames = []
    for col_name, (fred_id, yf_ticker) in series_cfg.items():
        s = _load_one_series(
            name=col_name,
            fred_id=fred_id,
            yf_ticker=yf_ticker if yf_ticker else None,
            start=start,
            end=end,
            api_key=api_key,
            cache_dir=fred_dir,
        )
        series_frames.append(s)

    if not series_frames:
        raise RuntimeError("No FRED series were loaded — check fred_series config.")

    df = pd.concat(series_frames, axis=1)
    df.index.name = "date"
    df = df.reset_index()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    logger.info(
        f"FRED data loaded: {len(df):,} rows | "
        f"{df['date'].min().date()} to {df['date'].max().date()} | "
        f"columns: {list(df.columns[1:])}"
    )
    return df


# ── Internal helpers ───────────────────────────────────────────────────────────

def _get_api_key() -> str | None:
    """Load FRED_API_KEY from environment, trying .env file first."""
    key = os.environ.get("FRED_API_KEY")
    if key:
        return key
    # Try loading from .env file if python-dotenv is available
    try:
        from dotenv import load_dotenv
        env_path = Path(__file__).parent.parent.parent.parent / ".env"
        if env_path.exists():
            load_dotenv(env_path)
            key = os.environ.get("FRED_API_KEY")
    except ImportError:
        pass
    if key:
        logger.info("FRED_API_KEY loaded from .env file.")
    else:
        logger.warning(
            "FRED_API_KEY not set — will use yfinance fallback where available. "
            "Add FRED_API_KEY to your .env file for full FRED access."
        )
    return key


def _load_one_series(
    name: str,
    fred_id: str,
    yf_ticker: str | None,
    start: str,
    end: str,
    api_key: str | None,
    cache_dir: Path,
) -> pd.Series:
    """Load a single series, using cache → FRED → yfinance in that order."""
    cache_file = cache_dir / f"{name}.csv"

    # ── 1. Try cache ──────────────────────────────────────────────────────────
    if cache_file.exists():
        logger.info(f"  {name:<16s}: loading from cache ({cache_file.name})")
        df = pd.read_csv(cache_file, index_col=0, parse_dates=True)
        s = df.iloc[:, 0].rename(name)
        # Extend cache if end date is beyond last cached date
        last_cached = s.dropna().index.max()
        if last_cached < pd.Timestamp(end) - pd.Timedelta(days=30):
            logger.info(f"  {name:<16s}: cache is stale (last: {last_cached.date()}), refreshing ...")
            s = _fetch_and_cache(name, fred_id, yf_ticker, start, end, api_key, cache_file)
        return s

    # ── 2. Fetch fresh ────────────────────────────────────────────────────────
    return _fetch_and_cache(name, fred_id, yf_ticker, start, end, api_key, cache_file)


def _fetch_and_cache(
    name: str,
    fred_id: str,
    yf_ticker: str | None,
    start: str,
    end: str,
    api_key: str | None,
    cache_file: Path,
) -> pd.Series:
    """Fetch from FRED or yfinance, save to cache CSV, return as Series."""

    # ── Try FRED API ──────────────────────────────────────────────────────────
    if api_key:
        try:
            from fredapi import Fred
            fred = Fred(api_key=api_key)
            s = fred.get_series(fred_id, observation_start=start, observation_end=end)
            s = s.rename(name)
            s = s[~s.index.duplicated(keep="last")]
            _save_to_cache(s, cache_file)
            logger.info(
                f"  {name:<16s}: fetched from FRED ({fred_id}) "
                f"| {s.notna().sum():,} observations"
            )
            return s
        except Exception as exc:
            logger.warning(f"  {name:<16s}: FRED fetch failed ({exc}), trying yfinance ...")

    # ── Fall back to yfinance ──────────────────────────────────────────────────
    if yf_ticker:
        try:
            import yfinance as yf
            raw = yf.download(
                yf_ticker,
                start=start,
                end=end,
                progress=False,
                auto_adjust=True,
                multi_level_index=False,
            )
            if raw.empty:
                raise ValueError(f"yfinance returned empty DataFrame for {yf_ticker}")
            s = raw["Close"].rename(name)
            s.index = pd.to_datetime(s.index)
            s = s[~s.index.duplicated(keep="last")]
            _save_to_cache(s, cache_file)
            logger.info(
                f"  {name:<16s}: fetched from yfinance ({yf_ticker}) "
                f"| {s.notna().sum():,} observations"
            )
            return s
        except Exception as exc:
            logger.error(f"  {name:<16s}: yfinance also failed ({exc}). Returning NaN series.")

    # ── No data available ─────────────────────────────────────────────────────
    idx = pd.date_range(start=start, end=end, freq="D")
    return pd.Series(data=float("nan"), index=idx, name=name)


def _save_to_cache(s: pd.Series, cache_file: Path) -> None:
    """Save a Series to CSV cache."""
    df = s.to_frame()
    df.index.name = "date"
    df.to_csv(cache_file)
