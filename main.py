from fastapi import FastAPI
import pandas as pd
from src.utils import calcular_kpi_eficiencia

app = FastAPI()

# Cargar tus 1103 registros
# Ajustá la ruta al nombre real de tu archivo en el repo
df = pd.read_csv("data/juzgados.csv") 

@app.get("/api/v1/juzgado/{id_juzgado}")
def get_juzgado(id_juzgado: int):
    # Lógica de auditoría para un juzgado específico de tu lista
    datos_juzgado = df[df['id'] == id_juzgado].to_dict(orient='records')
    return datos_juzgado[0] if datos_juzgado else {"error": "No encontrado"}
