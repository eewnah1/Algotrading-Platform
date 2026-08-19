import json
import logging
from pathlib import Path

from algoplatform.models.common import Strategy
from algoplatform.strategies.runner import StrategyRunner

logger = logging.getLogger(__name__)


class StrategyRegistry:
    def __init__(self, catalog_path: Path | None = None) -> None:
        self.catalog_path = catalog_path or Path(__file__).with_name("catalog.json")
        if not self.catalog_path.exists():
            from algoplatform.strategies.generator import generate_catalog
            generate_catalog(2000, self.catalog_path)
        self._strategies: dict[str, Strategy] = {}
        self._load()

    def _load(self) -> None:
        data = json.loads(self.catalog_path.read_text())
        for item in data:
            self._strategies[item["id"]] = Strategy(**item)

    def list_strategies(
        self,
        category: str | None = None,
        asset_class: str | None = None,
        q: str | None = None,
    ) -> list[Strategy]:
        out = list(self._strategies.values())
        if category:
            out = [s for s in out if s.category.lower() == category.lower()]
        if asset_class:
            out = [s for s in out if s.asset_class.lower() == asset_class.lower()]
        if q:
            q = q.lower()
            out = [
                s
                for s in out
                if q in s.name.lower()
                or q in s.description.lower()
                or any(q in t.lower() for t in s.tags)
            ]
        return out

    def get(self, strategy_id: str) -> StrategyRunner | None:
        strat = self._strategies.get(strategy_id)
        if not strat:
            return None
        return StrategyRunner(strat)

    def register(self, strategy: Strategy) -> None:
        self._strategies[strategy.id] = strategy
        logger.info("Registered strategy %s", strategy.id)

    def categories(self) -> list[str]:
        return sorted({s.category for s in self._strategies.values()})

    def asset_classes(self) -> list[str]:
        return sorted({s.asset_class for s in self._strategies.values()})
