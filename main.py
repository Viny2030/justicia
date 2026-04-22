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
        df = pd.read_csv(DATA_PATH)
        
        # 1. Convertimos TODO a string para evitar conflictos de tipos (Arrow/NaN)
        df = df.astype(str).replace("nan", "") 
        
        datos_completos = df.to_dict(orient="records")
        
        return {
            "total_registros": len(df),
            "data": datos_completos
        }
    except Exception as e:
        return {"error": str(e)}
