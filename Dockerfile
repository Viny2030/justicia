# Dockerfile — Poder Judicial Dashboard
# Soporta ambos dashboards vía variable de entorno DASHBOARD
#
# Build:   docker build -t justicia-dashboard .
# Correr:  docker run -p 8501:8501 -e DASHBOARD=estrategico justicia-dashboard
#          docker run -p 8501:8501 -e DASHBOARD=operativo   justicia-dashboard

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
# Copiamos requirements primero para aprovechar la caché de capas de Docker
COPY requirements.txt .

# Instalamos solo las dependencias esenciales para los dashboards Streamlit.
# Las pesadas (spaCy, PyMuPDF, etc.) se instalan solo si se necesitan.
RUN pip install --no-cache-dir \
    streamlit \
    pandas \
    plotly \
    numpy \
    requests \
    python-dotenv \
    fastapi \
    uvicorn

# Instalar el resto de requirements (puede fallar en entornos sin GPU — es ok)
RUN pip install --no-cache-dir -r requirements.txt || true

# ── Código fuente ─────────────────────────────────────────────────────────────
COPY . .

# Crear carpetas de datos si no existen
RUN mkdir -p data/raw data/processed

# ── Streamlit config ──────────────────────────────────────────────────────────
RUN mkdir -p /root/.streamlit
RUN cat > /root/.streamlit/config.toml << 'EOF'
[server]
port = 8501
address = "0.0.0.0"
headless = true
enableCORS = false
enableXsrfProtection = false

[browser]
gatherUsageStats = false

[theme]
base = "dark"
primaryColor = "#e63946"
backgroundColor = "#0d1b2a"
secondaryBackgroundColor = "#1e2a3a"
textColor = "#e2e8f0"
font = "sans serif"
EOF

# ── Healthcheck ───────────────────────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# ── Entrypoint ────────────────────────────────────────────────────────────────
EXPOSE 8501

# La variable DASHBOARD decide cuál app lanzar: "estrategico" o "operativo"
ENV DASHBOARD=operativo

CMD ["sh", "-c", "if [ \"$DASHBOARD\" = 'estrategico' ]; then \
    streamlit run dashboard_estrategico/app.py; \
  else \
    streamlit run dashboard_operativo/app.py; \
  fi"]
