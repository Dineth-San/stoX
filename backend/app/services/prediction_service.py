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
    h = int(hashlib.md5(ticker.upper().encode()).hexdigest(), 16)
    return ((h % 301) - 150) / 100


def _mock_predictions(ticker: str, last_close: float) -> dict:
    p50_chg = _mock_p50_change_pct(ticker)
    p50 = round(last_close * (1 + p50_chg / 100), 4)
    p10 = round(last_close * (1 - 0.015), 4)
    p90 = round(last_close * (1 + 0.015), 4)
    change_pct = (p50 - last_close) / last_close * 100
    return {
        "p10": p10, "p50": p50, "p90": p90,
        "last_close": last_close,
        "signal": derive_signal(change_pct),
    }


# ── Service class ─────────────────────────────────────────────────────────────

class PredictionService:
    def __init__(self, ml_dir: Path, use_mock: bool) -> None:
        self.ml_dir = ml_dir
        self.use_mock = use_mock
        self.directional_accuracy, self.mean_error = self._load_model_metrics()
        self._run_inference = None   # lazy-loaded on first real call

    def _load_model_metrics(self) -> tuple[float, float]:
        cfg_path = self.ml_dir / "models" / "tft_v1" / "model_config.json"
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            metrics = cfg.get("test_metrics", {})
            da  = float(metrics.get("directional_accuracy", _FALLBACK_DIRECTIONAL_ACCURACY))
            mae = float(metrics.get("mae", _FALLBACK_MEAN_ERROR))
            logger.info(
                "PredictionService: metrics — directionalAccuracy=%.4f, mae=%.4f", da, mae
            )
            return da, mae
        except Exception as exc:
            logger.warning("PredictionService: model_config.json unreadable (%s), using fallbacks", exc)
            return _FALLBACK_DIRECTIONAL_ACCURACY, _FALLBACK_MEAN_ERROR

    def _load_run_inference(self):
        """Lazy-import run_inference from ml/predict.py (adds sys.path shim)."""
        if self._run_inference is not None:
            return self._run_inference
        import sys
        sys.path.insert(0, str(self.ml_dir / "src"))
        sys.path.insert(0, str(self.ml_dir))
        import importlib.util
        spec = importlib.util.spec_from_file_location("predict", self.ml_dir / "predict.py")
        mod  = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self._run_inference = mod.run_inference
        logger.info("PredictionService: run_inference loaded from %s", self.ml_dir / "predict.py")
        return self._run_inference

    # ── DB helpers ────────────────────────────────────────────────────────────

    async def _get_cached(self, db: aiosqlite.Connection, ticker: str, as_of: str) -> Optional[dict]:
        cur = await db.execute(
            "SELECT p10, p50, p90, signal FROM predictions WHERE date=? AND ticker=?",
            (as_of, ticker.upper()),
        )
        row = await cur.fetchone()
        return {"p10": row[0], "p50": row[1], "p90": row[2], "signal": row[3]} if row else None

    async def _insert_cached(
        self, db: aiosqlite.Connection, ticker: str, as_of: str, preds: dict
    ) -> None:
        await db.execute(
            """INSERT OR IGNORE INTO predictions (date, ticker, p10, p50, p90, signal, model_ver)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (as_of, ticker.upper(), preds["p10"], preds["p50"], preds["p90"],
             preds["signal"], MODEL_VERSION),
        )
        await db.commit()

    # ── Core prediction entry point ───────────────────────────────────────────

    async def get_prediction(self, ticker: str, as_of: Optional[str] = None) -> dict:
        if as_of is None:
            as_of = date.today().isoformat()
        ticker = ticker.upper()
        async with aiosqlite.connect(_db_path()) as db:
            cached = await self._get_cached(db, ticker, as_of)
            if cached:
                last_close = self._get_last_close(ticker)
                return {**cached, "last_close": last_close}
            preds = await self._compute(ticker, as_of)
            await self._insert_cached(db, ticker, as_of, preds)
            return preds

    async def get_all_predictions(self, as_of: Optional[str] = None) -> list[dict]:
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

    # ── Prefill helpers (called from seed.py) ────────────────────────────────

    async def prefill_today(self) -> int:
        """
        Run real inference for today (latest panel date) and bulk-insert all 20 tickers.
        Returns number of rows inserted.
        Falls back to mock if inference fails.
        """
        try:
            run_inference = self._load_run_inference()
            logger.info("PredictionService: running real inference for all tickers …")
            raw = run_inference()           # list of 20 dicts
            inserted = 0
            async with aiosqlite.connect(_db_path()) as db:
                for r in raw:
                    ticker    = str(r["ticker"]).upper()
                    as_of     = str(r["as_of_date"])
                    last_close = float(r["last_close"])
                    p10, p50, p90 = float(r["p10"]), float(r["p50"]), float(r["p90"])
                    change_pct = (p50 - last_close) / last_close * 100 if last_close else 0.0
                    signal     = derive_signal(change_pct)
                    preds      = {"p10": p10, "p50": p50, "p90": p90, "signal": signal}
                    cur = await db.execute(
                        "SELECT 1 FROM predictions WHERE date=? AND ticker=?", (as_of, ticker)
                    )
                    if await cur.fetchone() is None:
                        await self._insert_cached(db, ticker, as_of, preds)
                        inserted += 1
            logger.info("PredictionService: prefilled %d real predictions (as_of=%s)", inserted, as_of)
            return inserted
        except Exception as exc:
            logger.warning(
                "PredictionService: real inference failed (%s) — falling back to mock prefill", exc
            )
            return await self.prefill_mock_for_date(date.today().isoformat())

    async def prefill_mock_for_date(self, as_of: str) -> int:
        """Insert mock predictions for a given date using closes from PriceService."""
        inserted = 0
        async with aiosqlite.connect(_db_path()) as db:
            for ticker in SL20_TICKERS:
                cur = await db.execute(
                    "SELECT 1 FROM predictions WHERE date=? AND ticker=?", (as_of, ticker)
                )
                if await cur.fetchone() is not None:
                    continue
                last_close = self._get_last_close(ticker)
                preds = _mock_predictions(ticker, last_close)
                await self._insert_cached(db, ticker, as_of, preds)
                inserted += 1
        return inserted

    async def backfill_historical(self, dates: list[str]) -> int:
        """
        Bulk-insert mock predictions for historical dates that are missing from the DB.
        Uses actual closes from the feature panel so the chart shows realistic spreads.
        """
        from app.services.price_service import get_price_service
        price_svc = get_price_service()

        rows_to_insert: list[tuple] = []
        async with aiosqlite.connect(_db_path()) as db:
            for date_str in dates:
                for ticker in SL20_TICKERS:
                    cur = await db.execute(
                        "SELECT 1 FROM predictions WHERE date=? AND ticker=?",
                        (date_str, ticker),
                    )
                    if await cur.fetchone() is not None:
                        continue
                    close = price_svc.get_close_on_date(ticker, date_str)
                    if close is None:
                        continue
                    preds = _mock_predictions(ticker, close)
                    rows_to_insert.append(
                        (date_str, ticker, preds["p10"], preds["p50"],
                         preds["p90"], preds["signal"], MODEL_VERSION)
                    )

            if rows_to_insert:
                await db.executemany(
                    """INSERT OR IGNORE INTO predictions
                       (date, ticker, p10, p50, p90, signal, model_ver)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    rows_to_insert,
                )
                await db.commit()

        logger.info("PredictionService: historical backfill inserted %d rows", len(rows_to_insert))
        return len(rows_to_insert)

    # ── Compute path ──────────────────────────────────────────────────────────

    async def _compute(self, ticker: str, as_of: str) -> dict:
        if self.use_mock:
            return self._compute_mock(ticker)
        return await self._compute_real(ticker, as_of)

    def _compute_mock(self, ticker: str) -> dict:
        last_close = self._get_last_close(ticker)
        return _mock_predictions(ticker, last_close)

    async def _compute_real(self, ticker: str, as_of: str) -> dict:
        """Call ml/predict.py run_inference for a single ticker."""
        try:
            run_inference = self._load_run_inference()
            raw = run_inference(ticker=ticker, date=as_of)
            if not raw:
                raise ValueError(f"Empty result for {ticker} on {as_of}")
            r = raw[0]
            last_close = float(r["last_close"])
            p10, p50, p90 = float(r["p10"]), float(r["p50"]), float(r["p90"])
            change_pct = (p50 - last_close) / last_close * 100 if last_close else 0.0
            return {
                "p10": p10, "p50": p50, "p90": p90,
                "last_close": last_close,
                "signal": derive_signal(change_pct),
            }
        except Exception as exc:
            logger.warning(
                "PredictionService: real inference failed for %s (%s), using mock", ticker, exc
            )
            return self._compute_mock(ticker)

    def _get_last_close(self, ticker: str) -> float:
        from app.services.price_service import get_price_service
        return get_price_service().get_latest_close(ticker) or 0.0


# ── Singleton lifecycle ───────────────────────────────────────────────────────

_instance: Optional[PredictionService] = None


def init_prediction_service() -> None:
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
    if _instance is None:
        raise RuntimeError("PredictionService not initialised")
    return _instance
