from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ALGOPLATFORM_")

    project_name: str = "AlgoPlatform"
    version: str = "0.1.0"
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"
    data_dir: Path = Path("data")
    timezone: str = "UTC"
    market_data_provider: str = "yfinance"
    default_benchmark: str = "SPY"
    default_universe: list[str] = ["SPY", "QQQ", "IWM", "AAPL", "MSFT", "AMZN", "TSLA", "NVDA", "GLD", "TLT"]
    paper_cash: float = 1_000_000.0
    commission_bps: float = 1.0
    slippage_bps: float = 2.0
    borrow_cost_bps: float = 50.0


settings = Settings()
