import logging
import uuid
from datetime import datetime

from algoplatform.config import settings
from algoplatform.models.common import Order, OrderStatus, OrderType, Side

logger = logging.getLogger(__name__)


class PaperBroker:
    def __init__(
        self,
        commission_bps: float = settings.commission_bps,
        slippage_bps: float = settings.slippage_bps,
    ) -> None:
        self.commission_bps = commission_bps
        self.slippage_bps = slippage_bps

    def fill(
        self,
        symbol: str,
        side: Side,
        qty: int,
        market_price: float,
        order_type: OrderType = OrderType.MARKET,
        limit_price: float | None = None,
        algo: str = "default",
    ) -> Order:
        if qty <= 0:
            raise ValueError("qty must be positive")

        fill_price = market_price
        if order_type == OrderType.LIMIT and limit_price:
            fill_price = limit_price

        slippage = fill_price * self.slippage_bps / 10000.0
        fill_price += slippage if side == Side.BUY else -slippage
        commission = fill_price * qty * self.commission_bps / 10000.0

        order = Order(
            id=str(uuid.uuid4())[:8],
            timestamp=datetime.utcnow(),
            symbol=symbol,
            side=side,
            qty=qty,
            order_type=order_type,
            limit_price=limit_price,
            avg_price=round(fill_price, 4),
            status=OrderStatus.FILLED,
            broker="paper",
            algo=algo,
            commission=round(commission, 4),
            slippage=round(slippage, 6),
        )
        return order
