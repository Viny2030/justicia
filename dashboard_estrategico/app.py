# dashboard_estrategico/app.py
# Monitor de Alta Gerencia y Administración (Estratégico)
# Fuentes: magistrados.json, vacantes.json, designaciones.json
# Correr con: streamlit run dashboard_estrategico/app.py

import streamlit as st
import pandas as pd
import json
import os
import sys
from datetime import datetime

# ── Path setup ──────────────────────────────────────────────────────────────
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(ROOT)

from src.utils import calcular_kpi_eficiencia, calcular_tasa_vacancia, calcular_costo_por_sentencia
from dashboard_estrategico.components import (
    grafico_vacancia_por_jurisdiccion,
    grafico_designaciones_por_fuero,
    grafico_timeline_concursos,
    tabla_magistrados_activos,
)

# ── Configuración de página ──────────────────────────────────────────────────
st.set_page_config(
    page_title="Monitor Estratégico — CSJN & Consejo",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS personalizado ────────────────────────────────────────────────────────
st.markdown("""
<style>
    .kpi-card { background:#1e2a3a; border-radius:10px; padding:18px 24px;
                border-left:4px solid #e63946; margin-bottom:8px; }
    .kpi-title { color:#adb5bd; font-size:12px; text-transform:uppercase;
                 letter-spacing:1px; margin:0; }
    .kpi-value { color:#ffffff; font-size:28px; font-weight:700; margin:4px 0 0; }
    .kpi-delta { font-size:12px; margin-top:2px; }
    .delta-red   { color:#e63946; }
    .delta-green { color:#2dc653; }
    .section-header { border-bottom:1px solid #2d3748; padding-bottom:8px;
                      margin:24px 0 16px; color:#e2e8f0; }
    [data-testid="stMetricValue"] { font-size:26px !important; }
</style>
""", unsafe_allow_html=True)

# ── Carga de datos ───────────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def cargar_magistrados():
    path = os.path.join(ROOT, "magistrados.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Normalizar si viene como lista o dict con clave 'data'/'magistrados'
    if isinstance(data, list):
        return pd.DataFrame(data)
    for key in ("data", "magistrados", "results"):
        if key in data:
            return pd.DataFrame(data[key])
    return pd.DataFrame(data)

@st.cache_data(ttl=3600)
def cargar_vacantes():
    path = os.path.join(ROOT, "vacantes.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return pd.DataFrame(data)
    for key in ("data", "vacantes", "results"):
        if key in data:
            return pd.DataFrame(data[key])
    return pd.DataFrame(data)

@st.cache_data(ttl=3600)
def cargar_designaciones():
    path = os.path.join(ROOT, "designaciones.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return pd.DataFrame(data)
    for key in ("data", "designaciones", "results"):
        if key in data:
            return pd.DataFrame(data[key])
    return pd.DataFrame(data)

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/1/1a/Flag_of_Argentina.svg/320px-Flag_of_Argentina.svg.png", width=120)
    st.title("⚖️ Monitor Estratégico")
    st.caption(f"Actualizado: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    st.markdown("---")

    st.subheader("🔍 Filtros")
    fuero_sel    = st.multiselect("Fuero / Ámbito", options=[], placeholder="Todos los fueros")
    jurisd_sel   = st.multiselect("Jurisdicción", options=[], placeholder="Todo el país")
    anio_sel     = st.slider("Año de designación", 2000, datetime.now().year,
                              (2015, datetime.now().year))

    st.markdown("---")
    st.markdown("**Dashboards**")
    st.markdown("🏛️ **Alta Gerencia** ← estás aquí")
    st.markdown("📊 [Juzgados → corré: `streamlit run dashboard_operativo/app.py --server.port 8502`]")

# ── Carga principal ──────────────────────────────────────────────────────────
try:
    df_mag   = cargar_magistrados()
    df_vac   = cargar_vacantes()
    df_des   = cargar_designaciones()
    datos_ok = True
except FileNotFoundError as e:
    st.error(f"⚠️ Archivo no encontrado: {e}\n\nAsegurate de correr los scrapers primero.")
    datos_ok = False
except Exception as e:
    st.error(f"⚠️ Error al cargar datos: {e}")
    datos_ok = False

# ── Header principal ─────────────────────────────────────────────────────────
st.title("🏛️ Monitor de Alta Gerencia y Administración Judicial")
st.caption("Corte Suprema · Consejo de la Magistratura · Cámaras Federales")

if not datos_ok:
    st.stop()

# ── Actualizar filtros con datos reales ──────────────────────────────────────
# Detectar columnas de jurisdicción y fuero de forma flexible
COL_JURISD = next((c for c in df_mag.columns if "jurisdic" in c.lower()), None)
COL_FUERO  = next((c for c in df_mag.columns
                    if any(x in c.lower() for x in ("fuero","ambito","organo"))), None)
COL_CARGO  = next((c for c in df_mag.columns if "cargo" in c.lower()), None)
COL_ESTADO = next((c for c in df_mag.columns
                    if any(x in c.lower() for x in ("estado","situac","activ"))), None)

# ── KPIs principales ─────────────────────────────────────────────────────────
st.markdown("<h3 class='section-header'>📊 Indicadores Clave de Gestión</h3>", unsafe_allow_html=True)

# Calcular métricas
total_cargos      = len(df_mag)
total_vacantes    = len(df_vac)
cargos_cubiertos  = total_cargos - total_vacantes
tasa_vacancia     = calcular_tasa_vacancia(cargos_cubiertos, total_cargos)
total_designac    = len(df_des)

# KPI de Costo por Sentencia (datos macro de presupuesto)
PRESUPUESTO_ANUAL = 280_000_000_000  # ARS — fuente: Ley de Presupuesto 2024 (ajustar con scraping TGN)
SENTENCIAS_ANUAL  = 85_000           # estimado — reemplazar con dato real del Dashboard Operativo
costo_sentencia   = calcular_costo_por_sentencia(PRESUPUESTO_ANUAL, SENTENCIAS_ANUAL)

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric(
        label="📋 Total de Magistrados",
        value=f"{total_cargos:,}",
        help="Registros en magistrados.json"
    )
with col2:
    st.metric(
        label="🔴 Vacantes Detectadas",
        value=f"{total_vacantes:,}",
        delta=f"-{tasa_vacancia}% del sistema",
        delta_color="inverse",
        help="Registros en vacantes.json"
    )
with col3:
    st.metric(
        label="✅ Cargos Cubiertos",
        value=f"{cargos_cubiertos:,}",
        help="Total − Vacantes"
    )
with col4:
    st.metric(
        label="📌 Designaciones Registradas",
        value=f"{total_designac:,}",
        help="Registros en designaciones.json"
    )
with col5:
    st.metric(
        label="💰 Costo Macro x Sentencia",
        value=f"${costo_sentencia:,.0f}",
        help=f"Presupuesto ${PRESUPUESTO_ANUAL/1e9:.0f}MM ÷ {SENTENCIAS_ANUAL:,} sentencias estimadas"
    )

st.markdown("---")

# ── Fila de gráficos: Vacancia y Designaciones ───────────────────────────────
st.markdown("<h3 class='section-header'>🏛️ Consejo de la Magistratura — Gestión de Vacancia</h3>",
            unsafe_allow_html=True)

col_izq, col_der = st.columns([1.3, 1])

with col_izq:
    st.subheader("Vacancia por Jurisdicción")
    fig_vac = grafico_vacancia_por_jurisdiccion(df_vac)
    if fig_vac:
        st.plotly_chart(fig_vac, use_container_width=True)
    else:
        # Fallback: tabla simple
        if COL_JURISD and COL_JURISD in df_vac.columns:
            st.dataframe(
                df_vac[COL_JURISD].value_counts().head(15).reset_index()
                .rename(columns={"index": "Jurisdicción", COL_JURISD: "Vacantes"}),
                use_container_width=True
            )
        else:
            st.info("No se detectó columna de jurisdicción en vacantes.json")

with col_der:
    st.subheader("Designaciones por Fuero")
    fig_des = grafico_designaciones_por_fuero(df_des)
    if fig_des:
        st.plotly_chart(fig_des, use_container_width=True)
    else:
        col_fuero_des = next((c for c in df_des.columns
                              if any(x in c.lower() for x in ("fuero","ambito","organo"))), None)
        if col_fuero_des:
            st.dataframe(
                df_des[col_fuero_des].value_counts().head(10).reset_index(),
                use_container_width=True
            )
        else:
            st.info("No se detectó columna de fuero en designaciones.json")

st.markdown("---")

# ── Timeline de concursos ────────────────────────────────────────────────────
st.markdown("<h3 class='section-header'>📅 Timeline de Concursos (Consejo)</h3>",
            unsafe_allow_html=True)
fig_timeline = grafico_timeline_concursos(df_des)
if fig_timeline:
    st.plotly_chart(fig_timeline, use_container_width=True)
else:
    st.info("Columna de fecha no detectada en designaciones.json — verificá el schema.")

st.markdown("---")

# ── Tabla de magistrados ─────────────────────────────────────────────────────
st.markdown("<h3 class='section-header'>👨‍⚖️ Registro de Magistrados</h3>", unsafe_allow_html=True)

# Filtro de búsqueda
busqueda = st.text_input("🔎 Buscar magistrado, juzgado o jurisdicción...")
df_filtrado = df_mag.copy()
if busqueda:
    mask = df_filtrado.apply(
        lambda col: col.astype(str).str.contains(busqueda, case=False, na=False)
    ).any(axis=1)
    df_filtrado = df_filtrado[mask]

st.caption(f"Mostrando {len(df_filtrado):,} de {len(df_mag):,} registros")
st.dataframe(df_filtrado.head(500), use_container_width=True, height=400)

# ── Footer ───────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption("Datos: Consejo de la Magistratura · datos.jus.gob.ar · CSJN  |  Ph.D. Monteverde")
