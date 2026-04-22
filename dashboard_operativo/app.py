import streamlit as st
import requests
import pandas as pd

st.title("📊 Monitor Operativo de Juzgados")

# Llamada a la API que acabás de levantar
URL_API = "http://localhost:8001/juzgados"

if st.button("Cargar Datos"):
    response = requests.get("http://localhost:8001/juzgados")
    if response.status_code == 200:
        json_data = response.json()
        df = pd.DataFrame(json_data['data'])
        
        # Limpieza de tipos para Streamlit/Arrow
        for col in df.columns:
            df[col] = df[col].astype(str) # Convertimos a string para evitar el error de Arrow
            
        st.dataframe(df)
