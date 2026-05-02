# Dockerfile — Poder Judicial Dashboard
# FastAPI + Uvicorn — Railway ready
#
# Build:   docker build -t justicia-dashboard .
# Correr:  docker run -p 8000:8000 justicia-dashboard

FROM python:3.11-slim

# ── Sistema ───────────────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        git \
    && rm -rf /var/lib/apt/lists/*

# ── Working directory ─────────────────────────────────────────────────────────
WORKDIR /app

# ── Dependencias Python ───────────────────────────────────────────────────────
COPY requirements.txt .

RUN pip install --no-cache-dir \
    fastapi \
    "uvicorn[standard]" \
    pandas \
    plotly \
    numpy \
    requests \
    python-dotenv

RUN pip install --no-cache-dir -r requirements.txt || true

# ── Código fuente ─────────────────────────────────────────────────────────────
COPY . .

# Crear carpetas de datos si no existen
RUN mkdir -p data/raw data/processed

# ── Healthcheck ───────────────────────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/ || exit 1

# ── Entrypoint ────────────────────────────────────────────────────────────────
EXPOSE 8000

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
