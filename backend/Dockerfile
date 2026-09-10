# Build from the repository root:
#   docker build -f backend/Dockerfile -t shimo-backend .
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc curl \
    && rm -rf /var/lib/apt/lists/*

# Dependencies first for better layer caching
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Application code + the `shimo` CLI entry point (editable so bind mounts stay live)
COPY pyproject.toml README.md ./
COPY backend ./backend
RUN pip install --no-cache-dir --no-deps -e . \
    && mkdir -p /app/data

ENV DATABASE_URL=sqlite:////app/data/shimo.db

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/api/health || exit 1

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
