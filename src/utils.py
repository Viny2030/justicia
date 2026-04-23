# src/utils.py
# Funciones de KPI compartidas entre ambos dashboards.
# Este módulo es el "puente de inteligencia" entre el nivel estratégico y el operativo.

from __future__ import annotations
import pandas as pd


# ═══════════════════════════════════════════════════════════════════════════════
# KPIs MACRO (Dashboard Estratégico)
# ═══════════════════════════════════════════════════════════════════════════════

def calcular_kpi_eficiencia(presupuesto: float, produccion: float) -> float:
    """
    Costo unitario genérico: presupuesto / producción.
    Usado en ambos dashboards con distintos valores.

    Args:
        presupuesto: Monto asignado en ARS.
        produccion:  Cantidad de sentencias, causas, trámites, etc.

    Returns:
        Costo unitario redondeado a 2 decimales. 0.0 si producción ≤ 0.
    """
    try:
        presupuesto = float(presupuesto)
        produccion  = float(produccion)
        if produccion <= 0:
            return 0.0
        return round(presupuesto / produccion, 2)
    except (ValueError, TypeError):
        return 0.0


def calcular_costo_por_sentencia(presupuesto_total: float, sentencias: float) -> float:
    """
    KPI estrella del Dashboard Estratégico.
    Cruza el presupuesto del Consejo (macro) con la producción de sentencias
    obtenida del Dashboard Operativo.

    Args:
        presupuesto_total: Presupuesto anual del Poder Judicial en ARS.
        sentencias:        Total de sentencias definitivas en el año.

    Returns:
        Costo en ARS por sentencia, o 0.0 si no hay datos.

    Ejemplo:
        calcular_costo_por_sentencia(280_000_000_000, 85_000)
        → 3_294_117.65  (≈ $3.3M ARS por sentencia)
    """
    return calcular_kpi_eficiencia(presupuesto_total, sentencias)


def calcular_tasa_vacancia(jueces_activos: int | float, cargos_totales: int | float) -> float:
    """
    Porcentaje de cargos vacantes sobre el total de cargos previstos.

    Args:
        jueces_activos: Magistrados en actividad.
        cargos_totales: Total de cargos creados por ley.

    Returns:
        Tasa de vacancia en porcentaje (0–100). La CSJN detectó 32.9% en 2024.
    """
    try:
        activos = float(jueces_activos)
        totales = float(cargos_totales)
        if totales <= 0:
            return 0.0
        vacantes = totales - activos
        return round((vacantes / totales) * 100, 2)
    except (ValueError, TypeError):
        return 0.0


def calcular_indice_subrogancia(df_vacantes: pd.DataFrame, df_juzgados: pd.DataFrame,
                                 col_juzgado_vac: str, col_juzgado_op: str,
                                 col_latencia: str) -> pd.DataFrame:
    """
    CRUCE ESTRATÉGICO ↔ OPERATIVO
    Dado un DataFrame de vacantes (Dashboard 1) y uno de juzgados con latencia
    (Dashboard 2), une ambos y retorna los juzgados vacantes con su impacto
    medido como diferencial de latencia vs. el promedio nacional.

    Args:
        df_vacantes:    DataFrame de vacantes (del scraper del Consejo).
        df_juzgados:    DataFrame operativo con latencia por juzgado.
        col_juzgado_vac: Nombre de columna identificadora en df_vacantes.
        col_juzgado_op:  Nombre de columna identificadora en df_juzgados.
        col_latencia:    Nombre de columna de días de latencia en df_juzgados.

    Returns:
        DataFrame con columnas: juzgado, vacante (bool), latencia_prom,
        latencia_nacional, delta_latencia, impacto.
    """
    if df_vacantes.empty or df_juzgados.empty:
        return pd.DataFrame()

    lat_col = pd.to_numeric(df_juzgados[col_latencia], errors="coerce")
    lat_nacional = round(float(lat_col.mean()), 1)

    lat_por_juzgado = (
        df_juzgados.groupby(col_juzgado_op)[col_latencia]
        .apply(lambda s: pd.to_numeric(s, errors="coerce").mean())
        .reset_index()
        .rename(columns={col_juzgado_op: "juzgado", col_latencia: "latencia_prom"})
    )

    vacantes_set = set(df_vacantes[col_juzgado_vac].astype(str).unique())

    lat_por_juzgado["vacante"]          = lat_por_juzgado["juzgado"].astype(str).isin(vacantes_set)
    lat_por_juzgado["latencia_nacional"] = lat_nacional
    lat_por_juzgado["delta_latencia"]   = (
        lat_por_juzgado["latencia_prom"] - lat_nacional
    ).round(1)
    lat_por_juzgado["impacto"] = lat_por_juzgado["delta_latencia"].apply(
        lambda d: "🔴 Crítico" if d > 90 else ("🟡 Alerta" if d > 30 else "🟢 Normal")
    )

    return lat_por_juzgado.sort_values("delta_latencia", ascending=False).reset_index(drop=True)


# ═══════════════════════════════════════════════════════════════════════════════
# KPIs OPERATIVOS (Dashboard Operativo)
# ═══════════════════════════════════════════════════════════════════════════════

def calcular_score_riesgo_juzgado(cantidad_causas: int, latencia_prom: float) -> float:
    """
    Score compuesto de riesgo operativo por juzgado.
    Combina volumen y demora para identificar los más urgentes de intervenir.

    Formula: causas × log₂(latencia + 1)
    (Logarítmica para no penalizar desproporcionadamente latencias extremas.)

    Returns:
        Score de riesgo. Mayor = más urgente.
    """
    import math
    try:
        return round(float(cantidad_causas) * math.log2(float(latencia_prom) + 1), 2)
    except (ValueError, TypeError, ZeroDivisionError):
        return 0.0


def porcentaje_causas_criticas(df: pd.DataFrame, col_latencia: str,
                                umbral_dias: int = 365) -> float:
    """
    Porcentaje de causas que superan el umbral de latencia.
    KPI clave del Dashboard Operativo: mide la "cola crítica".
    """
    if df.empty or col_latencia not in df.columns:
        return 0.0
    serie = pd.to_numeric(df[col_latencia], errors="coerce").dropna()
    if serie.empty:
        return 0.0
    criticas = (serie >= umbral_dias).sum()
    return round(float(criticas) / len(serie) * 100, 2)


# ═══════════════════════════════════════════════════════════════════════════════
# UTILIDADES DE FORMATO
# ═══════════════════════════════════════════════════════════════════════════════

def formatear_ars(valor: float) -> str:
    """Formatea un valor numérico como moneda ARS legible."""
    if valor >= 1_000_000_000:
        return f"${valor/1_000_000_000:.2f}MM"
    if valor >= 1_000_000:
        return f"${valor/1_000_000:.1f}M"
    return f"${valor:,.0f}"


def semaforo(valor: float, verde_max: float, amarillo_max: float) -> str:
    """Retorna emoji de semáforo según umbrales."""
    if valor <= verde_max:
        return "🟢"
    if valor <= amarillo_max:
        return "🟡"
    return "🔴"
