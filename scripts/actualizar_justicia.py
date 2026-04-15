import os
import sys
import pandas as pd
import json
from sqlalchemy import create_engine

# Asegurar que encuentre los scripts locales
sys.path.append(os.path.dirname(__file__))
from scraper_pjn_completo import ScraperPJN
from parser_nlp_justicia import ParserJudicial

# Base de datos
engine = create_engine("sqlite:///justicia_local.db")

def ejecutar():
    print("=== MONITOR JUDICIAL INTELIGENTE ===")
    scraper = ScraperPJN()
    parser = ParserJudicial()

    # 1. Scraping
    datos_crudos = scraper.buscar_ultimas_sentencias()
    
    if not datos_crudos:
        print("[!] No se obtuvieron datos nuevos.")
        return

    df = pd.DataFrame(datos_crudos)

    # 2. Análisis NLP con IA
    print(f"[*] Analizando {len(df)} registros con spaCy...")
    df['analisis_nlp'] = df['descripcion'].apply(
        lambda x: json.dumps(parser.analizar_escrito(x))
    )

    # 3. Guardar en DB
    print("[*] Actualizando base de datos local...")
    df.to_sql('actuaciones', engine, if_exists='append', index=False)
    print(f"[✓] Éxito. {len(df)} actuaciones procesadas y guardadas.")

if __name__ == "__main__":
    ejecutar()
