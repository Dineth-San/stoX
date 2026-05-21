from fastapi import APIRouter

from app.models.news import NewsItem
from app.services.news_service import get_news

router = APIRouter()


@router.get("", response_model=list[NewsItem], response_model_by_alias=True)
async def get_news_feed() -> list[NewsItem]:
    """Return the static news feed (20 items). Sentiment model is deferred."""
    return get_news()
