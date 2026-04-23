# dashboard_estrategico/components.py
# Componentes visuales reutilizables para el Dashboard Estratégico
# Todos retornan una figura Plotly o None si no hay datos suficientes.

import pandas as pd

try:
    import plotly.express as px
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    PLOTLY_OK = True
except ImportError:
    PLOTLY_OK = False
    px = None
    go = None

# ── Paleta institucional ─────────────────────────────────────────────────────
COLORES = {
    "primario":    "#e63946",
    "secundario":  "#457b9d",
    "terciario":   "#2dc653",
    "advertencia": "#f4a261",
    "fondo":       "#1e2a3a",
    "texto":       "#e2e8f0",
    "grisMedio":   "#4a5568",
}

TEMPLATE_OSCURO = dict(
    plot_bgcolor  = "#0d1b2a",
    paper_bgcolor = "#0d1b2a",
    font          = dict(color=COLORES["texto"], family="Arial"),
    xaxis         = dict(gridcolor="#2d3748", linecolor="#2d3748"),
    yaxis         = dict(gridcolor="#2d3748", linecolor="#2d3748"),
)


def _col_flexible(df: pd.DataFrame, *candidatos: str) -> str | None:
    """Encuentra la primera columna del DataFrame que contenga alguna de las palabras clave."""
    for kw in candidatos:
        match = next((c for c in df.columns if kw.lower() in c.lower()), None)
        if match:
            return match
    return None


# ── 1. Vacancia por Jurisdicción ─────────────────────────────────────────────
def grafico_vacancia_por_jurisdiccion(df_vac: pd.DataFrame, top_n: int = 15):
    """
    Barras horizontales con las jurisdicciones con más vacantes.
    Retorna figura Plotly o None.
    """
    if not PLOTLY_OK or df_vac.empty:
        return None

    col = _col_flexible(df_vac, "jurisdic", "provincia", "lugar", "sede")
    if col is None:
        return None

    conteo = (
        df_vac[col]
        .value_counts()
        .head(top_n)
        .reset_index()
        .rename(columns={"index": "jurisdiccion", col: "vacantes"})
    )
    # compatibilidad pandas ≥ 2.0
    if "jurisdiccion" not in conteo.columns:
        conteo.columns = ["jurisdiccion", "vacantes"]

    fig = px.bar(
        conteo,
        x="vacantes",
        y="jurisdiccion",
        orientation="h",
        color="vacantes",
        color_continuous_scale=["#457b9d", "#e63946"],
        title=f"Top {top_n} Jurisdicciones con Mayor Vacancia",
        labels={"vacantes": "Cargos Vacantes", "jurisdiccion": ""},
    )
    fig.update_layout(
        **TEMPLATE_OSCURO,
        coloraxis_showscale=False,
        yaxis=dict(autorange="reversed", gridcolor="#2d3748"),
        height=420,
        margin=dict(l=10, r=10, t=50, b=10),
    )
    return fig


# ── 2. Designaciones por Fuero (Donut) ───────────────────────────────────────
def grafico_designaciones_por_fuero(df_des: pd.DataFrame, top_n: int = 8):
    """
    Gráfico donut con distribución de designaciones por fuero/ámbito.
    """
    if not PLOTLY_OK or df_des.empty:
        return None

    col = _col_flexible(df_des, "fuero", "ambito", "organo", "tipo_cargo", "camara")
    if col is None:
        return None

    conteo = df_des[col].value_counts().head(top_n)

    fig = go.Figure(go.Pie(
        labels=conteo.index,
        values=conteo.values,
        hole=0.52,
        marker=dict(
            colors=px.colors.qualitative.Vivid[:top_n],
            line=dict(color="#0d1b2a", width=2),
        ),
        textinfo="label+percent",
        textfont_size=11,
    ))
    fig.update_layout(
        **TEMPLATE_OSCURO,
        title="Designaciones por Fuero / Ámbito",
        showlegend=False,
        height=380,
        margin=dict(l=10, r=10, t=50, b=10),
    )
    return fig


# ── 3. Timeline de Concursos ─────────────────────────────────────────────────
def grafico_timeline_concursos(df_des: pd.DataFrame):
    """
    Área apilada de designaciones/concursos a lo largo del tiempo (por año o mes).
    """
    if df_des.empty:
        return None

    col_fecha = _col_flexible(df_des, "fecha", "anio", "año", "date", "periodo")
    if col_fecha is None:
        return None

    try:
        df_des = df_des.copy()
        df_des["_fecha"] = pd.to_datetime(df_des[col_fecha], errors="coerce")
        df_des = df_des.dropna(subset=["_fecha"])
        df_des["_anio"] = df_des["_fecha"].dt.year

        serie = df_des.groupby("_anio").size().reset_index(name="cantidad")
        serie = serie[serie["_anio"].between(2000, 2026)]

        if serie.empty:
            return None

        fig = px.area(
            serie,
            x="_anio",
            y="cantidad",
            title="Evolución Anual de Designaciones / Concursos",
            labels={"_anio": "Año", "cantidad": "Cantidad"},
            color_discrete_sequence=[COLORES["secundario"]],
        )
        fig.update_traces(fill="tozeroy", line_color=COLORES["primario"])
        fig.update_layout(
            **TEMPLATE_OSCURO,
            height=300,
            margin=dict(l=10, r=10, t=50, b=10),
        )
        return fig

    except Exception:
        return None


# ── 4. Tabla de magistrados activos (con color condicional) ──────────────────
def tabla_magistrados_activos(df_mag: pd.DataFrame, max_filas: int = 300):
    """
    Retorna un DataFrame limpio y con columnas relevantes para mostrar en st.dataframe.
    No es una figura Plotly — usarla directamente con st.dataframe().
    """
    if df_mag.empty:
        return df_mag

    cols_prioritarias = [
        _col_flexible(df_mag, "nombre",     "magistrado"),
        _col_flexible(df_mag, "cargo",      "funcion"),
        _col_flexible(df_mag, "jurisdic",   "provincia"),
        _col_flexible(df_mag, "fuero",      "ambito"),
        _col_flexible(df_mag, "estado",     "situac", "activ"),
        _col_flexible(df_mag, "fecha",      "designac", "inicio"),
    ]
    cols_prioritarias = [c for c in cols_prioritarias if c is not None]

    if cols_prioritarias:
        return df_mag[cols_prioritarias].head(max_filas)
    return df_mag.head(max_filas)


# ── 5. Gauge de Vacancia Nacional ────────────────────────────────────────────
def gauge_vacancia(tasa: float, titulo: str = "Índice de Vacancia Nacional"):
    """
    Gauge/velocímetro con la tasa de vacancia. Verde < 15%, Naranja 15-25%, Rojo > 25%.
    """
    if tasa <= 15:
        color = COLORES["terciario"]
    elif tasa <= 25:
        color = COLORES["advertencia"]
    else:
        color = COLORES["primario"]

    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=tasa,
        delta={"reference": 15, "suffix": "%"},
        number={"suffix": "%", "font": {"size": 36, "color": color}},
        title={"text": titulo, "font": {"color": COLORES["texto"]}},
        gauge={
            "axis": {"range": [0, 50], "tickcolor": COLORES["texto"]},
            "bar":  {"color": color},
            "bgcolor": COLORES["fondo"],
            "steps": [
                {"range": [0,  15], "color": "#1a3a2a"},
                {"range": [15, 25], "color": "#3a2a0a"},
                {"range": [25, 50], "color": "#3a1a1a"},
            ],
            "threshold": {
                "line": {"color": "white", "width": 3},
                "thickness": 0.8,
                "value": tasa,
            },
        },
    ))
    fig.update_layout(
        **TEMPLATE_OSCURO,
        height=280,
        margin=dict(l=20, r=20, t=60, b=20),
    )
    return fig


# ── 6. Mapa de calor: Vacancia x Fuero x Jurisdicción ───────────────────────
def heatmap_vacancia_fuero_jurisdiccion(df_vac: pd.DataFrame):
    """
    Heatmap cruzando Fuero (columnas) vs Jurisdicción (filas).
    """
    if df_vac.empty:
        return None

    col_j = _col_flexible(df_vac, "jurisdic", "provincia")
    col_f = _col_flexible(df_vac, "fuero", "ambito", "organo")

    if not col_j or not col_f:
        return None

    pivot = (
        df_vac.groupby([col_j, col_f])
        .size()
        .unstack(fill_value=0)
    )
    pivot = pivot.loc[pivot.sum(axis=1).nlargest(15).index]  # top 15 jurisdicciones
    pivot = pivot[pivot.sum().nlargest(8).index]              # top 8 fueros

    fig = px.imshow(
        pivot,
        color_continuous_scale=["#1e2a3a", "#457b9d", "#e63946"],
        title="Vacancia: Jurisdicción × Fuero",
        labels=dict(x="Fuero", y="Jurisdicción", color="Vacantes"),
        aspect="auto",
    )
    fig.update_layout(
        **TEMPLATE_OSCURO,
        height=420,
        margin=dict(l=10, r=10, t=50, b=10),
    )
    return fig
