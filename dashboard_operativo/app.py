import streamlit as st
import requests

st.title("Monitor Operativo de Juzgados")

id_busqueda = st.number_input("ID del Juzgado a auditar", min_value=1, max_value=1103)

if st.button("Ver Auditoría"):
    # Llama a tu FastAPI local
    data = requests.get(f"http://localhost:8000/api/v1/juzgado/{id_busqueda}").json()
    st.write(f"Juzgado: {data['nombre']}")
    st.metric("Latencia Detectada", f"{data['dias_latencia']} días")
