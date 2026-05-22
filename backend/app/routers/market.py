from fastapi import APIRouter, Depends

from app.models.news import MarketMover
from app.services.price_service import PriceService, get_price_service

router = APIRouter()


@router.get("/movers", response_model=list[MarketMover], response_model_by_alias=True)
async def get_market_movers(
    price_svc: PriceService = Depends(get_price_service),
) -> list[MarketMover]:
    """Return the top 5 biggest movers on the latest trading date in the feature panel."""
    movers = price_svc.get_market_movers(top_n=5)
    return [MarketMover(**m) for m in movers]
