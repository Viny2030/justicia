import spacy
import pdfplumber
import re

# Cargamos el modelo en español
nlp = spacy.load("es_core_news_lg")

class ParserJudicial:
    def __init__(self):
        self.keywords_alerta = ["procesamiento", "embargo", "dádivas", "sobreseimiento", "corrupción"]

    def leer_pdf(self, path):
        texto = ""
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                texto += page.extract_text() or ""
        return texto

    def analizar_escrito(self, texto):
        doc = nlp(texto)
        
        # Extracción de Entidades (NER)
        personas = list(set([ent.text for ent in doc.ents if ent.label_ == "PER"]))
        empresas = list(set([ent.text for ent in doc.ents if ent.label_ == "ORG"]))
        
        # Detección de Hitos (Instancias)
        hitos = []
        for sent in doc.sents:
            if any(key in sent.text.lower() for key in self.keywords_alerta):
                hitos.append(sent.text.strip())
        
        # Búsqueda de montos (Embargos/Fianzas)
        montos = re.findall(r'\$\s?(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)', texto)

        return {
            "entidades_per": personas,
            "entidades_org": empresas,
            "hitos_detectados": hitos,
            "montos_identificados": montos
        }
