import streamlit as st
import requests
import pandas as pd

st.title("📊 Monitor Operativo de Juzgados")

# Llamada a la API que acabás de levantar
URL_API = "http://localhost:8001/juzgados"

if st.button("Cargar Datos de Auditoría"):
    response = requests.get(URL_API)
    if response.status_code == 200:
        datos = response.json()
        df = pd.DataFrame(datos)
        st.write(f"Mostrando {len(df)} registros de los 1103 juzgados.")
        st.dataframe(df) # Aquí verás la tabla interactiva
    else:
        st.error("No se pudo conectar con la API")
