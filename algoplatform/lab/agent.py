import logging
import uuid
from datetime import datetime
from typing import Any

from algoplatform.models.common import Experiment

logger = logging.getLogger(__name__)


class StrategyLab:
    """Mock AI strategy lab that generates a hypothesis, code skeleton and research note."""

    def __init__(self) -> None:
        self.experiments: dict[str, Experiment] = {}

    TEMPLATES = [
        "Hypothesis: mean reversion in {asset} after a {n}-day momentum spike is profitable.",
        "Hypothesis: a trend-following overlay on {asset} using {fast}/{slow} {ma} cross improves Sharpe.",
        "Hypothesis: combining carry and momentum in {asset} produces positive skew.",
        "Hypothesis: a stat-arb spread between {asset} and a proxy reverts with half-life {half_life} days.",
    ]

    def generate(self, prompt: str) -> Experiment:
        exp_id = str(uuid.uuid4())[:8]
        template = self.TEMPLATES[len(self.experiments) % len(self.TEMPLATES)]
        asset = "equity ETF"
        n = 5 + (len(self.experiments) % 15)
        hypothesis = template.format(asset=asset, n=n, fast=n, slow=n * 3, ma="EMA", half_life=n)
        code = self._code_skeleton(prompt, hypothesis)
        exp = Experiment(
            id=exp_id,
            timestamp=datetime.utcnow(),
            hypothesis=hypothesis,
            code=code,
            status="running",
        )
        self.experiments[exp_id] = exp
        return exp

    def _code_skeleton(self, prompt: str, hypothesis: str) -> str:
        return f"""# AI-generated strategy: {prompt}
class GeneratedStrategy:
    def __init__(self, params):
        self.params = params

    def generate_signals(self, price_data):
        # {hypothesis}
        signals = {{}}
        for sym, df in price_data.items():
            # placeholder: long on positive momentum
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
