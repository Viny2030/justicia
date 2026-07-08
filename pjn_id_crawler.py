#!/usr/bin/env python3
"""
pjn_id_crawler.py
==================
Crawler real de estadisticas.pjn.gov.ar — reemplaza a crawl_pjn()/descargar_url()
(requests+BeautifulSoup sobre <a href>) usados en scraper_juzgados_nacional.py y
scraper_pjn_completo.py, que ya no encuentran nada porque:

  1. Las rutas .php viejas (civil.php, comercial.php, etc. — las SEEDS originales)
     devuelven 404: el sitio se reescribió con ruteo CodeIgniter (index.php/...).
  2. El buscador en cascada Año→Jurisdicción→Título→Subtítulo→Archivo que arma el
     HTML actual llama a endpoints JSON (index.php/getArchivos, getArchivosJuris,
     getDivisiones, etc.) que IGNORAN los parámetros recibidos y devuelven siempre
     el mismo resultado fijo — es un bug del backend PHP, no de renderizado JS.
     Un navegador real (Playwright/Selenium) mandaría el mismo GET y recibiría la
     misma respuesta rota, así que no soluciona nada.

Lo que sí funciona: index.php/getUrlDescarga?id=N consulta el catálogo de archivos
directo por ID primario, sin pasar por el filtro roto. Enumerando id~1..9500 (con
huecos que tiran 500 — se saltean) aparece el catálogo real 2002-2025: mezcla de
.csv (formato PJN legado, cp1250 ";"-separado — el que ya parsea scraper_estadisticas.py),
.xls "libro" viejos (multi-hoja, formato de cuadro impreso) y .pdf (resúmenes
anuales/semestrales). Este módulo sólo enumera y descarga; el parseo de cada
formato vive en scraper_estadisticas.py (csv) y pjn_extraer_libro_xls.py /
pjn_extraer_pdf_tablas.py (xls/pdf).

Uso:
  python pjn_id_crawler.py                       # crawl completo, resumible
  python pjn_id_crawler.py --resume
  python pjn_id_crawler.py --max-id 9500 --delay 0.03
  python pjn_id_crawler.py --start-id 8000 --max-id 9000   # sólo un tramo
"""

import os, re, json, time, logging, argparse, threading, unicodedata
from pathlib import Path
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from requests.adapters import HTTPAdapter

# ── CONFIG ────────────────────────────────────────────────────────────────────
ROOT        = Path(__file__).parent
DOMINIO     = "https://estadisticas.pjn.gov.ar"
BASE        = f"{DOMINIO}/07_estadisticas/estadisticas/07_estadisticas/index.php"
CSV_DIR     = ROOT / "pjn_estadisticas"          # CSVs reales (cp1250) — mismo dir que usa scraper_juzgados_nacional.py
XLS_DIR     = ROOT / "pjn_libros_xls"            # .xls "libro" crudos
PDF_DIR     = ROOT / "pjn_pdfs"                  # .pdf crudos
OTROS_DIR   = ROOT / "pjn_otros"                 # cualquier otra extensión
CKPT_FILE   = ROOT / "pjn_id_checkpoint.json"

MAX_ID_DEFAULT = 9500     # visto empíricamente: catálogo real llega hasta ~8977 (2026-07-08). Margen por si crece.
TIMEOUT     = 20
DELAY       = 0.05        # jitter suave por descarga (con threads, no serializa todo)
WORKERS     = 12          # threads para consultar getUrlDescarga (sólo lectura JSON, liviano)

USER_AGENT = "MonitorJudicialAR/4.0 (github.com/Viny2030/justicia; academic; contacto: ver README)"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def _session(pool_size=WORKERS):
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json,*/*"})
    adapter = HTTPAdapter(pool_connections=pool_size, pool_maxsize=pool_size, max_retries=2)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s


def _slug(s, maxlen=80):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^\w.-]+", "_", s).strip("_")
    return s[:maxlen] or "archivo"


def checkpoint_load():
    if CKPT_FILE.exists():
        return json.loads(CKPT_FILE.read_text(encoding="utf-8"))
    return {"procesados": {}}


def checkpoint_save(cp):
    CKPT_FILE.write_text(json.dumps(cp, ensure_ascii=False, indent=2), encoding="utf-8")


# ── PASO 1: enumerar el catálogo vía getUrlDescarga?id=N ─────────────────────

def _consultar_id(sess, id_):
    """Devuelve dict de metadata del archivo con ese id, o None si no existe (404/500/gap)."""
    try:
        r = sess.get(f"{BASE}/getUrlDescarga", params={"id": id_}, timeout=TIMEOUT)
    except requests.RequestException:
        return None
    if r.status_code != 200:
        return None
    txt = r.text.strip()
    if not txt.startswith("{"):
        return None
    try:
        d = r.json()
    except ValueError:
        return None
    if not d.get("descarga"):
        return None
    return d


def enumerar_catalogo(start_id=1, max_id=MAX_ID_DEFAULT, workers=WORKERS):
    """Sondea id=start_id..max_id contra getUrlDescarga y devuelve la lista de
    entradas válidas (con URL de descarga real). Usa threads porque es sólo
    lectura de JSON liviano — no descarga archivos todavía."""
    encontrados = []
    ids = list(range(start_id, max_id + 1))
    log.info(f"Sondeando catálogo PJN: id {start_id}..{max_id} ({len(ids)} ids, {workers} threads)")

    sess = _session(pool_size=workers)
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(_consultar_id, sess, i): i for i in ids}
        for fut in as_completed(futs):
            i = futs[fut]
            d = fut.result()
            done += 1
            if d:
                d["id"] = i
                encontrados.append(d)
            if done % 500 == 0:
                log.info(f"  ... {done}/{len(ids)} sondeados, {len(encontrados)} archivos reales encontrados")

    encontrados.sort(key=lambda x: x["id"])
    log.info(f"Catálogo: {len(encontrados)} archivos reales de {len(ids)} ids sondeados")
    return encontrados


# ── PASO 2: descargar cada archivo real, clasificado por extensión ───────────

def _destino_para(ext):
    return {
        "csv": CSV_DIR,
        "xls": XLS_DIR,
        "xlsx": XLS_DIR,
        "pdf": PDF_DIR,
    }.get(ext, OTROS_DIR)


def _cat_de(ext):
    return "xls" if ext in ("xls", "xlsx") else (ext if ext in ("csv", "pdf") else "otros")


def _descargar_uno(sess, d):
    """Descarga una entrada. Devuelve (idk, registro_checkpoint, path_o_None)."""
    idk = str(d["id"])
    descarga_rel = d["descarga"]
    ext = descarga_rel.rsplit(".", 1)[-1].lower() if "." in descarga_rel else "sin_ext"
    url = urljoin(DOMINIO, descarga_rel)
    nombre_base = descarga_rel.rsplit("/", 1)[-1]
    stem = _slug(Path(nombre_base).stem)
    fname = f"{idk}__{stem}.{ext}" if ext != "sin_ext" else f"{idk}__{stem}"
    destino = _destino_para(ext) / fname

    try:
        r = sess.get(url, timeout=60)
        r.raise_for_status()
        destino.write_bytes(r.content)
        return idk, {
            "ok": True, "file": str(destino), "ext": ext,
            "descripcion": d.get("descripcion"), "url": url,
        }, str(destino)
    except Exception as e:
        return idk, {"ok": False, "error": str(e), "url": url}, None


def descargar_catalogo(entradas, resume=True, delay=DELAY, workers=8):
    """Descarga cada entrada del catálogo a disco (en paralelo, checkpoint thread-safe),
    clasificada por extensión. Devuelve dict con listas de paths por tipo:
    {'csv': [...], 'xls': [...], 'pdf': [...], 'otros': [...]}"""
    for d in (CSV_DIR, XLS_DIR, PDF_DIR, OTROS_DIR):
        d.mkdir(exist_ok=True)

    cp = checkpoint_load() if resume else {"procesados": {}}
    lock = threading.Lock()

    resultado = {"csv": [], "xls": [], "pdf": [], "otros": []}
    pendientes = []
    for d in entradas:
        idk = str(d["id"])
        prev = cp["procesados"].get(idk)
        if prev and prev.get("ok"):
            fpath = prev.get("file")
            if fpath and os.path.exists(fpath):
                resultado[_cat_de(prev.get("ext", ""))].append(fpath)
            continue
        pendientes.append(d)

    saltados = len(entradas) - len(pendientes)
    log.info(f"Descargando {len(pendientes)} archivos nuevos ({saltados} ya en checkpoint), {workers} threads")

    nuevos, fallidos = 0, 0
    sess = _session(pool_size=workers)

    def _tarea(d):
        time.sleep(delay)  # jitter suave por thread, no serializa todo
        return _descargar_uno(sess, d)

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(_tarea, d) for d in pendientes]
        for fut in as_completed(futs):
            idk, registro, path = fut.result()
            with lock:
                cp["procesados"][idk] = registro
                if registro.get("ok"):
                    resultado[_cat_de(registro["ext"])].append(path)
                    nuevos += 1
                    if nuevos % 100 == 0:
                        checkpoint_save(cp)
                        log.info(f"  descargados {nuevos}/{len(pendientes)}")
                else:
                    fallidos += 1

    checkpoint_save(cp)
    log.info(f"Descarga: {nuevos} nuevos, {saltados} ya procesados (checkpoint), {fallidos} fallidos")
    log.info(f"  CSV reales (formato PJN legado): {len(resultado['csv'])}")
    log.info(f"  XLS 'libro' (viejos, requieren pjn_extraer_libro_xls.py): {len(resultado['xls'])}")
    log.info(f"  PDF (requieren pjn_extraer_pdf_tablas.py): {len(resultado['pdf'])}")
    log.info(f"  Otros formatos: {len(resultado['otros'])}")
    return resultado


# ── Entrypoint combinado (usado por scraper_juzgados_nacional.py) ────────────

def crawl_y_descargar(start_id=1, max_id=MAX_ID_DEFAULT, resume=True, delay=DELAY, workers=WORKERS,
                       download_workers=8):
    entradas = enumerar_catalogo(start_id=start_id, max_id=max_id, workers=workers)
    return descargar_catalogo(entradas, resume=resume, delay=delay, workers=download_workers)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--start-id", type=int, default=1)
    ap.add_argument("--max-id", type=int, default=MAX_ID_DEFAULT)
    ap.add_argument("--resume", action="store_true", help="omitir ids ya descargados según pjn_id_checkpoint.json")
    ap.add_argument("--reset", action="store_true", help="borrar checkpoint y empezar de cero")
    ap.add_argument("--delay", type=float, default=DELAY)
    ap.add_argument("--workers", type=int, default=WORKERS, help="threads para sondear metadata (getUrlDescarga)")
    ap.add_argument("--download-workers", type=int, default=8, help="threads para descargar archivos")
    args = ap.parse_args()

    if args.reset and CKPT_FILE.exists():
        CKPT_FILE.unlink()
        log.info("Checkpoint borrado (--reset)")

    log.info("=" * 60)
    log.info("Crawler PJN por enumeración de ID — estadisticas.pjn.gov.ar")
    log.info("=" * 60)
    resultado = crawl_y_descargar(
        start_id=args.start_id, max_id=args.max_id,
        resume=args.resume, delay=args.delay, workers=args.workers,
        download_workers=args.download_workers,
    )
    log.info("=" * 60)
    log.info(f"TOTAL en disco -> csv:{len(resultado['csv'])} xls:{len(resultado['xls'])} "
              f"pdf:{len(resultado['pdf'])} otros:{len(resultado['otros'])}")


if __name__ == "__main__":
    main()
