import os
import pandas as pd
from sqlalchemy import create_engine
import sys
import json

# Agregamos el path para que encuentre el parser
sys.path.append(os.path.dirname(__file__))
from parser_nlp_justicia import ParserJudicial

# Usamos SQLite localmente
engine = create_engine("sqlite:///justicia_local.db")

def ejecutar():
    print("[*] Iniciando monitor judicial...")
    parser = ParserJudicial()
    
    # Datos de prueba
    datos = pd.DataFrame([{
        "fecha": "2026-04-10",
        "instancia": "Cámara Federal",
        "descripcion": "El juez dictó el procesamiento de los directivos de la empresa.",
        "url_documento": "http://pjn.gov.ar/causa_test.pdf"
    }])
    
    print("[*] Ejecutando análisis NLP...")
    # Analizamos y convertimos el diccionario a una cadena de texto JSON
    datos['analisis_nlp'] = datos['descripcion'].apply(
        lambda x: json.dumps(parser.analizar_escrito(x))
    )
    
    # Guardar en base de datos
    print("[*] Guardando en justicia_local.db...")
    datos.to_sql('actuaciones', engine, if_exists='replace', index=False)
    print("[✓] Proceso terminado con éxito.")

if __name__ == "__main__":
    ejecutar()
