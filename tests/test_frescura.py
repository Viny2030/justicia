"""GET /api/frescura con los datos del repo."""
import os
import sys

from fastapi.testclient import TestClient

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
