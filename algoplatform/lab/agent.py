import logging
import uuid
from datetime import datetime
from typing import Any

from algoplatform.models.common import Experiment, Strategy

logger = logging.getLogger(__name__)


# Map natural prompt fragments to the runner families used by StrategyRunner.
_FAMILY_HINTS = [
    ("sma cross", "sma_cross"),
    ("moving average cross", "sma_cross"),
    ("ema cross", "ema_cross"),
    ("exponential moving average", "ema_cross"),
    ("macd", "macd"),
    ("rsi", "rsi_mean_revert"),
    ("mean reversion", "rsi_mean_revert"),
    ("overbought", "rsi_mean_revert"),
    ("oversold", "rsi_mean_revert"),
    ("bollinger", "bollinger_revert"),
    ("keltner", "keltner_revert"),
    ("donchian", "donchian_breakout"),
    ("volume breakout", "volume_breakout"),
    ("range break", "range_break"),
    ("breakout", "breakout"),
    ("52 week high", "momentum_52_high"),
    ("52 high", "momentum_52_high"),
    ("rotation", "momentum_etf_rotation"),
    ("etf rotation", "momentum_etf_rotation"),
    ("momentum", "momentum_12_1"),
    ("trend following", "momentum_12_1"),
    ("trend", "momentum_12_1"),
    ("volatility target", "volatility_target"),
    ("vol target", "volatility_target"),
    ("stat arb", "stat_arb"),
    ("stat-arb", "stat_arb"),
    ("spread", "stat_arb"),
    ("pairs", "stat_arb"),
    ("pair trade", "stat_arb"),
    ("carry", "carry"),
    ("yield curve", "yield_curve"),
    ("seasonality", "seasonality"),
    ("gamma scalp", "gamma_scalp"),
    ("gamma", "gamma_scalp"),
    ("calendar spread", "calendar_spread"),
    ("calendar", "calendar_spread"),
    ("options spread", "options_spread"),
    ("options", "options_spread"),
    ("quality factor", "quality_factor"),
    ("dividend", "dividend_growth"),
    ("low volatility", "low_volatility"),
    ("factor momentum", "factor_momentum"),
    ("factor", "factor_momentum"),
    ("adx", "adx_trend"),
    ("volume profile", "volume_profile"),
    ("reversal", "trend_reversal"),
]

_PARAM_DEFAULTS = {
    "sma_cross": {"fast": 10, "slow": 30, "threshold": 0.0},
    "ema_cross": {"fast": 12, "slow": 26, "threshold": 0.0},
    "macd": {"fast": 12, "slow": 26, "signal": 9, "threshold": 0.0},
    "rsi_mean_revert": {"period": 14, "oversold": 30, "overbought": 70},
    "bollinger_revert": {"period": 20, "std": 2.0},
    "keltner_revert": {"period": 20, "atr_mult": 2.0},
    "breakout": {"lookback": 20, "vol_filter": True},
    "donchian_breakout": {"lookback": 20, "atr_period": 10},
    "volume_breakout": {"lookback": 20, "volume_mult": 2.0},
    "range_break": {"lookback": 20, "threshold_pct": 0.01},
    "momentum_12_1": {"lookback": 20, "holding": 10},
    "momentum_52_high": {"lookback": 200, "threshold_pct": 0.0},
    "momentum_etf_rotation": {"lookback": 20, "top_n": 3},
    "volatility_target": {"target_vol": 0.15, "lookback": 20},
    "stat_arb": {"half_life": 30, "entry_z": 1.5},
    "carry": {"yield_lookback": 30, "momentum_lookback": 10},
    "yield_curve": {"short_tenor": 2, "long_tenor": 10, "momentum_lookback": 30},
    "seasonality": {"month": 1, "weekday": 0},
    "options_spread": {"spread_type": "bull_put", "dte": 30},
    "gamma_scalp": {"delta_hedge": False, "dte": 30},
    "calendar_spread": {"near_dte": 7, "far_dte": 30},
    "quality_factor": {"lookback": 30, "quality_weight": 0.5},
    "dividend_growth": {"lookback": 30, "yield_growth_z": 0.5},
    "low_volatility": {"lookback": 20, "vol_z": 0.5},
    "factor_momentum": {"lookback": 20, "factor_weights": {"mom": 0.4, "vol": 0.3, "carry": 0.3}},
    "adx_trend": {"period": 14, "threshold": 25},
    "volume_profile": {"volume_period": 20, "vwap_dev": 0.005},
    "trend_reversal": {"lookback": 10, "threshold_pct": 0.01},
}


def _infer_family(prompt: str) -> tuple[str, dict[str, Any]]:
    text = prompt.lower()
    for hint, family in _FAMILY_HINTS:
        if hint in text:
            return family, _PARAM_DEFAULTS.get(family, {}).copy()
    return "momentum_12_1", _PARAM_DEFAULTS["momentum_12_1"].copy()


def _vary_params(family: str, params: dict[str, Any], index: int) -> dict[str, Any]:
    """Add deterministic variety to generated params so repeated prompts differ."""
    varied = params.copy()
    if "fast" in varied:
        varied["fast"] = max(2, varied["fast"] + (index % 20))
    if "slow" in varied:
        varied["slow"] = max(varied.get("fast", 0) + 2, varied["slow"] + (index % 60))
    if "period" in varied and isinstance(varied["period"], int):
        varied["period"] = max(2, varied["period"] + (index % 30))
    if "lookback" in varied and isinstance(varied["lookback"], int):
        varied["lookback"] = max(2, varied["lookback"] + (index % 60))
    if "target_vol" in varied:
        varied["target_vol"] = round(0.05 + ((index % 20) / 100), 2)
    return varied


class StrategyLab:
    """AI strategy lab: turns a prompt into a hypothesis, code skeleton, and runnable strategy."""

    def __init__(self) -> None:
        self.experiments: dict[str, Experiment] = {}

    TEMPLATES = [
        "Hypothesis: mean reversion in {asset} after a {n}-day momentum spike is profitable.",
        "Hypothesis: a trend-following overlay on {asset} using {fast}/{slow} {ma} cross improves Sharpe.",
        "Hypothesis: combining carry and momentum in {asset} produces positive skew.",
        "Hypothesis: a stat-arb spread between {asset} and a proxy reverts with half-life {half_life} days.",
    ]

    def generate(self, prompt: str, registry: Any | None = None) -> Experiment:
        exp_id = str(uuid.uuid4())[:8]
        family, params = _infer_family(prompt)
        params = _vary_params(family, params, len(self.experiments))

        template = self.TEMPLATES[len(self.experiments) % len(self.TEMPLATES)]
        asset = "equity ETF"
        n = 5 + (len(self.experiments) % 15)
        hypothesis = template.format(asset=asset, n=n, fast=n, slow=n * 3, ma="EMA", half_life=n)
        hypothesis = f"{hypothesis} (family: {family})"
        code = self._code_skeleton(prompt, family, params)

        exp = Experiment(
            id=exp_id,
            timestamp=datetime.utcnow(),
            hypothesis=hypothesis,
            code=code,
            status="running",
            strategy_id=exp_id,
            strategy_family=family,
            strategy_params=params,
        )

        if registry is not None:
            try:
                strategy = Strategy(
                    id=exp_id,
                    name=prompt[:80] or f"AI Lab {family}",
                    category="AI Lab",
                    type="long",
                    asset_class="equity",
                    family=family,
                    engine="StrategyRunner",
                    params=params,
                    description=hypothesis,
                    tags=["ai-lab", family],
                )
                registry.register(strategy)
                logger.info("Registered generated strategy %s as %s", exp_id, family)
            except Exception as e:
                logger.warning("Failed to register generated strategy %s: %s", exp_id, e)

        self.experiments[exp_id] = exp
        return exp

    def _code_skeleton(self, prompt: str, family: str, params: dict[str, Any]) -> str:
        return f"""# AI-generated strategy: {prompt}
# Runner family: {family}
# Params: {params}
class GeneratedStrategy:
    def __init__(self, params):
        self.params = params

    def generate_signals(self, price_data):
        # {prompt}
        signals = {{}}
        for sym, df in price_data.items():
            # Uses the {family} signal logic from StrategyRunner
            close = df['Close']
            momentum = close.pct_change(periods=self.params.get('lookback', 20))
            signals[sym] = np.where(momentum > 0, 1, -1)
        return signals
"""

    def list(self) -> list[Experiment]:
        return sorted(self.experiments.values(), key=lambda e: e.timestamp, reverse=True)

    def get(self, exp_id: str) -> Experiment | None:
        return self.experiments.get(exp_id)

    def update_status(self, exp_id: str, status: Any, backtest_id: str | None = None, note: str = "") -> None:
        exp = self.experiments.get(exp_id)
        if not exp:
            return
        exp.status = status
        if backtest_id:
            exp.backtest_id = backtest_id
        if note:
            exp.research_note = note
