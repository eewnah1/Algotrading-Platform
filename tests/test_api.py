from fastapi.testclient import TestClient

from algoplatform.api.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_strategies_list():
    r = client.get("/api/v1/strategies?limit=10")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 300
    assert len(data["items"]) == 10


def test_backtest():
    payload = {"strategy_id": "sma_cross_equity_long_000", "symbols": ["SPY"], "initial_cash": 100000}
    r = client.post("/api/v1/backtests/run", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "completed"
    assert data["metrics"]["total_return"] is not None
