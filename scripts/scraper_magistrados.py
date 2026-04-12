#!/usr/bin/env python3
"""
scraper_magistrados.py
======================
Descarga nómina de magistrados, designaciones y renuncias
desde datos.jus.gob.ar y exporta JSON para el frontend.

FUENTES:
  - Magistrados activos     → datos.jus.gob.ar (CSV)
  - Designaciones           → datos.jus.gob.ar (CSV)
  - Renuncias               → datos.jus.gob.ar (CSV)

OUTPUT:
  - data/magistrados.json
  - data/designaciones.json
  - data/vacantes.json
  - data/meta_justicia.json
"""

import os
import json
import logging
import requests
import pandas as pd
from io import StringIO
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

# ── Rutas ─────────────────────────────────────────────────────────────────────
BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_DIR  = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

# ── URLs datos.jus.gob.ar ─────────────────────────────────────────────────────
API_BASE = "https://datos.jus.gob.ar/api/3/action/package_search"

DATASETS = {
    "magistrados": {
        "query":  "magistrados justicia federal nacional",
        "titulo": "Magistrados de la Justicia Federal",
        "output": "magistrados.json",
    },
    "designaciones": {
        "query":  "designaciones magistrados justicia federal",
        "titulo": "Designaciones de magistrados",
        "output": "designaciones.json",
    },
    "renuncias": {
        "query":  "renuncias magistrados justicia federal",
        "titulo": "Renuncias de magistrados",
        "output": "renuncias.json",
    },
}

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


# ── Helpers ───────────────────────────────────────────────────────────────────
def obtener_url_csv(query, titulo_contiene):
    """Busca en la API el dataset que coincide con el título y retorna la URL del CSV más reciente."""
    r = requests.get(API_BASE, params={"q": query, "rows": 10}, headers=HEADERS, timeout=15)
    r.raise_for_status()
    results = r.json()["result"]["results"]

    for dataset in results:
        if titulo_contiene.lower() in dataset["title"].lower():
            # Buscar el CSV más reciente (no ZIP)
            csvs = [
                res for res in dataset.get("resources", [])
                if res.get("format", "").upper() == "CSV"
            ]
            if csvs:
                # Ordenar por nombre descendente para obtener el más reciente
                csvs.sort(key=lambda x: x.get("name", ""), reverse=True)
                return csvs[0]["url"]
    return None


def descargar_csv(url):
    """Descarga un CSV y retorna un DataFrame con encoding corregido."""
    log.info(f"Descargando: {url[:80]}...")
    r = requests.get(url, headers=HEADERS, timeout=60)
    r.raise_for_status()

    # Fix encoding UTF-8 BOM
    contenido = r.content.decode("utf-8-sig", errors="replace")
    df = pd.read_csv(StringIO(contenido))

    # Limpiar nombres de columnas (BOM residual)
    df.columns = [c.strip().strip('"').strip() for c in df.columns]

    log.info(f"  → {len(df)} filas, {len(df.columns)} columnas")
    return df


def limpiar_magistrados(df):
    """Normaliza el DataFrame de magistrados activos."""
    cols_map = {
        "orden":                       "orden",
        "justicia_federal_o_nacional": "tipo_justicia",
        "camara":                      "camara",
        "organo_tipo":                 "organo_tipo",
        "organo_nombre":               "organo_nombre",
        "organo_habilitado":           "organo_habilitado",
        "cargo_tipo":                  "cargo_tipo",
        "magistrado_nombre":           "nombre",
        "magistrado_dni":              "dni",
        "magistrado_genero":           "genero",
        "cargo_cobertura":             "cobertura",
        "cargo_fecha_jura":            "fecha_jura",
        "cargo_vacante":               "vacante",
        "cargo_licencia":              "licencia",
        "norma_tipo":                  "norma_tipo",
        "norma_numero":                "norma_numero",
        "norma_fecha":                 "norma_fecha",
        "norma_presidente":            "presidente_designante",
        "organo_provincia":            "provincia",
        "concurso_en_tramite":         "concurso_en_tramite",
    }

    # Renombrar columnas que existen
    rename = {k: v for k, v in cols_map.items() if k in df.columns}
    df = df.rename(columns=rename)

    # Seleccionar solo las columnas que necesitamos
    cols_keep = [v for v in cols_map.values() if v in df.columns]
    df = df[cols_keep].copy()

    # Limpiar tipos
    df["vacante"]  = df.get("vacante", "").fillna("NO").astype(str).str.strip()
    df["licencia"] = df.get("licencia", "").fillna("NO").astype(str).str.strip()
    df["genero"]   = df.get("genero", "").fillna("No informado").astype(str).str.strip()
    df["provincia"]= df.get("provincia", "").fillna("").astype(str).str.strip()

    return df


def exportar_json(df, path, max_rows=2000):
    """Exporta DataFrame a JSON limpio."""
    registros = df.head(max_rows).where(pd.notnull(df), None).to_dict(orient="records")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(registros, f, ensure_ascii=False, indent=2, default=str)
    log.info(f"  → Exportado: {path} ({len(registros)} registros)")


def calcular_kpis(df_mag, df_des, df_ren):
    """Calcula KPIs para el frontend."""
    total = len(df_mag)
    vacantes = len(df_mag[df_mag.get("vacante", pd.Series()) == "SI"]) if "vacante" in df_mag.columns else 0
    con_licencia = len(df_mag[df_mag.get("licencia", pd.Series()) == "SI"]) if "licencia" in df_mag.columns else 0
    titulares = len(df_mag[df_mag.get("cobertura", pd.Series()) == "Titular"]) if "cobertura" in df_mag.columns else 0
    femenino = len(df_mag[df_mag.get("genero", pd.Series()) == "Femenino"]) if "genero" in df_mag.columns else 0

    # Por provincia
    por_provincia = {}
    if "provincia" in df_mag.columns:
        por_provincia = df_mag["provincia"].value_counts().head(10).to_dict()

    # Por tipo de cargo
    por_cargo = {}
    if "cargo_tipo" in df_mag.columns:
        por_cargo = df_mag["cargo_tipo"].value_counts().head(10).to_dict()

    # Designaciones recientes por presidente
    por_presidente = {}
    if "presidente_designante" in df_mag.columns:
        por_presidente = df_mag["presidente_designante"].value_counts().head(8).to_dict()

    return {
        "generado_en":     datetime.now().isoformat(),
        "total_magistrados": total,
        "vacantes":        vacantes,
        "pct_vacantes":    round(vacantes / total * 100, 1) if total else 0,
        "con_licencia":    con_licencia,
        "titulares":       titulares,
        "femenino":        femenino,
        "pct_femenino":    round(femenino / total * 100, 1) if total else 0,
        "designaciones_total": len(df_des),
        "renuncias_total": len(df_ren),
        "por_provincia":   {str(k): int(v) for k, v in por_provincia.items()},
        "por_cargo":       {str(k): int(v) for k, v in por_cargo.items()},
        "por_presidente":  {str(k): int(v) for k, v in por_presidente.items()},
    }


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    log.info("=" * 60)
    log.info("SCRAPER MAGISTRADOS — datos.jus.gob.ar")
    log.info(f"  {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    log.info("=" * 60)

    # ── 1. Magistrados activos ────────────────────────────────────────────────
    log.info("\n[1] Magistrados activos...")
    url_mag = obtener_url_csv(
        DATASETS["magistrados"]["query"],
        DATASETS["magistrados"]["titulo"]
    )
    if not url_mag:
        log.error("No se encontró URL para magistrados")
        return
    df_mag = descargar_csv(url_mag)
    df_mag = limpiar_magistrados(df_mag)
    exportar_json(df_mag, os.path.join(DATA_DIR, "magistrados.json"))

    # ── 2. Designaciones ─────────────────────────────────────────────────────
    log.info("\n[2] Designaciones...")
    url_des = obtener_url_csv(
        DATASETS["designaciones"]["query"],
        DATASETS["designaciones"]["titulo"]
    )
    df_des = pd.DataFrame()
    if url_des:
        df_des = descargar_csv(url_des)
        df_des.columns = [c.strip().strip('"') for c in df_des.columns]
        exportar_json(df_des, os.path.join(DATA_DIR, "designaciones.json"))
    else:
        log.warning("No se encontró URL para designaciones")

    # ── 3. Renuncias ──────────────────────────────────────────────────────────
    log.info("\n[3] Renuncias...")
    url_ren = obtener_url_csv(
        DATASETS["renuncias"]["query"],
        DATASETS["renuncias"]["titulo"]
    )
    df_ren = pd.DataFrame()
    if url_ren:
        df_ren = descargar_csv(url_ren)
        df_ren.columns = [c.strip().strip('"') for c in df_ren.columns]
        exportar_json(df_ren, os.path.join(DATA_DIR, "renuncias.json"))
    else:
        log.warning("No se encontró URL para renuncias")

    # ── 4. KPIs y meta ───────────────────────────────────────────────────────
    log.info("\n[4] Calculando KPIs...")
    kpis = calcular_kpis(df_mag, df_des, df_ren)
    meta_path = os.path.join(DATA_DIR, "meta_justicia.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(kpis, f, ensure_ascii=False, indent=2)
    log.info(f"  → KPIs exportados: {meta_path}")

    # ── 5. Vacantes (subconjunto para alertas) ────────────────────────────────
    log.info("\n[5] Exportando vacantes...")
    if "vacante" in df_mag.columns:
        df_vac = df_mag[df_mag["vacante"] == "SI"].copy()
        exportar_json(df_vac, os.path.join(DATA_DIR, "vacantes.json"), max_rows=500)

    log.info("\n" + "=" * 60)
    log.info("RESUMEN")
    log.info(f"  Magistrados : {kpis['total_magistrados']}")
    log.info(f"  Vacantes    : {kpis['vacantes']} ({kpis['pct_vacantes']}%)")
    log.info(f"  Femenino    : {kpis['femenino']} ({kpis['pct_femenino']}%)")
    log.info(f"  Designaciones: {kpis['designaciones_total']}")
    log.info(f"  Renuncias   : {kpis['renuncias_total']}")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
