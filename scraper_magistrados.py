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

# URLs de descarga — el portal publica CSVs con fecha en el nombre
# Intentar en orden: CSV directo más reciente → ZIP 2024 → ZIP 2021
CSV_URLS = [
    # CSV directo (último publicado: 20240412)
    "https://datos.jus.gob.ar/dataset/3c18d46e-729e-4973-8efd-f54cab18b7e3/resource/b12bdbb7-646f-4701-99b7-1109ce919dd5/download/magistrados-justicia-federal-nacional-20240412.csv",
    # ZIP 2024 (fallback)
    "https://datos.jus.gob.ar/dataset/3c18d46e-729e-4973-8efd-f54cab18b7e3/resource/6f12c193-8502-449b-a04f-458ca0eb770f/download/magistrados-justicia-federal-nacional-2024.zip",
]
CSV_URL = CSV_URLS[0]  # compat

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))

HEADERS = {
    "User-Agent": "MonitorJusticiaAR/1.0 (github.com/Viny2030/justicia; transparencia pública)",
    "Accept": "application/json, text/csv",
}


# ── Descarga ──────────────────────────────────────────────────────────────────

def descargar_csv() -> pd.DataFrame:
    """Descarga el CSV oficial de magistrados y lo retorna como DataFrame.
    Prueba múltiples URLs en orden; soporta CSV directo y ZIP."""
    from io import StringIO, BytesIO
    import zipfile

    for url in CSV_URLS:
        log.info(f"Intentando: {url}")
        try:
            r = requests.get(url, headers=HEADERS, timeout=60)
            r.raise_for_status()

            if url.endswith(".zip"):
                # Descomprimir ZIP en memoria
                z = zipfile.ZipFile(BytesIO(r.content))
                csv_names = [n for n in z.namelist() if n.endswith(".csv")]
                if not csv_names:
                    log.warning("ZIP sin CSV adentro, probando siguiente URL")
                    continue
                csv_name = csv_names[0]
                log.info(f"Leyendo del ZIP: {csv_name}")
                with z.open(csv_name) as f:
                    df = pd.read_csv(f, encoding="utf-8", low_memory=False)
            else:
                df = pd.read_csv(StringIO(r.text), encoding="utf-8", low_memory=False)

            log.info(f"CSV cargado: {len(df)} filas, {len(df.columns)} columnas — fuente: {url}")
            return df

        except Exception as e:
            log.warning(f"Falló {url}: {e}")
            continue

    raise RuntimeError("No se pudo descargar el CSV de magistrados desde ninguna URL disponible")


# ── Normalización ─────────────────────────────────────────────────────────────

COLUMNAS_ESPERADAS = {
    "justicia_federal_o_nacional": "tipo_justicia",
    "camara": "camara",
    "organo_tipo": "organo_tipo",
    "organo_nombre": "organo_nombre",
    "organo_provincia": "provincia",
    "cargo_tipo": "cargo_tipo",
    "cargo_cobertura": "cargo_cobertura",
    "magistrado_nombre": "nombre_completo",   # CSV trae nombre completo junto
    "magistrado_genero": "genero",
    "magistrado_dni": "dni",
    "cargo_vacante": "vacante",
    "cargo_licencia": "licencia",
    "cargo_fecha_jura": "fecha_jura",
    "concurso_en_tramite": "concurso_en_tramite",
    "concurso_numero": "concurso_numero",
    "concurso_ambito": "concurso_ambito",
    "presidente_camara": "presidente_camara",
    "norma_tipo": "norma_tipo",
    "norma_numero": "norma_numero",
    "norma_fecha": "norma_fecha",
    "norma_presidente": "presidente_designacion",
    "norma_ministro": "ministro_designacion",
    "titular_con_licencia": "titular_con_licencia",
    "subrogante_calidad": "subrogante_calidad",
    "subrogancia_fecha_vencimiento": "subrogancia_fecha_vencimiento",
}


def normalizar(df: pd.DataFrame) -> pd.DataFrame:
    """Renombra columnas al esquema interno y limpia datos."""
    # Limpiar BOM del nombre de la primera columna (el CSV viene con UTF-8 BOM)
    df.columns = [c.lstrip("\ufeff").strip().strip('"') for c in df.columns]

    # Renombrar solo las columnas que existen en el df
    rename_map = {k: v for k, v in COLUMNAS_ESPERADAS.items() if k in df.columns}
    df = df.rename(columns=rename_map)

    # Limpiar strings
    str_cols = df.select_dtypes(include="object").columns
    for col in str_cols:
        df[col] = df[col].fillna("").astype(str).str.strip()

    # Booleanos canónicos (Sí/No)
    for col in ["vacante", "licencia", "concurso_en_tramite", "presidente_camara"]:
        if col in df.columns:
            df[col] = df[col].str.upper().str.normalize("NFKD").str.encode("ascii", errors="ignore").str.decode("ascii").isin(["SI", "S", "YES", "TRUE", "1"])

    # Separar apellido y nombre desde nombre_completo (formato "APELLIDO, Nombre" o "APELLIDO Nombre")
    if "nombre_completo" in df.columns:
        def split_nombre(s):
            s = str(s).strip()
            if "," in s:
                parts = s.split(",", 1)
                return parts[0].strip(), parts[1].strip()
            # Sin coma: asumir todo mayúsculas = apellido hasta primer minúscula
            parts = s.split(" ", 1)
            return parts[0].strip(), parts[1].strip() if len(parts) > 1 else ""
        df[["apellido", "nombre"]] = df["nombre_completo"].apply(
            lambda x: pd.Series(split_nombre(x))
        )

    log.info(f"DataFrame normalizado: {len(df)} magistrados")
    log.info(f"Columnas disponibles: {list(df.columns)}")
    return df


# ── Generación de JSONs ───────────────────────────────────────────────────────

def guardar_json(data, nombre: str):
    path = os.path.join(OUTPUT_DIR, nombre)
    with codecs.open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    log.info(f"✓ {nombre} guardado ({len(data) if isinstance(data, list) else 1} registros)")


def generar_magistrados(df: pd.DataFrame) -> list:
    """JSON principal: todos los magistrados (activos y vacantes)."""
    registros = []
    for _, row in df.iterrows():
        apellido = row.get("apellido", "")
        nombre   = row.get("nombre", "")
        nro      = str(row.get("norma_numero", "")).strip()
        tipo_n   = str(row.get("norma_tipo", "")).strip()
        decreto  = f"{tipo_n} {nro}".strip() if nro and nro != "nan" else ""
        registro = {
            "id": f"{apellido}_{nombre}".upper().replace(" ", "_").replace(",",""),
            "apellido": apellido,
            "nombre": nombre,
            "nombre_completo": row.get("nombre_completo", f"{apellido}, {nombre}".strip(", ")),
            "genero": row.get("genero", ""),
            "tipo_justicia": row.get("tipo_justicia", ""),
            "camara": row.get("camara", ""),
            "organo_tipo": row.get("organo_tipo", ""),
            "organo_nombre": row.get("organo_nombre", ""),
            "provincia": row.get("provincia", ""),
            "cargo_tipo": row.get("cargo_tipo", ""),
            "cargo_cobertura": row.get("cargo_cobertura", ""),
            "en_licencia": bool(row.get("licencia", False)),
            "vacante": bool(row.get("vacante", False)),
            "concurso_en_tramite": bool(row.get("concurso_en_tramite", False)),
            "concurso_numero": row.get("concurso_numero", ""),
            "presidente_camara": bool(row.get("presidente_camara", False)),
            "decreto_designacion": decreto,
            "fecha_jura": row.get("fecha_jura", ""),
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
            "provincia": row.get("provincia", ""),
            "concurso_en_tramite": bool(row.get("concurso_en_tramite", False)),
            "concurso_numero": row.get("concurso_numero", ""),
            "concurso_ambito": row.get("concurso_ambito", ""),
            "ultimo_titular": row.get("nombre_completo", ""),
            "fecha_jura_anterior": row.get("fecha_jura", ""),
        })
    return registros


def generar_renuncias(df: pd.DataFrame) -> list:
    """JSON de renuncias.
    El CSV 2024 no tiene columna de renuncias — ese dato viene de un dataset separado.
    Ver: datos.jus.gob.ar/dataset/renuncias-de-magistrados
    Retorna lista vacía para que el workflow no falle; se puede extender con el dataset de renuncias.
    """
    # TODO: agregar descarga de dataset de renuncias separado
    # URL: https://datos.jus.gob.ar/dataset/renuncias-de-magistrados-de-la-justicia-federal-y-la-justicia-nacional
    log.info("Renuncias: el CSV de magistrados 2024 no incluye esta columna — retornando []")
    log.info("  Para datos de renuncias ver: datos.jus.gob.ar/dataset/renuncias-de-magistrados-de-la-justicia-federal-y-la-justicia-nacional")
    return []


def generar_designaciones(df: pd.DataFrame) -> list:
    """JSON de designaciones con norma (para cruce de apellidos con JGM)."""
    # Usar magistrados con norma_numero cargado
    designados = df[df.get("norma_numero", pd.Series([""]* len(df))).astype(str).str.strip().str.len() > 0]
    registros = []
    for _, row in designados.iterrows():
        apellido   = row.get("apellido", "")
        nombre_mag = row.get("nombre", "")
        nro  = str(row.get("norma_numero", "")).strip()
        tipo = str(row.get("norma_tipo", "")).strip()
        decreto = f"{tipo} {nro}".strip() if nro and nro != "nan" else ""
        registros.append({
            "apellido": apellido,
            "nombre": nombre_mag,
            "apellido_normalizado": apellido.upper().strip(),
            "nombre_completo": row.get("nombre_completo", ""),
            "organo_nombre": row.get("organo_nombre", ""),
            "cargo_tipo": row.get("cargo_tipo", ""),
            "tipo_justicia": row.get("tipo_justicia", ""),
            "provincia": row.get("provincia", ""),
            "decreto_designacion": decreto,
            "fecha_jura": row.get("fecha_jura", ""),
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
        activos = df[~df["vacante"]] if "vacante" in df.columns else df
        genero_breakdown = activos["genero"].value_counts().to_dict()

    provincia_breakdown = {}
    if "provincia" in df.columns:
        provincia_breakdown = df["provincia"].value_counts().head(10).to_dict()

    return {
        "ultima_actualizacion": datetime.now().isoformat(),
        "fecha_datos": date.today().isoformat(),
        "fuente": "datos.jus.gob.ar - Ministerio de Justicia de la Nación",
        "url_fuente": "https://datos.jus.gob.ar/dataset/magistrados-justicia-federal-y-de-la-justicia-nacional",
        "totales": {
            "filas_csv": total,
            "magistrados_activos": len([m for m in magistrados if not m.get("vacante")]),
            "vacantes": len(vacantes),
            "renuncias": len(renuncias),
            "indice_vacancia_pct": round(len(vacantes) / total * 100, 1) if total > 0 else 0,
        },
        "cobertura_breakdown": cobertura_breakdown,
        "genero_breakdown": genero_breakdown,
        "provincia_breakdown": provincia_breakdown,
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
