"""
Tests para dashboard_operativo/metrics.py
Cubre: calcular_latencia_promedio, calcular_distribucion_estados,
       calcular_ranking_juzgados, detectar_cuellos_de_botella,
       calcular_metricas_tramites, tendencia_ingresos_mensual
"""
import sys
import os
import pytest
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dashboard_operativo.metrics import (
    calcular_latencia_promedio,
    calcular_distribucion_estados,
    calcular_ranking_juzgados,
    detectar_cuellos_de_botella,
    calcular_metricas_tramites,
    tendencia_ingresos_mensual,
)


# ═══════════════════════════════════════════════════════════════════
# calcular_latencia_promedio
# ═══════════════════════════════════════════════════════════════════

class TestCalcularLatenciaPromedio:
    def test_promedio_simple(self):
        df = pd.DataFrame({"dias": [100, 200, 300]})
        assert calcular_latencia_promedio(df, "dias") == 200.0

    def test_df_vacio(self):
        assert calcular_latencia_promedio(pd.DataFrame(), "dias") == 0.0

    def test_columna_none(self):
        df = pd.DataFrame({"dias": [100, 200]})
        # Sin columna de latencia y sin columnas de fecha → 0.0
        assert calcular_latencia_promedio(df, None) == 0.0

    def test_columna_inexistente(self):
        df = pd.DataFrame({"otra": [100, 200]})
        assert calcular_latencia_promedio(df, "dias") == 0.0

    def test_valores_nan_ignorados(self):
        df = pd.DataFrame({"dias": [100.0, None, 300.0]})
        assert calcular_latencia_promedio(df, "dias") == 200.0

    def test_strings_convertibles(self):
        df = pd.DataFrame({"dias": ["100", "200", "300"]})
        assert calcular_latencia_promedio(df, "dias") == 200.0

    def test_todos_nan_retorna_cero(self):
        df = pd.DataFrame({"dias": [None, None]})
        assert calcular_latencia_promedio(df, "dias") == 0.0

    def test_calculo_desde_fechas(self):
        df = pd.DataFrame({
            "inicio": ["2022-01-01", "2022-01-01"],
            "cierre": ["2022-04-11", "2022-07-20"],
        })
        result = calcular_latencia_promedio(df, None)
        # 100 días y 200 días → promedio 150
        assert result == pytest.approx(150.0, abs=1)

    def test_redondeo_un_decimal(self):
        df = pd.DataFrame({"dias": [100, 101]})
        assert calcular_latencia_promedio(df, "dias") == 100.5


# ═══════════════════════════════════════════════════════════════════
# calcular_distribucion_estados
# ═══════════════════════════════════════════════════════════════════

class TestCalcularDistribucionEstados:
    def test_columnas_correctas(self):
        df = pd.DataFrame({"estado": ["Activo", "Activo", "Cerrado"]})
        result = calcular_distribucion_estados(df, "estado")
        assert list(result.columns) == ["estado", "cantidad", "porcentaje"]

    def test_conteo_correcto(self):
        df = pd.DataFrame({"estado": ["A", "A", "B"]})
        result = calcular_distribucion_estados(df, "estado")
        fila_a = result[result["estado"] == "A"].iloc[0]
        assert fila_a["cantidad"] == 2

    def test_porcentajes_suman_100(self):
        df = pd.DataFrame({"estado": ["A", "A", "B", "C"]})
        result = calcular_distribucion_estados(df, "estado")
        assert result["porcentaje"].sum() == pytest.approx(100.0, rel=1e-3)

    def test_df_vacio_retorna_estructura_vacia(self):
        result = calcular_distribucion_estados(pd.DataFrame(), "estado")
        assert result.empty
        assert list(result.columns) == ["estado", "cantidad", "porcentaje"]

    def test_columna_inexistente_retorna_vacio(self):
        df = pd.DataFrame({"otra": ["x"]})
        result = calcular_distribucion_estados(df, "estado")
        assert result.empty

    def test_nan_se_rellena_con_sin_dato(self):
        df = pd.DataFrame({"estado": ["Activo", None]})
        result = calcular_distribucion_estados(df, "estado")
        assert "Sin dato" in result["estado"].values


# ═══════════════════════════════════════════════════════════════════
# calcular_ranking_juzgados
# ═══════════════════════════════════════════════════════════════════

class TestCalcularRankingJuzgados:
    def _df(self):
        return pd.DataFrame({
            "juzgado": ["J1", "J1", "J1", "J2", "J2"],
            "latencia": [100, 200, 300, 50, 150],
        })

    def test_columnas_requeridas(self):
        result = calcular_ranking_juzgados(self._df(), "juzgado", "latencia")
        for col in ["juzgado", "cantidad", "latencia_prom", "score_riesgo"]:
            assert col in result.columns

    def test_ordenado_por_cantidad_descendente(self):
        result = calcular_ranking_juzgados(self._df(), "juzgado", "latencia")
        cantidades = result["cantidad"].tolist()
        assert cantidades == sorted(cantidades, reverse=True)

    def test_cantidad_correcta(self):
        result = calcular_ranking_juzgados(self._df(), "juzgado", "latencia")
        assert result[result["juzgado"] == "J1"]["cantidad"].iloc[0] == 3

    def test_score_riesgo_mayor_que_cero(self):
        result = calcular_ranking_juzgados(self._df(), "juzgado", "latencia")
        assert all(result["score_riesgo"] >= 0)

    def test_df_vacio_retorna_vacio(self):
        result = calcular_ranking_juzgados(pd.DataFrame(), "juzgado", "latencia")
        assert result.empty

    def test_col_juzgado_none_retorna_vacio(self):
        result = calcular_ranking_juzgados(self._df(), None, "latencia")
        assert result.empty

    def test_sin_col_latencia(self):
        df = pd.DataFrame({"juzgado": ["J1", "J1", "J2"]})
        result = calcular_ranking_juzgados(df, "juzgado", None)
        assert not result.empty
        assert "latencia_prom" in result.columns


# ═══════════════════════════════════════════════════════════════════
# detectar_cuellos_de_botella
# ═══════════════════════════════════════════════════════════════════

class TestDetectarCuellosDeBottella:
    def _df(self, latencias):
        return pd.DataFrame({"latencia": latencias})

    def test_filtra_por_umbral(self):
        df = self._df([100, 400, 800])
        result = detectar_cuellos_de_botella(df, "latencia", 365)
        assert len(result) == 2
        assert all(result["latencia"] >= 365)

    def test_ninguna_supera_umbral(self):
        df = self._df([100, 200])
        result = detectar_cuellos_de_botella(df, "latencia", 365)
        assert result.empty

    def test_todas_superan_umbral(self):
        df = self._df([400, 500, 600])
        result = detectar_cuellos_de_botella(df, "latencia", 365)
        assert len(result) == 3

    def test_df_vacio(self):
        result = detectar_cuellos_de_botella(pd.DataFrame(), "latencia")
        assert result.empty

    def test_umbral_por_defecto_365(self):
        df = self._df([364, 365, 366])
        result = detectar_cuellos_de_botella(df, "latencia")
        assert len(result) == 2  # 365 y 366

    def test_fallback_desde_fechas(self):
        df = pd.DataFrame({
            "inicio": ["2020-01-01", "2023-01-01"],
            "cierre": ["2022-01-01", "2023-06-01"],  # ~730 días y ~150 días
        })
        result = detectar_cuellos_de_botella(df, col_latencia=None, umbral_dias=365)
        assert len(result) >= 1  # al menos la causa con >365 días

    def test_strings_en_latencia_convertidos(self):
        df = pd.DataFrame({"latencia": ["100", "400", "200"]})
        result = detectar_cuellos_de_botella(df, "latencia", 365)
        assert len(result) == 1


# ═══════════════════════════════════════════════════════════════════
# calcular_metricas_tramites
# ═══════════════════════════════════════════════════════════════════

class TestCalcularMetricasTramites:
    def test_df_vacio(self):
        result = calcular_metricas_tramites(pd.DataFrame())
        assert result == {"total_tramites": 0, "promedio_tramites": 0.0, "total_embargos": 0}

    def test_claves_presentes(self):
        df = pd.DataFrame({"tramit": [10, 20], "embargo": [1, 2]})
        result = calcular_metricas_tramites(df)
        assert "total_tramites" in result
        assert "promedio_tramites" in result
        assert "total_embargos" in result

    def test_suma_tramites_correcta(self):
        df = pd.DataFrame({"tramit": [10, 20, 30]})
        result = calcular_metricas_tramites(df)
        assert result["total_tramites"] == 60

    def test_promedio_tramites_correcto(self):
        df = pd.DataFrame({"tramit": [10, 20, 30]})
        result = calcular_metricas_tramites(df)
        assert result["promedio_tramites"] == 20.0

    def test_total_embargos_correcto(self):
        df = pd.DataFrame({"embargo": [1, 2, 3]})
        result = calcular_metricas_tramites(df)
        assert result["total_embargos"] == 6

    def test_sin_columnas_relevantes(self):
        df = pd.DataFrame({"otra_col": [1, 2]})
        result = calcular_metricas_tramites(df)
        assert result["total_tramites"] == 0
        assert result["total_embargos"] == 0


# ═══════════════════════════════════════════════════════════════════
# tendencia_ingresos_mensual
# ═══════════════════════════════════════════════════════════════════

class TestTendenciaIngresosMensual:
    def test_columnas_correctas(self):
        df = pd.DataFrame({"inicio": ["2023-01-15", "2023-02-10"]})
        result = tendencia_ingresos_mensual(df)
        assert list(result.columns) == ["periodo", "ingresos"]

    def test_agrupa_por_mes(self):
        df = pd.DataFrame({
            "inicio": ["2023-01-01", "2023-01-15", "2023-02-10"]
        })
        result = tendencia_ingresos_mensual(df)
        assert len(result) == 2
        enero = result[result["periodo"].str.contains("2023-01")]
        assert enero["ingresos"].iloc[0] == 2

    def test_df_vacio(self):
        result = tendencia_ingresos_mensual(pd.DataFrame())
        assert result.empty
        assert list(result.columns) == ["periodo", "ingresos"]

    def test_sin_columna_fecha(self):
        df = pd.DataFrame({"otro": [1, 2]})
        result = tendencia_ingresos_mensual(df)
        assert result.empty

    def test_orden_cronologico(self):
        df = pd.DataFrame({
            "inicio": ["2023-03-01", "2023-01-01", "2023-02-01"]
        })
        result = tendencia_ingresos_mensual(df)
        periodos = result["periodo"].tolist()
        assert periodos == sorted(periodos)

    def test_fechas_invalidas_ignoradas(self):
        df = pd.DataFrame({
            "inicio": ["2023-01-01", "no-es-fecha", "2023-01-15"]
        })
        result = tendencia_ingresos_mensual(df)
        assert result["ingresos"].sum() == 2