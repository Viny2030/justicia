cat <<EOF > scripts/parser_nlp_justicia.py
import spacy

try:
    nlp = spacy.load("es_core_news_lg")
except:
    nlp = None

class ParserJudicial:
    def analizar_escrito(self, texto):
        if not nlp: return {"error": "Modelo no cargado"}
        doc = nlp(texto)
        return {
            "personas": list(set([ent.text for ent in doc.ents if ent.label_ == "PER"])),
            "organizaciones": list(set([ent.text for ent in doc.ents if ent.label_ == "ORG"]))
        }
EOF
