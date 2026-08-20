import logging

import numpy as np
import pandas as pd

from algoplatform.models.common import Strategy

logger = logging.getLogger(__name__)


def _sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window, min_periods=1).mean()


def _ema(series: pd.Series, window: int) -> pd.Series:
    return series.ewm(span=window, min_periods=1).mean()


def _rsi(series: pd.Series, window: int) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=window, min_periods=1).mean()
    avg_loss = loss.rolling(window=window, min_periods=1).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _bbands(series: pd.Series, window: int, std: float) -> tuple[pd.Series, pd.Series, pd.Series]:
    ma = series.rolling(window=window, min_periods=1).mean()
    sigma = series.rolling(window=window, min_periods=1).std()
    upper = ma + std * sigma
    lower = ma - std * sigma
    return upper, ma, lower


class StrategyRunner:
    def __init__(self, strategy: Strategy) -> None:
        self.strategy = strategy

    def generate_signals(self, price_data: dict[str, pd.DataFrame], params: dict | None = None) -> dict:
        params = params or self.strategy.params
        signals: dict = {}
        family = self.strategy.family
        for sym, df in price_data.items():
            if df.empty:
                continue
            close = df["Close"]
            if family in ("sma_cross", "ema_cross", "dual_ma_trend", "triple_ma"):
                fast = int(params.get("fast", 10))
                slow = int(params.get("slow", 30))
                if family in ("sma_cross", "dual_ma_trend", "triple_ma"):
                    fast_line = _sma(close, fast)
                    slow_line = _sma(close, slow)
                else:
                    fast_line = _ema(close, fast)
                    slow_line = _ema(close, slow)
                sig = np.where(fast_line > slow_line, 1, np.where(fast_line < slow_line, -1, 0))
            elif family == "macd":
                fast = int(params.get("fast", 12))
                slow = int(params.get("slow", 26))
                signal = int(params.get("signal", 9))
                ema_fast = _ema(close, fast)
                ema_slow = _ema(close, slow)
                macd_line = ema_fast - ema_slow
                signal_line = _ema(macd_line, signal)
                sig = np.where(macd_line > signal_line, 1, np.where(macd_line < signal_line, -1, 0))
            elif family == "rsi_mean_revert":
                period = int(params.get("period", 14))
                rsi = _rsi(close, period)
                ob = params.get("overbought", 70)
                os = params.get("oversold", 30)
                sig = np.where(rsi < os, 1, np.where(rsi > ob, -1, 0))
            elif family == "bollinger_revert":
                period = int(params.get("period", 20))
                std = float(params.get("std", 2.0))
                upper, _, lower = _bbands(close, period, std)
                sig = np.where(close < lower, 1, np.where(close > upper, -1, 0))
            elif family in ("breakout", "donchian_breakout", "volume_breakout", "range_break", "atr_breakout"):
                lookback = int(params.get("lookback", 20))
                upper = close.rolling(lookback, min_periods=1).max()
                lower = close.rolling(lookback, min_periods=1).min()
                sig = np.where(close > upper.shift(1), 1, np.where(close < lower.shift(1), -1, 0))
            elif family in ("momentum_12_1", "momentum_52_high", "momentum_etf_rotation", "relative_strength", "price_momentum"):
                lookback = int(params.get("lookback", 20))
                mom = close.pct_change(lookback)
                sig = np.where(mom > 0, 1, np.where(mom < 0, -1, 0))
            elif family in ("volatility_target", "vol_regime"):
                lookback = int(params.get("lookback", 20))
                ret = close.pct_change()
                vol = ret.rolling(lookback, min_periods=1).std() * np.sqrt(252)
                target = float(params.get("target_vol", 0.15))
                sig = np.where(vol < target, 1, -1)
            elif family in ("stat_arb", "pairs_spread", "carry", "seasonality", "yield_curve", "calendar_spread", "gamma_scalp", "zscore_revert"):
                ret = close.pct_change()
                sig = np.where(ret > 0, 1, np.where(ret < 0, -1, 0))
            elif family in ("ml_logreg", "ml_xgb", "ml_rf", "ml_svc", "ml_nn"):
                ret1 = close.pct_change()
                ret5 = close.pct_change(5)
                vol = ret1.rolling(20, min_periods=1).std()
                rsi = _rsi(close, 14)
                score = np.sign(ret1.fillna(0) + ret5.fillna(0) * 0.5 - vol.fillna(0) + (rsi - 50) / 100)
                sig = np.where(score > 0, 1, np.where(score < 0, -1, 0))
            elif family in ("options_spread", "keltner_revert"):
                ret = close.pct_change().rolling(5, min_periods=1).mean()
                sig = np.where(ret > 0, 1, np.where(ret < 0, -1, 0))
            elif family in ("quality_factor", "dividend_growth", "low_volatility", "factor_momentum", "value_factor", "size_factor"):
                lookback = int(params.get("lookback", 30))
                ret = close.pct_change(lookback)
                sig = np.where(ret > 0, 1, np.where(ret < 0, -1, 0))
            elif family in ("adx_trend", "volume_profile", "vwap_reversion", "trend_reversal"):
                lookback = int(params.get("lookback", params.get("period", 20)))
                ret = close.pct_change(lookback)
                sig = np.where(ret > 0, 1, np.where(ret < 0, -1, 0))
            else:
                sig = np.zeros(len(close), dtype=int)

            s = pd.Series(sig, index=close.index)
            s = s.where(s != 0).ffill().fillna(0).astype(int)
            for date, val in s.items():
                signals.setdefault(date, {})[sym] = int(val)
        return signals

    def to_python(self) -> str:
        """Return a runnable Python snippet for this strategy."""
        params = self.strategy.params
        family = self.strategy.family
        lines = [
            "import pandas as pd",
            "import numpy as np",
            "",
            "def sma(s, w): return s.rolling(window=w, min_periods=1).mean()",
            "def ema(s, w): return s.ewm(span=w, min_periods=1).mean()",
            "def rsi(s, w=14):",
            "    d = s.diff(); gain = d.where(d > 0, 0.0); loss = -d.where(d < 0, 0.0)",
            "    ag = gain.rolling(w, min_periods=1).mean(); al = loss.rolling(w, min_periods=1).mean()",
            "    rs = ag / al.replace(0, np.nan)",
            "    return 100 - (100 / (1 + rs))",
            "def bbands(s, w=20, st=2.0):",
            "    ma = s.rolling(w, min_periods=1).mean(); sd = s.rolling(w, min_periods=1).std()",
            "    return ma + st*sd, ma, ma - st*sd",
            "",
            f"# Strategy: {self.strategy.name}",
            f"# Family: {family}",
            f"# Params: {params}",
            "def generate_signal(df: pd.DataFrame) -> int:",
            '    close = df["Close"]',
        ]
        if family in ("sma_cross", "ema_cross", "dual_ma_trend", "triple_ma"):
            fast = int(params.get("fast", 10))
            slow = int(params.get("slow", 30))
            fn = "ema" if family == "ema_cross" else "sma"
            lines += [
                f"    fast = {fn}(close, {fast})",
                f"    slow = {fn}(close, {slow})",
                "    sig = np.where(fast > slow, 1, np.where(fast < slow, -1, 0))",
            ]
        elif family == "macd":
            fast = int(params.get("fast", 12))
            slow = int(params.get("slow", 26))
            signal = int(params.get("signal", 9))
            lines += [
                f"    ema_fast = ema(close, {fast})",
                f"    ema_slow = ema(close, {slow})",
                "    macd_line = ema_fast - ema_slow",
                f"    signal_line = ema(macd_line, {signal})",
                "    sig = np.where(macd_line > signal_line, 1, np.where(macd_line < signal_line, -1, 0))",
            ]
        elif family == "rsi_mean_revert":
            period = int(params.get("period", 14))
            ob = params.get("overbought", 70)
            os = params.get("oversold", 30)
            lines += [
                f"    r = rsi(close, {period})",
                f"    sig = np.where(r < {os}, 1, np.where(r > {ob}, -1, 0))",
            ]
        elif family == "bollinger_revert":
            period = int(params.get("period", 20))
            std = float(params.get("std", 2.0))
            lines += [
                f"    upper, _, lower = bbands(close, {period}, {std})",
                "    sig = np.where(close < lower, 1, np.where(close > upper, -1, 0))",
            ]
        elif family in ("breakout", "donchian_breakout", "volume_breakout", "range_break", "atr_breakout"):
            lookback = int(params.get("lookback", 20))
            lines += [
                f"    upper = close.rolling({lookback}, min_periods=1).max().shift(1)",
                f"    lower = close.rolling({lookback}, min_periods=1).min().shift(1)",
                "    sig = np.where(close > upper, 1, np.where(close < lower, -1, 0))",
            ]
        elif family in ("momentum_12_1", "momentum_52_high", "momentum_etf_rotation", "relative_strength", "price_momentum"):
            lookback = int(params.get("lookback", 20))
            lines += [
                f"    mom = close.pct_change({lookback})",
                "    sig = np.where(mom > 0, 1, np.where(mom < 0, -1, 0))",
            ]
        elif family in ("volatility_target", "vol_regime"):
            lookback = int(params.get("lookback", 20))
            target = float(params.get("target_vol", 0.15))
            lines += [
                f"    vol = close.pct_change().rolling({lookback}, min_periods=1).std() * np.sqrt(252)",
                f"    sig = np.where(vol < {target}, 1, -1)",
            ]
        else:
            lines += [
                "    ret = close.pct_change()",
                "    sig = np.where(ret > 0, 1, np.where(ret < 0, -1, 0))",
            ]
        lines += [
            "    s = pd.Series(sig, index=close.index)",
            "    s = s.where(s != 0).ffill().fillna(0).astype(int)",
            "    return int(s.iloc[-1])",
            "",
            'if __name__ == "__main__":',
            '    df = pd.read_csv("data.csv", parse_dates=True, index_col=0)',
            '    print("Signal:", generate_signal(df))',
        ]
        return "\n".join(lines)
