from fastapi import FastAPI
import pandas as pd
import os

app = FastAPI(title="Monitor de Justicia - Ph.D. Monteverde")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Aseguramos la ruta a tus estadísticas
DATA_PATH = os.path.join(BASE_DIR, "pjn_estadisticas_completo.csv")

@app.get("/")
def home():
    return {"mensaje": "Monitor Judicial Activo", "teoria": "Ph.D. Monteverde"}

@app.get("/juzgados")
def listar_juzgados_completos():
    try:
        # 1. Cargar datos
        df = pd.read_csv(DATA_PATH)
        
        # 2. LIMPIEZA ABSOLUTA: 
        # Reemplazamos nulos por strings vacíos y convertimos todo a tipos nativos de Python
        df_limpio = df.fillna("").astype(str) 
        datos_finales = df_limpio.to_dict(orient="records")
        
        # 3. Respuesta
        return {
            "total_registros": len(df_limpio),
            "data": datos_finales
        }
    except Exception as e:
        # Si algo falla, lo atrapamos aquí para que la API no de 500
        return {"error": f"Error en el motor: {str(e)}"}
