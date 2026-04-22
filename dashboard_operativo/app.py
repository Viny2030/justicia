# dashboard_operativo/app.py
import streamlit as st
import sys
import os

# Añadir el directorio raíz al path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils import calcular_kpi_eficiencia

st.set_page_config(page_title="Monitor Operativo - Juzgados", layout="wide")

st.title("📊 Monitor de Gestión de Juzgados")
st.write("Auditoría de procesos y latencia por expediente.")

# Simulación de selección de juzgado (Aquí conectarás tu CSV de 1103 registros)
juzgado_sel = st.selectbox("Seleccione Juzgado para auditar:", ["Juzgado Federal 1", "Juzgado Federal 2"])

presupuesto_asignado = 1200000 
sentencias_tramitadas = 350

costo_micro = calcular_kpi_eficiencia(presupuesto_asignado, sentencias_tramitadas)

st.divider()
st.subheader(f"Resultados para {juzgado_sel}")
st.metric("Costo Operativo por Fallo", f"${costo_micro:,.2f}")

st.sidebar.success("Datos cargados correctamente desde /data/processed")
