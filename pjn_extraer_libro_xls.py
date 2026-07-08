#!/usr/bin/env python3
"""
pjn_extraer_libro_xls.py
=========================
Los .xls descargados por pjn_id_crawler.py para años viejos (~2002-2016) NO son
tablas planas tipo CSV: son "libros" de Excel con varias hojas (A, B, C, ... o
nombres similares) donde cada hoja es un cuadro impreso con título centrado
("CUADRO 1.A.I"), celdas combinadas, encabezados a dos niveles y notas al pie —
pensado para imprimirse, no para leerse con pandas.read_excel directo.

Este script NO intenta mapear cada cuadro a los campos específicos que usa
scraper_juzgados_nacional.py (pendientes_inicio, dictadas_def, clearance_rate,
etc.) — hacerlo bien requeriría un catálogo de qué significa cada "CUADRO N.X"
en cada fuero/período, y eso no está documentado en ningún lado del sitio.
Lo que sí hace, con criterio conservador:

  1. Abre cada hoja del .xls con pandas/xlrd.
  2. Vuelca la hoja completa (todas las filas/columnas, sin recortar) a un CSV
     plano en pjn_libros_xls_extraido/<archivo>__<hoja>.csv — así queda
     legible/greppable/importable en vez de atrapado en un binario .xls viejo.
  3. Intenta extraer metadata liviana por heurística (año desde la carpeta
     Estadi_XX del nombre de archivo original, título del cuadro = primera
     celda no vacía de las primeras ~10 filas) y la guarda en un manifest.

Uso:
  python pjn_extraer_libro_xls.py                  # procesa todo pjn_libros_xls/
  python pjn_extraer_libro_xls.py --solo-nuevos     # sólo si no existe el CSV de salida
"""

import re, json, logging, argparse
from pathlib import Path

import pandas as pd

ROOT       = Path(__file__).parent
XLS_DIR    = ROOT / "pjn_libros_xls"
OUT_DIR    = ROOT / "pjn_libros_xls_extraido"
MANIFEST   = ROOT / "pjn_libros_xls_manifest.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)


def _titulo_hoja(df):
    """Primera celda no vacía de las primeras filas — suele ser el título del cuadro."""
    for _, row in df.head(10).iterrows():
        for v in row:
            if isinstance(v, str) and v.strip():
                return v.strip()
    return ""


def _anio_desde_nombre(fname):
    m = re.search(r"_(\d{2})\b", fname) or re.search(r"Estadi_(\d{2})", fname)
    if m:
        n = int(m.group(1))
        return 2000 + n if n <= 50 else 1900 + n  # heurística simple, el sitio no tiene años < 2002
    return None


def procesar_archivo(path: Path, solo_nuevos=False):
    registros = []
    stem = re.sub(r"[^\w.-]+", "_", path.stem)
    try:
        xl = pd.ExcelFile(path)
    except Exception as e:
        log.warning(f"  {path.name}: no se pudo abrir ({e})")
        return registros

    anio = _anio_desde_nombre(path.name)

    for hoja in xl.sheet_names:
        hoja_slug = re.sub(r'[^\w.-]+', '_', hoja)
        out_name = f"{stem}__{hoja_slug}.csv"
        out_path = OUT_DIR / out_name
        if solo_nuevos and out_path.exists():
            continue
        try:
            df = xl.parse(hoja, header=None, dtype=str)
        except Exception as e:
            log.warning(f"  {path.name}[{hoja}]: {e}")
            continue
        if df.empty or df.dropna(how="all").empty:
            continue
        df.to_csv(out_path, index=False, header=False, encoding="utf-8-sig")
        registros.append({
            "archivo_origen": str(path),
            "hoja": hoja,
            "csv_extraido": str(out_path),
            "filas": int(df.shape[0]),
            "columnas": int(df.shape[1]),
            "titulo_detectado": _titulo_hoja(df),
            "anio_inferido": anio,
        })
    return registros


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--solo-nuevos", action="store_true", help="saltear hojas ya extraídas")
    args = ap.parse_args()

    OUT_DIR.mkdir(exist_ok=True)
    archivos = sorted(XLS_DIR.glob("*.xls")) + sorted(XLS_DIR.glob("*.xlsx"))
    log.info(f"Procesando {len(archivos)} archivos .xls 'libro' de {XLS_DIR}")

    manifest = []
    if MANIFEST.exists() and args.solo_nuevos:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    ok, fallidos = 0, 0
    for path in archivos:
        regs = procesar_archivo(path, solo_nuevos=args.solo_nuevos)
        if regs:
            manifest.extend(regs)
            ok += 1
        else:
            fallidos += 1

    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info(f"Listo: {ok} archivos con hojas extraídas, {fallidos} sin datos/fallidos")
    log.info(f"  {len(manifest)} hojas volcadas a CSV en {OUT_DIR}")
    log.info(f"  Manifest: {MANIFEST}")


if __name__ == "__main__":
    main()
