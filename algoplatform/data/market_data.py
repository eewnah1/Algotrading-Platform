import logging
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

from algoplatform.config import settings
from algoplatform.models.common import DataSourceHealth, Quote

logger = logging.getLogger(__name__)


class MarketDataService:
    def __init__(self, cache_dir: Path | None = None) -> None:
        self.cache_dir = cache_dir or settings.data_dir / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._quotes: dict[str, Quote] = {}
        self._last_update: dict[str, datetime] = {}
        self._health: dict[str, DataSourceHealth] = {}

    def _cache_path(self, symbol: str) -> Path:
        return self.cache_dir / f"{symbol.replace('/', '-')}.parquet"

    def get_history(
        self,
        symbol: str,
        period: str = "1y",
        interval: str = "1d",
        end: datetime | None = None,
    ) -> pd.DataFrame:
        path = self._cache_path(symbol)
        end = end or datetime.utcnow()
        if path.exists():
            try:
                df = pd.read_parquet(path)
                df.index = pd.to_datetime(df.index)
                if not df.empty and (end - df.index[-1]).days < 1:
                    return df
            except Exception:
                pass
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval=interval, auto_adjust=True)
            if not df.empty:
                df.index = pd.to_datetime(df.index)
                if df.index.tz is not None:
                    df.index = df.index.tz_localize(None)
                df.to_parquet(path)
                self._health[symbol] = DataSourceHealth(
                    source="yfinance",
                    status="ok",
                    last_update=datetime.utcnow(),
                    latency_ms=0.0,
                )
        except Exception as e:
            logger.warning("yfinance fetch failed for %s: %s", symbol, e)
            self._health[symbol] = DataSourceHealth(
                source="yfinance",
                status="failed",
                last_update=datetime.utcnow(),
                error=str(e),
            )
            if path.exists():
                df = pd.read_parquet(path)
                df.index = pd.to_datetime(df.index)
            else:
                df = pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
        return df

    def get_quote(self, symbol: str) -> Quote:
        cached = self._quotes.get(symbol)
        if cached and (datetime.utcnow() - cached.timestamp).total_seconds() < 60:
            return cached
        df = self.get_history(symbol, period="5d", interval="1m")
        if df.empty:
            return Quote(
                symbol=symbol,
                timestamp=datetime.utcnow(),
                bid=0.0,
                ask=0.0,
                last=0.0,
                volume=0,
                source="cache",
            )
        last = float(df["Close"].iloc[-1])
        volume = int(df["Volume"].iloc[-1]) if "Volume" in df.columns else 0
        self._health[symbol] = DataSourceHealth(
            source="yfinance",
            status="ok",
            last_update=datetime.utcnow(),
            latency_ms=0.0,
        )
        q = Quote(
            symbol=symbol,
            timestamp=datetime.utcnow(),
            bid=last * 0.9995,
            ask=last * 1.0005,
            last=last,
            volume=volume,
            source="yfinance",
        )
        self._quotes[symbol] = q
        return q

    def snapshot(self, symbols: list[str] | None = None) -> list[Quote]:
        symbols = symbols or settings.default_universe
        return [self.get_quote(s) for s in symbols]

    def health(self) -> list[DataSourceHealth]:
        return list(self._health.values())

    def clean_cache(self, max_age_days: int = 7) -> int:
        removed = 0
        cutoff = datetime.utcnow() - timedelta(days=max_age_days)
        for f in self.cache_dir.glob("*.parquet"):
            if datetime.fromtimestamp(f.stat().st_mtime) < cutoff:
                f.unlink()
                removed += 1
        return removed
