from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class PricePoint(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    date: str
    close: float
    predicted_p10: float = Field(alias="predictedP10")
    predicted_p50: float = Field(alias="predictedP50")
    predicted_p90: float = Field(alias="predictedP90")


class StockPrediction(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    ticker: str
    name: str
    sector: str
    last_close: float = Field(alias="lastClose")
    predicted_p10: float = Field(alias="predictedP10")
    predicted_p50: float = Field(alias="predictedP50")
    predicted_p90: float = Field(alias="predictedP90")
    predicted_change_percent: float = Field(alias="predictedChangePercent")
    signal: str  # 'BUY' | 'HOLD' | 'SELL'
    sparkline: list[PricePoint]  # last 30 days of price history
    directional_accuracy: float = Field(alias="directionalAccuracy")
    mean_error: float = Field(alias="meanError")


class StockInfo(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    ticker: str
    name: str
    sector: str
    blurb: str


class StockKeyStats(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    high_52w: float = Field(alias="high52w")
    low_52w: float = Field(alias="low52w")
    avg_volume: float = Field(alias="avgVolume")
    market_cap: float = Field(alias="marketCap")
    pe_ratio: Optional[float] = Field(alias="peRatio", default=None)
