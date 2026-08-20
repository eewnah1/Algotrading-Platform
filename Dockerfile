FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY algoplatform ./algoplatform
COPY dashboard ./dashboard

RUN pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["python3", "-m", "uvicorn", "algoplatform.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
