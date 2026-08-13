import logging
import uuid
from datetime import datetime
from typing import Any

import pandas as pd

from algoplatform.backtest.metrics import compute_metrics
from algoplatform.config import settings
from algoplatform.data.market_data import MarketDataService
from algoplatform.execution.broker import PaperBroker
from algoplatform.execution.portfolio import PortfolioManager
from algoplatform.models.common import BacktestResult, EquityPoint, Side
from algoplatform.strategies.registry import StrategyRegistry

logger = logging.getLogger(__name__)


class BacktestEngine:
    def __init__(self, market_data: MarketDataService | None = None) -> None:
        self.market_data = market_data or MarketDataService()
        self.registry = StrategyRegistry()

    def run(
        self,
        strategy_id: str,
        symbols: list[str] | None = None,
        start: str | None = None,
        end: str | None = None,
        initial_cash: float = settings.paper_cash,
        params: dict[str, Any] | None = None,
    ) -> BacktestResult:
        bt_id = str(uuid.uuid4())[:8]
        symbols = symbols or settings.default_universe[:5]
        start_dt = pd.to_datetime(start) if start else pd.Timestamp.now() - pd.DateOffset(years=1)
        end_dt = pd.to_datetime(end) if end else pd.Timestamp.now()

        portfolio = PortfolioManager(cash=initial_cash)
        broker = PaperBroker()
        strategy = self.registry.get(strategy_id)
        if strategy is None:
            return BacktestResult(
                id=bt_id,
                status="failed",
                strategy_id=strategy_id,
                start=datetime.utcnow(),
                end=datetime.utcnow(),
            )

        all_dates: set = set()
        price_data: dict[str, pd.DataFrame] = {}
        for sym in symbols:
            df = self.market_data.get_history(sym)
            df = df.loc[start_dt:end_dt]
            price_data[sym] = df
            all_dates.update(df.index)

        dates = sorted(all_dates)
        equity_curve: list[EquityPoint] = []
        trades: list[dict] = []
        signals = strategy.generate_signals(price_data, params or {})

        for date in dates:
            prices = {sym: float(df.loc[date, "Close"]) for sym, df in price_data.items() if date in df.index}
            for sym, signal in signals.get(date, {}).items():
                if signal == 0:
                    continue
                pos = portfolio.positions.get(sym)
                current_qty = pos.qty if pos else 0
                price = prices.get(sym, 0.0)
                if signal > 0 and current_qty <= 0:
                    qty = max(1, int(initial_cash * 0.1 / price))
                    order = broker.fill(sym, Side.BUY, qty, price, algo=strategy_id)
                    portfolio.apply_fill(order, price)
                    trades.append(order.model_dump())
                elif signal < 0 and current_qty >= 0:
                    qty = max(1, int(initial_cash * 0.1 / price))
                    order = broker.fill(sym, Side.SELL, qty, price, algo=strategy_id)
                    portfolio.apply_fill(order, price)
                    trades.append(order.model_dump())

            portfolio.update_prices(prices)
            snap = portfolio.get_portfolio()
            equity_curve.append(EquityPoint(timestamp=date.to_pydatetime(), equity=snap.equity, cash=snap.cash))

        equity_series = pd.Series({e.timestamp: e.equity for e in equity_curve})
        metrics = compute_metrics(equity_series)
        metrics.trades = len(trades)
        win_pnl = sum(1 for t in trades if t.get("side") == "SELL")
        metrics.win_rate = round(win_pnl / len(trades) * 100, 2) if trades else 0.0

        return BacktestResult(
            id=bt_id,
            status="completed",
            strategy_id=strategy_id,
            start=datetime.utcnow(),
            end=datetime.utcnow(),
            metrics=metrics,
            equity_curve=equity_curve,
            trades=trades,
            logs=[f"Ran {strategy_id} over {len(dates)} bars for {len(symbols)} symbols"],
        )
