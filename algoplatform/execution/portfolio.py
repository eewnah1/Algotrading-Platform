import logging
from datetime import datetime

from algoplatform.config import settings
from algoplatform.models.common import Order, Portfolio, Position, Side

logger = logging.getLogger(__name__)


class PortfolioManager:
    def __init__(self, cash: float = settings.paper_cash) -> None:
        self.cash = cash
        self.initial_cash = cash
        self.positions: dict[str, Position] = {}
        self.history: list[dict] = []
        self.orders: list[Order] = []
        self.total_commission = 0.0
        self.total_slippage = 0.0

    def apply_fill(self, order: Order, market_price: float) -> Order:
        self.orders.append(order)
        cost = order.avg_price * order.qty + order.commission
        if order.side == Side.BUY:
            self.cash -= cost
        else:
            self.cash += order.avg_price * order.qty - order.commission

        pos = self.positions.get(order.symbol, Position(symbol=order.symbol))
        if order.side == Side.BUY:
            new_qty = pos.qty + order.qty
            new_cost = pos.avg_cost * pos.qty + order.avg_price * order.qty
        else:
            new_qty = pos.qty - order.qty
            new_cost = pos.avg_cost * pos.qty - order.avg_price * order.qty

        if new_qty == 0:
            pos.qty = 0
            pos.avg_cost = 0.0
        else:
            pos.qty = new_qty
            pos.avg_cost = max(0.0, new_cost / new_qty)

        pos.market_price = market_price
        pos.market_value = pos.qty * market_price
        pos.unrealized_pnl = pos.market_value - pos.qty * pos.avg_cost if pos.qty else 0.0
        pos.unrealized_pnl_pct = (pos.unrealized_pnl / (pos.qty * pos.avg_cost) * 100) if pos.avg_cost else 0.0
        self.positions[order.symbol] = pos
        self.total_commission += order.commission
        self.total_slippage += order.qty * order.slippage
        return order

    def update_prices(self, prices: dict[str, float]) -> None:
        total = self.cash
        long_value = 0.0
        short_value = 0.0
        for symbol, price in prices.items():
            pos = self.positions.get(symbol)
            if not pos:
                continue
            pos.market_price = price
            pos.market_value = pos.qty * price
            pos.unrealized_pnl = pos.market_value - pos.qty * pos.avg_cost
            pos.unrealized_pnl_pct = (pos.unrealized_pnl / (pos.qty * pos.avg_cost) * 100) if pos.avg_cost else 0.0
            total += pos.market_value
            if pos.qty > 0:
                long_value += pos.market_value
            else:
                short_value += abs(pos.market_value)

        gross = long_value + short_value
        net = long_value - short_value
        for pos in self.positions.values():
            pos.weight = (pos.market_value / total * 100) if total else 0.0

        total_pnl = total - self.initial_cash
        self.snapshot = Portfolio(
            cash=self.cash,
            equity=total,
            long_value=long_value,
            short_value=short_value,
            gross_exposure=gross,
            net_exposure=net,
            margin_used=gross,
            day_pnl=0.0,
            total_pnl=total_pnl,
            total_pnl_pct=(total_pnl / self.initial_cash * 100) if self.initial_cash else 0.0,
            positions=list(self.positions.values()),
        )
        self.history.append({
            "timestamp": datetime.utcnow().isoformat(),
            "equity": total,
            "cash": self.cash,
        })

    def get_orders(self, limit: int = 100) -> list[Order]:
        return self.orders[-limit:]

    def get_portfolio(self) -> Portfolio:
        if hasattr(self, "snapshot"):
            return self.snapshot
        return Portfolio(
            cash=self.cash,
            equity=self.cash,
            long_value=0.0,
            short_value=0.0,
            gross_exposure=0.0,
            net_exposure=0.0,
            margin_used=0.0,
            day_pnl=0.0,
            total_pnl=0.0,
            total_pnl_pct=0.0,
            positions=list(self.positions.values()),
        )

    def target_weights(self, weights: dict[str, float], prices: dict[str, float]) -> list[Order]:
        orders: list[Order] = []
        total = self.get_portfolio().equity
        for symbol, target in weights.items():
            target_value = total * target
            target_qty = int(target_value / prices.get(symbol, 0)) if prices.get(symbol) else 0
            pos = self.positions.get(symbol)
            current_qty = pos.qty if pos else 0
            delta = target_qty - current_qty
            if delta > 0:
                from algoplatform.execution.broker import PaperBroker
                o = PaperBroker().fill(symbol, Side.BUY, delta, prices[symbol], algo="rebalance")
                self.apply_fill(o, prices[symbol])
                orders.append(o)
            elif delta < 0:
                from algoplatform.execution.broker import PaperBroker
                o = PaperBroker().fill(symbol, Side.SELL, abs(delta), prices[symbol], algo="rebalance")
                self.apply_fill(o, prices[symbol])
                orders.append(o)
        return orders
