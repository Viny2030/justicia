"""
scraper_datos_jus_completo.py
─────────────────────────────────────────────────────────────────────
Descarga TODOS los datasets del Portal de Datos Abiertos de la
Justicia Argentina (datos.jus.gob.ar) usando la API CKAN v3.

Genera:
  datos_jus_<dataset_id>.csv       ← un CSV por dataset
  datos_jus_<dataset_id>.json      ← ídem en JSON
  datos_jus_index.json             ← índice maestro de todos los datasets
  datos_jus_meta.json              ← métricas de la corrida

Uso:
  python scraper_datos_jus_completo.py
  python scraper_datos_jus_completo.py --solo magistrados designaciones
"""

import os
import sys
import json
import time
import logging
import argparse
import requests
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone

# ── CONFIG ────────────────────────────────────────────────────────────────────
BASE_URL   = "https://datos.jus.gob.ar"
API_BASE   = f"{BASE_URL}/api/3/action"
OUT_DIR    = Path("datos_jus")          # carpeta de salida
DELAY      = 1.2                        # segundos entre requests
TIMEOUT    = 30
MAX_ROWS   = 500_000                    # seguridad: descartar recursos gigantes

# Datasets de interés principal (se descargan siempre)
DATASETS_PRIORITARIOS = [
    "magistrados-justicia-federal-y-de-la-justicia-nacional",
    "designaciones-de-magistrados-de-la-justicia-federal-y-la-justicia-nacional",
    "renuncias-de-magistrados-de-la-justicia-federal-y-de-la-justicia-nacional",
    "seleccion-de-magistrados-del-poder-judicial-y-el-ministerio-publico-de-la-nacion",
    "vacantes-concursos-abiertos",
    "estructura-organica-del-ministerio-de-justicia",
]

# Formatos aceptados (en orden de preferencia)
FORMATOS_OK = ["CSV", "csv", "XLSX", "xlsx", "XLS", "xls", "JSON", "json"]

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

def ckan_get(action: str, **params) -> dict:
    """Llama a la API CKAN y devuelve result."""
    url = f"{API_BASE}/{action}"
    r = session.get(url, params=params, timeout=TIMEOUT)
    r.raise_for_status()
    data = r.json()
    if not data.get("success"):
        raise ValueError(f"CKAN error en {action}: {data.get('error')}")
    return data["result"]


def descargar_recurso(url: str, nombre: str) -> pd.DataFrame | None:
    """Descarga un recurso CSV/Excel/JSON y lo convierte a DataFrame."""
    log.info(f"  ↓ descargando {nombre}")
    try:
        r = session.get(url, timeout=60, stream=True)
        r.raise_for_status()

        ext = Path(url.split("?")[0]).suffix.lower()
        if not ext:
            ct = r.headers.get("content-type", "")
            if "csv" in ct:         ext = ".csv"
            elif "excel" in ct:     ext = ".xlsx"
            elif "json" in ct:      ext = ".json"
            else:                   ext = ".csv"

        # guardar temporalmente
        tmp = Path(f"/tmp/_jus_tmp{ext}")
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)

        size_mb = tmp.stat().st_size / 1e6
        log.info(f"    tamaño: {size_mb:.2f} MB")

        if ext in (".csv",):
            for enc in ("utf-8-sig", "latin-1", "cp1252"):
                try:
                    df = pd.read_csv(tmp, encoding=enc, low_memory=False,
                                     dtype=str, na_values=["", "NULL", "N/A"])
                    break
                except Exception:
                    continue
            else:
                raise ValueError("no se pudo leer el CSV con ningún encoding")

        elif ext in (".xlsx", ".xls"):
            df = pd.read_excel(tmp, dtype=str)

        elif ext in (".json",):
            df = pd.read_json(tmp, dtype=str)

        else:
            log.warning(f"    formato desconocido: {ext}")
            return None

        if len(df) > MAX_ROWS:
            log.warning(f"    truncando a {MAX_ROWS:,} filas ({len(df):,} totales)")
            df = df.head(MAX_ROWS)

        # limpiar nombres de columnas
        df.columns = (
            df.columns.str.strip()
                      .str.lower()
                      .str.replace(r"\s+", "_", regex=True)
                      .str.replace(r"[^\w]", "_", regex=True)
        )
        df = df.fillna("")
        log.info(f"    ✓ {len(df):,} filas × {len(df.columns)} columnas")
        return df

    except Exception as e:
        log.error(f"    ✗ error: {e}")
        return None


def guardar_df(df: pd.DataFrame, stem: str):
    """Guarda DataFrame como CSV + JSON en OUT_DIR."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path  = OUT_DIR / f"{stem}.csv"
    json_path = OUT_DIR / f"{stem}.json"

    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    records = df.to_dict(orient="records")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    log.info(f"    → {csv_path}  ({len(df):,} filas)")
    return str(csv_path), str(json_path)


# ── LÓGICA PRINCIPAL ──────────────────────────────────────────────────────────

def procesar_dataset(pkg_id: str, stats: dict) -> dict | None:
    """Descarga y guarda todos los recursos CSV/Excel de un dataset."""
    try:
        pkg = ckan_get("package_show", id=pkg_id)
    except Exception as e:
        log.warning(f"No se pudo obtener metadata de '{pkg_id}': {e}")
        return None

    nombre     = pkg.get("title", pkg_id)
    recursos   = pkg.get("resources", [])
    resultados = []

    log.info(f"\n📦 [{pkg_id}]  '{nombre}'  ({len(recursos)} recursos)")

    for rec in recursos:
        fmt = (rec.get("format") or "").upper()
        url = rec.get("url", "")
        rec_name = rec.get("name", rec.get("id", "sin_nombre"))

        if not url:
            continue
        if fmt not in [f.upper() for f in FORMATOS_OK]:
            log.debug(f"  skip formato {fmt}: {rec_name}")
            continue

        stem = f"datos_jus_{pkg_id}_{rec.get('id','')[:8]}"
        df   = descargar_recurso(url, rec_name)
        time.sleep(DELAY)

        if df is None or df.empty:
            stats["recursos_fallidos"] += 1
            continue

        csv_p, json_p = guardar_df(df, stem)
        stats["recursos_ok"] += 1
        stats["filas_total"]  += len(df)

        resultados.append({
            "recurso_id":   rec.get("id"),
            "recurso_name": rec_name,
            "formato":      fmt,
            "url":          url,
            "filas":        len(df),
            "columnas":     list(df.columns),
            "csv":          csv_p,
            "json":         json_p,
        })

    if not resultados:
        return None

    return {
        "dataset_id":    pkg_id,
        "titulo":        nombre,
        "descripcion":   pkg.get("notes", ""),
        "organizacion":  (pkg.get("organization") or {}).get("name", ""),
        "tags":          [t["name"] for t in pkg.get("tags", [])],
        "recursos":      resultados,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--solo", nargs="*",
                        help="procesar solo estos dataset IDs")
    parser.add_argument("--todos", action="store_true",
                        help="descargar TODOS los datasets del portal")
    args = parser.parse_args()

    stats = {
        "inicio":           datetime.now(timezone.utc).isoformat(),
        "datasets_ok":      0,
        "datasets_fallidos":0,
        "recursos_ok":      0,
        "recursos_fallidos":0,
        "filas_total":      0,
    }

    # ── elegir lista de datasets ──
    if args.solo:
        ids = args.solo
        log.info(f"Modo selectivo: {ids}")

    elif args.todos:
        log.info("Obteniendo lista completa de datasets del portal...")
        try:
            ids = ckan_get("package_list")
            log.info(f"Total datasets disponibles: {len(ids)}")
        except Exception as e:
            log.error(f"No se pudo obtener la lista: {e}")
            sys.exit(1)

    else:
        # modo por defecto: datasets prioritarios + búsqueda por tags judiciales
        log.info("Modo default: datasets prioritarios + judiciales")
        ids = list(DATASETS_PRIORITARIOS)

        try:
            busqueda = ckan_get("package_search",
                                q="tags:judiciales OR tags:magistrados OR tags:juzgados",
                                rows=100)
            extra = [p["name"] for p in busqueda.get("results", [])]
            for e in extra:
                if e not in ids:
                    ids.append(e)
            log.info(f"Datasets encontrados: {len(ids)}")
        except Exception as e:
            log.warning(f"Búsqueda adicional falló (continuando): {e}")

    # ── procesar ──
    indice = []
    for i, pkg_id in enumerate(ids, 1):
        log.info(f"\n[{i}/{len(ids)}] {pkg_id}")
        resultado = procesar_dataset(pkg_id, stats)

        if resultado:
            indice.append(resultado)
            stats["datasets_ok"] += 1
        else:
            stats["datasets_fallidos"] += 1

        time.sleep(DELAY)

    # ── guardar índice maestro ──
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    idx_path = OUT_DIR / "datos_jus_index.json"
    with open(idx_path, "w", encoding="utf-8") as f:
        json.dump(indice, f, ensure_ascii=False, indent=2)

    stats["fin"]              = datetime.now(timezone.utc).isoformat()
    stats["datasets_en_indice"] = len(indice)

    meta_path = OUT_DIR / "datos_jus_meta.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    log.info(f"""
╔══════════════════════════════════╗
║  datos.jus.gob.ar  COMPLETADO   ║
╠══════════════════════════════════╣
║  Datasets OK      : {stats['datasets_ok']:>6}       ║
║  Datasets fallidos: {stats['datasets_fallidos']:>6}       ║
║  Recursos OK      : {stats['recursos_ok']:>6}       ║
║  Recursos fallidos: {stats['recursos_fallidos']:>6}       ║
║  Filas totales    : {stats['filas_total']:>6,}       ║
╚══════════════════════════════════╝
""")


if __name__ == "__main__":
    main()