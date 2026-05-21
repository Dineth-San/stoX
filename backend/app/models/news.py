from pydantic import BaseModel, ConfigDict, Field


class NewsItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    source: str
    is_local: bool = Field(alias="isLocal")
    headline: str
    url: str
    sentiment: str  # 'Positive' | 'Neutral' | 'Negative'
    time_ago: str = Field(alias="timeAgo")


class MarketMover(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    ticker: str
    name: str
    price: float
    change_percent: float = Field(alias="changePercent")
