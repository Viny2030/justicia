from fastapi import FastAPI
from fastapi.responses import JSONResponse
import pandas as pd
import os

app = FastAPI(title="Motor de Auditoría Judicial - Ph.D. Monteverde")

# Detectar la ruta del archivo
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "pjn_estadisticas_completo.csv")

@app.get("/")
def home():
    return {"status": "Online", "fuente": "PJN - Auditoría Operativa"}

@app.get("/juzgados")
def obtener_salida_fastapi_completa():
    """
    Salida de datos crudos procesados para auditoría.
    Maneja el 100% de los registros (24,963) sin errores de serialización.
    """
    try:
        # Carga del dataset de 1103 juzgados / 24,963 registros
        df = pd.read_csv(DATA_PATH)
        
        # --- LIMPIEZA DE AUDITORÍA ---
        # Convertimos todo a string para evitar errores de NaN/Out of range
        # Esto asegura que la salida en FastAPI sea 200 OK siempre.
        df_limpio = df.fillna("").astype(str)
        
        # Transformación a diccionario nativo de Python (orientado a registros)
        datos_crudos = df_limpio.to_dict(orient="records")
        
        # Retorno estructurado
        return {
            "metadata": {
                "total_registros": len(df_limpio),
                "autor": "Ph.D. Vicente Monteverde",
                "version": "1.0.2"
            },
            "juzgados": datos_crudos
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Fallo en el motor de datos: {str(e)}"}
        )
