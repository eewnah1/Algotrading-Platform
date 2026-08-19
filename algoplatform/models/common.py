from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field

__all__ = [
    "Side",
    "OrderStatus",
    "OrderType",
    "Quote",
    "Position",
    "Order",
    "Portfolio",
    "PerformanceMetrics",
    "EquityPoint",
    "BacktestResult",
    "Strategy",
    "Experiment",
    "DataSourceHealth",
    "Job",
]


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    FILLED = "FILLED"
    PARTIAL = "PARTIAL"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class Quote(BaseModel):
    symbol: str
    timestamp: datetime
    bid: float
    ask: float
    last: float
    volume: int
    source: str = "yfinance"


class Position(BaseModel):
    symbol: str
    qty: int = 0
    avg_cost: float = 0.0
    market_price: float = 0.0
    market_value: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    weight: float = 0.0
    sector: str = ""


class Order(BaseModel):
    id: str
    timestamp: datetime
    symbol: str
    side: Side
    qty: int
    order_type: OrderType = OrderType.MARKET
    limit_price: float | None = None
    avg_price: float = 0.0
    status: OrderStatus = OrderStatus.PENDING
    broker: str = "paper"
    algo: str = "default"
    commission: float = 0.0
    slippage: float = 0.0


class Portfolio(BaseModel):
    cash: float
    equity: float
    long_value: float
    short_value: float
    gross_exposure: float
    net_exposure: float
    margin_used: float
    day_pnl: float
    total_pnl: float
    total_pnl_pct: float
    positions: list[Position]


class PerformanceMetrics(BaseModel):
    total_return: float
    cagr: float
    volatility: float
    sharpe: float
    sortino: float
    max_drawdown: float
    calmar: float
    win_rate: float
    profit_factor: float
    avg_trade: float
    trades: int


class EquityPoint(BaseModel):
    timestamp: datetime
    equity: float
    cash: float
    benchmark: float = 0.0


class BacktestResult(BaseModel):
    id: str
    status: Literal["running", "completed", "failed"]
    strategy_id: str
    start: datetime
    end: datetime | None = None
    metrics: PerformanceMetrics | None = None
    equity_curve: list[EquityPoint] = []
    trades: list[dict[str, Any]] = []
    logs: list[str] = []


class Strategy(BaseModel):
    id: str
    name: str
    category: str
    type: str
    asset_class: str
    family: str = ""
    engine: str = ""
    params: dict[str, Any] = Field(default_factory=dict)
    description: str = ""
    tags: list[str] = []
    version: str = "1.0.0"


class Experiment(BaseModel):
    id: str
    timestamp: datetime
    hypothesis: str
    code: str = ""
    status: Literal["running", "passed", "failed", "review"] = "running"
    backtest_id: str | None = None
    research_note: str = ""
    strategy_id: str = ""
    strategy_family: str = ""
    strategy_params: dict[str, Any] = Field(default_factory=dict)


class DataSourceHealth(BaseModel):
    source: str
    status: Literal["ok", "degraded", "failed"]
    last_update: datetime | None = None
    latency_ms: float = 0.0
    error: str = ""


class Job(BaseModel):
    id: str
    name: str
    status: Literal["pending", "running", "completed", "failed"]
    schedule: str = ""
    started: datetime | None = None
    finished: datetime | None = None
    log_tail: list[str] = []
