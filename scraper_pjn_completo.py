
"""
scraper_pjn_completo.py
Descarga estadisticas de todos los juzgados del PJN desde 2024.
Fuentes: estadisticas.pjn.gov.ar (CSV/Excel) + datos.gob.ar (PJN datasets)
NO procesa PDFs.
"""

import re
import sys
import json
import time
import logging
import argparse
import requests
import pandas as pd
from io import StringIO
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
    for enc in ("utf-8-sig", "latin-1", "cp1252", "utf-8"):
        try:
            texto = content_bytes.decode(enc)
            df = pd.read_csv(
                StringIO(texto), sep=None, engine="python",
                dtype=str, na_values=["", "NULL", "N/A", "S/D"], low_memory=False
            )
            if not df.empty:
                return df
        except Exception:
            continue
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


def descargar(url, ext):
    try:
        r = session.get(url, timeout=60, stream=True)
        r.raise_for_status()
        tmp = Path(f"C:/Temp/_pjn_tmp{ext}") if sys.platform == "win32" else Path(f"/tmp/_pjn_tmp{ext}")
        tmp.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(16384):
                f.write(chunk)

        size_kb = tmp.stat().st_size / 1024
        log.info(f"    {size_kb:.1f} KB")

        if ext == ".zip":
            import zipfile
            frames = []
            with zipfile.ZipFile(tmp) as z:
                for name in z.namelist():
                    inner_ext = Path(name).suffix.lower()
                    content = z.read(name)
                    if inner_ext == ".csv":
                        df = parsear_csv(content)
                    elif inner_ext in (".xlsx", ".xls"):
                        p2 = tmp.parent / f"_inner{inner_ext}"
                        p2.write_bytes(content)
                        df = parsear_excel(p2)
                    else:
                        continue
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
                if "justicia" not in org.lower() and "judicial" not in pkg.get("title", "").lower():
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

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--desde", type=int, default=2024,
                        help="anno de inicio (default: 2024)")
    parser.add_argument("--max", type=int, default=None,
                        help="maximo archivos a procesar (test)")
    args = parser.parse_args()

    año_actual = datetime.now().year
    log.info(f"Periodo: {args.desde} -> {año_actual}")

    stats = {
        "inicio": datetime.now(timezone.utc).isoformat(),
        "desde": args.desde,
        "ok": 0, "fallidos": 0, "filas_total": 0,
        "por_jurisdiccion": {},
    }

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

    log.info(f"\nTotal archivos a descargar: {len(todos)}")

    if args.max:
        todos = todos[:args.max]
        log.info(f"Limitado a {args.max} (modo test)")

    if not todos:
        log.error("Sin archivos encontrados. Revisar conectividad con el portal.")
        sys.exit(1)

    # ── 2. descargar y parsear ──
    todos_records = []
    indice = []

    for i, item in enumerate(todos, 1):
        url = item["url"]
        ext = item["ext"]
        texto = item.get("texto") or item.get("nombre") or item.get("titulo") or ""
        log.info(f"\n[{i}/{len(todos)}] {ext.upper()} {url[-60:]}")

        # detectar jurisdiccion y año desde la URL/texto
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
        df = descargar(url, ext)

        if df is None or df.empty:
            stats["fallidos"] += 1
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

        indice.append({"jurisdiccion": jur, "anno": año, "filas": len(df), "url": url})
        todos_records.extend(df.to_dict(orient="records"))
        log.info(f"  OK: {jur} {año} -> {len(df):,} filas")

    # ── 3. archivo maestro ──
    if todos_records:
        df_m = pd.DataFrame(todos_records)
        df_m.to_csv("pjn_estadisticas_completo.csv", index=False, encoding="utf-8-sig")
        with open("pjn_estadisticas_completo.json", "w", encoding="utf-8") as f:
            json.dump(todos_records, f, ensure_ascii=False, indent=2)
        log.info(f"\n-> pjn_estadisticas_completo.csv ({len(todos_records):,} filas totales)")

    with open(OUT_DIR / "pjn_indice.json", "w", encoding="utf-8") as f:
        json.dump(indice, f, ensure_ascii=False, indent=2)

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
==================================""")
    for jur, n in sorted(stats["por_jurisdiccion"].items(), key=lambda x: -x[1]):
        log.info(f"  {n:>8,} filas  ->  {jur}")


if __name__ == "__main__":
    main()