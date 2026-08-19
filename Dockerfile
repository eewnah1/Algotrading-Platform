FROM python:3.12-slim

WORKDIR /app

# System deps for scientific stack + healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app
RUN pip install -e . --no-deps || true

# Persist cache + backtest results
RUN mkdir -p /app/data/cache /app/data/backtests

ENV ALGOPLATFORM_DATA_DIR=/app/data
ENV ALGOPLATFORM_LOG_LEVEL=INFO
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["python", "-m", "uvicorn", "algoplatform.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
