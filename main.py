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
        # Cargamos el archivo
        df = pd.read_csv(DATA_PATH)
        
        # --- LIMPIEZA CRÍTICA ---
        # Convertimos todo a string y reemplazamos los NaN por vacío
        # Esto evita el error "JSON compliant: nan"
        df = df.astype(str).replace("nan", "")
        
        datos = df.to_dict(orient="records")
        
        return {
            "total_registros": len(df),
            "data": datos
        }
    except Exception as e:
        return {"error": f"Error de procesamiento: {str(e)}"}
