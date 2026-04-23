# dashboard_operativo/metrics.py
# Cálculos de métricas operativas de juzgados
# Funciones puras: reciben DataFrames y devuelven DataFrames o escalares.

import pandas as pd
import numpy as np


# ── 1. Latencia promedio ───────────────────────────────────────────────────────
def calcular_latencia_promedio(df: pd.DataFrame, col_latencia: str | None) -> float:
    """
    Retorna la latencia promedio en días. Si no hay columna de latencia,
    intenta calcularla desde columnas de fecha de inicio y fin.

    Returns 0.0 si no hay datos suficientes.
    """
    if df.empty:
        return 0.0

    if col_latencia and col_latencia in df.columns:
        serie = pd.to_numeric(df[col_latencia], errors="coerce").dropna()
        return round(float(serie.mean()), 1) if not serie.empty else 0.0

    # Intento alternativo: calcular desde fechas
    col_ini = _col(df, "inicio", "ingreso", "fecha_ini", "creac")
    col_fin = _col(df, "cierre", "resolucion", "fecha_fin", "sentencia")

    if col_ini and col_fin:
        try:
            ini = pd.to_datetime(df[col_ini], errors="coerce")
            fin = pd.to_datetime(df[col_fin], errors="coerce")
            delta = (fin - ini).dt.days
            delta = delta[delta > 0].dropna()
            return round(float(delta.mean()), 1) if not delta.empty else 0.0
        except Exception:
            pass

    return 0.0


# ── 2. Distribución de estados ────────────────────────────────────────────────
def calcular_distribucion_estados(df: pd.DataFrame, col_estado: str) -> pd.DataFrame:
    """
    Cuenta causas por estado/situación procesal.
    Retorna DataFrame con columnas ['estado', 'cantidad', 'porcentaje'].
    """
    if df.empty or col_estado not in df.columns:
        return pd.DataFrame(columns=["estado", "cantidad", "porcentaje"])

    conteo = (
        df[col_estado]
        .fillna("Sin dato")
        .value_counts()
        .reset_index()
    )
    conteo.columns = ["estado", "cantidad"]
    total = conteo["cantidad"].sum()
    conteo["porcentaje"] = (conteo["cantidad"] / total * 100).round(1)
    return conteo


# ── 3. Ranking de juzgados ────────────────────────────────────────────────────
def calcular_ranking_juzgados(
    df: pd.DataFrame,
    col_juzgado: str | None,
    col_latencia: str | None,
) -> pd.DataFrame:
    """
    Ordena juzgados por cantidad de causas y latencia promedio.
    Retorna DataFrame con columnas ['juzgado', 'cantidad', 'latencia_prom', 'score_riesgo'].

    score_riesgo = causas * log(latencia + 1) — indica juzgados con alta carga Y alta latencia.
    """
    if df.empty or not col_juzgado or col_juzgado not in df.columns:
        return pd.DataFrame()

    agg: dict = {"cantidad": (col_juzgado, "count")}

    if col_latencia and col_latencia in df.columns:
        df = df.copy()
        df[col_latencia] = pd.to_numeric(df[col_latencia], errors="coerce")
        agg["latencia_prom"] = (col_latencia, "mean")
    else:
        df = df.copy()
        df["_lat_dummy"] = 0
        agg["latencia_prom"] = ("_lat_dummy", "mean")

    ranking = (
        df.groupby(col_juzgado)
        .agg(**agg)
        .reset_index()
        .rename(columns={col_juzgado: "juzgado"})
    )
    ranking["latencia_prom"] = ranking["latencia_prom"].fillna(0).round(0)
    ranking["score_riesgo"]  = (
        ranking["cantidad"] * np.log1p(ranking["latencia_prom"])
    ).round(1)

    return ranking.sort_values("cantidad", ascending=False).reset_index(drop=True)


# ── 4. Detección de cuellos de botella ────────────────────────────────────────
def detectar_cuellos_de_botella(
    df: pd.DataFrame,
    col_latencia: str | None,
    umbral_dias: int = 365,
) -> pd.DataFrame:
    """
    Retorna las causas cuya latencia supera el umbral (default: 1 año).
    Si no hay columna de latencia, intenta calcularla desde fechas.
    """
    if df.empty:
        return pd.DataFrame()

    df_work = df.copy()

    if col_latencia and col_latencia in df_work.columns:
        df_work[col_latencia] = pd.to_numeric(df_work[col_latencia], errors="coerce")
        return df_work[df_work[col_latencia] >= umbral_dias].copy()

    # Fallback: calcular desde fechas
    col_ini = _col(df_work, "inicio", "ingreso", "fecha_ini", "creac")
    col_fin = _col(df_work, "cierre", "resolucion", "fecha_fin", "sentencia")

    if col_ini:
        try:
            ini = pd.to_datetime(df_work[col_ini], errors="coerce")
            ref = pd.to_datetime(
                df_work[col_fin], errors="coerce"
            ).fillna(pd.Timestamp.now()) if col_fin else pd.Timestamp.now()

            df_work["_dias_calc"] = (ref - ini).dt.days
            return df_work[df_work["_dias_calc"] >= umbral_dias].copy()
        except Exception:
            pass

    return pd.DataFrame()


# ── 5. Análisis de trámites y embargos ────────────────────────────────────────
def calcular_metricas_tramites(df: pd.DataFrame) -> dict:
    """
    Calcula métricas relacionadas con trámites y embargos/cautelares.
    Retorna un dict con claves: total_tramites, promedio_tramites, total_embargos.
    """
    resultado = {"total_tramites": 0, "promedio_tramites": 0.0, "total_embargos": 0}

    if df.empty:
        return resultado

    col_tram = _col(df, "tramit", "actuacion", "movim")
    if col_tram:
        serie_t = pd.to_numeric(df[col_tram], errors="coerce").fillna(0)
        resultado["total_tramites"]   = int(serie_t.sum())
        resultado["promedio_tramites"] = round(float(serie_t.mean()), 1)

    col_emb = _col(df, "embargo", "cautelar", "medida")
    if col_emb:
        serie_e = pd.to_numeric(df[col_emb], errors="coerce").fillna(0)
        resultado["total_embargos"] = int(serie_e.sum())

    return resultado


# ── 6. Tendencia mensual de ingresos ──────────────────────────────────────────
def tendencia_ingresos_mensual(df: pd.DataFrame) -> pd.DataFrame:
    """
    Agrupa causas por mes de ingreso/inicio.
    Retorna DataFrame con columnas ['periodo', 'ingresos'].
    """
    if df.empty:
        return pd.DataFrame(columns=["periodo", "ingresos"])

    col_ini = _col(df, "inicio", "ingreso", "fecha_ini", "creac", "presentac")
    if not col_ini:
        return pd.DataFrame(columns=["periodo", "ingresos"])

    try:
        df_work = df.copy()
        df_work["_fecha"] = pd.to_datetime(df_work[col_ini], errors="coerce")
        df_work = df_work.dropna(subset=["_fecha"])
        df_work["periodo"] = df_work["_fecha"].dt.to_period("M").astype(str)

        return (
            df_work.groupby("periodo")
            .size()
            .reset_index(name="ingresos")
            .sort_values("periodo")
        )
    except Exception:
        return pd.DataFrame(columns=["periodo", "ingresos"])


# ── Utilidad interna ──────────────────────────────────────────────────────────
def _col(df: pd.DataFrame, *kws: str) -> str | None:
    """Encuentra primera columna que contenga alguna de las keywords."""
    for kw in kws:
        m = next((c for c in df.columns if kw.lower() in c.lower()), None)
        if m:
            return m
    return None
