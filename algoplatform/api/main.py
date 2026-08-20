import logging
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
try:
    import psutil
except ImportError:
    psutil = None  # type: ignore
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from algoplatform.backtest.engine import BacktestEngine
from algoplatform.config import settings
from algoplatform.data.cleaner import DataCleaner
from algoplatform.data.market_data import MarketDataService
from algoplatform.execution.broker import PaperBroker
from algoplatform.execution.portfolio import PortfolioManager
from algoplatform.lab.agent import StrategyLab
from algoplatform.logging_config import setup_logging
from algoplatform.models.common import (
    BacktestResult,
    Experiment,
    OrderStatus,
    Side,
)
from algoplatform.operations.scheduler import OpsScheduler
from algoplatform.reporting.pnl import PnLReporter
from algoplatform.strategies.registry import StrategyRegistry

setup_logging(settings.log_level)
logger = logging.getLogger(__name__)

market_data = MarketDataService()
portfolio = PortfolioManager()
registry = StrategyRegistry()
lab = StrategyLab()
scheduler = OpsScheduler()
engine = BacktestEngine(market_data, registry=registry)

live_jobs: dict[str, Any] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.start()
    scheduler.add_job("market_data_refresh", lambda: market_data.snapshot(), seconds=60)
    scheduler.add_job("portfolio_snapshot", lambda: _update_portfolio(), seconds=60)
    scheduler.add_job("data_cleaner", lambda: market_data.clean_cache(), seconds=3600)
    yield
    scheduler.shutdown()


def _update_portfolio() -> None:
    quotes = market_data.snapshot()
    prices = {q.symbol: q.last for q in quotes}
    portfolio.update_prices(prices)


def _prices() -> dict[str, float]:
    return {q.symbol: q.last for q in market_data.snapshot()}


app = FastAPI(title=settings.project_name, version=settings.version, lifespan=lifespan)
static_dir = Path(__file__).parent.parent.parent / "dashboard"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.get("/api/v1/system")
def system() -> dict:
    if psutil is None:
        return {"cpu_percent": 0.0, "memory": {}, "disk": {}, "uptime_seconds": 0.0, "error": "psutil not installed"}
    try:
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        return {
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "memory": {"percent": mem.percent, "used_gb": mem.used / (1024**3), "total_gb": mem.total / (1024**3)},
            "disk": {"percent": disk.percent, "used_gb": disk.used / (1024**3), "total_gb": disk.total / (1024**3)},
            "uptime_seconds": time.time() - psutil.boot_time(),
        }
    except Exception as e:
        return {"cpu_percent": 0.0, "memory": {}, "disk": {}, "uptime_seconds": 0.0, "error": str(e)}


@app.get("/api/v1/market/snapshot")
def market_snapshot() -> list[dict]:
    return [q.model_dump() for q in market_data.snapshot()]


@app.get("/api/v1/portfolio")
def get_portfolio() -> dict:
    _update_portfolio()
    return portfolio.get_portfolio().model_dump()


@app.get("/api/v1/orders")
def get_orders(limit: int = 50) -> list[dict]:
    return [o.model_dump() for o in portfolio.get_orders(limit)]


@app.post("/api/v1/orders")
def place_order(payload: dict) -> dict:
    symbol = payload.get("symbol", "SPY").upper()
    side_str = payload.get("side", "BUY").upper()
    qty = int(payload.get("qty", 0))
    order_type = payload.get("order_type", "MARKET").upper()
    algo = payload.get("algo", "manual")
    price = payload.get("price")
    prices = _prices()
    market_price = prices.get(symbol)
    if not market_price:
        raise HTTPException(status_code=400, detail=f"no price for {symbol}")
    if qty <= 0:
        raise HTTPException(status_code=400, detail="qty must be positive")
    side = Side.BUY if side_str == "BUY" else Side.SELL
    limit_price = float(price) if price and order_type == "LIMIT" else None
    order = PaperBroker().fill(
        symbol,
        side,
        qty,
        market_price,
        order_type=order_type,
        limit_price=limit_price,
        algo=algo,
    )
    if order.status == OrderStatus.FAILED:
        raise HTTPException(status_code=400, detail="order failed to fill")
    portfolio.apply_fill(order, market_price)
    return order.model_dump()


@app.get("/api/v1/performance")
def get_performance() -> dict:
    hist = portfolio.history
    if not hist:
        return {"equity": [], "metrics": {}}
    from algoplatform.backtest.metrics import compute_metrics
    equity = pd.Series({pd.to_datetime(r["timestamp"]): r["equity"] for r in hist})
    metrics = compute_metrics(equity)
    return {"equity": hist, "metrics": metrics.model_dump()}


@app.post("/api/v1/live/trade")
def live_trade(payload: dict) -> dict:
    strategy_id = payload.get("strategy_id")
    if not strategy_id:
        raise HTTPException(status_code=400, detail="strategy_id required")
    runner = registry.get(strategy_id)
    if not runner:
        raise HTTPException(status_code=404, detail="strategy not found")
    symbols = payload.get("symbols") or settings.default_universe[:5]
    qty = int(payload.get("qty", 10))
    order_type = payload.get("order_type", "MARKET").upper()
    price = payload.get("price")
    price_data: dict[str, pd.DataFrame] = {}
    for sym in symbols:
        df = market_data.get_history(sym, period="60d", interval="1d")
        if not df.empty:
            price_data[sym] = df
    if not price_data:
        raise HTTPException(status_code=400, detail="no market data available for requested symbols")
    signals = runner.generate_signals(price_data)
    if not signals:
        raise HTTPException(status_code=400, detail="no signals generated")
    latest_date = max(signals.keys())
    latest_signals = signals.get(latest_date, {})
    prices = {sym: float(df["Close"].iloc[-1]) for sym, df in price_data.items()}
    broker = PaperBroker()
    placed: list[dict] = []
    skipped: list[str] = []
    for sym, signal in latest_signals.items():
        if signal == 0:
            skipped.append(f"{sym}: flat signal")
            continue
        market_price = prices.get(sym)
        if not market_price:
            skipped.append(f"{sym}: no price")
            continue
        side = Side.BUY if signal > 0 else Side.SELL
        limit_price = float(price) if price and order_type == "LIMIT" else None
        order = broker.fill(
            sym,
            side,
            qty,
            market_price,
            order_type=order_type,
            limit_price=limit_price,
            algo=strategy_id,
        )
        if order.status == OrderStatus.FAILED:
            skipped.append(f"{sym}: order failed")
            continue
        portfolio.apply_fill(order, market_price)
        placed.append(order.model_dump())
    job_id = str(uuid.uuid4())[:8]
    live_jobs[job_id] = {
        "id": job_id,
        "strategy_id": strategy_id,
        "timestamp": datetime.utcnow().isoformat(),
        "status": "completed",
        "signals": latest_signals,
        "placed": placed,
        "skipped": skipped,
    }
    _update_portfolio()
    return {"job_id": job_id, "status": "completed", "placed": placed, "skipped": skipped}


@app.get("/api/v1/live/trade/jobs")
def list_live_trade_jobs(limit: int = Query(20, ge=1, le=100)) -> dict:
    items = sorted(live_jobs.values(), key=lambda j: j["timestamp"], reverse=True)[:limit]
    return {"total": len(live_jobs), "items": items}


@app.get("/api/v1/live/trade/jobs/{job_id}")
def get_live_trade_job(job_id: str) -> dict:
    job = live_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return job


@app.post("/api/v1/live-trades/run")
def live_trades_run_alias(payload: dict) -> dict:
    return live_trade(payload)


@app.get("/api/v1/live-trades")
def live_trades_list_alias(limit: int = Query(20, ge=1, le=100)) -> dict:
    return list_live_trade_jobs(limit)


@app.get("/api/v1/strategies")
def list_strategies(
    category: str | None = None,
    asset_class: str | None = None,
    q: str | None = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> dict:
    items = registry.list_strategies(category=category, asset_class=asset_class, q=q)
    total = len(items)
    page = items[offset : offset + limit]
    return {
        "total": total,
        "items": [s.model_dump() for s in page],
        "categories": registry.categories(),
        "asset_classes": registry.asset_classes(),
    }


@app.get("/api/v1/strategies/categories")
def strategy_categories() -> dict:
    return {"categories": registry.categories(), "asset_classes": registry.asset_classes()}


@app.get("/api/v1/strategies/{strategy_id}")
def get_strategy(strategy_id: str) -> dict:
    s = registry._strategies.get(strategy_id)
    if not s:
        raise HTTPException(status_code=404, detail="strategy not found")
    return s.model_dump()


@app.get("/api/v1/strategies/{strategy_id}/python")
@app.get("/api/v1/strategies/{strategy_id}/code")
def get_strategy_python(strategy_id: str) -> dict:
    runner = registry.get(strategy_id)
    if not runner:
        raise HTTPException(status_code=404, detail="strategy not found")
    try:
        code = runner.to_python()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"code generation failed: {e}")
    return {"strategy_id": strategy_id, "code": code, "python": code}


@app.post("/api/v1/backtests/run", response_model=BacktestResult)
def run_backtest(payload: dict) -> BacktestResult:
    strategy_id = payload.get("strategy_id", "sma_cross_equity_long_0000")
    symbols = payload.get("symbols")
    start = payload.get("start")
    end = payload.get("end")
    cash = payload.get("initial_cash", settings.paper_cash)
    try:
        return engine.run(strategy_id, symbols=symbols, start=start, end=end, initial_cash=cash)
    except Exception as e:
        logger.exception("backtest failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/backtests/{backtest_id}")
def get_backtest(backtest_id: str) -> dict:
    result = engine.get(backtest_id)
    if not result:
        raise HTTPException(
            status_code=404,
            detail="backtest not found (results kept in-memory + on disk for recent runs)",
        )
    return result.model_dump()


@app.get("/api/v1/backtests")
def list_backtests(limit: int = Query(20, ge=1, le=50)) -> dict:
    items = engine.list_recent(limit)
    return {"total": len(items), "items": [r.model_dump() for r in items]}


@app.post("/api/v1/lab/generate", response_model=Experiment)
def lab_generate(payload: dict) -> Experiment:
    return lab.generate(payload.get("prompt", "momentum strategy"), registry=registry)


@app.post("/api/v1/lab/{exp_id}/backtest", response_model=BacktestResult)
def run_lab_backtest(exp_id: str) -> BacktestResult:
    exp = lab.get(exp_id)
    if not exp:
        raise HTTPException(status_code=404, detail="experiment not found")
    if not exp.strategy_id:
        raise HTTPException(status_code=400, detail="experiment has no runnable strategy")
    result = engine.run(
        exp.strategy_id,
        symbols=settings.default_universe[:3],
        initial_cash=settings.paper_cash,
    )
    lab.update_status(exp_id, "passed" if result.status == "completed" else "failed", backtest_id=result.id)
    return result


@app.get("/api/v1/lab/experiments")
def list_experiments() -> list[dict]:
    return [e.model_dump() for e in lab.list()]


@app.get("/api/v1/reporting/pnl")
def reporting_pnl() -> dict:
    reporter = PnLReporter(portfolio)
    return {"daily": reporter.daily_pnl(), "costs": reporter.cost_analysis()}


@app.get("/api/v1/reporting/costs")
def reporting_costs() -> dict:
    return PnLReporter(portfolio).cost_analysis()


@app.get("/api/v1/reporting/attribution")
def reporting_attribution() -> dict:
    return {"attribution": PnLReporter(portfolio).pnl_attribution()}


@app.get("/api/v1/data/status")
def data_status() -> list[dict]:
    return [h.model_dump() for h in market_data.health()]


@app.post("/api/v1/data/clean")
def data_clean(payload: dict | None = None, symbol: str | None = None) -> dict:
    sym = (payload or {}).get("symbol") if isinstance(payload, dict) else None
    sym = sym or symbol or "SPY"
    df = market_data.get_history(sym)
    cleaner = DataCleaner()
    cleaned = cleaner.clean_ohlcv(df, sym)
    try:
        cleaned.to_parquet(market_data._cache_path(sym))
    except Exception:
        pass
    return {"symbol": sym, "rows": len(cleaned), "anomalies": cleaner.detect_anomalies(cleaned, sym)}


@app.get("/api/v1/operations/jobs")
def list_jobs() -> list[dict]:
    return [j.model_dump() for j in scheduler.list_jobs()]


@app.get("/api/v1/operations/jobs/{job_id}/logs")
def get_job_logs(job_id: str, lines: int = Query(20, ge=1, le=200)) -> dict:
    j = scheduler.get(job_id)
    if not j:
        raise HTTPException(status_code=404, detail="job not found")
    return {"job_id": job_id, "lines": j.log_tail[-lines:]}


@app.get("/api/v1/operations/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    j = scheduler.get(job_id)
    if not j:
        raise HTTPException(status_code=404, detail="job not found")
    return j.model_dump()


@app.get("/api/v1/risk")
def risk_metrics() -> dict:
    pf = portfolio.get_portfolio()
    positions = pf.positions
    total = pf.equity
    weights = {p.symbol: (p.market_value / total * 100) if total else 0.0 for p in positions}
    sorted_w = sorted(weights.values(), reverse=True)
    gross = pf.gross_exposure
    net = pf.net_exposure
    cash_pct = (pf.cash / total * 100) if total else 100.0
    concentration = sorted_w[0] if sorted_w else 0.0
    top5 = sum(sorted_w[:5])
    return {
        "gross_exposure_pct": round(gross / total * 100, 2) if total else 0.0,
        "net_exposure_pct": round(net / total * 100, 2) if total else 0.0,
        "long_pct": round(pf.long_value / total * 100, 2) if total else 0.0,
        "cash_pct": round(cash_pct, 2),
        "concentration_top1_pct": round(concentration, 2),
        "concentration_top5_pct": round(top5, 2),
        "margin_used_pct": round(pf.margin_used / total * 100, 2) if total else 0.0,
        "gross_exposure": gross,
        "net_exposure": net,
        "leverage": round(gross / total, 2) if total else 0.0,
        "var_95": 0.0,
        "positions_count": len(positions),
    }


@app.get("/api/v1/market/depth")
def market_depth(symbol: str = "SPY", levels: int = Query(5, ge=1, le=20)) -> dict:
    quotes = {q.symbol: q for q in market_data.snapshot()}
    q = quotes.get(symbol.upper())
    if not q:
        raise HTTPException(status_code=404, detail="symbol not in snapshot")
    mid = (q.bid + q.ask) / 2.0 if q.bid and q.ask else q.last
    spread = max(0.01, abs(q.ask - q.bid)) if q.bid and q.ask else mid * 0.0005
    bids = []
    asks = []
    import random

    rng = random.Random(symbol)
    for i in range(levels):
        size_bid = int(rng.gauss(1000, 300) * (1 + i * 0.2))
        size_ask = int(rng.gauss(1000, 300) * (1 + i * 0.2))
        bids.append({"price": round(mid - spread * (i + 0.5), 2), "size": max(100, size_bid)})
        asks.append({"price": round(mid + spread * (i + 0.5), 2), "size": max(100, size_ask)})
    return {"symbol": symbol.upper(), "mid": round(mid, 2), "bids": bids, "asks": asks, "timestamp": q.timestamp}


@app.get("/api/v1/live/feed")
def live_feed() -> StreamingResponse:
    def event_stream():
        import json
        import time as _time

        while True:
            _update_portfolio()
            snap = portfolio.get_portfolio()
            quotes = [q.model_dump(mode="json") for q in market_data.snapshot()]
            data = json.dumps(
                {
                    "timestamp": datetime.utcnow().isoformat(),
                    "portfolio": snap.model_dump(mode="json"),
                    "quotes": quotes,
                }
            )
            yield f"data: {data}\n\n"
            _time.sleep(5)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    index_file = static_dir / "index.html"
    if index_file.exists():
        return HTMLResponse(content=index_file.read_text())
    return HTMLResponse("<h1>AlgoPlatform</h1><p>Dashboard not built yet.</p>")
