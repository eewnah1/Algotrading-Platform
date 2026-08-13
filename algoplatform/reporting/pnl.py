from typing import Any

import pandas as pd

from algoplatform.execution.portfolio import PortfolioManager


class PnLReporter:
    def __init__(self, portfolio: PortfolioManager) -> None:
        self.portfolio = portfolio

    def daily_pnl(self, history: list[dict] | None = None) -> list[dict]:
        hist = history or self.portfolio.history
        df = pd.DataFrame(hist)
        if df.empty:
            return []
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.set_index("timestamp").resample("D").last().ffill()
        df["daily_pnl"] = df["equity"].diff()
        df["daily_return"] = df["equity"].pct_change()
        df = df.reset_index()
        return [
            {
                "date": row["timestamp"].date().isoformat(),
                "equity": round(row["equity"], 2),
                "daily_pnl": round(row["daily_pnl"], 2),
                "daily_return": round(row["daily_return"] * 100, 2) if pd.notna(row["daily_return"]) else 0.0,
            }
            for _, row in df.iterrows()
        ]

    def cost_analysis(self) -> dict[str, Any]:
        total = self.portfolio.total_commission + self.portfolio.total_slippage
        return {
            "total_commission": round(self.portfolio.total_commission, 2),
            "total_slippage": round(self.portfolio.total_slippage, 2),
            "total_cost": round(total, 2),
            "cost_bps": round(total / self.portfolio.initial_cash * 10000, 2) if self.portfolio.initial_cash else 0.0,
        }

    def realized_vs_simulated(self, backtest_equity: list[float], live_equity: list[float]) -> list[dict]:
        out = []
        for i, (b, live_val) in enumerate(zip(backtest_equity, live_equity)):
            out.append(
                {
                    "day": i,
                    "simulated": round(b, 2),
                    "live": round(live_val, 2),
                    "drift": round(live_val - b, 2),
                }
            )
        return out

    def pnl_attribution(self) -> list[dict[str, Any]]:
        positions = self.portfolio.positions.values()
        total_pnl = sum(p.unrealized_pnl for p in positions) or 1.0
        return [
            {
                "symbol": p.symbol,
                "unrealized_pnl": round(p.unrealized_pnl, 2),
                "weight_pct": round(p.weight, 2),
                "contribution_pct": round(p.unrealized_pnl / total_pnl * 100, 2),
            }
            for p in sorted(positions, key=lambda x: abs(x.unrealized_pnl), reverse=True)
        ]
