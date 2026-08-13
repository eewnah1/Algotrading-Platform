import logging

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)


class DataCleaner:
    """Detect and repair common market-data errors."""

    def clean_ohlcv(
        self,
        df: pd.DataFrame,
        symbol: str = "",
        z_threshold: float = 4.0,
        max_gap_fill: int = 5,
    ) -> pd.DataFrame:
        df = df.copy()
        df.index = pd.to_datetime(df.index)
        df = df[~df.index.duplicated(keep="last")].sort_index()

        # Ensure standard columns
        for col in ["Open", "High", "Low", "Close", "Volume"]:
            if col not in df.columns:
                df[col] = np.nan
        df["Volume"] = df["Volume"].fillna(0).astype(float)

        # Fix negative prices / volumes
        price_cols = ["Open", "High", "Low", "Close"]
        for c in price_cols:
            df[c] = df[c].clip(lower=0.0)

        # Ensure high >= low, high >= max(open,close), low <= min(open,close)
        df["High"] = df[price_cols].max(axis=1)
        df["Low"] = df[price_cols].min(axis=1)

        # Remove extreme single-bar spikes (z-score)
        for c in price_cols:
            logp = np.log1p(df[c].replace(0, np.nan))
            z = np.abs(stats.zscore(logp, nan_policy="omit"))
            df[c] = df[c].mask(z > z_threshold, np.nan)

        # Forward fill small gaps, then linear interpolate remaining
        df[price_cols] = df[price_cols].ffill(limit=max_gap_fill)
        df[price_cols] = df[price_cols].interpolate(method="linear", limit_direction="both")
        df["Volume"] = df["Volume"].fillna(0)

        # Drop rows with no prices after cleaning
        df = df.dropna(subset=["Close"])
        return df

    def detect_anomalies(
        self,
        df: pd.DataFrame,
        symbol: str = "",
    ) -> list[dict]:
        issues = []
        for c in ["Open", "High", "Low", "Close"]:
            if (df[c] < 0).any():
                issues.append({"type": "negative_price", "column": c, "count": int((df[c] < 0).sum())})
        if "Volume" in df.columns and (df["Volume"] < 0).any():
            issues.append({"type": "negative_volume", "count": int((df["Volume"] < 0).sum())})
        # overnight gaps > 10%
        if len(df) > 1:
            rets = df["Close"].pct_change().abs()
            spikes = (rets > 0.10).sum()
            if spikes:
                issues.append({"type": "large_overnight_gap", "count": int(spikes)})
        # duplicated index
        dups = df.index.duplicated().sum()
        if dups:
            issues.append({"type": "duplicated_timestamps", "count": int(dups)})
        return issues
