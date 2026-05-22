from fastapi import APIRouter, Depends, HTTPException, Query

from app.models.stocks import PricePoint, StockInfo, StockKeyStats
from app.services.price_service import PriceService, get_price_service
from app.services.stock_info_service import SL20_TICKERS, get_static_key_stats, get_stock_info

router = APIRouter()


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
) -> list[PricePoint]:
    """
    Return the last `days` closing prices for a ticker.
    predictedP10/P50/P90 mirror the close until the predictions table is
    backfilled in Iteration 6.
    """
    if ticker.upper() not in SL20_TICKERS:
        raise HTTPException(status_code=404, detail=f"Ticker '{ticker.upper()}' not found in SL20")
    records = price_svc.get_price_history(ticker, days)
    return [PricePoint(**r) for r in records]


@router.get(
    "/{ticker}/stats",
    response_model=StockKeyStats,
    response_model_by_alias=True,
)
async def get_stock_stats(
    ticker: str,
    price_svc: PriceService = Depends(get_price_service),
) -> StockKeyStats:
    """
    Return key stats: dynamic 52w high/low/avgVolume from the feature panel,
    plus hardcoded marketCap and peRatio estimates.
    """
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
