import json
from pathlib import Path

ASSET_CLASSES = ["equity", "etf", "futures", "fx", "crypto", "commodity", "multi_asset"]
TYPES = ["long", "short", "long_short", "market_neutral", "pairs", "multi_timeframe"]
FAMILIES = [
    ("sma_cross", "Trend", "moving_average_crossover"),
    ("ema_cross", "Trend", "moving_average_crossover"),
    ("macd", "Momentum", "macd"),
    ("rsi_mean_revert", "MeanReversion", "rsi"),
    ("bollinger_revert", "MeanReversion", "bollinger"),
    ("breakout", "Breakout", "breakout"),
    ("donchian_breakout", "Breakout", "donchian"),
    ("momentum_12_1", "Momentum", "momentum"),
    ("volatility_target", "Volatility", "volatility"),
    ("stat_arb", "StatArb", "stat_arb"),
    ("ml_logreg", "ML", "ml"),
    ("ml_xgb", "ML", "ml"),
    ("carry", "Carry", "carry"),
    ("seasonality", "Seasonality", "seasonality"),
    ("options_spread", "Options", "options"),
]
TAG_BANK = [
    "technical", "quantitative", "systematic", "statistical", "machine_learning",
    "risk_parity", "factor", "momentum", "value", "carry", "volatility", "macro",
    "high_frequency", "intraday", "swing", "position", "multi_asset", "long_only",
    "market_neutral", "event_driven", "pairs", "calendar", "trend_following",
]


def make_strategy(index: int) -> dict:
    family, category, engine = FAMILIES[index % len(FAMILIES)]
    asset = ASSET_CLASSES[(index // len(FAMILIES)) % len(ASSET_CLASSES)]
    typ = TYPES[(index // (len(FAMILIES) * len(ASSET_CLASSES))) % len(TYPES)]
    param_sets = {
        "sma_cross": {"fast": 10 + (index % 30), "slow": 30 + (index % 120), "threshold": 0.0},
        "ema_cross": {"fast": 5 + (index % 20), "slow": 20 + (index % 80), "threshold": 0.0},
        "macd": {"fast": 8 + (index % 10), "slow": 17 + (index % 20), "signal": 9, "threshold": 0.0},
        "rsi_mean_revert": {"period": 7 + (index % 21), "oversold": 30, "overbought": 70},
        "bollinger_revert": {"period": 10 + (index % 40), "std": 1.5 + (index % 4) * 0.5},
        "breakout": {"lookback": 10 + (index % 50), "vol_filter": True},
        "donchian_breakout": {"lookback": 15 + (index % 60), "atr_period": 10},
        "momentum_12_1": {"lookback": 20 + (index % 100), "holding": 5 + (index % 20)},
        "volatility_target": {"target_vol": 0.05 + (index % 10) / 100, "lookback": 20},
        "stat_arb": {"half_life": 20 + (index % 60), "entry_z": 1.0 + (index % 3) * 0.5},
        "ml_logreg": {"features": ["return_1d", "return_5d", "volatility", "rsi"], "model": "logreg"},
        "ml_xgb": {"features": ["return_1d", "return_5d", "volatility", "rsi"], "model": "xgb"},
        "carry": {"yield_lookback": 30 + (index % 60), "momentum_lookback": 10},
        "seasonality": {"month": (index % 12) + 1, "weekday": index % 5},
        "options_spread": {"spread_type": "bull_put" if index % 2 else "iron_condor", "dte": 30},
    }
    params = param_sets.get(family, {})
    tags = list(set([TAG_BANK[index % len(TAG_BANK)], category.lower(), asset, typ, family]))[:5]
    name_parts = [category, family.replace("_", " ").title(), asset.title(), typ.replace("_", " ").title()]
    return {
        "id": f"{family}_{asset}_{typ}_{index:03d}",
        "name": " ".join(name_parts),
        "category": category,
        "type": typ,
        "asset_class": asset,
        "family": family,
        "engine": engine,
        "params": params,
        "description": f"{category} strategy using {family} on {asset} assets with {typ} exposure.",
        "tags": tags,
        "version": "1.0.0",
    }


def generate_catalog(n: int = 300, path: Path | None = None) -> list[dict]:
    catalog = [make_strategy(i) for i in range(n)]
    if path:
        path.write_text(json.dumps(catalog, indent=2))
    return catalog


if __name__ == "__main__":
    generate_catalog(300, Path(__file__).with_name("catalog.json"))
