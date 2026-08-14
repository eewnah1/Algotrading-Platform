# AlgoPlatform

An institutional-grade, open-source algorithmic trading platform built to rival commercial execution and research suites. It covers live execution, realistic backtesting, AI-assisted strategy research, reporting, data cleaning, and production operations.

## Live Dashboard

**Public no-auth dashboard:** https://seven-women-float.loca.lt

> Dashboard: live execution with market depth, order entry, risk telemetry, backtesting, 1000+ strategy library with filters, AI strategy lab, reporting, data cleaning, operations, and system health.

## All Dashboards Workspace

Clone and monitor every `eewnah1` dashboard repo in one place:

```bash
cd workspace
./clone_all.sh
code dashboards.code-workspace
```

Open the Colab notebook for live health checks:

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/eewnah1/Algotrading-Platform/blob/main/workspace/notebooks/dashboards_colab.ipynb)

## Modules

- **Live Execution** — portfolio monitoring, order blotter, positions, PnL, and risk metrics in real time.
- **Backtesting** — event-driven engine with transaction costs, slippage, and per-strategy analytics.
- **AI Strategy Lab** — generate hypotheses, code skeletons, and experiment ledgers.
- **Reporting** — daily PnL, cost attribution, and drift analysis.
- **Data Cleaning** — anomaly detection and repair for OHLCV data.
- **Operations** — scheduled job scheduler with live logs.
- **1000 Strategy Catalog** — diverse technical, statistical, machine-learning, options, macro, factor, and volume strategies.

## Quick Start

```bash
pip install -r requirements.txt
python -m uvicorn algoplatform.api.main:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000`.

## Architecture

- `algoplatform/api/main.py` — FastAPI app and static dashboard.
- `algoplatform/data/` — market data fetcher and data cleaner.
- `algoplatform/execution/` — paper broker and portfolio manager.
- `algoplatform/backtest/` — event-driven backtester and metrics.
- `algoplatform/strategies/` — 1000-strategy registry and signal runner.
- `algoplatform/lab/` — AI strategy lab.
- `algoplatform/reporting/` — PnL and cost reporting.
- `algoplatform/operations/` — scheduler and job monitor.

## License

Apache-2.0
