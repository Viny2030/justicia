cat <<EOF > scripts/actualizar_justicia.py
import os
import pandas as pd
from sqlalchemy import create_engine
from parser_nlp_justicia import ParserJudicial

# Usamos SQLite localmente
engine = create_engine("sqlite:///justicia_local.db")

def ejecutar():
    print("[*] Iniciando proceso local...")
    parser = ParserJudicial()
    
    # Datos de prueba para verificar que el sistema funciona
    datos_prueba = pd.DataFrame([{
        "fecha": "2024-05-20",
        "instancia": "Primera Instancia",
        "descripcion": "Se ordena el procesamiento de Juan Perez por malversacion.",
        "url_documento": "http://ejemplo.com/doc.pdf"
    }])
    
    # Analizamos con NLP
    print("[*] Ejecutando NLP de prueba...")
    datos_prueba['analisis_nlp'] = datos_prueba['descripcion'].apply(lambda x: parser.analizar_escrito(x))
    
    # Guardamos en la DB local
    datos_prueba.to_sql('actuaciones', engine, if_exists='replace', index=False)
    print("[✓] Base de datos 'justicia_local.db' generada con éxito.")

if __name__ == "__main__":
    ejecutar()
EOF
