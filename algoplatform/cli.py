import argparse

import uvicorn

from algoplatform.config import settings
from algoplatform.logging_config import setup_logging


def main() -> None:
    parser = argparse.ArgumentParser(prog="algoplatform")
    sub = parser.add_subparsers(dest="cmd")

    runp = sub.add_parser("run", help="Run the dashboard")
    runp.add_argument("--host", default=settings.host)
    runp.add_argument("--port", type=int, default=settings.port)

    backp = sub.add_parser("backtest", help="Run a backtest from CLI")
    backp.add_argument("--strategy", default="sma_cross_equity_long_000")
    backp.add_argument("--symbols", default="SPY,QQQ")
    backp.add_argument("--cash", type=float, default=settings.paper_cash)

    args = parser.parse_args()
    setup_logging("INFO")
    if args.cmd == "run":
        uvicorn.run("algoplatform.api.main:app", host=args.host, port=args.port, log_level="info")
    elif args.cmd == "backtest":
        from algoplatform.backtest.engine import BacktestEngine
        res = BacktestEngine().run(args.strategy, symbols=args.symbols.split(","), initial_cash=args.cash)
        print(res.model_dump_json(indent=2))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
