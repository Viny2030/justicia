"""
scraper_pjn_completo.py
─────────────────────────────────────────────────────────────────────
Descarga y procesa las estadísticas de TODOS los juzgados del
Poder Judicial de la Nación desde estadisticas.pjn.gov.ar

Estrategia:
  1. Scrapea el índice HTML del portal para encontrar TODOS los
     links a archivos (CSV, Excel, PDF).
  2. Descarga cada archivo.
  3. Parsea tablas usando pandas (CSV/Excel) o pdfplumber (PDF).
  4. Unifica en un JSON maestro + CSVs por jurisdicción.

Genera:
  pjn_estadisticas/
    <jurisdiccion>_<año>.csv
    <jurisdiccion>_<año>.json
  pjn_estadisticas_completo.json   ← todos los registros unificados
  pjn_estadisticas_completo.csv
  pjn_meta.json

Uso:
  python scraper_pjn_completo.py                  # 2024 a hoy (default)
  python scraper_pjn_completo.py --desde 2024     # explícito
  python scraper_pjn_completo.py --desde 2023     # desde 2023
  python scraper_pjn_completo.py --desde 2024 --max 50  # test
"""

import os
import re
import sys
import csv
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
BASE_URL = "https://estadisticas.pjn.gov.ar"

# Rutas del portal (nueva versión + fallback a la antigua)
INDEX_URLS = [
    f"{BASE_URL}/",
    f"{BASE_URL}/07_estadisticas/estadisticas/07_estadisticas/index.php",
    "https://old.pjn.gov.ar/07_estadisticas/estadisticas/07_estadisticas/index.php",
]

OUT_DIR = Path("pjn_estadisticas")
DELAY = 1.5
TIMEOUT = 45

# Las 22 jurisdicciones conocidas del PJN
JURISDICCIONES = [
    "Buenos Aires Capital Federal",
    "Bahía Blanca",
    "Comodoro Rivadavia",
    "Córdoba",
    "Corrientes",
    "General Roca",
    "La Plata",
    "Mar del Plata",
    "Mendoza",
    "Paraná",
    "Posadas",
    "Resistencia",
    "Rosario",
    "Salta",
    "San Justo",
    "San Martín",
    "San Rafael",
    "Santa Fe",
    "Santiago del Estero",
    "Tucumán",
    # Fueros nacionales con sede en CABA
    "Justicia Nacional en lo Civil",
    "Justicia Nacional en lo Comercial",
    "Justicia Nacional en lo Criminal y Correccional",
    "Justicia Nacional del Trabajo",
    "Justicia Nacional en lo Contencioso Administrativo Federal",
    "Justicia Nacional en lo Penal Económico",
    "Cámara Federal de Casación Penal",
    "Cámara Federal de la Seguridad Social",
    "Cámara Nacional Electoral",
]

FORMATOS_DESCARGABLES = {".csv", ".xlsx", ".xls", ".zip"}
FORMATOS_PDF = {".pdf"}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

session = requests.Session()
session.headers.update({
    "User-Agent": "MonitorJudicialAR/2.0 (github.com/Viny2030/justicia)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
})


# ── HELPERS ───────────────────────────────────────────────────────────────────

def get_html(url: str) -> BeautifulSoup | None:
    try:
        r = session.get(url, timeout=TIMEOUT)
        r.raise_for_status()
        return BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        log.warning(f"  HTML error {url}: {e}")
        return None


def extraer_links(soup: BeautifulSoup, base: str) -> list[dict]:
    """Extrae todos los links a archivos descargables del HTML."""
    links = []
    seen = set()

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith("#") or href.startswith("mailto:"):
            continue

        url = urljoin(base, href)
        ext = Path(urlparse(url).path).suffix.lower()
        text = a.get_text(strip=True)

        if ext not in FORMATOS_DESCARGABLES | FORMATOS_PDF:
            continue
        if url in seen:
            continue
        seen.add(url)

        links.append({
            "url": url,
            "extension": ext,
            "texto": text,
            "es_pdf": ext in FORMATOS_PDF,
        })

    return links


def detectar_jurisdiccion_año(url: str, texto: str) -> tuple[str, str]:
    """Intenta inferir jurisdicción y año desde la URL o texto del link."""
    texto_lower = (url + " " + texto).lower()

    # año
    m = re.search(r"(20[12]\d)", texto_lower)
    año = m.group(1) if m else "desconocido"

    # jurisdicción
    for j in JURISDICCIONES:
        if any(p in texto_lower for p in j.lower().split()[:2]):
            return j, año

    # fallback: tomar segmentos de la URL
    partes = urlparse(url).path.split("/")
    for p in reversed(partes):
        p = p.replace("_", " ").replace("-", " ").strip()
        if len(p) > 4 and not p.lower().endswith((".csv", ".xlsx", ".pdf")):
            return p.title(), año

    return "Sin clasificar", año


def parsear_csv(contenido_bytes: bytes) -> pd.DataFrame | None:
    for enc in ("utf-8-sig", "latin-1", "cp1252", "utf-8"):
        try:
            texto = contenido_bytes.decode(enc)
            df = pd.read_csv(
                StringIO(texto),
                sep=None,  # detecta ; o ,
                engine="python",
                dtype=str,
                na_values=["", "NULL", "N/A", "S/D"],
                low_memory=False,
            )
            if not df.empty:
                return df
        except Exception:
            continue
    return None


def parsear_excel(path_tmp: Path) -> pd.DataFrame | None:
    try:
        xl = pd.ExcelFile(path_tmp)
        frames = []
        for hoja in xl.sheet_names:
            df = xl.parse(hoja, dtype=str)
            if not df.empty:
                df["_hoja"] = hoja
                frames.append(df)
        if frames:
            return pd.concat(frames, ignore_index=True)
    except Exception as e:
        log.warning(f"    Excel error: {e}")
    return None


def parsear_pdf_tablas(path_tmp: Path) -> pd.DataFrame | None:
    """Extrae tablas de un PDF con pdfplumber."""
    try:
        import pdfplumber
        frames = []
        with pdfplumber.open(path_tmp) as pdf:
            for i, page in enumerate(pdf.pages):
                for tabla in (page.extract_tables() or []):
                    if not tabla or not tabla[0]:
                        continue
                    encabezado = [str(c).strip() if c else f"col_{j}"
                                  for j, c in enumerate(tabla[0])]
                    filas = [
                        {encabezado[k]: str(v).strip() if v else ""
                         for k, v in enumerate(fila)}
                        for fila in tabla[1:]
                    ]
                    if filas:
                        df = pd.DataFrame(filas)
                        df["_pagina_pdf"] = i + 1
                        frames.append(df)
        if frames:
            return pd.concat(frames, ignore_index=True)
    except ImportError:
        log.warning("    pdfplumber no instalado — saltando PDFs")
    except Exception as e:
        log.warning(f"    PDF parse error: {e}")
    return None


def descargar_y_parsear(link: dict) -> pd.DataFrame | None:
    url = link["url"]
    ext = link["extension"]
    log.info(f"  ↓ {ext.upper():<5} {url[-70:]}")

    try:
        r = session.get(url, timeout=60, stream=True)
        r.raise_for_status()

        tmp = Path(f"/tmp/_pjn_tmp{ext}")
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(16384):
                f.write(chunk)

        size_kb = tmp.stat().st_size / 1024
        log.info(f"    {size_kb:.1f} KB")

        if ext == ".zip":
            import zipfile, tempfile
            frames = []
            with zipfile.ZipFile(tmp) as z:
                for name in z.namelist():
                    inner_ext = Path(name).suffix.lower()
                    with z.open(name) as inner:
                        content = inner.read()
                    if inner_ext == ".csv":
                        df = parsear_csv(content)
                    elif inner_ext in (".xlsx", ".xls"):
                        p2 = Path(f"/tmp/_pjn_inner{inner_ext}")
                        p2.write_bytes(content)
                        df = parsear_excel(p2)
                    else:
                        continue
                    if df is not None:
                        df["_archivo_zip"] = name
                        frames.append(df)
            return pd.concat(frames, ignore_index=True) if frames else None

        elif ext == ".csv":
            return parsear_csv(tmp.read_bytes())

        elif ext in (".xlsx", ".xls"):
            return parsear_excel(tmp)

        elif ext == ".pdf":
            return parsear_pdf_tablas(tmp)

    except Exception as e:
        log.error(f"    ✗ error descargando: {e}")

    return None


def limpiar_df(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = (
        df.columns.astype(str)
        .str.strip()
        .str.lower()
        .str.replace(r"\s+", "_", regex=True)
        .str.replace(r"[^\w]", "_", regex=True)
        .str.strip("_")
    )
    df = df.fillna("").copy()
    # quitar filas completamente vacías
    df = df[df.apply(lambda r: any(v.strip() for v in r.values if isinstance(v, str)), axis=1)]
    return df


def guardar(df: pd.DataFrame, stem: str):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_p = OUT_DIR / f"{stem}.csv"
    json_p = OUT_DIR / f"{stem}.json"
    df.to_csv(csv_p, index=False, encoding="utf-8-sig")
    with open(json_p, "w", encoding="utf-8") as f:
        json.dump(df.to_dict(orient="records"), f, ensure_ascii=False, indent=2)
    return str(csv_p), str(json_p)


# ── DISCOVERY ─────────────────────────────────────────────────────────────────

def descubrir_links_portal(desde_año: int = 2024) -> list[dict]:
    """Recorre el portal y recolecta todos los links descargables desde desde_año."""
    todos_links = []
    urls_visitadas = set()
    año_actual = datetime.now().year

    # Páginas a visitar (índice + sub-páginas)
    cola = list(INDEX_URLS)

    for url_actual in cola[:8]:  # máximo 8 páginas de índice
        if url_actual in urls_visitadas:
            continue
        urls_visitadas.add(url_actual)

        log.info(f"🔍 scrapeando índice: {url_actual}")
        soup = get_html(url_actual)
        if not soup:
            continue
        time.sleep(DELAY)

        links = extraer_links(soup, url_actual)
        log.info(f"   {len(links)} archivos encontrados")

        # filtrar: solo años >= desde_año y <= año_actual
        for lnk in links:
            jur, año = detectar_jurisdiccion_año(lnk["url"], lnk["texto"])
            if año != "desconocido":
                try:
                    if not (desde_año <= int(año) <= año_actual):
                        continue
                except ValueError:
                    pass
            todos_links.append(lnk)

        # agregar sub-páginas HTML a la cola
        for a in soup.find_all("a", href=True):
            href = a["href"]
            sub = urljoin(url_actual, href)
            ext = Path(urlparse(sub).path).suffix.lower() if sub else ""
            if (sub.startswith(BASE_URL) or
                sub.startswith("https://old.pjn.gov.ar")) and \
                    str(ext) not in FORMATOS_DESCARGABLES and \
                    sub not in urls_visitadas and \
                    len(cola) < 30:
                cola.append(sub)

    # deduplicar
    seen = set()
    uniq = []
    for lnk in todos_links:
        if lnk["url"] not in seen:
            seen.add(lnk["url"])
            uniq.append(lnk)

    log.info(f"\nTotal links únicos encontrados: {len(uniq)}")
    return uniq


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--desde", type=int, default=2024,
                        help="año de inicio (default: 2024, incluye hasta hoy)")
    parser.add_argument("--max", type=int, default=None,
                        help="máximo de archivos a procesar (test)")
    parser.add_argument("--pdf", action="store_true",
                        help="incluir PDFs (requiere pdfplumber)")
    args = parser.parse_args()

    año_actual = datetime.now().year
    log.info(f"Período: {args.desde} → {año_actual}")

    stats = {
        "inicio": datetime.now(timezone.utc).isoformat(),
        "desde_año": args.desde,
        "hasta_año": año_actual,
        "ok": 0,
        "fallidos": 0,
        "filas_total": 0,
        "por_jurisdiccion": {},
    }

    # ── 1. discovery ──
    links = descubrir_links_portal(desde_año=args.desde)

    if not args.pdf:
        links = [l for l in links if not l["es_pdf"]]
        log.info(f"PDFs excluidos — {len(links)} archivos a procesar")

    if args.max:
        links = links[:args.max]
        log.info(f"Limitado a {args.max} archivos (modo test)")

    if not links:
        log.error("No se encontraron archivos. Verificar conectividad con el portal.")
        sys.exit(1)

    # ── 2. descargar y parsear ──
    todos_records = []
    indice = []

    for i, lnk in enumerate(links, 1):
        log.info(f"\n[{i}/{len(links)}]")
        jur, año = detectar_jurisdiccion_año(lnk["url"], lnk["texto"])
        time.sleep(DELAY)

        df = descargar_y_parsear(lnk)
        if df is None or df.empty:
            stats["fallidos"] += 1
            continue

        df = limpiar_df(df)
        df["_jurisdiccion"] = jur
        df["_año"] = año
        df["_fuente_url"] = lnk["url"]
        df["_descarga"] = datetime.now(timezone.utc).date().isoformat()

        stem = re.sub(r"[^\w]", "_",
                      f"pjn_{jur[:30]}_{año}_{i}").lower().strip("_")
        csv_p, json_p = guardar(df, stem)

        stats["ok"] += 1
        stats["filas_total"] += len(df)
        stats["por_jurisdiccion"].setdefault(jur, 0)
        stats["por_jurisdiccion"][jur] += len(df)

        indice.append({
            "jurisdiccion": jur,
            "año": año,
            "filas": len(df),
            "columnas": list(df.columns),
            "url_fuente": lnk["url"],
            "csv": csv_p,
            "json": json_p,
        })

        todos_records.extend(df.to_dict(orient="records"))
        log.info(f"  ✓ {jur} {año}  →  {len(df):,} filas")

    # ── 3. archivo maestro ──
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if todos_records:
        df_master = pd.DataFrame(todos_records)
        master_csv = "pjn_estadisticas_completo.csv"
        master_json = "pjn_estadisticas_completo.json"

        df_master.to_csv(master_csv, index=False, encoding="utf-8-sig")
        with open(master_json, "w", encoding="utf-8") as f:
            json.dump(todos_records, f, ensure_ascii=False, indent=2)

        log.info(f"\n→ {master_csv}  ({len(todos_records):,} filas totales)")
    else:
        log.warning("Sin datos para el archivo maestro.")

    # ── 4. índice + meta ──
    with open(OUT_DIR / "pjn_indice.json", "w", encoding="utf-8") as f:
        json.dump(indice, f, ensure_ascii=False, indent=2)

    stats["fin"] = datetime.now(timezone.utc).isoformat()
    stats["archivos_en_indice"] = len(indice)

    with open("pjn_meta.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    log.info(f"""
╔══════════════════════════════════════════╗
║  estadisticas.pjn.gov.ar  COMPLETADO    ║
╠══════════════════════════════════════════╣
║  Archivos OK      : {stats['ok']:>6}             ║
║  Archivos fallidos: {stats['fallidos']:>6}             ║
║  Filas totales    : {stats['filas_total']:>10,}       ║
║  Jurisdicciones   : {len(stats['por_jurisdiccion']):>6}             ║
╚══════════════════════════════════════════╝
""")
    for jur, n in sorted(stats["por_jurisdiccion"].items(), key=lambda x: -x[1]):
        log.info(f"  {n:>8,} filas  →  {jur}")


if __name__ == "__main__":
    main()