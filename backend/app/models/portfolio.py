from pydantic import BaseModel, ConfigDict, Field


class Position(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    ticker: str
    name: str
    shares: float
    avg_buy_price: float = Field(alias="avgBuyPrice")
    current_price: float = Field(alias="currentPrice")
    unrealized_pnl: float = Field(alias="unrealizedPnL")
    unrealized_pnl_percent: float = Field(alias="unrealizedPnLPercent")
    position_weight: float = Field(alias="positionWeight")


class Trade(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    date: str
    ticker: str
    action: str  # 'BUY' | 'SELL'
    quantity: float
    price: float
    reason: str


class PortfolioSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    total_value: float = Field(alias="totalValue")
    daily_pnl: float = Field(alias="dailyPnL")
    daily_pnl_percent: float = Field(alias="dailyPnLPercent")
    today_trades_count: int = Field(alias="todayTradesCount")
    active_positions_count: int = Field(alias="activePositionsCount")


class PortfolioHistoryPoint(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    date: str
    value: float
    sl20_index: float = Field(alias="sl20Index")


class PerformanceMetrics(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    sharpe_ratio: float = Field(alias="sharpeRatio")
    max_drawdown: float = Field(alias="maxDrawdown")
    total_return: float = Field(alias="totalReturn")
    win_rate: float = Field(alias="winRate")
