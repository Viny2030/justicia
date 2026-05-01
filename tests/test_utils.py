"""
Tests para src/utils.py
Cubre: calcular_kpi_eficiencia, calcular_costo_por_sentencia,
       calcular_tasa_vacancia, calcular_indice_subrogancia,
       calcular_score_riesgo_juzgado, porcentaje_causas_criticas,
       formatear_ars, semaforo
"""
import math
import sys
import os
import pytest
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.utils import (
    calcular_kpi_eficiencia,
    calcular_costo_por_sentencia,
    calcular_tasa_vacancia,
    calcular_indice_subrogancia,
    calcular_score_riesgo_juzgado,
    porcentaje_causas_criticas,
    formatear_ars,
    semaforo,
)


# ═══════════════════════════════════════════════════════════════════
# calcular_kpi_eficiencia
# ═══════════════════════════════════════════════════════════════════

class TestCalcularKpiEficiencia:
    def test_caso_normal(self):
        assert calcular_kpi_eficiencia(1_000_000, 500) == 2_000.0

    def test_redondeo_dos_decimales(self):
        resultado = calcular_kpi_eficiencia(100, 3)
        assert resultado == 33.33

    def test_produccion_cero_retorna_cero(self):
        assert calcular_kpi_eficiencia(500_000, 0) == 0.0

    def test_produccion_negativa_retorna_cero(self):
        assert calcular_kpi_eficiencia(500_000, -10) == 0.0

    def test_presupuesto_cero_retorna_cero(self):
        assert calcular_kpi_eficiencia(0, 100) == 0.0

    def test_valores_string_numericos(self):
        assert calcular_kpi_eficiencia("200", "4") == 50.0

    def test_valor_no_numerico_retorna_cero(self):
        assert calcular_kpi_eficiencia("abc", 10) == 0.0

    def test_none_retorna_cero(self):
        assert calcular_kpi_eficiencia(None, 10) == 0.0

    def test_resultado_grande(self):
        result = calcular_kpi_eficiencia(280_000_000_000, 85_000)
        assert result == round(280_000_000_000 / 85_000, 2)


# ═══════════════════════════════════════════════════════════════════
# calcular_costo_por_sentencia
# ═══════════════════════════════════════════════════════════════════

class TestCalcularCostoPorSentencia:
    def test_ejemplo_docstring(self):
        resultado = calcular_costo_por_sentencia(280_000_000_000, 85_000)
        assert resultado == pytest.approx(3_294_117.65, rel=1e-3)

    def test_sin_sentencias_retorna_cero(self):
        assert calcular_costo_por_sentencia(1_000_000, 0) == 0.0

    def test_delega_en_kpi_eficiencia(self):
        """Debe comportarse igual que calcular_kpi_eficiencia."""
        assert calcular_costo_por_sentencia(500, 5) == calcular_kpi_eficiencia(500, 5)


# ═══════════════════════════════════════════════════════════════════
# calcular_tasa_vacancia
# ═══════════════════════════════════════════════════════════════════

class TestCalcularTasaVacancia:
    def test_caso_tipico(self):
        # 540 vacantes sobre 1643 cargos ≈ 32.87%
        result = calcular_tasa_vacancia(1103, 1643)
        assert result == pytest.approx(32.87, rel=1e-2)

    def test_sin_vacantes(self):
        assert calcular_tasa_vacancia(100, 100) == 0.0

    def test_todos_vacantes(self):
        assert calcular_tasa_vacancia(0, 200) == 100.0

    def test_cargos_totales_cero_retorna_cero(self):
        assert calcular_tasa_vacancia(50, 0) == 0.0

    def test_mas_activos_que_totales_retorna_negativo_o_ok(self):
        # No debe lanzar excepción; el resultado puede ser negativo
        result = calcular_tasa_vacancia(120, 100)
        assert isinstance(result, float)

    def test_strings_numericos(self):
        assert calcular_tasa_vacancia("80", "100") == 20.0

    def test_valor_invalido_retorna_cero(self):
        assert calcular_tasa_vacancia("x", 100) == 0.0

    def test_resultado_redondeado_dos_decimales(self):
        result = calcular_tasa_vacancia(1, 3)
        assert result == round((2 / 3) * 100, 2)


# ═══════════════════════════════════════════════════════════════════
# calcular_indice_subrogancia
# ═══════════════════════════════════════════════════════════════════

class TestCalcularIndiceSubrogancia:
    def _df_vacantes(self, nombres):
        return pd.DataFrame({"juzgado": nombres})

    def _df_juzgados(self, data):
        return pd.DataFrame(data, columns=["juzgado", "latencia"])

    def test_retorna_dataframe_vacio_si_vacantes_vacio(self):
        df_j = self._df_juzgados([("J1", 300), ("J2", 100)])
        resultado = calcular_indice_subrogancia(
            pd.DataFrame(), df_j, "juzgado", "juzgado", "latencia"
        )
        assert resultado.empty

    def test_retorna_dataframe_vacio_si_juzgados_vacio(self):
        df_v = self._df_vacantes(["J1"])
        resultado = calcular_indice_subrogancia(
            df_v, pd.DataFrame(), "juzgado", "juzgado", "latencia"
        )
        assert resultado.empty

    def test_columnas_requeridas_presentes(self):
        df_v = self._df_vacantes(["J1"])
        df_j = self._df_juzgados([("J1", 400), ("J2", 200)])
        resultado = calcular_indice_subrogancia(df_v, df_j, "juzgado", "juzgado", "latencia")
        for col in ["juzgado", "vacante", "latencia_prom", "latencia_nacional", "delta_latencia", "impacto"]:
            assert col in resultado.columns

    def test_juzgado_vacante_marcado_correctamente(self):
        df_v = self._df_vacantes(["J1"])
        df_j = self._df_juzgados([("J1", 500), ("J2", 100)])
        resultado = calcular_indice_subrogancia(df_v, df_j, "juzgado", "juzgado", "latencia")
        fila_j1 = resultado[resultado["juzgado"] == "J1"].iloc[0]
        assert fila_j1["vacante"] == True

    def test_juzgado_no_vacante_marcado_correctamente(self):
        df_v = self._df_vacantes(["J1"])
        df_j = self._df_juzgados([("J1", 500), ("J2", 100)])
        resultado = calcular_indice_subrogancia(df_v, df_j, "juzgado", "juzgado", "latencia")
        fila_j2 = resultado[resultado["juzgado"] == "J2"].iloc[0]
        assert fila_j2["vacante"] == False

    def test_impacto_critico(self):
        df_v = self._df_vacantes(["J1"])
        # J1 con latencia muy alta → delta > 90
        rows = [("J1", 800)] + [("J2", 100)] * 9
        df_j = pd.DataFrame(rows, columns=["juzgado", "latencia"])
        resultado = calcular_indice_subrogancia(df_v, df_j, "juzgado", "juzgado", "latencia")
        fila_j1 = resultado[resultado["juzgado"] == "J1"].iloc[0]
        assert "Crítico" in fila_j1["impacto"]

    def test_impacto_normal(self):
        df_v = self._df_vacantes(["J99"])  # vacante no existe en juzgados
        df_j = self._df_juzgados([("J1", 200), ("J2", 210)])
        resultado = calcular_indice_subrogancia(df_v, df_j, "juzgado", "juzgado", "latencia")
        # Todos deberían tener delta bajo → Normal
        assert all("Normal" in imp for imp in resultado["impacto"])

    def test_ordenado_por_delta_descendente(self):
        df_v = self._df_vacantes(["J1"])
        df_j = self._df_juzgados([("J1", 100), ("J2", 900), ("J3", 50)])
        resultado = calcular_indice_subrogancia(df_v, df_j, "juzgado", "juzgado", "latencia")
        deltas = resultado["delta_latencia"].tolist()
        assert deltas == sorted(deltas, reverse=True)


# ═══════════════════════════════════════════════════════════════════
# calcular_score_riesgo_juzgado
# ═══════════════════════════════════════════════════════════════════

class TestCalcularScoreRiesgoJuzgado:
    def test_formula_correcta(self):
        causas, latencia = 100, 63
        esperado = round(100 * math.log2(64), 2)
        assert calcular_score_riesgo_juzgado(causas, latencia) == esperado

    def test_latencia_cero(self):
        # log2(0+1) = 0
        assert calcular_score_riesgo_juzgado(100, 0) == 0.0

    def test_causas_cero(self):
        assert calcular_score_riesgo_juzgado(0, 500) == 0.0

    def test_valores_invalidos_retornan_cero(self):
        assert calcular_score_riesgo_juzgado("x", 10) == 0.0
        assert calcular_score_riesgo_juzgado(10, None) == 0.0

    def test_mayor_carga_mayor_score(self):
        score_bajo = calcular_score_riesgo_juzgado(50, 100)
        score_alto = calcular_score_riesgo_juzgado(200, 100)
        assert score_alto > score_bajo

    def test_mayor_latencia_mayor_score(self):
        score_bajo = calcular_score_riesgo_juzgado(100, 10)
        score_alto = calcular_score_riesgo_juzgado(100, 1000)
        assert score_alto > score_bajo


# ═══════════════════════════════════════════════════════════════════
# porcentaje_causas_criticas
# ═══════════════════════════════════════════════════════════════════

class TestPorcentajeCausasCriticas:
    def _df(self, latencias):
        return pd.DataFrame({"latencia": latencias})

    def test_todas_criticas(self):
        df = self._df([400, 500, 600])
        assert porcentaje_causas_criticas(df, "latencia", 365) == 100.0

    def test_ninguna_critica(self):
        df = self._df([100, 200, 300])
        assert porcentaje_causas_criticas(df, "latencia", 365) == 0.0

    def test_mitad_critica(self):
        df = self._df([100, 200, 400, 500])
        assert porcentaje_causas_criticas(df, "latencia", 365) == 50.0

    def test_df_vacio(self):
        assert porcentaje_causas_criticas(pd.DataFrame(), "latencia") == 0.0

    def test_columna_inexistente(self):
        df = self._df([400, 500])
        assert porcentaje_causas_criticas(df, "col_inexistente") == 0.0

    def test_umbral_personalizado(self):
        df = self._df([100, 200, 300])
        assert porcentaje_causas_criticas(df, "latencia", umbral_dias=150) == pytest.approx(66.67, rel=1e-2)

    def test_exactamente_en_umbral_cuenta_como_critica(self):
        df = self._df([365])
        assert porcentaje_causas_criticas(df, "latencia", 365) == 100.0

    def test_valores_nan_ignorados(self):
        df = pd.DataFrame({"latencia": [400, None, 500]})
        # 2 de 2 válidos son críticos
        assert porcentaje_causas_criticas(df, "latencia", 365) == 100.0

    def test_strings_numericos_en_columna(self):
        df = pd.DataFrame({"latencia": ["400", "100", "500"]})
        result = porcentaje_causas_criticas(df, "latencia", 365)
        assert result == pytest.approx(66.67, rel=1e-2)


# ═══════════════════════════════════════════════════════════════════
# formatear_ars
# ═══════════════════════════════════════════════════════════════════

class TestFormatearArs:
    def test_millones(self):
        assert formatear_ars(5_000_000) == "$5.0M"

    def test_miles_de_millones(self):
        assert formatear_ars(2_000_000_000) == "$2.00MM"

    def test_valor_menor_al_millon(self):
        resultado = formatear_ars(50_000)
        assert resultado.startswith("$")
        assert "50" in resultado

    def test_cero(self):
        resultado = formatear_ars(0)
        assert resultado == "$0"

    def test_exactamente_un_millon(self):
        assert formatear_ars(1_000_000) == "$1.0M"

    def test_exactamente_mil_millones(self):
        assert formatear_ars(1_000_000_000) == "$1.00MM"

    def test_millon_con_decimales(self):
        resultado = formatear_ars(1_500_000)
        assert "1.5" in resultado


# ═══════════════════════════════════════════════════════════════════
# semaforo
# ═══════════════════════════════════════════════════════════════════

class TestSemaforo:
    def test_verde(self):
        assert semaforo(10, 20, 40) == "🟢"

    def test_amarillo(self):
        assert semaforo(30, 20, 40) == "🟡"

    def test_rojo(self):
        assert semaforo(50, 20, 40) == "🔴"

    def test_exactamente_verde_max(self):
        assert semaforo(20, 20, 40) == "🟢"

    def test_exactamente_amarillo_max(self):
        assert semaforo(40, 20, 40) == "🟡"

    def test_uno_mas_del_amarillo_max(self):
        assert semaforo(41, 20, 40) == "🔴"

    def test_cero_es_verde(self):
        assert semaforo(0, 10, 20) == "🟢"