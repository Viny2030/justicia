#!/usr/bin/env python3
"""
pjn_extraer_pdf_tablas.py
===========================
Los .pdf descargados por pjn_id_crawler.py son resúmenes anuales/semestrales
por jurisdicción (ej. "(2024) Córdoba.pdf", "(2018-1S) Cámara Nacional...pdf").
Son PDFs "de verdad" (no escaneados) con tablas de texto seleccionable, así que
pdfplumber puede extraer las tablas sin necesitar OCR.

Igual que con los .xls "libro" (ver pjn_extraer_libro_xls.py): esto NO mapea
cada tabla a los campos específicos del pipeline (pendientes_inicio,
dictadas_def, etc.) — cada PDF trae varios cuadros distintos por fuero/período
sin un layout uniforme entre años. Lo que hace es un volcado best-effort:
cada tabla detectada por página se guarda como CSV en pjn_pdfs_extraido/, con
metadata (año/período/jurisdicción) inferida del nombre de archivo.

Uso:
  python pjn_extraer_pdf_tablas.py
  python pjn_extraer_pdf_tablas.py --solo-nuevos
"""

import re, json, logging, argparse
from pathlib import Path

import pdfplumber

ROOT     = Path(__file__).parent
PDF_DIR  = ROOT / "pjn_pdfs"
OUT_DIR  = ROOT / "pjn_pdfs_extraido"
MANIFEST = ROOT / "pjn_pdfs_manifest.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

_RE_META = re.compile(
    r"\((?P<anio>20\d{2})(?:-(?P<periodo>1S|2S))?\)\s*(?P<lugar>[^.]+)",
    re.IGNORECASE,
)


def _meta_desde_nombre(fname):
    m = _RE_META.search(fname)
    if not m:
        return {"anio": None, "periodo": "Anual", "lugar": ""}
    return {
        "anio": m.group("anio"),
        "periodo": m.group("periodo") or "Anual",
        "lugar": m.group("lugar").strip(" -_"),
    }


def procesar_archivo(path: Path, solo_nuevos=False):
    registros = []
    stem = re.sub(r"[^\w.-]+", "_", path.stem)
    meta = _meta_desde_nombre(path.name)

    try:
        pdf = pdfplumber.open(path)
    except Exception as e:
        log.warning(f"  {path.name}: no se pudo abrir ({e})")
        return registros

    with pdf:
        for pnum, page in enumerate(pdf.pages, start=1):
            try:
                tablas = page.extract_tables()
            except Exception as e:
                log.warning(f"  {path.name} p{pnum}: {e}")
                continue
            for tnum, tabla in enumerate(tablas, start=1):
                if not tabla or len(tabla) < 2:
                    continue
                out_name = f"{stem}__p{pnum:02d}_t{tnum}.csv"
                out_path = OUT_DIR / out_name
                if solo_nuevos and out_path.exists():
                    continue
                with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
                    for fila in tabla:
                        f.write(";".join((c or "").replace("\n", " ").strip() for c in fila) + "\n")
                registros.append({
                    "archivo_origen": str(path),
                    "pagina": pnum,
                    "tabla": tnum,
                    "csv_extraido": str(out_path),
                    "filas": len(tabla),
                    "columnas": len(tabla[0]) if tabla else 0,
                    **meta,
                })
    return registros


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--solo-nuevos", action="store_true")
    args = ap.parse_args()

    OUT_DIR.mkdir(exist_ok=True)
    archivos = sorted(PDF_DIR.glob("*.pdf"))
    log.info(f"Procesando {len(archivos)} PDFs de {PDF_DIR}")

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
    log.info(f"Listo: {ok} PDFs con tablas extraídas, {fallidos} sin tablas/fallidos")
    log.info(f"  {len(manifest)} tablas volcadas a CSV en {OUT_DIR}")
    log.info(f"  Manifest: {MANIFEST}")


if __name__ == "__main__":
    main()
