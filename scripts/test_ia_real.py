import spacy
import json

nlp = spacy.load("es_core_news_lg")

texto_judicial = """
En la ciudad de Buenos Aires, a los 10 días de abril de 2026, el Dr. Claudio Bonadio 
analiza la situación de la empresa Techint y la participación de Paolo Rocca en la 
causa caratulada 'Cuadernos'. Se solicita la intervención de la Inspección General de Justicia.
"""

doc = nlp(texto_judicial)

resultado = {
    "personas": list(set([ent.text for ent in doc.ents if ent.label_ == "PER"])),
    "organizaciones": list(set([ent.text for ent in doc.ents if ent.label_ == "ORG"])),
    "lugares": list(set([ent.text for ent in doc.ents if ent.label_ == "LOC"]))
}

print("--- RESULTADO DE LA IA ---")
print(json.dumps(resultado, indent=4, ensure_ascii=False))
