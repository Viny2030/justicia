"""
scripts/vigia_csjn.py — Vigía semanal de la Corte Suprema
─────────────────────────────────────────────────────────────────────
Las cifras de la Corte (datos_csjn.json) se cargan a mano porque la CSJN
publica sus estadísticas en PDF / tableros interactivos, una vez por año.
Este script NO modifica datos: sólo revisa si hay algo nuevo para cargar
y lo informa, para que una persona lo revise y actualice el JSON.

Revisa:
  1. Si se publicó el Anuario Estadístico del año siguiente al último cargado
     (csjn.gov.ar/archivos/estadisticas/informe_anuario_CSJN_<año>.pdf).
  2. Si los ministros cargados siguen figurando en la página oficial de jueces
     (si alguno ya no aparece, cambió la composición).
  3. Si se publicó el cierre de ejecución presupuestaria (diciembre) del año
     siguiente al cargado, en datos.csjn.gob.ar.

Salida:
  · Imprime un resumen (y lo agrega al resumen del job si corre en Actions).
  · Escribe vigia_csjn_alertas.md con las novedades (vacío si no hay).
  · Código de salida 0 siempre: que un sitio no responda NO es un error del
    repo, se informa como "no se pudo verificar" y se reintenta la semana próxima.

Uso:  python scripts/vigia_csjn.py
"""
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
DATOS = ROOT / "datos_csjn.json"
SALIDA = ROOT / "vigia_csjn_alertas.md"

URL_ANUARIO = "https://www.csjn.gov.ar/archivos/estadisticas/informe_anuario_CSJN_{anio}.pdf"
URL_JUECES = "https://www.csjn.gov.ar/institucional/jueces"
URL_PRESUP = "https://datos.csjn.gob.ar/api/3/action/package_show?id=ejecucion-presupuestaria-diciembre-{anio}"
URL_PRESUP_WEB = "https://datos.csjn.gob.ar/dataset/ejecucion-presupuestaria-diciembre-{anio}"

HEADERS = {"User-Agent": "MonitorJusticiaAR-vigia/1.0 (github.com/Viny2030/justicia; transparencia pública)"}
TIMEOUT = 45


def _get(url, **kw):
    """GET que nunca lanza: devuelve (response | None, error | None)."""
    try:
        return requests.get(url, headers=HEADERS, timeout=TIMEOUT, **kw), None
    except requests.RequestException as e:
        return None, str(e)


def _norm(txt: str) -> str:
    txt = unicodedata.normalize("NFKD", txt).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", txt).lower()


def _parece_bloqueo(r) -> bool:
    """Páginas anti-bot / desafío devuelven 200 con HTML genérico."""
    cuerpo = r.text[:4000].lower() if "html" in r.headers.get("content-type", "") else ""
    return any(p in cuerpo for p in ("captcha", "challenge", "access denied", "request rejected"))


def revisar_anuario(datos, fetch=_get):
    ultimo = max((a["anio"] for a in datos.get("anuarios", [])), default=None)
    if not ultimo:
        return "error", "datos_csjn.json no tiene anuarios cargados."
    anio = ultimo + 1
    url = URL_ANUARIO.format(anio=anio)
    r, err = fetch(url, stream=True)
    if r is None:
        return "sin_verificar", f"Anuario {anio}: no se pudo consultar ({err})."
    ctype = r.headers.get("content-type", "")
    if r.status_code == 200 and "pdf" in ctype.lower():
        return "novedad", f"Se publicó el **Anuario Estadístico {anio}**: {url}"
    if r.status_code in (403, 429) or (r.status_code == 200 and _parece_bloqueo(r)):
        return "sin_verificar", f"Anuario {anio}: el sitio bloqueó la consulta (HTTP {r.status_code})."
    return "ok", f"Anuario {anio}: todavía no publicado (HTTP {r.status_code})."


def revisar_composicion(datos, fetch=_get):
    nombres = [m["nombre"] for m in datos.get("composicion", {}).get("ministros", [])]
    r, err = fetch(URL_JUECES)
    if r is None:
        return "sin_verificar", f"Composición: no se pudo consultar ({err})."
    if r.status_code != 200 or _parece_bloqueo(r):
        return "sin_verificar", f"Composición: el sitio no devolvió la página (HTTP {r.status_code})."
    pagina = _norm(re.sub(r"<[^>]+>", " ", r.text))
    # se busca el apellido (última palabra), que es lo que nunca cambia de forma
    faltan = [n for n in nombres if _norm(n.split()[-1]) not in pagina]
    if not nombres or len(faltan) == len(nombres):
        return "sin_verificar", "Composición: la página no tiene el formato esperado (no se encontró ningún ministro)."
    if faltan:
        return "novedad", ("Posible **cambio en la composición de la Corte**: ya no figura(n) "
                           f"{', '.join(faltan)} en {URL_JUECES}")
    return "ok", f"Composición: siguen figurando los {len(nombres)} ministros cargados."


def revisar_presupuesto(datos, fetch=_get):
    anio_cargado = datos.get("presupuesto", {}).get("anio")
    if not anio_cargado:
        return "error", "datos_csjn.json no tiene presupuesto cargado."
    anio = anio_cargado + 1
    r, err = fetch(URL_PRESUP.format(anio=anio))
    if r is None:
        return "sin_verificar", f"Presupuesto {anio}: no se pudo consultar ({err})."
    try:
        d = r.json()
    except ValueError:
        return "sin_verificar", f"Presupuesto {anio}: respuesta no válida del portal (HTTP {r.status_code})."
    if d.get("success"):
        return "novedad", (f"Se publicó la **ejecución presupuestaria a diciembre {anio}** de la CSJN: "
                           f"{URL_PRESUP_WEB.format(anio=anio)}")
    return "ok", f"Presupuesto {anio}: todavía no publicado el cierre anual."


def main(fetch=_get) -> int:
    datos = json.loads(DATOS.read_text(encoding="utf-8"))
    resultados = [
        ("Anuario", *revisar_anuario(datos, fetch)),
        ("Composición", *revisar_composicion(datos, fetch)),
        ("Presupuesto", *revisar_presupuesto(datos, fetch)),
    ]
    icono = {"novedad": "🔔", "ok": "✅", "sin_verificar": "⚠️", "error": "❌"}
    resumen = ["## Vigía CSJN", "", f"Última carga manual de datos_csjn.json: {datos.get('actualizado', '—')}", ""]
    resumen += [f"- {icono[e]} {msg}" for _, e, msg in resultados]
    texto = "\n".join(resumen)
    print(texto)

    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(texto + "\n")

    novedades = [msg for _, e, msg in resultados if e == "novedad"]
    if novedades:
        cuerpo = ["Hay novedades oficiales de la Corte Suprema para cargar en `datos_csjn.json`:", ""]
        cuerpo += [f"- {m}" for m in novedades]
        cuerpo += ["", "Revisar la fuente, actualizar las cifras a mano y la fecha `actualizado`.",
                   "", "_Issue abierto automáticamente por el workflow «Vigía Corte Suprema»._"]
        SALIDA.write_text("\n".join(cuerpo), encoding="utf-8")
    else:
        SALIDA.write_text("", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
