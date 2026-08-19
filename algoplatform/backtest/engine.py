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
    """Event-driven paper backtester with transaction costs and basic analytics."""

    def __init__(
        self,
        market_data: MarketDataService | None = None,
        registry: StrategyRegistry | None = None,
    ) -> None:
        self.market_data = market_data or MarketDataService()
        self.registry = registry or StrategyRegistry()
        # In-memory result store (last N backtests) so GET /backtests/{id} works
        self._results: dict[str, BacktestResult] = {}
        self._max_store = 50

    def get(self, backtest_id: str) -> BacktestResult | None:
        return self._results.get(backtest_id)

    def list_recent(self, limit: int = 20) -> list[BacktestResult]:
        items = list(self._results.values())
        items.sort(key=lambda r: r.start, reverse=True)
        return items[:limit]

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
            result = BacktestResult(
                id=bt_id,
                status="failed",
                strategy_id=strategy_id,
                start=datetime.utcnow(),
                end=datetime.utcnow(),
                logs=[f"Strategy {strategy_id} not found"],
            )
            self._store(result)
            return result

        price_data: dict[str, pd.DataFrame] = {}
        for sym in symbols:
            df = self.market_data.get_history(sym, start=start_dt, end=end_dt, interval="1d")
            if df.empty:
                logger.warning("No history for %s", sym)
                continue
            # Normalize index to date (strip time) for reliable alignment
            df = df.copy()
            df.index = pd.to_datetime(df.index).normalize()
            df = df[~df.index.duplicated(keep="last")]
            df = df.loc[start_dt:end_dt]
            if not df.empty:
                price_data[sym] = df

        if not price_data:
            result = BacktestResult(
                id=bt_id,
                status="failed",
                strategy_id=strategy_id,
                start=datetime.utcnow(),
                end=datetime.utcnow(),
                logs=["No price data available for any requested symbol"],
            )
            self._store(result)
            return result

        # Union of trading days, sorted
        all_dates = sorted(set().union(*(set(df.index) for df in price_data.values())))
        equity_curve: list[EquityPoint] = []
        trades: list[dict] = []
        signals = strategy.generate_signals(price_data, params or {})

        # Track previous signal per symbol so we only trade on *changes*
        prev_signal: dict[str, int] = {s: 0 for s in symbols}
        # Simple round-trip tracking for win rate
        entry_price: dict[str, float] = {}
        closed_pnls: list[float] = []

        for date in all_dates:
            prices = {}
            for sym, df in price_data.items():
                if date in df.index:
                    try:
                        prices[sym] = float(df.loc[date, "Close"])
                    except Exception:
                        continue

            day_signals = signals.get(date, {})
            # Also try normalized key in case of Timestamp vs datetime mismatch
            if not day_signals and hasattr(date, "to_pydatetime"):
                day_signals = signals.get(pd.Timestamp(date).normalize(), {}) or signals.get(date.to_pydatetime(), {})

            for sym in list(prices.keys()):
                signal = int(day_signals.get(sym, prev_signal.get(sym, 0)))
                pos = portfolio.positions.get(sym)
                current_qty = pos.qty if pos else 0
                price = prices[sym]
                if price <= 0:
                    continue

                # Enter / flip only on signal change relative to current position
                if signal > 0 and current_qty <= 0:
                    # Close short if any, then go long
                    if current_qty < 0:
                        close_qty = abs(current_qty)
                        order = broker.fill(sym, Side.BUY, close_qty, price, algo=strategy_id)
                        portfolio.apply_fill(order, price)
                        trades.append(self._trade_dict(order, signal))
                        if sym in entry_price:
                            closed_pnls.append(entry_price[sym] - price)  # short profit
                            del entry_price[sym]
                    qty = max(1, int((initial_cash * 0.15) / price))
                    order = broker.fill(sym, Side.BUY, qty, price, algo=strategy_id)
                    portfolio.apply_fill(order, price)
                    trades.append(self._trade_dict(order, signal))
                    entry_price[sym] = order.avg_price
                elif signal < 0 and current_qty >= 0:
                    if current_qty > 0:
                        close_qty = current_qty
                        order = broker.fill(sym, Side.SELL, close_qty, price, algo=strategy_id)
                        portfolio.apply_fill(order, price)
                        trades.append(self._trade_dict(order, signal))
                        if sym in entry_price:
                            closed_pnls.append(price - entry_price[sym])
                            del entry_price[sym]
                    qty = max(1, int((initial_cash * 0.15) / price))
                    order = broker.fill(sym, Side.SELL, qty, price, algo=strategy_id)
                    portfolio.apply_fill(order, price)
                    trades.append(self._trade_dict(order, signal))
                    entry_price[sym] = order.avg_price
                elif signal == 0 and current_qty != 0:
                    # Flat signal → close position
                    if current_qty > 0:
                        order = broker.fill(sym, Side.SELL, current_qty, price, algo=strategy_id)
                    else:
                        order = broker.fill(sym, Side.BUY, abs(current_qty), price, algo=strategy_id)
                    portfolio.apply_fill(order, price)
                    trades.append(self._trade_dict(order, signal))
                    if sym in entry_price:
                        if current_qty > 0:
                            closed_pnls.append(price - entry_price[sym])
                        else:
                            closed_pnls.append(entry_price[sym] - price)
                        del entry_price[sym]

                prev_signal[sym] = signal

            portfolio.update_prices(prices)
            snap = portfolio.get_portfolio()
            ts = date.to_pydatetime() if hasattr(date, "to_pydatetime") else date
            equity_curve.append(EquityPoint(timestamp=ts, equity=snap.equity, cash=snap.cash))

        equity_series = pd.Series({e.timestamp: e.equity for e in equity_curve})
        metrics = compute_metrics(equity_series)
        metrics.trades = len(trades)
        if closed_pnls:
            wins = sum(1 for p in closed_pnls if p > 0)
            metrics.win_rate = round(wins / len(closed_pnls) * 100, 2)
            avg = sum(closed_pnls) / len(closed_pnls)
            metrics.avg_trade = round(avg, 4)
            gross_win = sum(p for p in closed_pnls if p > 0)
            gross_loss = abs(sum(p for p in closed_pnls if p < 0))
            metrics.profit_factor = round(gross_win / gross_loss, 3) if gross_loss > 0 else 0.0
        else:
            metrics.win_rate = 0.0

        result_start = all_dates[0].to_pydatetime() if all_dates else datetime.utcnow()
        result_end = all_dates[-1].to_pydatetime() if all_dates else datetime.utcnow()
        result = BacktestResult(
            id=bt_id,
            status="completed",
            strategy_id=strategy_id,
            start=result_start,
            end=result_end,
            metrics=metrics,
            equity_curve=equity_curve,
            trades=trades,
            logs=[
                f"Ran {strategy_id} over {len(all_dates)} bars for {len(price_data)} symbols",
                f"Symbols: {', '.join(price_data.keys())}",
                f"Trades executed: {len(trades)}, closed round-trips: {len(closed_pnls)}",
            ],
        )
        self._store(result)
        return result

    def _trade_dict(self, order, signal: int) -> dict:
        d = order.model_dump()
        # Ensure JSON-serializable and frontend-friendly fields
        d["signal"] = signal
        d["price"] = d.get("avg_price", 0.0)
        if hasattr(d.get("timestamp"), "isoformat"):
            d["timestamp"] = d["timestamp"].isoformat()
        if hasattr(d.get("side"), "value"):
            d["side"] = d["side"].value
        return d

    def _store(self, result: BacktestResult) -> None:
        self._results[result.id] = result
        if len(self._results) > self._max_store:
            # drop oldest
            oldest = sorted(self._results.values(), key=lambda r: r.start)[0]
            self._results.pop(oldest.id, None)
