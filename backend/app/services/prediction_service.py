"""
PredictionService — delivers P10/P50/P90 predictions with SQLite caching.

Two code paths, gated on settings.use_mock_predictions:
  Mock  → deterministic synthetic predictions (no model load, instant)
  Real  → calls ml/predict.py run_inference() (wired in Iteration 6)

Cache strategy (Section 8 of SPEC):
  - On first request for (date, ticker), compute and INSERT OR IGNORE into DB
  - Subsequent requests read from the DB — warm path is a single SELECT
"""

import hashlib
import json
import logging
from datetime import date
from pathlib import Path
from typing import Optional

import aiosqlite

from app.config import settings
from app.db.database import _db_path

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

SL20_TICKERS: list[str] = [
    "AEL", "BUKI", "CARG", "CCS", "COMB",
    "CTC", "DFCC", "DIAL", "HAYL", "HHL",
    "HNB", "JKH", "LIOC", "LION", "MELS",
    "NTB", "SAMP", "SPEN", "TKYO", "VONE",
]

MODEL_VERSION = "tft_v1"

# Fallback accuracy metrics used when model_config.json is absent
_FALLBACK_DIRECTIONAL_ACCURACY = 0.55
_FALLBACK_MEAN_ERROR = 0.018


def derive_signal(predicted_change_percent: float) -> str:
    """Convert a predicted % change into a BUY / HOLD / SELL signal."""
    if predicted_change_percent > 0.5:
        return "BUY"
    elif predicted_change_percent < -0.5:
        return "SELL"
    return "HOLD"


# ── Mock helpers ──────────────────────────────────────────────────────────────

def _mock_p50_change_pct(ticker: str) -> float:
    """
    Deterministic P50 % change in [-1.5, +1.5] derived from ticker hash.
    Gives a realistic spread of BUY / HOLD / SELL across the 20 tickers.
    """
    h = int(hashlib.md5(ticker.upper().encode()).hexdigest(), 16)
    return ((h % 301) - 150) / 100  # –1.50 … +1.50


def _mock_predictions(ticker: str, last_close: float) -> dict:
    """Return synthetic P10/P50/P90 dicts based on last close."""
    p50_chg = _mock_p50_change_pct(ticker)
    p50 = round(last_close * (1 + p50_chg / 100), 4)
    p10 = round(last_close * (1 - 0.015), 4)   # –1.5 % floor
    p90 = round(last_close * (1 + 0.015), 4)   # +1.5 % ceiling
    return {"p10": p10, "p50": p50, "p90": p90, "last_close": last_close}


# ── Service class ─────────────────────────────────────────────────────────────

class PredictionService:
    def __init__(self, ml_dir: Path, use_mock: bool) -> None:
        self.ml_dir = ml_dir
        self.use_mock = use_mock
        self.directional_accuracy, self.mean_error = self._load_model_metrics()

    def _load_model_metrics(self) -> tuple[float, float]:
        cfg_path = self.ml_dir / "models" / "tft_v1" / "model_config.json"
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            metrics = cfg.get("test_metrics", {})
            da = float(metrics.get("directional_accuracy", _FALLBACK_DIRECTIONAL_ACCURACY))
            mae = float(metrics.get("mae", _FALLBACK_MEAN_ERROR))
            logger.info(
                "PredictionService: loaded model metrics — directionalAccuracy=%.4f, mae=%.4f",
                da, mae,
            )
            return da, mae
        except Exception as exc:
            logger.warning("PredictionService: could not load model_config.json (%s), using fallback", exc)
            return _FALLBACK_DIRECTIONAL_ACCURACY, _FALLBACK_MEAN_ERROR

    # ── DB helpers ────────────────────────────────────────────────────────────

    async def _get_cached(self, db: aiosqlite.Connection, ticker: str, as_of: str) -> Optional[dict]:
        cur = await db.execute(
            "SELECT p10, p50, p90, signal FROM predictions WHERE date=? AND ticker=?",
            (as_of, ticker.upper()),
        )
        row = await cur.fetchone()
        if row is None:
            return None
        return {"p10": row[0], "p50": row[1], "p90": row[2], "signal": row[3]}

    async def _insert_cached(
        self, db: aiosqlite.Connection, ticker: str, as_of: str, preds: dict
    ) -> None:
        await db.execute(
            """INSERT OR IGNORE INTO predictions (date, ticker, p10, p50, p90, signal, model_ver)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                as_of,
                ticker.upper(),
                preds["p10"],
                preds["p50"],
                preds["p90"],
                preds["signal"],
                MODEL_VERSION,
            ),
        )
        await db.commit()

    # ── Core prediction entry point ───────────────────────────────────────────

    async def get_prediction(self, ticker: str, as_of: Optional[str] = None) -> dict:
        """
        Return {p10, p50, p90, signal, last_close} for one ticker.

        Checks the DB cache first. On a miss, computes (mock or real) and stores.
        """
        if as_of is None:
            as_of = date.today().isoformat()

        ticker = ticker.upper()

        async with aiosqlite.connect(_db_path()) as db:
            cached = await self._get_cached(db, ticker, as_of)
            if cached:
                # Return from cache — we need last_close from price service
                last_close = self._get_last_close(ticker)
                return {**cached, "last_close": last_close}

            # Cache miss — compute
            preds = await self._compute(ticker, as_of)
            await self._insert_cached(db, ticker, as_of, preds)
            return preds

    async def get_all_predictions(self, as_of: Optional[str] = None) -> list[dict]:
        """
        Return predictions for all 20 SL20 tickers, checking cache in bulk.
        """
        if as_of is None:
            as_of = date.today().isoformat()

        results = []
        async with aiosqlite.connect(_db_path()) as db:
            for ticker in SL20_TICKERS:
                cached = await self._get_cached(db, ticker, as_of)
                if cached:
                    last_close = self._get_last_close(ticker)
                    results.append({**cached, "last_close": last_close, "ticker": ticker})
                else:
                    preds = await self._compute(ticker, as_of)
                    await self._insert_cached(db, ticker, as_of, preds)
                    results.append({**preds, "ticker": ticker})

        return results

    # ── Compute path ──────────────────────────────────────────────────────────

    async def _compute(self, ticker: str, as_of: str) -> dict:
        if self.use_mock:
            return self._compute_mock(ticker)
        return await self._compute_real(ticker, as_of)

    def _compute_mock(self, ticker: str) -> dict:
        last_close = self._get_last_close(ticker)
        preds = _mock_predictions(ticker, last_close)
        change_pct = (preds["p50"] - last_close) / last_close * 100
        preds["signal"] = derive_signal(change_pct)
        return preds

    async def _compute_real(self, ticker: str, as_of: str) -> dict:
        # Filled in Iteration 6
        raise NotImplementedError(
            "Real model inference not yet wired. Set USE_MOCK_PREDICTIONS=true "
            "or wait for Iteration 6."
        )

    def _get_last_close(self, ticker: str) -> float:
        """Pull last close from the PriceService singleton."""
        from app.services.price_service import get_price_service
        return get_price_service().get_latest_close(ticker) or 0.0


# ── Singleton lifecycle ───────────────────────────────────────────────────────

_instance: Optional[PredictionService] = None


def init_prediction_service() -> None:
    """Called once from main.py lifespan."""
    global _instance
    ml_dir = Path(settings.ml_dir).resolve()
    _instance = PredictionService(ml_dir=ml_dir, use_mock=settings.use_mock_predictions)
    logger.info(
        "PredictionService: ready (mock=%s, directionalAccuracy=%.4f, mae=%.4f)",
        settings.use_mock_predictions,
        _instance.directional_accuracy,
        _instance.mean_error,
    )


def get_prediction_service() -> PredictionService:
    """FastAPI dependency."""
    if _instance is None:
        raise RuntimeError("PredictionService not initialised — call init_prediction_service() in lifespan")
    return _instance
