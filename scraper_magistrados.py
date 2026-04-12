"""
scraper_magistrados.py
Monitor de Transparencia Judicial - Consejo de la Magistratura PJN
Genera: magistrados.json, vacantes.json, renuncias.json, designaciones.json, meta_justicia.json
Fuente: datos.jus.gob.ar (dataset público oficial)
Autor: Monitor Justicia AR | github.com/Viny2030/justicia
"""

import requests
import json
import pandas as pd
from datetime import datetime, date
import os
import sys
import logging
import codecs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger(__name__)

# ── Configuración ─────────────────────────────────────────────────────────────

# Dataset público del Ministerio de Justicia (CKAN / datos.gob.ar)
DATASET_BASE = "https://datos.jus.gob.ar/api/3/action/datastore_search"
RESOURCE_IDS = {
    # ID del recurso CSV de magistrados federales y nacionales
    # Verificar vigencia en: https://datos.jus.gob.ar/dataset/magistrados-justicia-federal-y-de-la-justicia-nacional
    "magistrados": "2a50f418-bc3b-4e5d-abe8-99ab0aad58bc",
}

# Fallback: descarga directa del CSV
CSV_URL = (
    "https://datos.jus.gob.ar/dataset/magistrados-justicia-federal-y-de-la-justicia-nacional"
    "/resource/2a50f418-bc3b-4e5d-abe8-99ab0aad58bc/download/"
    "magistrados-justicia-federal-y-de-la-justicia-nacional.csv"
)

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))

HEADERS = {
    "User-Agent": "MonitorJusticiaAR/1.0 (github.com/Viny2030/justicia; transparencia pública)",
    "Accept": "application/json, text/csv",
}


# ── Descarga ──────────────────────────────────────────────────────────────────

def descargar_csv() -> pd.DataFrame:
    """Descarga el CSV oficial de magistrados y lo retorna como DataFrame."""
    log.info("Descargando CSV de magistrados desde datos.jus.gob.ar ...")
    try:
        r = requests.get(CSV_URL, headers=HEADERS, timeout=60)
        r.raise_for_status()
        from io import StringIO
        df = pd.read_csv(StringIO(r.text), encoding="utf-8", low_memory=False)
        log.info(f"CSV descargado: {len(df)} filas, {len(df.columns)} columnas")
        return df
    except Exception as e:
        log.error(f"Error descargando CSV: {e}")
        raise


# ── Normalización ─────────────────────────────────────────────────────────────

COLUMNAS_ESPERADAS = {
    "justicia_federal_o_nacional": "tipo_justicia",
    "camara": "camara",
    "organo_tipo": "organo_tipo",
    "organo_nombre": "organo_nombre",
    "cargo_tipo": "cargo_tipo",
    "cargo_cobertura": "cargo_cobertura",
    "magistrado_apellido": "apellido",
    "magistrado_nombre": "nombre",
    "magistrado_genero": "genero",
    "cargo_vacante": "vacante",
    "cargo_licencia": "licencia",
    "concurso_en_tramite": "concurso_en_tramite",
    "presidente_camara": "presidente_camara",
    "decreto_designacion": "decreto_designacion",
    "fecha_designacion": "fecha_designacion",
    "decreto_aceptacion_renuncia": "decreto_renuncia",
    "fecha_aceptacion_renuncia": "fecha_renuncia",
    "ministro_designacion": "ministro_designacion",
    "presidente_designacion": "presidente_designacion",
}


def normalizar(df: pd.DataFrame) -> pd.DataFrame:
    """Renombra columnas al esquema interno y limpia datos."""
    # Renombrar solo las columnas que existen en el df
    rename_map = {k: v for k, v in COLUMNAS_ESPERADAS.items() if k in df.columns}
    df = df.rename(columns=rename_map)

    # Limpiar strings
    str_cols = df.select_dtypes(include="object").columns
    for col in str_cols:
        df[col] = df[col].fillna("").astype(str).str.strip()

    # Booleanos canónicos
    for col in ["vacante", "licencia", "concurso_en_tramite", "presidente_camara"]:
        if col in df.columns:
            df[col] = df[col].str.upper().isin(["SÍ", "SI", "S", "YES", "TRUE", "1"])

    log.info(f"DataFrame normalizado: {len(df)} magistrados")
    return df


# ── Generación de JSONs ───────────────────────────────────────────────────────

def guardar_json(data, nombre: str):
    path = os.path.join(OUTPUT_DIR, nombre)
    with codecs.open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    log.info(f"✓ {nombre} guardado ({len(data) if isinstance(data, list) else 1} registros)")


def generar_magistrados(df: pd.DataFrame) -> list:
    """JSON principal: todos los magistrados activos."""
    activos = df[~df.get("vacante", pd.Series([False]*len(df)))]
    registros = []
    for _, row in activos.iterrows():
        apellido = row.get("apellido", "")
        nombre = row.get("nombre", "")
        registro = {
            "id": f"{apellido}_{nombre}".upper().replace(" ", "_"),
            "apellido": apellido,
            "nombre": nombre,
            "nombre_completo": f"{apellido}, {nombre}".strip(", "),
            "genero": row.get("genero", ""),
            "tipo_justicia": row.get("tipo_justicia", ""),
            "camara": row.get("camara", ""),
            "organo_tipo": row.get("organo_tipo", ""),
            "organo_nombre": row.get("organo_nombre", ""),
            "cargo_tipo": row.get("cargo_tipo", ""),
            "cargo_cobertura": row.get("cargo_cobertura", ""),
            "en_licencia": bool(row.get("licencia", False)),
            "concurso_en_tramite": bool(row.get("concurso_en_tramite", False)),
            "presidente_camara": bool(row.get("presidente_camara", False)),
            "decreto_designacion": row.get("decreto_designacion", ""),
            "fecha_designacion": row.get("fecha_designacion", ""),
            "presidente_designacion": row.get("presidente_designacion", ""),
            "ministro_designacion": row.get("ministro_designacion", ""),
        }
        registros.append(registro)
    return registros


def generar_vacantes(df: pd.DataFrame) -> list:
    """JSON de cargos vacantes."""
    if "vacante" not in df.columns:
        return []
    vacantes = df[df["vacante"] == True]
    registros = []
    for _, row in vacantes.iterrows():
        registros.append({
            "organo_nombre": row.get("organo_nombre", ""),
            "organo_tipo": row.get("organo_tipo", ""),
            "camara": row.get("camara", ""),
            "tipo_justicia": row.get("tipo_justicia", ""),
            "cargo_tipo": row.get("cargo_tipo", ""),
            "concurso_en_tramite": bool(row.get("concurso_en_tramite", False)),
            "ultimo_titular": f"{row.get('apellido', '')} {row.get('nombre', '')}".strip(),
            "fecha_designacion_anterior": row.get("fecha_designacion", ""),
        })
    return registros


def generar_renuncias(df: pd.DataFrame) -> list:
    """JSON de magistrados con renuncia aceptada (tienen decreto de renuncia)."""
    if "decreto_renuncia" not in df.columns:
        return []
    renuncias = df[df["decreto_renuncia"].str.len() > 0]
    registros = []
    for _, row in renuncias.iterrows():
        registros.append({
            "apellido": row.get("apellido", ""),
            "nombre": row.get("nombre", ""),
            "organo_nombre": row.get("organo_nombre", ""),
            "cargo_tipo": row.get("cargo_tipo", ""),
            "decreto_renuncia": row.get("decreto_renuncia", ""),
            "fecha_renuncia": row.get("fecha_renuncia", ""),
            "decreto_designacion_anterior": row.get("decreto_designacion", ""),
            "fecha_designacion_anterior": row.get("fecha_designacion", ""),
        })
    return registros


def generar_designaciones(df: pd.DataFrame) -> list:
    """JSON de todas las designaciones con decreto (para cruce con JGM)."""
    if "decreto_designacion" not in df.columns:
        return []
    designados = df[df["decreto_designacion"].str.len() > 0]
    registros = []
    for _, row in designados.iterrows():
        apellido = row.get("apellido", "")
        nombre_mag = row.get("nombre", "")
        registros.append({
            "apellido": apellido,
            "nombre": nombre_mag,
            "apellido_normalizado": apellido.upper().strip(),
            "organo_nombre": row.get("organo_nombre", ""),
            "cargo_tipo": row.get("cargo_tipo", ""),
            "tipo_justicia": row.get("tipo_justicia", ""),
            "decreto_designacion": row.get("decreto_designacion", ""),
            "fecha_designacion": row.get("fecha_designacion", ""),
            "presidente_designacion": row.get("presidente_designacion", ""),
            "ministro_designacion": row.get("ministro_designacion", ""),
        })
    return registros


def generar_meta(df: pd.DataFrame, magistrados: list, vacantes: list, renuncias: list) -> dict:
    """JSON de metadatos del scrape."""
    total = len(df)
    cobertura_breakdown = {}
    if "cargo_cobertura" in df.columns:
        cobertura_breakdown = df["cargo_cobertura"].value_counts().to_dict()

    genero_breakdown = {}
    if "genero" in df.columns:
        genero_breakdown = df[df.get("vacante", pd.Series([False]*len(df))) == False]["genero"].value_counts().to_dict()

    return {
        "ultima_actualizacion": datetime.now().isoformat(),
        "fecha_datos": date.today().isoformat(),
        "fuente": "datos.jus.gob.ar - Ministerio de Justicia de la Nación",
        "url_fuente": "https://datos.jus.gob.ar/dataset/magistrados-justicia-federal-y-de-la-justicia-nacional",
        "totales": {
            "filas_csv": total,
            "magistrados_activos": len(magistrados),
            "vacantes": len(vacantes),
            "renuncias": len(renuncias),
            "indice_vacancia_pct": round(len(vacantes) / total * 100, 1) if total > 0 else 0,
        },
        "cobertura_breakdown": cobertura_breakdown,
        "genero_breakdown": genero_breakdown,
        "columnas_csv": list(df.columns),
        "generado_por": "scraper_magistrados.py - Monitor Justicia AR",
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    log.info("═" * 60)
    log.info("Monitor Justicia AR — Scraper Magistrados")
    log.info(f"Ejecución: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info("═" * 60)

    # 1. Descargar
    df_raw = descargar_csv()

    # 2. Normalizar
    df = normalizar(df_raw)

    # 3. Generar JSONs
    magistrados = generar_magistrados(df)
    vacantes = generar_vacantes(df)
    renuncias = generar_renuncias(df)
    designaciones = generar_designaciones(df)
    meta = generar_meta(df, magistrados, vacantes, renuncias)

    # 4. Guardar
    guardar_json(magistrados, "magistrados.json")
    guardar_json(vacantes, "vacantes.json")
    guardar_json(renuncias, "renuncias.json")
    guardar_json(designaciones, "designaciones.json")
    guardar_json(meta, "meta_justicia.json")

    log.info("═" * 60)
    log.info(f"✅ Completado: {len(magistrados)} magistrados | {len(vacantes)} vacantes | {len(renuncias)} renuncias")
    log.info(f"   Índice de vacancia: {meta['totales']['indice_vacancia_pct']}%")
    log.info("═" * 60)


if __name__ == "__main__":
    main()
