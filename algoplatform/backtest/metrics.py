import numpy as np
import pandas as pd

from algoplatform.models.common import PerformanceMetrics


def compute_metrics(
    equity: pd.Series,
    benchmark: pd.Series | None = None,
    risk_free_rate: float = 0.02,
) -> PerformanceMetrics:
    if equity.empty:
        return PerformanceMetrics(
            total_return=0.0,
            cagr=0.0,
            volatility=0.0,
            sharpe=0.0,
            sortino=0.0,
            max_drawdown=0.0,
            calmar=0.0,
            win_rate=0.0,
            profit_factor=0.0,
            avg_trade=0.0,
            trades=0,
        )
    total_return = equity.iloc[-1] / equity.iloc[0] - 1.0
    days = max(1, len(equity))
    years = days / 252.0
    cagr = (equity.iloc[-1] / equity.iloc[0]) ** (1.0 / years) - 1.0 if years > 0 else 0.0
    rets = equity.pct_change().dropna()
    vol = rets.std() * np.sqrt(252)
    downside = rets[rets < 0].std() * np.sqrt(252)
    excess = rets.mean() * 252 - risk_free_rate
    sharpe = excess / vol if vol else 0.0
    sortino = excess / downside if downside else 0.0
    running_max = equity.cummax()
    drawdown = (equity - running_max) / running_max
    max_dd = drawdown.min()
    calmar = cagr / abs(max_dd) if max_dd else 0.0
    return PerformanceMetrics(
        total_return=round(total_return * 100, 2),
        cagr=round(cagr * 100, 2),
        volatility=round(vol * 100, 2),
        sharpe=round(sharpe, 3),
        sortino=round(sortino, 3),
        max_drawdown=round(max_dd * 100, 2),
        calmar=round(calmar, 3),
        win_rate=0.0,
        profit_factor=0.0,
        avg_trade=0.0,
        trades=0,
    )
