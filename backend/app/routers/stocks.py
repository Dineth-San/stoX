import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Query

from app.db.database import get_db
from app.models.stocks import PricePoint, StockInfo, StockKeyStats, StockPrediction
from app.services.prediction_service import (
    PredictionService,
    SL20_TICKERS,
    derive_signal,
    get_prediction_service,
)
from app.services.price_service import PriceService, get_price_service
from app.services.stock_info_service import (
    get_static_key_stats,
    get_stock_info,
)

router = APIRouter()

_SPARKLINE_DAYS = 30


def _build_stock_prediction(
    ticker: str,
    pred: dict,
    price_svc: PriceService,
    pred_svc: PredictionService,
) -> StockPrediction:
    """Assemble a StockPrediction from raw prediction dict + services."""
    info = get_stock_info(ticker)
    last_close = pred["last_close"]
    p10, p50, p90 = pred["p10"], pred["p50"], pred["p90"]
    change_pct = (p50 - last_close) / last_close * 100 if last_close else 0.0

    # Sparkline: last 30 days of price history
    raw_sparkline = price_svc.get_price_history(ticker, days=_SPARKLINE_DAYS)
    sparkline = [PricePoint(**pt) for pt in raw_sparkline]

    return StockPrediction(
        **{
            "ticker": ticker,
            "name": info.name if info else ticker,
            "sector": info.sector if info else "Unknown",
            "lastClose": last_close,
            "predictedP10": p10,
            "predictedP50": p50,
            "predictedP90": p90,
            "predictedChangePercent": round(change_pct, 4),
            "signal": derive_signal(change_pct),
            "sparkline": sparkline,
            "directionalAccuracy": round(pred_svc.directional_accuracy, 4),
            "meanError": round(pred_svc.mean_error, 6),
        }
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=list[StockPrediction], response_model_by_alias=True)
async def get_all_stocks(
    pred_svc: PredictionService = Depends(get_prediction_service),
    price_svc: PriceService = Depends(get_price_service),
) -> list[StockPrediction]:
    """Return predictions for all 20 SL20 tickers, sorted alphabetically."""
    all_preds = await pred_svc.get_all_predictions()
    # all_preds already comes back in SL20_TICKERS order (alphabetical)
    results = []
    for pred in all_preds:
        ticker = pred["ticker"]
        results.append(_build_stock_prediction(ticker, pred, price_svc, pred_svc))
    return results


@router.get(
    "/{ticker}/prediction",
    response_model=StockPrediction,
    response_model_by_alias=True,
)
async def get_stock_prediction(
    ticker: str,
    pred_svc: PredictionService = Depends(get_prediction_service),
    price_svc: PriceService = Depends(get_price_service),
) -> StockPrediction:
    """Return prediction for a single SL20 ticker."""
    if ticker.upper() not in SL20_TICKERS:
        raise HTTPException(status_code=404, detail=f"Ticker '{ticker.upper()}' not found in SL20")
    pred = await pred_svc.get_prediction(ticker)
    return _build_stock_prediction(ticker.upper(), pred, price_svc, pred_svc)


@router.get("/{ticker}/info", response_model=StockInfo, response_model_by_alias=True)
async def get_stock_info_endpoint(ticker: str) -> StockInfo:
    """Return static company info for one SL20 ticker."""
    info = get_stock_info(ticker)
    if info is None:
        raise HTTPException(status_code=404, detail=f"Ticker '{ticker.upper()}' not found in SL20")
    return info


@router.get(
    "/{ticker}/history",
    response_model=list[PricePoint],
    response_model_by_alias=True,
)
async def get_stock_history(
    ticker: str,
    days: int = Query(default=90, ge=1, le=3650),
    price_svc: PriceService = Depends(get_price_service),
    db: aiosqlite.Connection = Depends(get_db),
) -> list[PricePoint]:
    """
    Return the last `days` closing prices for a ticker.
    predictedP10/P50/P90 are read from the predictions DB table where available;
    fall back to close for dates with no stored prediction.
    """
    if ticker.upper() not in SL20_TICKERS:
        raise HTTPException(status_code=404, detail=f"Ticker '{ticker.upper()}' not found in SL20")

    records = price_svc.get_price_history(ticker, days)
    if not records:
        return []

    # Batch-fetch predictions for all dates in this history window
    dates = [r["date"] for r in records]
    placeholders = ",".join("?" * len(dates))
    cur = await db.execute(
        f"SELECT date, p10, p50, p90 FROM predictions "
        f"WHERE ticker=? AND date IN ({placeholders})",
        [ticker.upper()] + dates,
    )
    rows = await cur.fetchall()
    pred_map: dict[str, dict] = {
        row[0]: {"p10": row[1], "p50": row[2], "p90": row[3]} for row in rows
    }

    result = []
    for r in records:
        pred = pred_map.get(r["date"])
        result.append(
            PricePoint(
                date=r["date"],
                close=r["close"],
                **{
                    "predictedP10": pred["p10"] if pred else r["close"],
                    "predictedP50": pred["p50"] if pred else r["close"],
                    "predictedP90": pred["p90"] if pred else r["close"],
                },
            )
        )
    return result


@router.get(
    "/{ticker}/stats",
    response_model=StockKeyStats,
    response_model_by_alias=True,
)
async def get_stock_stats(
    ticker: str,
    price_svc: PriceService = Depends(get_price_service),
) -> StockKeyStats:
    """Return 52w stats (dynamic) merged with static marketCap/peRatio."""
    if ticker.upper() not in SL20_TICKERS:
        raise HTTPException(status_code=404, detail=f"Ticker '{ticker.upper()}' not found in SL20")
    dynamic = price_svc.get_52w_stats(ticker)
    static = get_static_key_stats(ticker)
    return StockKeyStats(
        **{
            "high52w": dynamic["high52w"],
            "low52w": dynamic["low52w"],
            "avgVolume": dynamic["avgVolume"],
            "marketCap": static["marketCap"] if static else 0.0,
            "peRatio": static["peRatio"] if static else None,
        }
    )
