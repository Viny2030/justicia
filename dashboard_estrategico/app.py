# dashboard_estrategico/app.py
import streamlit as st
import sys
import os

# Añadir el directorio raíz al path para que encuentre 'src'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils import calcular_kpi_eficiencia, calcular_tasa_vacancia

st.set_page_config(page_title="Monitor Estratégico - CSJN & Consejo", layout="wide")

st.title("⚖️ Alta Gerencia y Administración Judicial")
st.markdown("---")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Consejo de la Magistratura")
    presupuesto_anual = 150000000  # Este dato vendrá de tu scraping de TGN/BORA
    total_sentencias_pais = 45000
    
    costo_macro = calcular_kpi_eficiencia(presupuesto_anual, total_sentencias_pais)
    st.metric("KPI: Costo Macro por Sentencia", f"${costo_macro:,.2f}")

with col2:
    st.subheader("Gestión de Vacancia")
    # Datos basados en tu detección del 32.9%
    tasa = calcular_tasa_vacancia(jueces_activos=671, cargos_totales=1000)
    st.metric("Índice de Vacancia Nacional", f"{tasa}%", delta="-32.9% crítico")

st.info("Este monitor analiza instituciones que definen el rumbo del Poder Judicial.")
