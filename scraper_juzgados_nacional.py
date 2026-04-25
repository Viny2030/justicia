#!/usr/bin/env python3
"""
scraper_juzgados_nacional.py
============================
Obtiene estadísticas de TODOS los juzgados del PJN (Poder Judicial de la Nación).
Fuentes:
  1. estadisticas.pjn.gov.ar — CSVs de sentencias/movimiento/trámite por jurisdicción
  2. datos_jus/oralidad         — causas civiles individuales (Clearance Rate, Disposition Time)
  3. magistrados.json           — nombre del juez titular + antigüedad
  4. vacantes.json              — vacancia / concurso activo

Salida:  juzgados_nacional.json   — 1 fila por juzgado con todas las métricas
         juzgados_nacional.csv    — idem en CSV

Uso:
  python scraper_juzgados_nacional.py
  python scraper_juzgados_nacional.py --resume      # retomar descarga interrumpida
  python scraper_juzgados_nacional.py --max-pages 200
"""

import os, re, json, time, zipfile, logging, argparse, codecs
from io import BytesIO, StringIO
from pathlib import Path
from datetime import datetime, date, timedelta
from collections import defaultdict, Counter
from urllib.parse import urljoin, urlparse

import requests
import pandas as pd
from bs4 import BeautifulSoup

# ── CONFIG ────────────────────────────────────────────────────────────────────
ROOT       = Path(__file__).parent
OUT_JSON   = ROOT / "juzgados_nacional.json"
OUT_CSV    = ROOT / "juzgados_nacional.csv"
CKPT_FILE  = ROOT / "juzgados_checkpoint.json"
CSV_DIR    = ROOT / "pjn_estadisticas"
DATOS_JUS  = ROOT / "datos_jus"
DELAY      = 1.2
TIMEOUT    = 45
HOY        = date.today()

# Semillas del crawler — todas las rutas conocidas del portal PJN
SEEDS = [
    "https://estadisticas.pjn.gov.ar/",
    "https://estadisticas.pjn.gov.ar/07_estadisticas/estadisticas/07_estadisticas/index.php",
    "https://estadisticas.pjn.gov.ar/07_estadisticas/",
    "https://estadisticas.pjn.gov.ar/estadisticas/",
    # Jurisdicciones conocidas — civil, comercial, laboral, penal, seguridad social, familia
    "https://estadisticas.pjn.gov.ar/07_estadisticas/estadisticas/07_estadisticas/civil.php",
    "https://estadisticas.pjn.gov.ar/07_estadisticas/estadisticas/07_estadisticas/comercial.php",
    "https://estadisticas.pjn.gov.ar/07_estadisticas/estadisticas/07_estadisticas/laboral.php",
    "https://estadisticas.pjn.gov.ar/07_estadisticas/estadisticas/07_estadisticas/penal.php",
    "https://estadisticas.pjn.gov.ar/07_estadisticas/estadisticas/07_estadisticas/seguridad_social.php",
    "https://estadisticas.pjn.gov.ar/07_estadisticas/estadisticas/07_estadisticas/familia.php",
    "https://estadisticas.pjn.gov.ar/07_estadisticas/estadisticas/07_estadisticas/federal.php",
    "https://estadisticas.pjn.gov.ar/07_estadisticas/estadisticas/07_estadisticas/federal_civil.php",
    "https://estadisticas.pjn.gov.ar/07_estadisticas/estadisticas/07_estadisticas/federal_penal.php",
    "https://estadisticas.pjn.gov.ar/07_estadisticas/estadisticas/07_estadisticas/federal_laboral.php",
    "https://estadisticas.pjn.gov.ar/07_estadisticas/estadisticas/07_estadisticas/menores.php",
]

FORMATOS = {".csv", ".xlsx", ".xls", ".zip"}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

session = requests.Session()
session.headers.update({
    "User-Agent": "MonitorJudicialAR/3.0 (github.com/Viny2030/justicia; academic)",
    "Accept": "text/html,application/xhtml+xml,application/xml,*/*",
})

# ── HELPERS ───────────────────────────────────────────────────────────────────

def safe_num(v):
    try:
        s = re.sub(r"[^\d\.\-]", "", str(v).strip().replace(",", "."))
        return int(float(s)) if s and s != "-" else 0
    except:
        return 0

def decode_bytes(raw):
    for enc in ("cp1252", "latin-1", "utf-8-sig", "utf-8"):
        try:
            return raw.decode(enc)
        except:
            pass
    return raw.decode("latin-1", errors="replace")

def checkpoint_load():
    if CKPT_FILE.exists():
        return json.loads(CKPT_FILE.read_text(encoding="utf-8"))
    return {"procesados": {}}

def checkpoint_save(cp):
    CKPT_FILE.write_text(json.dumps(cp, ensure_ascii=False, indent=2), encoding="utf-8")

# ── PASO 1: CRAWL estadisticas.pjn.gov.ar ────────────────────────────────────

def crawl_pjn(max_pages=300):
    """Rastrea el portal PJN sin límite de páginas, recoge todos los CSV/XLS/ZIP."""
    encontrados = []
    visitadas   = set()
    cola        = list(dict.fromkeys(SEEDS))  # dedup preservando orden

    while cola and len(visitadas) < max_pages:
        url = cola.pop(0)
        if url in visitadas:
            continue
        visitadas.add(url)
        log.info(f"  [{len(visitadas)}/{max_pages}] crawl: {url[-80:]}")

        try:
            r = session.get(url, timeout=TIMEOUT)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
        except Exception as e:
            log.warning(f"    HTTP error: {e}")
            time.sleep(DELAY)
            continue
        time.sleep(DELAY)

        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if not href or href.startswith(("mailto:", "#", "javascript:")):
                continue
            full = urljoin(url, href)
            ext  = Path(urlparse(full).path).suffix.lower()

            if ext in FORMATOS and full not in {e["url"] for e in encontrados}:
                texto = a.get_text(strip=True)
                # filtrar por año reciente (2022 en adelante)
                combinado = (full + " " + texto).lower()
                m = re.search(r"20(2[2-9]|[3-9]\d)", combinado)
                if m or not re.search(r"20\d\d", combinado):  # sin año = incluir igual
                    encontrados.append({"url": full, "ext": ext, "texto": texto})
                    log.info(f"    + {ext.upper()} {full[-70:]}")

            elif ext not in {".pdf", ".doc", ".docx", ".exe"} and \
                    any(full.startswith(s.rsplit("/",1)[0]) for s in SEEDS) and \
                    full not in visitadas:
                cola.append(full)

    log.info(f"  Crawl completo: {len(encontrados)} archivos, {len(visitadas)} páginas visitadas")
    return encontrados

# ── PASO 2: DESCARGA y PARSE CSVs del PJN ────────────────────────────────────

def descargar_url(url, ext):
    """Descarga y devuelve DataFrame. Soporta CSV, XLS/X, ZIP."""
    r = session.get(url, timeout=60, stream=True)
    r.raise_for_status()
    raw = r.content

    if ext == ".zip":
        try:
            with zipfile.ZipFile(BytesIO(raw)) as z:
                frames = []
                for name in z.namelist():
                    ne = Path(name).suffix.lower()
                    if ne in (".csv", ".xlsx", ".xls"):
                        inner = z.read(name)
                        df = _parse_raw(inner, ne)
                        if df is not None and not df.empty:
                            df["_archivo_zip"] = name
                            frames.append(df)
                return pd.concat(frames, ignore_index=True) if frames else None
        except Exception as e:
            log.warning(f"  ZIP error: {e}")
            return None

    return _parse_raw(raw, ext)

def _parse_raw(raw, ext):
    if ext in (".xlsx", ".xls"):
        try:
            xl = pd.ExcelFile(BytesIO(raw))
            frames = [xl.parse(s, dtype=str) for s in xl.sheet_names if not xl.parse(s).empty]
            return pd.concat(frames, ignore_index=True) if frames else None
        except Exception as e:
            log.warning(f"  Excel error: {e}")
            return None

    texto = decode_bytes(raw)
    for sep in (";", ",", "\t"):
        try:
            df = pd.read_csv(StringIO(texto), sep=sep, dtype=str,
                             on_bad_lines="skip", low_memory=False)
            if not df.empty and len(df.columns) > 1:
                return df
        except:
            pass
    return None

# ── PASO 3: PARSE del formato PJN legacy (cp1250) ────────────────────────────

def parse_pjn_legacy(path_or_bytes):
    """Parsea CSVs en formato PJN legacy (cp1250, metadata en filas 0-8)."""
    if isinstance(path_or_bytes, (str, Path)):
        with open(path_or_bytes, "rb") as f:
            raw = f.read()
    else:
        raw = path_or_bytes

    texto = decode_bytes(raw)
    lines = texto.replace("\r\n","\n").replace("\r","\n").split("\n")
    if not lines:
        return []

    # detectar tipo
    tipo = "tramite"
    for l in lines[:9]:
        cells = [c.strip() for c in l.split(";")]
        if "Movimiento de Sentencias" in cells[0]:  tipo = "sentencias"; break
        if "Recursos interpuestos"    in cells[0]:  tipo = "recursos";   break
        if "Resumen del per"          in cells[0]:  tipo = "resumen";    break

    # extraer metadata
    meta = {"anio":"","jurisdiccion":"","tipo_csv": tipo}
    for i, l in enumerate(lines[:10]):
        cells = [c.strip() for c in l.split(";")]
        v = cells[0]
        m = re.match(r"[Aa]ño\s+(\d{4})", v)
        if m: meta["anio"] = m.group(1)
        if "Jurisdicci" in v: meta["jurisdiccion"] = re.sub(r"Jurisdicci[oó]n\s*","",v).strip()

    # buscar fila header
    hr = None
    for i, l in enumerate(lines):
        cells = [c.strip() for c in l.split(";")]
        if cells[0] in ("Secretaría","Secretaria","Tribunal","tribunal"):
            hr = i; break
    if hr is None:
        return []

    registros = []
    org_actual = ""
    for l in lines[hr+3:]:
        cells = [c.strip() for c in l.split(";")]
        if not any(c for c in cells): continue
        if "Datos actualizados" in cells[0]: break
        if cells[0] and cells[0] not in ["-",""]:
            org_actual = cells[0]

        sec = cells[1] if len(cells) > 1 else ""
        organismo = f"{org_actual} | {sec}".strip(" |") if sec else org_actual

        r = {**meta, "organismo": organismo,
             "es_total": "Total" in org_actual or "Subtotal" in org_actual}

        if tipo == "sentencias":
            r.update({
                "pendientes_inicio":  safe_num(cells[2] if len(cells)>2 else 0),
                "agregadas":          safe_num(cells[3] if len(cells)>3 else 0),
                "dictadas_def":       safe_num(cells[5] if len(cells)>5 else 0),
                "dictadas_inter":     safe_num(cells[6] if len(cells)>6 else 0),
                "pendientes_cierre":  safe_num(cells[8] if len(cells)>8 else 0),
            })
            tot_dict = r["dictadas_def"] + r["dictadas_inter"]
            denom    = r["pendientes_inicio"] + r["agregadas"]
            r["clearance_rate"] = round(tot_dict / denom * 100, 1) if denom else 0.0
        elif tipo == "tramite":
            r.update({
                "en_tramite_inicio":  safe_num(cells[1] if len(cells)>1 else 0),
                "ingresos":          safe_num(cells[2] if len(cells)>2 else 0),
                "resueltos":         safe_num(cells[5] if len(cells)>5 else 0),
                "en_tramite_cierre": safe_num(cells[12] if len(cells)>12 else 0),
                "permanencia_breve": safe_num(cells[15] if len(cells)>15 else 0),
            })
            sub_a = safe_num(cells[4] if len(cells)>4 else 0)
            r["clearance_rate"] = round(r["resueltos"]/sub_a*100,1) if sub_a else 0.0
            r["disposition_time"] = r["permanencia_breve"]
        elif tipo == "recursos":
            r.update({
                "recursos_apelacion": safe_num(cells[2] if len(cells)>2 else 0),
                "otros_recursos":     safe_num(cells[3] if len(cells)>3 else 0),
            })

        registros.append(r)

    return registros

# ── PASO 4: PROCESAR ORALIDAD (per-causa → per-juzgado) ──────────────────────

def procesar_oralidad():
    """Lee todos los archivos de oralidad civil y agrega métricas por juzgado."""
    if not DATOS_JUS.exists():
        log.warning("  datos_jus/ no encontrado")
        return {}

    filas = []
    for fname in sorted(os.listdir(DATOS_JUS)):
        if "oralidad-en-los-procesos-civiles" in fname and fname.endswith(".json") \
                and "encuesta" not in fname:
            try:
                with open(DATOS_JUS / fname, encoding="utf-8") as f:
                    d = json.load(f)
                chunk = d if isinstance(d, list) else d.get("data", d.get("results", []))
                filas.extend(chunk)
            except Exception as e:
                log.warning(f"  oralidad {fname}: {e}")

    if not filas:
        return {}

    log.info(f"  Oralidad: {len(filas):,} causas individuales")
    agg = defaultdict(lambda: {
        "causas": 0, "dias_total": 0, "dias_cnt": 0,
        "resueltas": 0, "mora": 0, "objetos": Counter()
    })

    for r in filas:
        prov  = r.get("provincia_nombre", "")
        jnum  = r.get("juzgado_numero", "")
        if not jnum:
            continue
        key = f"{prov} | Juzgado {jnum}"

        fecha_i_str = r.get("causa_fecha_ingreso") or r.get("causa_fecha_recepcion","")
        fecha_f_str = r.get("proceso_finalización_fecha","")
        resultado   = r.get("proceso_resultado_descripcion","")
        obj         = r.get("causa_objeto_litigio_descripcion","")

        agg[key]["causas"] += 1
        if obj:
            agg[key]["objetos"][obj] += 1

        # calcular días
        try:
            fi = date.fromisoformat(fecha_i_str[:10])
            if fecha_f_str:
                ff = date.fromisoformat(fecha_f_str[:10])
                dias = (ff - fi).days
                agg[key]["resueltas"] += 1
            else:
                ff = HOY
                dias = (ff - fi).days
                if dias > 730:
                    agg[key]["mora"] += 1
            if dias > 0:
                agg[key]["dias_total"] += dias
                agg[key]["dias_cnt"]   += 1
        except:
            pass

    result = {}
    for key, v in agg.items():
        total = v["causas"]
        disp_time = round(v["dias_total"] / v["dias_cnt"], 0) if v["dias_cnt"] else 0
        cr = round(v["resueltas"] / total * 100, 1) if total else 0
        top_obj = v["objetos"].most_common(1)[0][0] if v["objetos"] else ""
        result[key] = {
            "total_causas":    total,
            "resueltas":       v["resueltas"],
            "mora_2anios":     v["mora"],
            "pct_mora":        round(v["mora"] / total * 100, 1) if total else 0,
            "disposition_time": disp_time,
            "clearance_rate":  cr,
            "objeto_principal": top_obj,
            "fuente_oralidad": True,
        }

    log.info(f"  Oralidad: {len(result)} juzgados procesados")
    return result

# ── PASO 5: CRUZAR con magistrados.json / vacantes.json ──────────────────────

def cargar_magistrados():
    """Devuelve dict organismo_nombre → {magistrado, fecha_jura, en_licencia}"""
    path = ROOT / "magistrados.json"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    data = d if isinstance(d, list) else list(d.values())[0]
    result = {}
    for r in data:
        org = r.get("organo_nombre","").strip()
        if not org:
            continue
        nombre = r.get("nombre_completo","").strip()
        jura   = r.get("fecha_jura","")
        antig  = None
        try:
            antig = (HOY - date.fromisoformat(jura[:10])).days // 365
        except:
            pass
        result[org.lower()] = {
            "magistrado":      nombre,
            "fecha_jura":      jura,
            "antiguedad_anos": antig,
            "en_licencia":     r.get("en_licencia", False),
            "vacante":         r.get("vacante", False),
        }
    return result

def cargar_vacantes():
    """Devuelve dict organismo_nombre → {concurso_en_tramite, ultimo_titular}"""
    path = ROOT / "vacantes.json"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    data = d if isinstance(d, list) else list(d.values())[0]
    result = {}
    for r in data:
        org = r.get("organo_nombre","").strip()
        if org:
            result[org.lower()] = {
                "vacante":           True,
                "concurso_activo":   r.get("concurso_en_tramite", False),
                "concurso_numero":   r.get("concurso_numero",""),
                "ultimo_titular":    r.get("ultimo_titular",""),
            }
    return result

# ── PASO 6: CALCULAR SCORE DE RIESGO ─────────────────────────────────────────

WJP_CIVIL_BENCH    = 0.42   # Argentina WJP Factor 7
CEPEJ_CR_BENCH     = 100.0  # CEPEJ clearance rate objetivo
CEPEJ_DT_BENCH     = 230    # CEPEJ disposition time objetivo (días)
MORA_ALERTA        = 15.0   # % mora que dispara alerta roja

def calcular_ira(r):
    """
    Índice de Riesgo Algorítmico (IRA) 0-100.
    Compuesto de: mora%, clearance rate, disposition time, acumulación, vacancia.
    """
    score = 0
    # 1. mora (+30 pts si > 25%, proporcional)
    pct_mora = r.get("pct_mora", 0) or 0
    score += min(30, pct_mora * 1.2)

    # 2. clearance rate bajo (+25 pts si CR < 80%)
    cr = r.get("clearance_rate", 100) or 100
    if cr < 100:
        score += min(25, (100 - cr) * 0.5)

    # 3. disposition time alto (+20 pts si > 460 días = 2×CEPEJ)
    dt = r.get("disposition_time", 0) or 0
    if dt > CEPEJ_DT_BENCH:
        score += min(20, (dt - CEPEJ_DT_BENCH) / CEPEJ_DT_BENCH * 10)

    # 4. acumulación (+15 pts si índice > 1.1)
    pend = r.get("pendientes_cierre", 0) or 0
    inic = r.get("pendientes_inicio", 1) or 1
    acum = pend / inic if inic > 0 else 1
    if acum > 1.0:
        score += min(15, (acum - 1.0) * 30)

    # 5. vacante sin concurso (+10 pts)
    if r.get("vacante") and not r.get("concurso_activo"):
        score += 10

    ira = round(min(100, score), 1)
    semaforo = "🔴" if ira >= 60 else "🟡" if ira >= 30 else "🟢"
    return ira, semaforo

# ── PASO 7: PIPELINE COMPLETO ────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--resume",    action="store_true", help="retomar checkpoint")
    ap.add_argument("--max-pages", type=int, default=300)
    ap.add_argument("--skip-crawl", action="store_true",
                    help="usar solo CSVs ya descargados en pjn_estadisticas/")
    args = ap.parse_args()

    CSV_DIR.mkdir(exist_ok=True)
    cp = checkpoint_load() if args.resume else {"procesados": {}}

    # ── 1. Crawl + descarga PJN ──
    todos_pjn = []

    if not args.skip_crawl:
        log.info("\n=== PASO 1: Crawl estadisticas.pjn.gov.ar ===")
        links = crawl_pjn(max_pages=args.max_pages)
        log.info(f"\n=== PASO 2: Descarga de {len(links)} archivos ===")

        ya = set(cp["procesados"].keys())
        for item in links:
            url = item["url"]
            if url in ya:
                log.info(f"  skip (ya procesado): {url[-60:]}")
                continue
            log.info(f"  descargando: {url[-70:]}")
            try:
                df = descargar_url(url, item["ext"])
                if df is not None and not df.empty:
                    stem = re.sub(r"[^\w]","_", urlparse(url).path.split("/")[-1])[:60]
                    out  = CSV_DIR / f"{stem}.csv"
                    df.to_csv(out, index=False, encoding="utf-8-sig")
                    log.info(f"    OK: {len(df):,} filas → {out.name}")
                    cp["procesados"][url] = {"ok": True, "file": str(out)}
                else:
                    cp["procesados"][url] = {"ok": False}
                checkpoint_save(cp)
            except Exception as e:
                log.warning(f"    FALLO: {e}")
                cp["procesados"][url] = {"ok": False, "error": str(e)}
                checkpoint_save(cp)
            time.sleep(DELAY)
    else:
        log.info("\n  --skip-crawl: usando CSVs ya descargados")

    # ── 2. Parsear CSVs descargados ──
    log.info("\n=== PASO 3: Parseo de CSVs PJN ===")
    juz_pjn = defaultdict(lambda: defaultdict(lambda: None))

    csv_files = list(CSV_DIR.glob("*.csv")) + list(CSV_DIR.glob("*.xlsx"))
    log.info(f"  {len(csv_files)} archivos en {CSV_DIR}")

    for fpath in csv_files:
        try:
            recs = parse_pjn_legacy(fpath)
            if not recs:
                # intentar como DataFrame normal
                df = pd.read_csv(fpath, dtype=str, on_bad_lines="skip",
                                 encoding="utf-8-sig", low_memory=False)
                recs = df.to_dict(orient="records")
            for r in recs:
                if r.get("es_total"):
                    continue
                org = str(r.get("organismo","")).strip()
                if not org:
                    continue
                key = org.lower()
                # acumular: preferir registros más recientes
                if juz_pjn[key].get("anio","") <= str(r.get("anio","")):
                    juz_pjn[key].update({k:v for k,v in r.items() if v is not None})
                    juz_pjn[key]["organismo"] = org
        except Exception as e:
            log.warning(f"  {fpath.name}: {e}")

    log.info(f"  Juzgados parseados desde PJN CSVs: {len(juz_pjn)}")

    # ── 3. Oralidad ──
    log.info("\n=== PASO 4: Oralidad civil (per-causa) ===")
    oral = procesar_oralidad()

    # ── 4. Magistrados / Vacantes ──
    log.info("\n=== PASO 5: Cruce con magistrados y vacantes ===")
    mags = cargar_magistrados()
    vacs = cargar_vacantes()

    # ── 5. Unificar ──
    log.info("\n=== PASO 6: Unificación y cálculo IRA ===")
    juzgados_final = {}

    # Combinar fuentes
    todos_keys = set(juz_pjn.keys()) | {k.lower() for k in oral.keys()}

    for key in todos_keys:
        pjn_data  = dict(juz_pjn.get(key, {}))
        oral_data = oral.get(key, oral.get(
            next((k for k in oral if k.lower() == key), None), {}))

        organismo = pjn_data.get("organismo") or key.title()

        # métricas base
        r = {
            "juzgado":           organismo,
            "jurisdiccion":      pjn_data.get("jurisdiccion",""),
            "anio":              pjn_data.get("anio",""),
            # estadísticas causas
            "pendientes_inicio": pjn_data.get("pendientes_inicio") or 0,
            "pendientes_cierre": pjn_data.get("pendientes_cierre") or 0,
            "agregadas":         pjn_data.get("agregadas") or 0,
            "dictadas_def":      pjn_data.get("dictadas_def") or 0,
            "dictadas_inter":    pjn_data.get("dictadas_inter") or 0,
            "ingresos":          pjn_data.get("ingresos") or 0,
            "resueltos":         pjn_data.get("resueltos") or 0,
            "clearance_rate":    pjn_data.get("clearance_rate") or oral_data.get("clearance_rate") or 0,
            "disposition_time":  pjn_data.get("disposition_time") or oral_data.get("disposition_time") or 0,
            # oralidad
            "total_causas_oral": oral_data.get("total_causas") or 0,
            "mora_2anios":       oral_data.get("mora_2anios") or 0,
            "pct_mora":          oral_data.get("pct_mora") or 0,
            "objeto_principal":  oral_data.get("objeto_principal",""),
            # costo estimado (presupuesto PJN 2024 ≈ ARS 600.000M / ~600 organismos)
            "costo_anual_estimado": 1_000_000_000,
            "costo_por_causa": round(1_000_000_000 / max(
                (pjn_data.get("pendientes_cierre") or 0) +
                (pjn_data.get("dictadas_def") or 0) +
                (oral_data.get("total_causas") or 0), 1
            ), 0),
            # comparación internacional
            "vs_wjp_civil":    round((pjn_data.get("clearance_rate") or oral_data.get("clearance_rate") or 0) / 100 * WJP_CIVIL_BENCH, 2),
            "vs_cepej_cr":     f"{'OK' if (pjn_data.get('clearance_rate') or oral_data.get('clearance_rate') or 0) >= CEPEJ_CR_BENCH else 'BAJO'}",
            "vs_cepej_dt":     f"{'OK' if 0 < (pjn_data.get('disposition_time') or oral_data.get('disposition_time') or 0) <= CEPEJ_DT_BENCH else 'ALTO'}",
        }

        # magistrado
        mag = mags.get(key) or mags.get(organismo.lower(), {})
        r.update({
            "magistrado":       mag.get("magistrado",""),
            "fecha_jura":       mag.get("fecha_jura",""),
            "antiguedad_anos":  mag.get("antiguedad_anos"),
            "en_licencia":      mag.get("en_licencia", False),
            "vacante":          vacs.get(key, {}).get("vacante", mag.get("vacante", False)),
            "concurso_activo":  vacs.get(key, {}).get("concurso_activo", False),
            "concurso_numero":  vacs.get(key, {}).get("concurso_numero",""),
        })

        # IRA
        ira, semaforo = calcular_ira(r)
        r["ira_score"]   = ira
        r["ira_semaforo"] = semaforo

        juzgados_final[organismo] = r

    # ── 6. Guardar ──
    lista = sorted(juzgados_final.values(), key=lambda x: x.get("juzgado",""))
    log.info(f"\n=== RESULTADO: {len(lista)} juzgados ===")

    OUT_JSON.write_text(json.dumps(lista, ensure_ascii=False, indent=2, default=str),
                        encoding="utf-8")
    log.info(f"  → {OUT_JSON}")

    df_out = pd.DataFrame(lista)
    df_out.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    log.info(f"  → {OUT_CSV}")

    # Resumen
    con_ira_rojo   = sum(1 for r in lista if r.get("ira_score",0) >= 60)
    con_ira_amarillo = sum(1 for r in lista if 30 <= r.get("ira_score",0) < 60)
    con_mag = sum(1 for r in lista if r.get("magistrado"))
    con_oral = sum(1 for r in lista if r.get("total_causas_oral",0) > 0)

    log.info(f"""
==================================================
  Juzgados totales        : {len(lista)}
  Con magistrado cruzado  : {con_mag}
  Con datos oralidad      : {con_oral}
  IRA 🔴 Alto riesgo      : {con_ira_rojo}
  IRA 🟡 Riesgo medio     : {con_ira_amarillo}
  IRA 🟢 Normal           : {len(lista)-con_ira_rojo-con_ira_amarillo}
==================================================
  Salida: {OUT_JSON}
  Salida: {OUT_CSV}
==================================================""")


if __name__ == "__main__":
    main()
