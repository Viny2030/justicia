import os
import pandas as pd
from fastapi import FastAPI

app = FastAPI()

# Esto detecta automáticamente la carpeta de tu proyecto
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Unimos la ruta: carpeta_del_proyecto + data + juzgados.csv
DATA_PATH = os.path.join(BASE_DIR, "data", "juzgados.csv")

@app.on_event("startup")
def load_data():
    if not os.path.exists(DATA_PATH):
        print(f"⚠️ Error: No encuentro el archivo en {DATA_PATH}")
    else:
        global df
        df = pd.read_csv(DATA_PATH)
        print("✅ Datos de los 1103 juzgados cargados correctamente")

@app.get("/")
def home():
    return {"mensaje": "Monitor Judicial Activo", "teoria": "Ph.D. Monteverde"}
