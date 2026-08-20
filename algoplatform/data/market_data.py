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

    def _to_dt(self, value: datetime | str | None) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        return pd.to_datetime(value).to_pydatetime()

    def get_history(
        self,
        symbol: str,
        period: str = "1y",
        interval: str = "1d",
        end: datetime | str | None = None,
        start: datetime | str | None = None,
    ) -> pd.DataFrame:
        """Fetch OHLCV history. Accepts start/end (used by the backtester).

        Falls back to synthetic data when yfinance is rate-limited or empty so
        backtests never fail purely due to data availability.
        """
        path = self._cache_path(symbol)
        end_dt = self._to_dt(end) or datetime.utcnow()
        start_dt = self._to_dt(start)

        def _slice(df: pd.DataFrame) -> pd.DataFrame:
            if df is None or df.empty:
                return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
            df = df.copy()
            df.index = pd.to_datetime(df.index)
            if getattr(df.index, "tz", None) is not None:
                df.index = df.index.tz_localize(None)
            if start_dt is not None:
                df = df.loc[start_dt:end_dt]
            else:
                df = df.loc[:end_dt]
            return df

        # 1) Try cache
        if path.exists():
            try:
                df = pd.read_parquet(path)
                df = _slice(df)
                if not df.empty:
                    return df
            except Exception:
                try:
                    csv_path = path.with_suffix(".csv")
                    if csv_path.exists():
                        df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
                        df = _slice(df)
                        if not df.empty:
                            return df
                except Exception:
                    pass

        # 2) Try yfinance
        try:
            ticker = yf.Ticker(symbol)
            if start_dt is not None:
                yf_end = (end_dt + timedelta(days=1)).strftime("%Y-%m-%d")
                df = ticker.history(
                    start=start_dt.strftime("%Y-%m-%d"),
                    end=yf_end,
                    interval=interval,
                    auto_adjust=True,
                )
            else:
                df = ticker.history(period=period, interval=interval, auto_adjust=True)
            if not df.empty:
                df.index = pd.to_datetime(df.index)
                if getattr(df.index, "tz", None) is not None:
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
                return _slice(df)
        except Exception as e:
            logger.warning("yfinance fetch failed for %s: %s", symbol, e)
            self._health[symbol] = DataSourceHealth(
                source="yfinance",
                status="failed",
                last_update=datetime.utcnow(),
                error=str(e),
            )

        # 3) Synthetic fallback — always covers the requested window
        logger.info("Generating synthetic OHLCV for %s (demo / offline mode)", symbol)
        df = self._synthetic_ohlcv(symbol, period=period, start=start_dt, end=end_dt)
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
            error="yfinance unavailable or empty; using synthetic data",
        )
        return _slice(df)

    def _synthetic_ohlcv(
        self,
        symbol: str,
        period: str = "1y",
        start: datetime | None = None,
        end: datetime | None = None,
        seed: int | None = None,
    ) -> pd.DataFrame:
        end = end or datetime.utcnow()
        if start is not None:
            dates = pd.bdate_range(start=start - timedelta(days=5), end=end)
            if len(dates) < 30:
                dates = pd.bdate_range(end=end, periods=260)
        else:
            n = 1260
            dates = pd.bdate_range(end=end, periods=n)
        n = len(dates)
        rng = np.random.default_rng(abs(hash(symbol) % (2**32)) if seed is None else seed)
        base = 50 + (abs(hash(symbol)) % 400)
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
