"""
PriceService — reads the SL20 feature panel parquet once at startup.

Provides:
  - price history for chart rendering
  - 52-week high/low/avgVolume for stats sidebar
  - market movers (top 5 by absolute daily return)
  - SL20 index value for a given date (used by portfolio history)

Predicted P10/P50/P90 columns are placeholder (= close) until
Iteration 6 populates the predictions table.
"""

import logging
from pathlib import Path
from typing import Optional

import pandas as pd

from app.config import settings

logger = logging.getLogger(__name__)

# Module-level singleton — initialised once in lifespan via init_price_service()
_instance: Optional["PriceService"] = None


class PriceService:
    def __init__(self, ml_dir: Path) -> None:
        panel_path = ml_dir / "data" / "features" / "sl20_feature_panel.parquet"
        logger.info("PriceService: loading feature panel from %s …", panel_path)
        self._panel: pd.DataFrame = pd.read_parquet(panel_path)
        # date is already datetime64[ns] in this panel — no conversion needed
        logger.info(
            "PriceService: loaded %d rows, date range %s → %s",
            len(self._panel),
            self._panel["date"].min().date(),
            self._panel["date"].max().date(),
        )

    # ── Public helpers ────────────────────────────────────────────────────────

    def get_price_history(self, ticker: str, days: int = 90) -> list[dict]:
        """
        Return the last `days` rows for `ticker` as a list of PricePoint-compatible dicts.
        predictedP10/P50/P90 all default to close until the predictions table is
        backfilled in Iteration 6.
        """
        df = (
            self._panel[self._panel["ticker"] == ticker.upper()]
            .sort_values("date")
            .tail(days)
        )
        records = []
        for _, row in df.iterrows():
            close = float(row["close"])
            records.append(
                {
                    "date": row["date"].strftime("%Y-%m-%d"),
                    "close": close,
                    "predictedP10": close,
                    "predictedP50": close,
                    "predictedP90": close,
                }
            )
        return records

    def get_52w_stats(self, ticker: str) -> dict:
        """Return high52w, low52w, avgVolume for the 52-week window ending at the latest date."""
        latest = self._panel["date"].max()
        cutoff = latest - pd.Timedelta(days=365)
        df = self._panel[
            (self._panel["ticker"] == ticker.upper())
            & (self._panel["date"] >= cutoff)
        ]
        if df.empty:
            return {"high52w": 0.0, "low52w": 0.0, "avgVolume": 0.0}
        return {
            "high52w": float(df["close"].max()),
            "low52w": float(df["close"].min()),
            "avgVolume": float(df["volume"].mean()),
        }

    def get_latest_close(self, ticker: str) -> Optional[float]:
        """Return the most recent close price for a ticker."""
        df = self._panel[self._panel["ticker"] == ticker.upper()].sort_values("date")
        if df.empty:
            return None
        return float(df.iloc[-1]["close"])

    def get_market_movers(self, top_n: int = 5) -> list[dict]:
        """
        Return top_n tickers by absolute daily_return on the latest trading date
        present in the panel.
        """
        latest_date = self._panel["date"].max()
        latest = self._panel[self._panel["date"] == latest_date].copy()
        latest["abs_change"] = latest["daily_return"].abs()
        top = latest.nlargest(top_n, "abs_change")

        from app.services.stock_info_service import STOCK_INFO  # avoid circular at module level

        movers = []
        for _, row in top.iterrows():
            ticker = str(row["ticker"])
            info = STOCK_INFO.get(ticker)
            movers.append(
                {
                    "ticker": ticker,
                    "name": info.name if info else ticker,
                    "price": float(row["close"]),
                    "changePercent": float(row["daily_return"]) * 100,
                }
            )
        return movers

    def get_sl20_index(self, date_str: str) -> Optional[float]:
        """Return the SL20 index value for a given YYYY-MM-DD date string."""
        row = self._panel[
            self._panel["date"] == pd.Timestamp(date_str)
        ].head(1)
        if row.empty:
            return None
        return float(row.iloc[0]["sl20_index"])

    def get_sl20_index_series(self, dates: list[str]) -> dict[str, float]:
        """Bulk lookup of SL20 index values for a list of date strings."""
        ts_dates = pd.to_datetime(dates)
        subset = self._panel[self._panel["date"].isin(ts_dates)][["date", "sl20_index"]]
        subset = subset.drop_duplicates("date")
        return {
            row["date"].strftime("%Y-%m-%d"): float(row["sl20_index"])
            for _, row in subset.iterrows()
        }


# ── Singleton lifecycle ───────────────────────────────────────────────────────

def init_price_service() -> None:
    """Called once from main.py lifespan to load the parquet into memory."""
    global _instance
    ml_dir = Path(settings.ml_dir).resolve()
    _instance = PriceService(ml_dir)


def get_price_service() -> PriceService:
    """FastAPI dependency — returns the singleton (raises if not initialised)."""
    if _instance is None:
        raise RuntimeError("PriceService not initialised — call init_price_service() in lifespan")
    return _instance
