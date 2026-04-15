import pandas as pd
from sqlalchemy import create_engine
import json

engine = create_engine("sqlite:///justicia_local.db")
df = pd.read_sql("SELECT * FROM actuaciones ORDER BY rowid DESC LIMIT 5", engine)

print("\n--- ÚLTIMAS ACTUACIONES EN DB ---")
for i, r in df.iterrows():
    nlp_data = json.loads(r['analisis_nlp'])
    print(f"FECHA: {r['fecha']} | INSTANCIA: {r['instancia']}")
    print(f"TEXTO: {r['descripcion'][:80]}...")
    print(f"IA ENCONTRÓ: Personas: {nlp_data.get('personas')} | Org: {nlp_data.get('organizaciones')}")
    print("-" * 50)
