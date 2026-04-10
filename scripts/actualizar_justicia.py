import os
import pandas as pd
from sqlalchemy import create_engine
from parser_nlp_justicia import ParserJudicial

# Intentamos usar la DB de Railway, si no, una local para pruebas
DB_URL = os.getenv("DATABASE_URL", "sqlite:///justicia_local.db")
engine = create_engine(DB_URL)

def ejecutar():
    print("[*] Iniciando monitor judicial...")
    parser = ParserJudicial()
    
    # Simulación de datos para verificar creación de DB y NLP
    datos = pd.DataFrame([{
        "fecha": "2026-04-10",
        "instancia": "Cámara Federal",
        "descripcion": "Se confirma el procesamiento de ex funcionarios por defraudación.",
        "url_documento": "http://pjn.gov.ar/causa_test.pdf"
    }])
    
    print("[*] Analizando contenido con NLP...")
    datos['analisis_nlp'] = datos['descripcion'].apply(lambda x: parser.analizar_escrito(x))
    
    # Guardar en base de datos
    datos.to_sql('actuaciones', engine, if_exists='replace', index=False)
    print(f"[✓] Proceso terminado. Base de datos actualizada.")

if __name__ == "__main__":
    ejecutar()
