from fastapi import APIRouter, HTTPException

from app.models.stocks import StockInfo
from app.services.stock_info_service import SL20_TICKERS, get_stock_info

router = APIRouter()


@router.get("/{ticker}/info", response_model=StockInfo, response_model_by_alias=True)
async def get_stock_info_endpoint(ticker: str) -> StockInfo:
    """Return static company info for one SL20 ticker."""
    info = get_stock_info(ticker)
    if info is None:
        raise HTTPException(status_code=404, detail=f"Ticker '{ticker.upper()}' not found in SL20")
    return info
