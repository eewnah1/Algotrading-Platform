"""Strategy catalog generator — institutional equity & ETF focused library.

Generates up to 10,000 diverse, parameterised strategies with heavy weight on
equity and ETF asset classes while preserving multi-asset coverage.
"""

from __future__ import annotations

import json
from pathlib import Path

ASSET_CLASSES = [
    "equity", "equity", "equity", "equity", "equity",
    "etf", "etf", "etf", "etf", "etf",
    "futures", "fx", "crypto", "commodity", "multi_asset",
]

TYPES = ["long", "short", "long_short", "market_neutral", "pairs", "multi_timeframe"]

FAMILIES = [
    ("sma_cross", "Trend", "moving_average_crossover"),
    ("ema_cross", "Trend", "moving_average_crossover"),
    ("adx_trend", "Trend", "adx"),
    ("dual_ma_trend", "Trend", "moving_average_crossover"),
    ("triple_ma", "Trend", "moving_average_crossover"),
    ("macd", "Momentum", "macd"),
    ("momentum_12_1", "Momentum", "momentum"),
    ("momentum_52_high", "Momentum", "momentum52"),
    ("momentum_etf_rotation", "Momentum", "rotation"),
    ("relative_strength", "Momentum", "momentum"),
    ("price_momentum", "Momentum", "momentum"),
    ("rsi_mean_revert", "MeanReversion", "rsi"),
    ("bollinger_revert", "MeanReversion", "bollinger"),
    ("keltner_revert", "MeanReversion", "keltner"),
    ("trend_reversal", "MeanReversion", "reversal"),
    ("zscore_revert", "MeanReversion", "stat_arb"),
    ("breakout", "Breakout", "breakout"),
    ("donchian_breakout", "Breakout", "donchian"),
    ("volume_breakout", "Breakout", "volume_breakout"),
    ("range_break", "Breakout", "range"),
    ("atr_breakout", "Breakout", "breakout"),
    ("volatility_target", "Volatility", "volatility"),
    ("vol_regime", "Volatility", "volatility"),
    ("low_volatility", "Factor", "factor"),
    ("quality_factor", "Factor", "factor"),
    ("dividend_growth", "Factor", "factor"),
    ("factor_momentum", "Factor", "factor"),
    ("value_factor", "Factor", "factor"),
    ("size_factor", "Factor", "factor"),
    ("stat_arb", "StatArb", "stat_arb"),
    ("pairs_spread", "StatArb", "stat_arb"),
    ("ml_logreg", "ML", "ml"),
    ("ml_xgb", "ML", "ml"),
    ("ml_rf", "ML", "ml"),
    ("ml_svc", "ML", "ml"),
    ("ml_nn", "ML", "ml"),
    ("volume_profile", "Volume", "volume_profile"),
    ("vwap_reversion", "Volume", "volume_profile"),
    ("carry", "Carry", "carry"),
    ("seasonality", "Seasonality", "seasonality"),
    ("options_spread", "Options", "options"),
    ("gamma_scalp", "Options", "options"),
    ("calendar_spread", "Options", "options"),
]

TAG_BANK = [
    "technical", "quantitative", "systematic", "statistical", "machine_learning",
    "risk_parity", "factor", "momentum", "value", "carry", "volatility", "macro",
    "high_frequency", "intraday", "swing", "position", "multi_asset", "long_only",
    "market_neutral", "event_driven", "pairs", "calendar", "trend_following",
    "equity", "etf", "sector_rotation", "smart_beta", "low_vol", "quality",
    "dividend", "growth", "mean_reversion", "breakout", "regime",
]


def _params_for(family: str, index: int) -> dict:
    i = index
    grids = {
        "sma_cross": {"fast": 5 + (i % 40), "slow": 20 + (i % 180), "threshold": round((i % 5) * 0.001, 4)},
        "ema_cross": {"fast": 3 + (i % 25), "slow": 15 + (i % 100), "threshold": round((i % 5) * 0.001, 4)},
        "dual_ma_trend": {"fast": 8 + (i % 20), "slow": 40 + (i % 80), "threshold": 0.0},
        "triple_ma": {"fast": 5 + (i % 15), "mid": 20 + (i % 30), "slow": 50 + (i % 100)},
        "macd": {"fast": 8 + (i % 12), "slow": 17 + (i % 26), "signal": 5 + (i % 12), "threshold": 0.0},
        "rsi_mean_revert": {"period": 5 + (i % 25), "oversold": 20 + (i % 15), "overbought": 70 + (i % 15)},
        "bollinger_revert": {"period": 10 + (i % 50), "std": 1.0 + (i % 6) * 0.35},
        "keltner_revert": {"period": 10 + (i % 40), "atr_mult": 1.0 + (i % 6) * 0.4},
        "zscore_revert": {"lookback": 15 + (i % 60), "entry_z": 1.0 + (i % 4) * 0.5, "exit_z": 0.25},
        "breakout": {"lookback": 8 + (i % 60), "vol_filter": bool(i % 2)},
        "donchian_breakout": {"lookback": 10 + (i % 70), "atr_period": 8 + (i % 20)},
        "volume_breakout": {"lookback": 8 + (i % 50), "volume_mult": 1.1 + (i % 8) * 0.15},
        "range_break": {"lookback": 8 + (i % 50), "threshold_pct": 0.003 + (i % 15) * 0.0004},
        "atr_breakout": {"lookback": 10 + (i % 40), "atr_mult": 1.0 + (i % 5) * 0.5},
        "momentum_12_1": {"lookback": 15 + (i % 120), "holding": 3 + (i % 25)},
        "momentum_52_high": {"lookback": 120 + (i % 120), "threshold_pct": round((i % 5) * 0.002, 4)},
        "momentum_etf_rotation": {"lookback": 15 + (i % 80), "top_n": 2 + (i % 8)},
        "relative_strength": {"lookback": 20 + (i % 100), "rank_top": 0.2 + (i % 5) * 0.05},
        "price_momentum": {"lookback": 10 + (i % 90), "skip": 1 + (i % 5)},
        "volatility_target": {"target_vol": 0.06 + (i % 15) / 100, "lookback": 15 + (i % 40)},
        "vol_regime": {"lookback": 20 + (i % 40), "high_vol_threshold": 0.18 + (i % 10) / 100},
        "stat_arb": {"half_life": 15 + (i % 70), "entry_z": 1.0 + (i % 4) * 0.4},
        "pairs_spread": {"lookback": 30 + (i % 60), "entry_z": 1.5 + (i % 3) * 0.5},
        "ml_logreg": {"features": ["return_1d", "return_5d", "volatility", "rsi"], "model": "logreg"},
        "ml_xgb": {"features": ["return_1d", "return_5d", "volatility", "rsi"], "model": "xgb"},
        "ml_rf": {"features": ["return_1d", "return_5d", "volatility", "rsi"], "model": "rf"},
        "ml_svc": {"features": ["return_1d", "return_5d", "volatility", "rsi"], "model": "svc"},
        "ml_nn": {"features": ["return_1d", "return_5d", "volatility", "rsi"], "model": "nn"},
        "carry": {"yield_lookback": 20 + (i % 80), "momentum_lookback": 8 + (i % 20)},
        "seasonality": {"month": (i % 12) + 1, "weekday": i % 5},
        "options_spread": {"spread_type": "bull_put" if i % 2 else "iron_condor", "dte": 20 + (i % 40)},
        "gamma_scalp": {"delta_hedge": bool(i % 2), "dte": 20 + (i % 40)},
        "calendar_spread": {"near_dte": 5 + (i % 20), "far_dte": 25 + (i % 40)},
        "quality_factor": {"lookback": 20 + (i % 80), "quality_weight": 0.4 + (i % 6) * 0.1},
        "dividend_growth": {"lookback": 20 + (i % 80), "yield_growth_z": 0.4 + (i % 4) * 0.2},
        "low_volatility": {"lookback": 15 + (i % 70), "vol_z": 0.4 + (i % 4) * 0.2},
        "factor_momentum": {"lookback": 15 + (i % 70), "factor_weights": {"mom": 0.4, "vol": 0.3, "carry": 0.3}},
        "value_factor": {"lookback": 60 + (i % 120), "value_weight": 0.5 + (i % 5) * 0.1},
        "size_factor": {"lookback": 20 + (i % 60), "size_tilt": 0.3 + (i % 5) * 0.1},
        "adx_trend": {"period": 8 + (i % 25), "threshold": 15 + (i % 25)},
        "volume_profile": {"volume_period": 8 + (i % 40), "vwap_dev": 0.0008 + (i % 12) * 0.0004},
        "vwap_reversion": {"lookback": 10 + (i % 30), "vwap_dev": 0.001 + (i % 10) * 0.0005},
        "trend_reversal": {"lookback": 4 + (i % 20), "threshold_pct": 0.008 + (i % 12) * 0.001},
    }
    return grids.get(family, {"lookback": 20 + (i % 40)})


def make_strategy(index: int) -> dict:
    family, category, engine = FAMILIES[index % len(FAMILIES)]
    asset = ASSET_CLASSES[(index // len(FAMILIES)) % len(ASSET_CLASSES)]
    typ = TYPES[(index // (len(FAMILIES) * len(ASSET_CLASSES))) % len(TYPES)]
    params = _params_for(family, index)
    tags = list({
        TAG_BANK[index % len(TAG_BANK)],
        category.lower(),
        asset,
        typ,
        family,
        "equity_etf_focus" if asset in ("equity", "etf") else "multi_asset",
    })[:6]
    name = f"{category} {family.replace('_', ' ').title()} {asset.upper()} {typ.replace('_', ' ').title()}"
    return {
        "id": f"{family}_{asset}_{typ}_{index:04d}",
        "name": name,
        "category": category,
        "type": typ,
        "asset_class": asset,
        "family": family,
        "engine": engine,
        "params": params,
        "description": (
            f"{category} strategy using {family} on {asset} with {typ} exposure. "
            f"Parameterised for systematic research and risk-parity compatible backtests."
        ),
        "tags": tags,
        "version": "1.1.0",
    }


def generate_catalog(n: int = 10000, path: Path | None = None) -> list[dict]:
    catalog = [make_strategy(i) for i in range(n)]
    if path:
        path.write_text(json.dumps(catalog, indent=2))
    return catalog


if __name__ == "__main__":
    out = Path(__file__).with_name("catalog.json")
    generate_catalog(10000, out)
    print(f"Wrote {out} with 10000 strategies (equity/etf focused)")
