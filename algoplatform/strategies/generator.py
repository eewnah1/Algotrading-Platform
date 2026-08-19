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
    ("keltner_revert", "MeanReversion", "keltner"),
    ("breakout", "Breakout", "breakout"),
    ("donchian_breakout", "Breakout", "donchian"),
    ("volume_breakout", "Breakout", "volume_breakout"),
    ("range_break", "Breakout", "range"),
    ("momentum_12_1", "Momentum", "momentum"),
    ("momentum_52_high", "Momentum", "momentum52"),
    ("momentum_etf_rotation", "Momentum", "rotation"),
    ("volatility_target", "Volatility", "volatility"),
    ("stat_arb", "StatArb", "stat_arb"),
    ("ml_logreg", "ML", "ml"),
    ("ml_xgb", "ML", "ml"),
    ("ml_rf", "ML", "ml"),
    ("ml_svc", "ML", "ml"),
    ("ml_nn", "ML", "ml"),
    ("carry", "Carry", "carry"),
    ("yield_curve", "Macro", "yield_curve"),
    ("seasonality", "Seasonality", "seasonality"),
    ("options_spread", "Options", "options"),
    ("gamma_scalp", "Options", "options"),
    ("calendar_spread", "Options", "options"),
    ("quality_factor", "Factor", "factor"),
    ("dividend_growth", "Factor", "factor"),
    ("low_volatility", "Factor", "factor"),
    ("factor_momentum", "Factor", "factor"),
    ("adx_trend", "Trend", "adx"),
    ("volume_profile", "Volume", "volume_profile"),
    ("trend_reversal", "MeanReversion", "reversal"),
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
        "keltner_revert": {"period": 10 + (index % 40), "atr_mult": 1.0 + (index % 5) * 0.5},
        "breakout": {"lookback": 10 + (index % 50), "vol_filter": True},
        "donchian_breakout": {"lookback": 15 + (index % 60), "atr_period": 10},
        "volume_breakout": {"lookback": 10 + (index % 50), "volume_mult": 1.2 + (index % 5) * 0.2},
        "range_break": {"lookback": 10 + (index % 50), "threshold_pct": 0.005 + (index % 10) * 0.0005},
        "momentum_12_1": {"lookback": 20 + (index % 100), "holding": 5 + (index % 20)},
        "momentum_52_high": {"lookback": 200 + (index % 60), "threshold_pct": 0.0},
        "momentum_etf_rotation": {"lookback": 20 + (index % 60), "top_n": 2 + (index % 5)},
        "volatility_target": {"target_vol": 0.05 + (index % 10) / 100, "lookback": 20},
        "stat_arb": {"half_life": 20 + (index % 60), "entry_z": 1.0 + (index % 3) * 0.5},
        "ml_logreg": {"features": ["return_1d", "return_5d", "volatility", "rsi"], "model": "logreg"},
        "ml_xgb": {"features": ["return_1d", "return_5d", "volatility", "rsi"], "model": "xgb"},
        "ml_rf": {"features": ["return_1d", "return_5d", "volatility", "rsi"], "model": "rf"},
        "ml_svc": {"features": ["return_1d", "return_5d", "volatility", "rsi"], "model": "svc"},
        "ml_nn": {"features": ["return_1d", "return_5d", "volatility", "rsi"], "model": "nn"},
        "carry": {"yield_lookback": 30 + (index % 60), "momentum_lookback": 10},
        "yield_curve": {"short_tenor": 2, "long_tenor": 10, "momentum_lookback": 30 + (index % 60)},
        "seasonality": {"month": (index % 12) + 1, "weekday": index % 5},
        "options_spread": {"spread_type": "bull_put" if index % 2 else "iron_condor", "dte": 30},
        "gamma_scalp": {"delta_hedge": index % 2 == 0, "dte": 30 + (index % 30)},
        "calendar_spread": {"near_dte": 7 + (index % 14), "far_dte": 30 + (index % 30)},
        "quality_factor": {"lookback": 30 + (index % 60), "quality_weight": 0.5 + (index % 5) * 0.1},
        "dividend_growth": {"lookback": 30 + (index % 60), "yield_growth_z": 0.5 + (index % 3) * 0.25},
        "low_volatility": {"lookback": 20 + (index % 60), "vol_z": 0.5 + (index % 3) * 0.25},
        "factor_momentum": {"lookback": 20 + (index % 60), "factor_weights": {"mom": 0.4, "vol": 0.3, "carry": 0.3}},
        "adx_trend": {"period": 10 + (index % 20), "threshold": 20 + (index % 15)},
        "volume_profile": {"volume_period": 10 + (index % 30), "vwap_dev": 0.001 + (index % 10) * 0.0005},
        "trend_reversal": {"lookback": 5 + (index % 15), "threshold_pct": 0.01 + (index % 10) * 0.001},
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
    generate_catalog(2000, Path(__file__).with_name("catalog.json"))
