"""GET /api/frescura con los datos del repo."""
import os
import sys

import pytest

pytest.importorskip("fastapi", reason="el CI no instala las dependencias de la app")

from fastapi.testclient import TestClient  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app  # noqa: E402


def test_frescura():
    with TestClient(app) as c:
        d = c.get("/api/frescura").json()
        assert d["formato"] == "frescura/1" and d["sitio"] == "justicia"
        assert {x["id"] for x in d["datos"]} == {"magistrados", "datos_abiertos", "csjn"}
        assert all(x["dato"] and x["fuente"] for x in d["datos"])
        assert c.get("/frescura.js").status_code == 200
        assert "frescura-ficha" in c.get("/").text


def test_red_vacantes():
    with TestClient(app) as c:
        d = c.get("/api/red-vacantes").json()
        r = d["resumen"]
        camaras = [n for n in d["nodos"] if n["tipo"] == "camara"]
        assert r["camaras"] == len(camaras) and all(n["label"] for n in d["nodos"])
        ids = {n["id"] for n in d["nodos"]}
        assert all(a["from"] in ids and a["to"] in ids for a in d["aristas"])
        assert sum(a["vacantes"] for a in d["aristas"]) == r["vacantes"]
        assert "apellido" not in str(d) and "ultimo_titular" not in str(d)
        assert "red-vacantes" in c.get("/red").text
        assert 'id="grafos"' in c.get("/manual").text and 'id="grafos"' in c.get("/manual/en").text
