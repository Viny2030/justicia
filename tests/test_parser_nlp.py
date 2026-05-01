"""
Tests para scripts/parser_nlp_justicia.py
spaCy puede no estar disponible en el entorno de CI — se usa mock cuando falta.
"""
import sys
import os
import types
import pytest
from unittest.mock import MagicMock, patch

# ── Mock de spaCy si no está instalado ──────────────────────────────────────
if "spacy" not in sys.modules:
    spacy_mock = types.ModuleType("spacy")
    spacy_mock.load = MagicMock(side_effect=Exception("modelo no disponible"))
    sys.modules["spacy"] = spacy_mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from scripts.parser_nlp_justicia import ParserJudicial
import scripts.parser_nlp_justicia as modulo_parser


class TestParserJudicial:
    def setup_method(self):
        self.parser = ParserJudicial()

    def test_retorna_dict(self):
        resultado = self.parser.analizar_escrito("Texto de prueba")
        assert isinstance(resultado, dict)

    def test_sin_modelo_retorna_clave_error(self):
        """Sin spaCy, analizar_escrito debe retornar {'error': ...}."""
        nlp_original = modulo_parser.nlp
        modulo_parser.nlp = None
        resultado = self.parser.analizar_escrito("Texto cualquiera")
        modulo_parser.nlp = nlp_original
        assert "error" in resultado

    def test_texto_vacio_no_lanza_excepcion(self):
        resultado = self.parser.analizar_escrito("")
        assert isinstance(resultado, dict)

    def test_con_modelo_mock_retorna_personas_y_organizaciones(self):
        """Simula un modelo de spaCy que detecta entidades."""
        ent_per = MagicMock(); ent_per.text = "Juan Pérez"; ent_per.label_ = "PER"
        ent_org = MagicMock(); ent_org.text = "Poder Judicial"; ent_org.label_ = "ORG"
        doc_mock = MagicMock(); doc_mock.ents = [ent_per, ent_org]
        nlp_mock = MagicMock(return_value=doc_mock)

        nlp_original = modulo_parser.nlp
        modulo_parser.nlp = nlp_mock
        resultado = self.parser.analizar_escrito("Juan Pérez vs Poder Judicial")
        modulo_parser.nlp = nlp_original

        assert "personas" in resultado
        assert "organizaciones" in resultado
        assert "Juan Pérez" in resultado["personas"]
        assert "Poder Judicial" in resultado["organizaciones"]

    def test_con_modelo_mock_personas_sin_duplicados(self):
        ent1 = MagicMock(); ent1.text = "María García"; ent1.label_ = "PER"
        ent2 = MagicMock(); ent2.text = "María García"; ent2.label_ = "PER"
        doc_mock = MagicMock(); doc_mock.ents = [ent1, ent2]
        nlp_mock = MagicMock(return_value=doc_mock)

        nlp_original = modulo_parser.nlp
        modulo_parser.nlp = nlp_mock
        resultado = self.parser.analizar_escrito("María García y María García")
        modulo_parser.nlp = nlp_original

        assert resultado["personas"].count("María García") == 1

    def test_con_modelo_mock_sin_entidades(self):
        doc_mock = MagicMock(); doc_mock.ents = []
        nlp_mock = MagicMock(return_value=doc_mock)

        nlp_original = modulo_parser.nlp
        modulo_parser.nlp = nlp_mock
        resultado = self.parser.analizar_escrito("texto sin entidades")
        modulo_parser.nlp = nlp_original

        assert resultado["personas"] == []
        assert resultado["organizaciones"] == []

    def test_claves_del_resultado_con_modelo(self):
        doc_mock = MagicMock(); doc_mock.ents = []
        nlp_mock = MagicMock(return_value=doc_mock)

        nlp_original = modulo_parser.nlp
        modulo_parser.nlp = nlp_mock
        resultado = self.parser.analizar_escrito("texto")
        modulo_parser.nlp = nlp_original

        assert set(resultado.keys()) == {"personas", "organizaciones"}