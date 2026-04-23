# dashboard_operativo/app.py
# Monitor de Gestión de Juzgados (Operativo / Territorial)
# Fuentes: estadisticas_causas.json, pjn_checkpoint.json
# Correr con: streamlit run dashboard_operativo/app.py

import streamlit as st
import pandas as pd
import json
import os
import sys
from datetime import datetime

try:
    import plotly.express as px
    import plotly.graph_objects as go
    PLOTLY_OK = True
except ImportError:
    PLOTLY_OK = False
    px = None
    go = None

# ── Path setup ───────────────────────────────────────────────────────────────
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(ROOT)

from src.utils import calcular_kpi_eficiencia, calcular_tasa_vacancia
from dashboard_operativo.metrics import (
    calcular_latencia_promedio,
    calcular_distribucion_estados,
    calcular_ranking_juzgados,
    detectar_cuellos_de_botella,
)

# ── Configuración de página ───────────────────────────────────────────────────
st.set_page_config(
    page_title="Monitor Operativo — Juzgados Federales",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .badge-critico   { background:#e63946; color:white; border-radius:4px; padding:2px 8px; font-size:11px; }
    .badge-alerta    { background:#f4a261; color:#1a1a1a; border-radius:4px; padding:2px 8px; font-size:11px; }
    .badge-eficiente { background:#2dc653; color:white; border-radius:4px; padding:2px 8px; font-size:11px; }
    .section-header  { border-bottom:1px solid #2d3748; padding-bottom:8px; margin:24px 0 16px; }
</style>
""", unsafe_allow_html=True)


# ── Carga de datos ────────────────────────────────────────────────────────────
@st.cache_data(ttl=1800)
def cargar_estadisticas_causas():
    path = os.path.join(ROOT, "estadisticas_causas.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return pd.DataFrame(data)
    for key in ("data", "causas", "estadisticas", "results"):
        if key in data:
            return pd.DataFrame(data[key])
    return pd.DataFrame(data)


@st.cache_data(ttl=1800)
def cargar_pjn_checkpoint():
    path = os.path.join(ROOT, "pjn_checkpoint.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    # pjn_checkpoint suele tener { "juzgados": [...], "timestamp": "..." }
    if isinstance(data, list):
        return pd.DataFrame(data)
    for key in ("juzgados", "data", "results", "registros"):
        if key in data:
            return pd.DataFrame(data[key])
    return pd.DataFrame(data)


def _col(df: pd.DataFrame, *kws: str):
    """Encuentra primera columna que contenga alguna keyword."""
    for kw in kws:
        m = next((c for c in df.columns if kw.lower() in c.lower()), None)
        if m:
            return m
    return None


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("📊 Monitor Operativo")
    st.caption(f"Actualizado: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    st.markdown("---")

    fuente = st.radio(
        "Fuente de datos",
        ["estadisticas_causas.json", "pjn_checkpoint.json"],
        help="Elegí qué dataset usar como base del análisis"
    )

    st.subheader("🔍 Filtros")

    # Selector de instancia — diferencia Juzgados de Cámaras
    instancia = st.radio(
        "Instancia judicial",
        ["Todas", "Juzgados (1ª Instancia)", "Cámaras Federales"],
        help="Filtrá por nivel de instancia. Consejo y CSJN están en el Dashboard Estratégico."
    )

    latencia_max = st.slider("Latencia máxima (días)", 0, 3650, 3650,
                              help="Filtrar causas con más días de proceso")
    estado_filtro = st.multiselect("Estado de causa", options=[], placeholder="Todos")
    busqueda_juzg  = st.text_input("🔎 Buscar juzgado / cámara...")

    st.markdown("---")
    st.markdown("**Dashboards**")
    st.markdown("🏛️ [Alta Gerencia → corré: `streamlit run dashboard_estrategico/app.py`]")
    st.markdown("📊 **Juzgados** ← estás aquí")

# ── Carga ─────────────────────────────────────────────────────────────────────
try:
    if fuente == "estadisticas_causas.json":
        df = cargar_estadisticas_causas()
        origen = "estadisticas_causas.json"
    else:
        df = cargar_pjn_checkpoint()
        origen = "pjn_checkpoint.json"
    datos_ok = True
except FileNotFoundError as e:
    st.error(f"⚠️ Archivo no encontrado: {e}")
    datos_ok = False
except Exception as e:
    st.error(f"⚠️ Error al cargar datos: {e}")
    datos_ok = False

# ── Header ───────────────────────────────────────────────────────────────────
st.title("📋 Monitor Operativo — Juzgados & Cámaras Federales")
st.caption("Primera Instancia · Instancia de Apelación (Cámaras) · Auditoría de Procesos · Latencia · Cuellos de Botella")
st.info("📌 **Scope:** Juzgados de Primera Instancia + Cámaras Federales. "
        "El Consejo de la Magistratura y la CSJN se analizan en el **Dashboard Estratégico**.")

if not datos_ok:
    st.stop()

# ── Detección de columnas ─────────────────────────────────────────────────────
COL_JUZGADO   = _col(df, "juzgado", "organo", "tribunal", "camara")
COL_JURISD    = _col(df, "jurisdic", "provincia", "lugar")
COL_FUERO     = _col(df, "fuero", "ambito", "materia", "tipo")
COL_ESTADO    = _col(df, "estado", "situac", "activ", "resolucion")
COL_FECHA_INI = _col(df, "inicio", "ingreso", "fecha_ini", "creac", "presentac")
COL_FECHA_FIN = _col(df, "cierre", "resolucion", "fecha_fin", "sentencia")
COL_TRAMITES  = _col(df, "tramit", "actuacion", "movim")
COL_EMBARGOS  = _col(df, "embargo", "cautelar", "medida")
COL_LATENCIA  = _col(df, "latencia", "dias", "tiempo_proceso", "duracion")

# Aplicar filtro de instancia (Juzgados vs Cámaras)
df_filtrado = df.copy()
if instancia != "Todas" and COL_JUZGADO:
    if instancia == "Cámaras Federales":
        mask_inst = df_filtrado[COL_JUZGADO].astype(str).str.contains(
            r"cámara|camara|cam\.", case=False, na=False, regex=True
        )
    else:  # Juzgados (1ª Instancia)
        mask_inst = ~df_filtrado[COL_JUZGADO].astype(str).str.contains(
            r"cámara|camara|cam\.", case=False, na=False, regex=True
        )
    df_filtrado = df_filtrado[mask_inst]

# Aplicar filtro de búsqueda
if busqueda_juzg and COL_JUZGADO:
    df_filtrado = df_filtrado[
        df_filtrado[COL_JUZGADO].astype(str).str.contains(busqueda_juzg, case=False, na=False)
    ]

# Aplicar filtro de latencia
if COL_LATENCIA:
    df_filtrado[COL_LATENCIA] = pd.to_numeric(df_filtrado[COL_LATENCIA], errors="coerce")
    df_filtrado = df_filtrado[df_filtrado[COL_LATENCIA].fillna(0) <= latencia_max]

# ── Desglose rápido por instancia ─────────────────────────────────────────────
st.markdown("### 🏛️ Composición por Instancia")

if COL_JUZGADO:
    mask_cam = df[COL_JUZGADO].astype(str).str.contains(
        r"cámara|camara|cam\.", case=False, na=False, regex=True
    )
    n_camaras   = mask_cam.sum()
    n_juzgados  = (~mask_cam).sum()
    inst_c1, inst_c2, inst_c3 = st.columns(3)
    with inst_c1:
        st.metric("🏢 Juzgados (1ª Instancia)", f"{n_juzgados:,}")
    with inst_c2:
        st.metric("🏛️ Cámaras Federales", f"{n_camaras:,}")
    with inst_c3:
        st.metric("📁 Total registros", f"{len(df):,}")
else:
    st.metric("📁 Total registros", f"{len(df):,}")

st.markdown("---")

# ── KPIs ──────────────────────────────────────────────────────────────────────
st.markdown("### 📊 Indicadores Operativos"
            + (f" — {instancia}" if instancia != 'Todas' else " — Todas las instancias"))

total_registros = len(df_filtrado)
latencia_prom   = calcular_latencia_promedio(df_filtrado, COL_LATENCIA)
n_criticos      = len(detectar_cuellos_de_botella(df_filtrado, COL_LATENCIA, umbral_dias=365))

# Calcular KPI de eficiencia operativa (placeholder — reemplazar con presupuesto scrapeado)
PRESUPUESTO_JUZGADOS = 45_000_000_000  # ARS estimado para primera instancia federal
kpi_op = calcular_kpi_eficiencia(PRESUPUESTO_JUZGADOS, max(total_registros, 1))

k1, k2, k3, k4 = st.columns(4)
with k1:
    st.metric("📁 Registros Totales",    f"{total_registros:,}", help=f"Fuente: {origen}")
with k2:
    color_lat = "normal" if latencia_prom < 180 else "inverse"
    st.metric("⏱️ Latencia Promedio",     f"{latencia_prom:.0f} días",
              delta="Objetivo: < 180 días", delta_color=color_lat)
with k3:
    st.metric("🔴 Causas Críticas (>1 año)", f"{n_criticos:,}",
              delta=f"{n_criticos/max(total_registros,1)*100:.1f}% del total",
              delta_color="inverse")
with k4:
    st.metric("💸 Costo Operativo x Causa", f"${kpi_op:,.0f}",
              help="Presupuesto estimado ÷ registros")

st.markdown("---")

# ── Gráficos ──────────────────────────────────────────────────────────────────
TEMPLATE = dict(
    plot_bgcolor="#0d1b2a", paper_bgcolor="#0d1b2a",
    font=dict(color="#e2e8f0"), xaxis=dict(gridcolor="#2d3748"),
    yaxis=dict(gridcolor="#2d3748"),
)

col_izq, col_der = st.columns([1.2, 1])

# ── Izquierda: distribución por estado de causa ───────────────────────────────
with col_izq:
    st.subheader("Estado de las Causas")
    if COL_ESTADO:
        dist = calcular_distribucion_estados(df_filtrado, COL_ESTADO)
        if not dist.empty:
            if PLOTLY_OK:
                fig_est = px.bar(
                    dist, x="estado", y="cantidad",
                    color="cantidad",
                    color_continuous_scale=["#2dc653", "#f4a261", "#e63946"],
                    title="Distribución por Estado",
                    labels={"estado": "", "cantidad": "Causas"},
                )
                fig_est.update_layout(**TEMPLATE, coloraxis_showscale=False, height=360,
                                      margin=dict(l=10, r=10, t=40, b=10))
                st.plotly_chart(fig_est, use_container_width=True)
            else:
                st.bar_chart(dist.set_index("estado")["cantidad"])
        else:
            st.info("Sin datos de estado disponibles.")
    else:
        st.info("No se detectó columna de estado en los datos.")

# ── Derecha: distribución por fuero ──────────────────────────────────────────
with col_der:
    st.subheader("Causas por Fuero / Materia")
    if COL_FUERO:
        conteo_fuero = df_filtrado[COL_FUERO].value_counts().head(10).reset_index()
        conteo_fuero.columns = ["fuero", "causas"]
        if PLOTLY_OK:
            fig_fuero = px.pie(
                conteo_fuero, names="fuero", values="causas",
                title="Top 10 Fueros",
                color_discrete_sequence=px.colors.qualitative.Vivid,
                hole=0.4,
            )
            fig_fuero.update_layout(**TEMPLATE, height=360,
                                    margin=dict(l=10, r=10, t=40, b=10))
            st.plotly_chart(fig_fuero, use_container_width=True)
        else:
            st.dataframe(conteo_fuero, use_container_width=True)
    else:
        st.info("No se detectó columna de fuero en los datos.")

st.markdown("---")

# ── Ranking de juzgados por carga/latencia ────────────────────────────────────
st.markdown("### 🏆 Ranking de Juzgados por Carga de Expedientes")

if COL_JUZGADO:
    ranking = calcular_ranking_juzgados(df_filtrado, COL_JUZGADO, COL_LATENCIA)
    if not ranking.empty:
        if PLOTLY_OK:
            fig_rank = px.bar(
                ranking.head(20),
                x="cantidad",
                y="juzgado",
                orientation="h",
                color="latencia_prom",
                color_continuous_scale=["#2dc653", "#f4a261", "#e63946"],
                title="Top 20 Juzgados (color = latencia promedio en días)",
                labels={"cantidad": "Causas", "juzgado": "", "latencia_prom": "Latencia (días)"},
            )
            fig_rank.update_layout(
                **TEMPLATE,
                yaxis=dict(autorange="reversed", gridcolor="#2d3748"),
                height=500,
                margin=dict(l=10, r=10, t=50, b=10),
            )
            st.plotly_chart(fig_rank, use_container_width=True)
        else:
            st.dataframe(ranking.head(20), use_container_width=True)
else:
    st.info("No se detectó columna de juzgado. Verificá el schema del JSON.")

st.markdown("---")

# ── Tabla: Cuellos de botella ─────────────────────────────────────────────────
st.markdown("### ⚠️ Alertas — Causas con Latencia Crítica (> 365 días)")

df_cuello = detectar_cuellos_de_botella(df_filtrado, COL_LATENCIA, umbral_dias=365)
if not df_cuello.empty:
    st.caption(f"{len(df_cuello):,} causas superan el umbral de 1 año sin resolución")
    st.dataframe(df_cuello.head(300), use_container_width=True, height=350)
else:
    if COL_LATENCIA:
        st.success("✅ No se detectaron causas con latencia crítica en los filtros actuales.")
    else:
        st.info("No se detectó columna de latencia/días en los datos.")

st.markdown("---")

# ── Tabla completa de datos ───────────────────────────────────────────────────
with st.expander("📄 Ver todos los registros", expanded=False):
    st.caption(f"{len(df_filtrado):,} registros (máx. 1000 mostrados)")
    st.dataframe(df_filtrado.head(1000), use_container_width=True, height=400)

# ── Cruce con Dashboard Estratégico ──────────────────────────────────────────
st.markdown("---")
with st.expander("🔗 Cruce con Dashboard Estratégico (Cascada de Vacancia)", expanded=False):
    st.info("""
    **Cómo usar este cruce:**
    1. En el Dashboard Estratégico detectás qué juzgado tiene una vacante activa.
    2. Buscás ese juzgado en el filtro de arriba (sidebar).
    3. La latencia promedio de ese juzgado refleja el impacto de la subrogancia.

    **KPI de Costo por Sentencia** = Presupuesto Dashboard 1 ÷ Producción Dashboard 2.
    Ese dato ya está calculado en `src/utils.py → calcular_costo_por_sentencia()`.
    """)

# ── Footer ────────────────────────────────────────────────────────────────────
st.caption("Datos: datos.jus.gob.ar · PJN · Consejo de la Magistratura  |  Ph.D. Monteverde")
