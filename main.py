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
def listar_juzgados():
    try:
        df = pd.read_csv(DATA_PATH)
        # Retornamos los primeros 100 para no saturar el navegador
        return df.head(100).to_dict(orient="records")
    except Exception as e:
        return {"error": str(e)}

