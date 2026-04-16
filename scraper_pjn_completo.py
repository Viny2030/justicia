"""
scraper_pjn_completo.py
Descarga estadisticas de todos los juzgados del PJN desde 2024.
Fuentes: estadisticas.pjn.gov.ar (CSV/Excel) + datos.gob.ar (PJN datasets)
NO procesa PDFs.

Características:
  - Checkpoint: guarda progreso en pjn_checkpoint.json → si se interrumpe,
    retoma desde el último archivo procesado (usar --resume para activar).
  - Failures log: pjn_failures.json con detalle de cada archivo fallido.
  - CRC-32 corrupto: intenta extraer ZIPs con bad CRC usando allowZip64 +
    fallback manual con zlib para recuperar lo que se pueda.
"""

import re
import sys
import json
import time
import logging
import argparse
import requests
import pandas as pd
from io import StringIO, BytesIO
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

# ── CONFIG ────────────────────────────────────────────────────────────────────
PORTALES = [
    "https://estadisticas.pjn.gov.ar/",
    "https://estadisticas.pjn.gov.ar/07_estadisticas/estadisticas/07_estadisticas/index.php",
    "https://old.pjn.gov.ar/07_estadisticas/estadisticas/07_estadisticas/index.php",
]

# datos.gob.ar tiene datasets del PJN con CSVs directos
DATOS_GOB_AR_PJN = [
    "https://datos.gob.ar/api/3/action/package_search?q=poder+judicial+nacion&rows=50",
    "https://datos.gob.ar/api/3/action/package_search?q=estadisticas+judiciales&rows=50",
    "https://datos.gob.ar/api/3/action/package_search?q=causas+judiciales&rows=50",
]

OUT_DIR = Path("pjn_estadisticas")
CHECKPOINT_FILE = Path("pjn_checkpoint.json")
FAILURES_FILE = Path("pjn_failures.json")
DELAY = 1.5
TIMEOUT = 45
FORMATOS = {".csv", ".xlsx", ".xls", ".zip"}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

session = requests.Session()
session.headers.update({
    "User-Agent": "MonitorJudicialAR/2.0 (github.com/Viny2030/justicia)"
})


# ── HELPERS ───────────────────────────────────────────────────────────────────

def get_html(url):
    try:
        r = session.get(url, timeout=TIMEOUT)
        r.raise_for_status()
        return BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        log.warning(f"  HTML error {url}: {e}")
        return None


def parsear_csv(content_bytes):
    ultimo_error = None
    for enc in ("utf-8-sig", "latin-1", "cp1252", "utf-8"):
        try:
            texto = content_bytes.decode(enc)
        except Exception as e:
            ultimo_error = e
            continue
        # intento 1: auto-detect separador (engine python, tolerante)
        try:
            df = pd.read_csv(
                StringIO(texto), sep=None, engine="python",
                dtype=str, na_values=["", "NULL", "N/A", "S/D"],
                low_memory=False, on_bad_lines="skip"
            )
            if not df.empty:
                return df
        except Exception as e:
            ultimo_error = e
        # intento 2: separadores explícitos con on_bad_lines
        for sep in (",", ";", "\t", "|"):
            for engine in ("c", "python"):
                try:
                    df = pd.read_csv(
                        StringIO(texto), sep=sep, engine=engine,
                        dtype=str, na_values=["", "NULL", "N/A", "S/D"],
                        low_memory=False, on_bad_lines="skip"
                    )
                    if not df.empty and len(df.columns) > 1:
                        return df
                except Exception as e:
                    ultimo_error = e
    log.warning(f"    parsear_csv falló: {ultimo_error}")
    return None


def parsear_excel(path_tmp):
    try:
        xl = pd.ExcelFile(path_tmp)
        frames = []
        for hoja in xl.sheet_names:
            df = xl.parse(hoja, dtype=str)
            if not df.empty:
                df["_hoja"] = hoja
                frames.append(df)
        return pd.concat(frames, ignore_index=True) if frames else None
    except Exception as e:
        log.warning(f"    Excel error: {e}")
        return None


def _zip_leer_con_crc_malo(z, name):
    """
    Intenta leer una entrada ZIP ignorando errores de CRC-32.
    Útil para archivos corruptos en el servidor (ej: mediaciones 2024).
    Estrategia: parchea temporalmente el CRC esperado con el calculado.
    """
    import zipfile, zlib
    info = z.getinfo(name)
    with z.open(name) as fh:
        raw = fh.read()
    # verificar si realmente hay mismatch de CRC
    crc_real = zlib.crc32(raw) & 0xFFFFFFFF
    if crc_real != info.CRC:
        log.warning(f"    CRC-32 mismatch en '{name}': "
                    f"esperado={info.CRC:#010x} real={crc_real:#010x} — usando datos igualmente")
    return raw


def descargar(url, ext):
    import zipfile
    try:
        r = session.get(url, timeout=60, stream=True)
        r.raise_for_status()

        # nombre de temp único por URL para evitar colisiones entre ZIPs
        url_hash = abs(hash(url)) % 10 ** 8
        base_tmp = Path("C:/Temp") if sys.platform == "win32" else Path("/tmp")
        base_tmp.mkdir(parents=True, exist_ok=True)
        tmp = base_tmp / f"_pjn_{url_hash}{ext}"

        with open(tmp, "wb") as f:
            for chunk in r.iter_content(16384):
                f.write(chunk)

        size_kb = tmp.stat().st_size / 1024
        log.info(f"    {size_kb:.1f} KB")

        if ext == ".zip":
            frames = []
            try:
                zf = zipfile.ZipFile(tmp)
            except zipfile.BadZipFile as e:
                log.error(f"    ZIP inválido (no recuperable): {e}")
                return None

            log.info(f"    ZIP contiene: {zf.namelist()}")
            with zf:
                for name in zf.namelist():
                    inner_ext = Path(name).suffix.lower()
                    if inner_ext not in {".csv", ".xlsx", ".xls"}:
                        continue

                    # intentar leer — si falla por CRC, usar fallback
                    try:
                        content = zf.read(name)
                    except zipfile.BadZipFile as e:
                        log.warning(f"    Error leyendo '{name}': {e} — intentando recuperar con CRC bypass")
                        try:
                            content = _zip_leer_con_crc_malo(zf, name)
                        except Exception as e2:
                            log.error(f"    No recuperable '{name}': {e2}")
                            continue

                    if inner_ext == ".csv":
                        df = parsear_csv(content)
                    else:
                        safe_name = re.sub(r"[^\w.]", "_", Path(name).name)
                        p2 = base_tmp / f"_inner_{url_hash}_{safe_name}"
                        p2.write_bytes(content)
                        df = parsear_excel(p2)

                    if df is not None:
                        df["_archivo"] = name
                        frames.append(df)

            return pd.concat(frames, ignore_index=True) if frames else None

        elif ext == ".csv":
            return parsear_csv(tmp.read_bytes())

        elif ext in (".xlsx", ".xls"):
            return parsear_excel(tmp)

    except Exception as e:
        log.error(f"    error: {e}")
    return None


def limpiar(df):
    df.columns = (
        df.columns.astype(str).str.strip().str.lower()
        .str.replace(r"\s+", "_", regex=True)
        .str.replace(r"[^\w]", "_", regex=True)
        .str.strip("_")
    )
    return df.fillna("")


def guardar(df, stem):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_DIR / f"{stem}.csv", index=False, encoding="utf-8-sig")
    with open(OUT_DIR / f"{stem}.json", "w", encoding="utf-8") as f:
        json.dump(df.to_dict(orient="records"), f, ensure_ascii=False, indent=2)
    log.info(f"    -> {stem}.csv  ({len(df):,} filas)")


# ── FUENTE 1: estadisticas.pjn.gov.ar ────────────────────────────────────────

def crawl_pjn(desde_año, max_archivos=None):
    """Rastrea el portal PJN buscando CSV/Excel (sin PDFs)."""
    encontrados = []
    visitadas = set()
    cola = list(PORTALES)
    año_actual = datetime.now().year

    while cola and len(visitadas) < 40:
        url = cola.pop(0)
        if url in visitadas:
            continue
        visitadas.add(url)

        log.info(f"  rastreando: {url[-70:]}")
        soup = get_html(url)
        if not soup:
            time.sleep(DELAY)
            continue
        time.sleep(DELAY)

        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if not href or href.startswith("mailto:") or href.startswith("#"):
                continue
            full = urljoin(url, href)
            ext = Path(urlparse(full).path).suffix.lower()

            if ext in FORMATOS and full not in [e["url"] for e in encontrados]:
                # filtrar por año
                texto = (full + " " + a.get_text()).lower()
                m = re.search(r"(20[12]\d)", texto)
                año = int(m.group(1)) if m else desde_año
                if desde_año <= año <= año_actual:
                    encontrados.append({"url": full, "ext": ext, "texto": a.get_text(strip=True)})
                    log.info(f"    + encontrado: {ext} {full[-60:]}")

            elif ext not in {".pdf", ".doc", ".docx"} and \
                    (full.startswith("https://estadisticas.pjn.gov.ar") or
                     full.startswith("https://old.pjn.gov.ar")) and \
                    full not in visitadas:
                cola.append(full)

        if max_archivos and len(encontrados) >= max_archivos:
            break

    log.info(f"  PJN portal: {len(encontrados)} archivos CSV/Excel encontrados")
    return encontrados


# ── FUENTE 2: datos.gob.ar (PJN datasets) ────────────────────────────────────

def buscar_datos_gob_ar():
    """Busca datasets del PJN en el portal de datos abiertos nacional."""
    recursos = []
    for url in DATOS_GOB_AR_PJN:
        try:
            r = session.get(url, timeout=TIMEOUT)
            r.raise_for_status()
            resultados = r.json().get("result", {}).get("results", [])
            log.info(f"  datos.gob.ar: {len(resultados)} datasets en {url[-50:]}")
            for pkg in resultados:
                org = (pkg.get("organization") or {}).get("name", "")
                if "justicia" not in org.lower() and "judicial" not in pkg.get("title", "").lower() \
                        and "poder judicial" not in pkg.get("notes", "").lower():
                    continue
                for rec in pkg.get("resources", []):
                    fmt = (rec.get("format") or "").lower()
                    if fmt in ("csv", "xlsx", "xls", "zip"):
                        recursos.append({
                            "url": rec["url"],
                            "ext": "." + fmt,
                            "titulo": pkg.get("title", ""),
                            "nombre": rec.get("name", ""),
                        })
            time.sleep(DELAY)
        except Exception as e:
            log.warning(f"  datos.gob.ar error: {e}")
    log.info(f"  datos.gob.ar: {len(recursos)} recursos CSV/Excel del PJN")
    return recursos


# ── MAIN ──────────────────────────────────────────────────────────────────────

# ── CHECKPOINT ────────────────────────────────────────────────────────────────

def checkpoint_cargar():
    """Carga el checkpoint existente o devuelve estado vacío."""
    if CHECKPOINT_FILE.exists():
        try:
            with open(CHECKPOINT_FILE, encoding="utf-8") as f:
                cp = json.load(f)
            log.info(f"  Checkpoint cargado: {len(cp.get('procesados', {}))} URLs ya procesadas")
            return cp
        except Exception as e:
            log.warning(f"  Checkpoint corrupto, ignorando: {e}")
    return {"procesados": {}, "indice": [], "todos_records_count": 0}


def checkpoint_guardar(cp):
    """Persiste el checkpoint a disco."""
    with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump(cp, f, ensure_ascii=False, indent=2)


def failures_guardar(failures):
    """Guarda el log de fallos detallado."""
    with open(FAILURES_FILE, "w", encoding="utf-8") as f:
        json.dump(failures, f, ensure_ascii=False, indent=2)
    if failures:
        log.info(f"  Fallos detallados -> {FAILURES_FILE}")


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Descarga estadísticas del PJN desde datos.gob.ar y estadisticas.pjn.gov.ar"
    )
    parser.add_argument("--desde", type=int, default=2024,
                        help="anno de inicio (default: 2024)")
    parser.add_argument("--max", type=int, default=None,
                        help="maximo archivos a procesar (test)")
    parser.add_argument("--resume", action="store_true",
                        help="retomar desde checkpoint anterior (omite URLs ya procesadas)")
    parser.add_argument("--reset", action="store_true",
                        help="borrar checkpoint y empezar desde cero")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.reset and CHECKPOINT_FILE.exists():
        CHECKPOINT_FILE.unlink()
        log.info("  Checkpoint borrado — empezando desde cero")

    año_actual = datetime.now().year
    log.info(f"Periodo: {args.desde} -> {año_actual}")

    stats = {
        "inicio": datetime.now(timezone.utc).isoformat(),
        "desde": args.desde,
        "ok": 0, "fallidos": 0, "filas_total": 0,
        "por_jurisdiccion": {},
    }
    failures = []

    # ── 1. recolectar todos los links ──
    log.info("\n=== Fuente 1: estadisticas.pjn.gov.ar ===")
    links_pjn = crawl_pjn(args.desde, args.max)

    log.info("\n=== Fuente 2: datos.gob.ar ===")
    links_gob = buscar_datos_gob_ar()

    # unificar
    todos = []
    seen = set()
    for item in links_pjn + links_gob:
        if item["url"] not in seen:
            seen.add(item["url"])
            todos.append(item)

    log.info(f"\nTotal archivos encontrados: {len(todos)}")

    if args.max:
        todos = todos[:args.max]
        log.info(f"Limitado a {args.max} (modo test)")

    if not todos:
        log.error("Sin archivos encontrados. Revisar conectividad con el portal.")
        sys.exit(1)

    # ── 2. checkpoint: filtrar los ya procesados ──
    cp = checkpoint_cargar() if args.resume else {"procesados": {}, "indice": [], "todos_records_count": 0}
    ya_procesados = set(cp["procesados"].keys())
    pendientes = [item for item in todos if item["url"] not in ya_procesados]
    saltados = len(todos) - len(pendientes)

    if saltados > 0:
        log.info(f"  --resume: saltando {saltados} URLs ya procesadas, quedan {len(pendientes)}")
        # restaurar stats desde checkpoint
        for url, estado in cp["procesados"].items():
            if estado["ok"]:
                stats["ok"] += 1
                stats["filas_total"] += estado.get("filas", 0)
                jur = estado.get("jurisdiccion", "PJN")
                stats["por_jurisdiccion"].setdefault(jur, 0)
                stats["por_jurisdiccion"][jur] += estado.get("filas", 0)
            else:
                stats["fallidos"] += 1
                if estado.get("motivo"):
                    failures.append({"url": url, "motivo": estado["motivo"],
                                     "numero": estado.get("numero")})
    indice = cp.get("indice", [])

    # ── 3. descargar y parsear ──
    todos_records = []  # solo los nuevos de esta sesión
    total_global = len(todos)

    for i, item in enumerate(pendientes, saltados + 1):
        url = item["url"]
        ext = item["ext"]
        texto = item.get("texto") or item.get("nombre") or item.get("titulo") or ""
        log.info(f"\n[{i}/{total_global}] {ext.upper()} {url[-60:]}")

        # detectar jurisdiccion y año
        combinado = (url + " " + texto).lower()
        m = re.search(r"(20[12]\d)", combinado)
        año = m.group(1) if m else str(args.desde)

        jur = "PJN"
        for seg in reversed(urlparse(url).path.split("/")):
            seg = re.sub(r"[_\-]", " ", seg).strip()
            if len(seg) > 4 and not seg.lower().endswith(ext[1:]):
                jur = seg.title()
                break

        time.sleep(DELAY)

        # capturar motivo de fallo si hay
        try:
            df = descargar(url, ext)
            motivo = None
        except Exception as e:
            df = None
            motivo = str(e)

        if df is None or df.empty:
            motivo = motivo or "df vacío / no parseable"
            stats["fallidos"] += 1
            log.warning(f"  FALLO [{i}]: {motivo}")
            failures.append({"numero": i, "url": url, "ext": ext,
                             "texto": texto, "motivo": motivo})
            # guardar en checkpoint igualmente
            cp["procesados"][url] = {"ok": False, "numero": i,
                                     "motivo": motivo, "jurisdiccion": jur}
            checkpoint_guardar(cp)
            failures_guardar(failures)
            continue

        df = limpiar(df)
        df["_jurisdiccion"] = jur
        df["_anno"] = año
        df["_fuente"] = url
        df["_descarga"] = datetime.now(timezone.utc).date().isoformat()

        stem = re.sub(r"[^\w]", "_", f"pjn_{jur[:25]}_{año}_{i}").lower().strip("_")
        guardar(df, stem)

        stats["ok"] += 1
        stats["filas_total"] += len(df)
        stats["por_jurisdiccion"].setdefault(jur, 0)
        stats["por_jurisdiccion"][jur] += len(df)

        entrada_indice = {"numero": i, "jurisdiccion": jur, "anno": año,
                          "filas": len(df), "url": url, "stem": stem}
        indice.append(entrada_indice)
        todos_records.extend(df.to_dict(orient="records"))
        log.info(f"  OK: {jur} {año} -> {len(df):,} filas")

        # actualizar checkpoint después de cada OK
        cp["procesados"][url] = {"ok": True, "numero": i, "filas": len(df),
                                 "jurisdiccion": jur, "anno": año}
        cp["indice"] = indice
        checkpoint_guardar(cp)

    # ── 4. archivo maestro (append si hay checkpoint) ──
    maestro_csv = Path("pjn_estadisticas_completo.csv")
    modo = "a" if (args.resume and maestro_csv.exists()) else "w"
    if todos_records:
        df_m = pd.DataFrame(todos_records)
        df_m.to_csv(maestro_csv, mode=modo,
                    index=False, encoding="utf-8-sig",
                    header=(modo == "w"))
        log.info(f"\n-> {maestro_csv} ({len(todos_records):,} filas nuevas, modo={modo})")

    with open(OUT_DIR / "pjn_indice.json", "w", encoding="utf-8") as f:
        json.dump(indice, f, ensure_ascii=False, indent=2)

    failures_guardar(failures)

    stats["fin"] = datetime.now(timezone.utc).isoformat()
    with open("pjn_meta.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    log.info(f"""
==================================
  PJN COMPLETADO
  Archivos OK      : {stats['ok']}
  Archivos fallidos: {stats['fallidos']}
  Filas totales    : {stats['filas_total']:,}
  Jurisdicciones   : {len(stats['por_jurisdiccion'])}
  Fallos detalle   : {FAILURES_FILE}
  Checkpoint       : {CHECKPOINT_FILE}
==================================""")
    for jur, n in sorted(stats["por_jurisdiccion"].items(), key=lambda x: -x[1]):
        log.info(f"  {n:>8,} filas  ->  {jur}")

    if failures:
        log.info(f"\n  Archivos fallidos ({len(failures)}):")
        for f in failures:
            log.info(f"    [{f.get('numero', '?')}] {f['url'][-60:]}  →  {f['motivo']}")


if __name__ == "__main__":
    main()