import logging
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
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
                try:
                    csv_path = path.with_suffix(".csv")
                    if csv_path.exists():
                        df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
                        if not df.empty:
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
                try:
                    df.to_parquet(path)
                except Exception:
                    try:
                        df.to_csv(path.with_suffix(".csv"))
                    except Exception:
                        pass
                self._health[symbol] = DataSourceHealth(
                    source="yfinance",
                    status="ok",
                    last_update=datetime.utcnow(),
                    latency_ms=0.0,
                )
                return df
        except Exception as e:
            logger.warning("yfinance fetch failed for %s: %s", symbol, e)
            self._health[symbol] = DataSourceHealth(
                source="yfinance",
                status="failed",
                last_update=datetime.utcnow(),
                error=str(e),
            )
            if path.exists():
                try:
                    df = pd.read_parquet(path)
                    df.index = pd.to_datetime(df.index)
                    if not df.empty:
                        return df
                except Exception:
                    pass
            logger.info("Generating synthetic OHLCV for %s (demo / offline mode)", symbol)
            df = self._synthetic_ohlcv(symbol, period=period, end=end)
            try:
                df.to_parquet(path)
            except Exception:
                try:
                    df.to_csv(path.with_suffix(".csv"))
                except Exception:
                    pass
            self._health[symbol] = DataSourceHealth(
                source="synthetic",
                status="degraded",
                last_update=datetime.utcnow(),
                error=str(e),
            )
            return df
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])

    def _synthetic_ohlcv(
        self,
        symbol: str,
        period: str = "1y",
        end: datetime | None = None,
        seed: int | None = None,
    ) -> pd.DataFrame:
        end = end or datetime.utcnow()
        n = 1260
        rng = np.random.default_rng(abs(hash(symbol) % (2**32)) if seed is None else seed)
        base = 50 + (abs(hash(symbol)) % 400)
        dates = pd.bdate_range(end=end, periods=n)
        rets = rng.normal(0.00035, 0.011, size=n)
        close = base * np.cumprod(1.0 + rets)
        open_ = np.concatenate([[close[0]], close[:-1]])
        high = np.maximum(open_, close) * (1.0 + rng.uniform(0, 0.008, n))
        low = np.minimum(open_, close) * (1.0 - rng.uniform(0, 0.008, n))
        volume = rng.integers(200_000, 5_000_000, size=n).astype(int)
        df = pd.DataFrame(
            {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume},
            index=dates,
        )
        df.index.name = "Date"
        return df

    def get_quote(self, symbol: str) -> Quote:
        cached = self._quotes.get(symbol)
        if cached and (datetime.utcnow() - cached.timestamp).total_seconds() < 60:
            return cached
        df = self.get_history(symbol, period="5d", interval="1d")
        if df.empty:
            df = self.get_history(symbol, period="5d", interval="1m")
        if df.empty:
            base = 50 + (abs(hash(symbol)) % 400)
            return Quote(
                symbol=symbol,
                timestamp=datetime.utcnow(),
                bid=round(base * 0.9995, 4),
                ask=round(base * 1.0005, 4),
                last=float(base),
                volume=1_000_000,
                source="synthetic",
            )
        last = float(df["Close"].iloc[-1])
        volume = int(df["Volume"].iloc[-1]) if "Volume" in df.columns else 0
        src = "synthetic" if (self._health.get(symbol) and self._health[symbol].source == "synthetic") else "yfinance"
        self._health[symbol] = DataSourceHealth(
            source=src,
            status="ok" if src == "yfinance" else "degraded",
            last_update=datetime.utcnow(),
            latency_ms=0.0,
        )
        q = Quote(
            symbol=symbol,
            timestamp=datetime.utcnow(),
            bid=round(last * 0.9995, 4),
            ask=round(last * 1.0005, 4),
            last=last,
            volume=volume,
            source=src,
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
        for f in list(self.cache_dir.glob("*.parquet")) + list(self.cache_dir.glob("*.csv")):
            if datetime.fromtimestamp(f.stat().st_mtime) < cutoff:
                f.unlink()
                removed += 1
        return removed
