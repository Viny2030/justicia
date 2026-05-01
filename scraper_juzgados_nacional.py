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
  python scraper_juzgados_nacional.py --skip-crawl  # usar solo CSVs ya descargados
"""

import os, re, json, time, zipfile, logging, argparse, codecs, unicodedata
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

def _nfc(s):
    """Normaliza a NFC para eliminar diferencias invisibles de encoding (ej: acentos compuestos vs descompuestos)."""
    if not s:
        return ""
    return unicodedata.normalize("NFC", str(s).strip())

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

# FIX #2: helper para corregir mojibake (latin-1 interpretado como utf-8) en magistrados.json
def _fix_enc(s):
    """Corrige doble-encoding común: 'CÃ¡mara' → 'Cámara'"""
    if not isinstance(s, str):
        return s
    try:
        return s.encode('latin-1').decode('utf-8')
    except:
        return s

def _inferir_fuero(organismo: str, jurisdiccion: str, objeto: str) -> str:
    """
    Infiere el fuero/materia desde nombre del organismo, jurisdicción u objeto principal.
    Prioridad: nombre del organismo > jurisdicción > presencia de datos de oralidad civil.
    """
    org = (organismo or "").lower()
    jur = (jurisdiccion or "").lower()
    if "federal" in jur:                              return "Federal"
    if "comercial" in org:                            return "Comercial"
    if "laboral" in org:                              return "Laboral"
    if "penal" in org or "criminal" in org:           return "Penal"
    if "familia" in org or "menores" in org:          return "Familia"
    if "seguridad social" in org:                     return "Seg. Social"
    if "civil" in org:                                return "Civil"
    if objeto:                                        return "Civil"  # datos_jus = siempre civil
    if "federal" in org:                              return "Federal"
    return ""

# ── PASO 1: CRAWL estadisticas.pjn.gov.ar ────────────────────────────────────

def crawl_pjn(max_pages=300):
    """Rastrea el portal PJN sin límite de páginas, recoge todos los CSV/XLS/ZIP."""
    encontrados = []
    visitadas   = set()
    cola        = list(dict.fromkeys(SEEDS))

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
                combinado = (full + " " + texto).lower()
                m = re.search(r"20(2[2-9]|[3-9]\d)", combinado)
                if m or not re.search(r"20\d\d", combinado):
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

    tipo = "tramite"
    for l in lines[:9]:
        cells = [c.strip() for c in l.split(";")]
        if "Movimiento de Sentencias" in cells[0]:  tipo = "sentencias"; break
        if "Recursos interpuestos"    in cells[0]:  tipo = "recursos";   break
        if "Resumen del per"          in cells[0]:  tipo = "resumen";    break

    meta = {"anio":"","jurisdiccion":"","tipo_csv": tipo}
    for i, l in enumerate(lines[:10]):
        cells = [c.strip() for c in l.split(";")]
        v = cells[0]
        m = re.match(r"[Aa]ño\s+(\d{4})", v)
        if m: meta["anio"] = m.group(1)
        if "Jurisdicci" in v: meta["jurisdiccion"] = re.sub(r"Jurisdicci[oó]n\s*","",v).strip()

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
        prov  = _nfc(r.get("provincia_nombre", ""))   # FIX #1: NFC normaliza acentos compuestos/descompuestos
        jnum  = str(r.get("juzgado_numero", "")).strip()
        if not jnum or jnum in ("0", ""):
            continue
        key = f"{prov} | Juzgado {jnum}"

        fecha_i_str = r.get("causa_fecha_ingreso") or r.get("causa_fecha_recepcion","")
        fecha_f_str = r.get("proceso_finalización_fecha","")
        obj         = r.get("causa_objeto_litigio_descripcion","")

        agg[key]["causas"] += 1
        if obj:
            agg[key]["objetos"][obj] += 1

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

# Mapeo de nombres de provincia oral → provincia en magistrados.json
_PROV_MAP = {
    "buenos aires":        "buenos aires",
    "ciudad de buenos aires": "ciudad autónoma de bs.as.",
    "caba":                "ciudad autónoma de bs.as.",
    "córdoba":             "córdoba",
    "cordoba":             "córdoba",
    "santa fe":            "santa fe",
    "chaco":               "chaco",
    "entre ríos":         "entre ríos",
    "entre rios":          "entre ríos",
    "corrientes":          "corrientes",
    "tucumán":             "tucumán",
    "tucuman":             "tucumán",
    "chubut":              "chubut",
    "san juan":            "san juan",
    "mendoza":             "mendoza",
    "salta":               "salta",
    "jujuy":               "jujuy",
    "misiones":            "misiones",
    "formosa":             "formosa",
    "neuquén":             "neuquén",
    "neuquen":             "neuquén",
    "río negro":           "río negro",
    "rio negro":           "río negro",
    "santa cruz":          "santa cruz",
    "la pampa":            "la pampa",
    "san luis":            "san luis",
    "la rioja":            "la rioja",
    "catamarca":           "catamarca",
    "santiago del estero": "santiago del estero",
    "tierra del fuego":    "tierra del fuego",
}

def cargar_magistrados():
    """
    Devuelve dict con tres índices:
      - organo_nombre.lower()         → match exacto
      - (prov_norm, numero_str)       → FIX D: match por provincia+número (oral data)
      - '__num_X'                    → fallback genérico por número
    """
    path = ROOT / "magistrados.json"
    if not path.exists():
        log.warning("  magistrados.json no encontrado")
        return {}
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    data = d if isinstance(d, list) else list(d.values())[0]
    result       = {}
    prov_num_idx = {}   # (prov_norm, num) → entry — FIX D

    for r in data:
        org    = _nfc(_fix_enc(r.get("organo_nombre",""))).strip()
        nombre = _nfc(_fix_enc(r.get("nombre_completo",""))).strip()
        prov   = _nfc(_fix_enc(r.get("provincia",""))).strip().lower()
        if not org:
            continue
        jura  = r.get("fecha_jura","")
        antig = None
        try:
            antig = (HOY - date.fromisoformat(jura[:10])).days // 365
        except:
            pass
        entry = {
            "magistrado":      nombre,
            "fecha_jura":      jura,
            "antiguedad_anos": antig,
            "en_licencia":     r.get("en_licencia", False),
            "vacante":         r.get("vacante", False),
        }
        # Index 1: exacto por organo_nombre
        result[org.lower()] = entry
        # Index 2: (provincia_normalizada, número) — para oral keys "Prov | Juzgado N"
        prov_norm = _PROV_MAP.get(prov, prov)
        nums = re.findall(r'\b(\d+)\b', org)
        if nums and prov_norm:
            key_pn = (prov_norm, nums[-1])
            if key_pn not in prov_num_idx:   # primer magistrado con ese par gana
                prov_num_idx[key_pn] = entry
        # Index 3: solo número como fallback último recurso
        if nums:
            num_key = f"__num_{nums[-1]}"
            if num_key not in result:
                result[num_key] = entry

    # Guardar el índice provincia+número como atributo del dict
    result["__prov_num_idx__"] = prov_num_idx  # type: ignore

    log.info(f"  Magistrados cargados: {len([k for k in result if not k.startswith('__')])} organismos "
             f"| {len(prov_num_idx)} pares (prov,num)")
    return result

def cargar_vacantes():
    path = ROOT / "vacantes.json"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    data = d if isinstance(d, list) else list(d.values())[0]
    result = {}
    for r in data:
        org = _fix_enc(r.get("organo_nombre","")).strip()
        if org:
            result[org.lower()] = {
                "vacante":           True,
                "concurso_activo":   r.get("concurso_en_tramite", False),
                "concurso_numero":   r.get("concurso_numero",""),
                "ultimo_titular":    r.get("ultimo_titular",""),
            }
    return result

# ── PASO 6: CALCULAR SCORE DE RIESGO ─────────────────────────────────────────

WJP_CIVIL_BENCH    = 0.42
CEPEJ_CR_BENCH     = 100.0
CEPEJ_DT_BENCH     = 230
MORA_ALERTA        = 15.0

def calcular_ira(r):
    # FIX #2: si no hay datos estadísticos, no calcular IRA — retornar "sin_datos" string (no emoji)
    if r.get("sin_datos_estadisticos"):
        return 0.0, "sin_datos"

    score = 0
    pct_mora = r.get("pct_mora", 0) or 0
    score += min(30, pct_mora * 1.2)

    cr = r.get("clearance_rate", 100) or 100
    if cr < 100:
        score += min(25, (100 - cr) * 0.5)

    dt = r.get("disposition_time", 0) or 0
    if dt > CEPEJ_DT_BENCH:
        score += min(20, (dt - CEPEJ_DT_BENCH) / CEPEJ_DT_BENCH * 10)

    pend = r.get("pendientes_cierre", 0) or 0
    inic = r.get("pendientes_inicio", 1) or 1
    acum = pend / inic if inic > 0 else 1
    if acum > 1.0:
        score += min(15, (acum - 1.0) * 30)

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

    def _acumular(recs_list):
        for r in recs_list:
            if r.get("es_total"):
                continue
            org = str(r.get("organismo","")).strip()
            if not org or "total" in org.lower():
                continue
            # normalizar nombre de columnas
            r.setdefault("dictadas_def", r.get("dictadas_definitivas") or 0)
            r.setdefault("dictadas_inter", r.get("dictadas_interlocutorias") or 0)
            key = org.lower()
            if str(juz_pjn[key].get("anio","")) <= str(r.get("anio","")):
                juz_pjn[key].update({k: v for k, v in r.items() if v is not None})
                juz_pjn[key]["organismo"] = org

    # ── FIX #1: Cargar estadisticas_causas.json pre-parseado ──────────────────
    # Los CSVs en pjn_estadisticas/ fueron guardados por pandas (sin metadata PJN),
    # así que parse_csv no puede leerlos. estadisticas_causas.json fue generado
    # por scraper_estadisticas.py sobre los CSVs originales y tiene los datos correctos.
    ec_path = ROOT / "estadisticas_causas.json"
    if ec_path.exists():
        size_kb = ec_path.stat().st_size // 1024
        log.info(f"  Cargando estadisticas_causas.json pre-parseado ({size_kb}KB)")
        try:
            with open(ec_path, encoding="utf-8") as f:
                ec_data = json.load(f)
            _acumular(ec_data)
            log.info(f"  → {len(ec_data)} registros → {len(juz_pjn)} juzgados únicos en juz_pjn")
        except Exception as e:
            log.warning(f"  No se pudo cargar estadisticas_causas.json: {e}")
    else:
        log.warning("  estadisticas_causas.json no encontrado — ejecutá scraper_estadisticas.py primero")

    # ── Parsear CSVs descargados (complementario al JSON) ─────────────────────
    csv_files = list(CSV_DIR.glob("*.csv")) + list(CSV_DIR.glob("*.xlsx"))
    if csv_files:
        try:
            from scraper_estadisticas import parse_csv as _parse_csv_ext
            log.info(f"  Parseando {len(csv_files)} CSVs con scraper_estadisticas.parse_csv")
            ok_count = 0
            for fpath in csv_files:
                try:
                    recs = _parse_csv_ext(str(fpath))
                    if recs:
                        _acumular(recs)
                        ok_count += 1
                except Exception as e:
                    log.warning(f"  {fpath.name}: {e}")
            log.info(f"  CSVs con datos: {ok_count}/{len(csv_files)}")
        except ImportError:
            log.info(f"  Parseando {len(csv_files)} CSVs con parse_pjn_legacy")
            for fpath in csv_files:
                try:
                    recs = parse_pjn_legacy(fpath)
                    _acumular(recs)
                except Exception as e:
                    log.warning(f"  {fpath.name}: {e}")
    else:
        log.warning(f"  No se encontraron CSVs en {CSV_DIR}")

    log.info(f"  Juzgados parseados desde PJN CSVs+JSON: {len(juz_pjn)}")

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

    # FIX #1: índice oral con NFC + lowercase para match robusto
    oral_lc = {_nfc(k).lower(): v for k, v in oral.items()}

    todos_keys = set(juz_pjn.keys()) | set(oral_lc.keys())

    for key in todos_keys:
        pjn_data  = dict(juz_pjn.get(key, {}))
        # FIX #1: lookup NFC-normalizado elimina diferencias invisibles de encoding
        oral_data = oral_lc.get(_nfc(key).lower(), {})

        organismo = pjn_data.get("organismo") or key.title()

        oral_total     = oral_data.get("total_causas") or 0
        oral_resueltas = oral_data.get("resueltas") or 0
        oral_pendientes = max(oral_total - oral_resueltas, 0)

        pend_cierre  = pjn_data.get("pendientes_cierre") or oral_pendientes
        dict_def     = pjn_data.get("dictadas_def") or pjn_data.get("dictadas_definitivas") or oral_resueltas
        total_causas_denom = max(pend_cierre + dict_def, oral_total, 1)

        r = {
            "juzgado":           organismo,
            "jurisdiccion":      pjn_data.get("jurisdiccion",""),
            "fuero":             pjn_data.get("fuero","") or _inferir_fuero(organismo, pjn_data.get("jurisdiccion",""), oral_data.get("objeto_principal","")),
            "anio":              pjn_data.get("anio",""),
            "pendientes_inicio": pjn_data.get("pendientes_inicio") or 0,
            "pendientes_cierre": pend_cierre,
            "agregadas":         pjn_data.get("agregadas") or 0,
            "dictadas_def":      dict_def,
            "dictadas_inter":    pjn_data.get("dictadas_inter") or pjn_data.get("dictadas_interlocutorias") or 0,
            "ingresos":          pjn_data.get("ingresos") or 0,
            "resueltos":         pjn_data.get("resueltos") or oral_resueltas,
            "clearance_rate":    pjn_data.get("clearance_rate") or oral_data.get("clearance_rate") or 0,
            "disposition_time":  pjn_data.get("disposition_time") or oral_data.get("disposition_time") or 0,
            "total_causas_oral": oral_total,
            "mora_2anios":       oral_data.get("mora_2anios") or 0,
            "pct_mora":          oral_data.get("pct_mora") or 0,
            "objeto_principal":  oral_data.get("objeto_principal",""),
            "costo_anual_estimado": 500_000_000,       # ~$500M ARS/año por juzgado (PJN 2024)
            "costo_por_causa": round(500_000_000 / total_causas_denom, 0),
            "vs_wjp_civil":    round((pjn_data.get("clearance_rate") or oral_data.get("clearance_rate") or 0) / 100, 3),
            "gap_wjp_civil":   round((pjn_data.get("clearance_rate") or oral_data.get("clearance_rate") or 0) / 100 - WJP_CIVIL_BENCH, 3),
            "vs_cepej_cr":     f"{'OK' if (pjn_data.get('clearance_rate') or oral_data.get('clearance_rate') or 0) >= CEPEJ_CR_BENCH else 'BAJO'}",
            "vs_cepej_dt":     (lambda dt: "—" if not dt else ("OK" if dt <= CEPEJ_DT_BENCH else "ALTO"))(pjn_data.get('disposition_time') or oral_data.get('disposition_time') or 0),
        }

        # FIX D: buscar magistrado — exacto → (prov+num) → solo num
        mag = mags.get(key) or mags.get(organismo.lower(), {})
        if not mag:
            # FIX D: intentar match por (provincia, número) — cubre oral keys "Prov | Juzgado N"
            prov_num_idx = mags.get("__prov_num_idx__", {})
            if "|" in organismo:
                prov_part = _nfc(organismo.split("|")[0]).strip().lower()
                prov_norm = _PROV_MAP.get(prov_part, prov_part)
                nums = re.findall(r'\b(\d+)\b', organismo)
                if nums and prov_norm:
                    mag = prov_num_idx.get((prov_norm, nums[-1]), {})
        if not mag:
            nums = re.findall(r'\b(\d+)\b', organismo)
            if nums:
                mag = mags.get(f"__num_{nums[-1]}", {})

        r.update({
            "magistrado":       mag.get("magistrado",""),
            "fecha_jura":       mag.get("fecha_jura",""),
            "antiguedad_anos":  mag.get("antiguedad_anos"),
            "en_licencia":      mag.get("en_licencia", False),
            "vacante":          vacs.get(key, {}).get("vacante", mag.get("vacante", False)),
            "concurso_activo":  vacs.get(key, {}).get("concurso_activo", False),
            "concurso_numero":  vacs.get(key, {}).get("concurso_numero",""),
        })

        # FIX #2: flag bool puro — no depende de emoji para contar "sin datos"
        r["sin_datos_estadisticos"] = not bool(
            r.get("pendientes_cierre", 0) or
            r.get("dictadas_def", 0) or
            r.get("total_causas_oral", 0) or
            r.get("clearance_rate", 0)
        )

        ira, semaforo = calcular_ira(r)
        r["ira_score"]    = ira
        r["ira_semaforo"] = semaforo

        # FIX C: descartar artefactos del parseo CSV (registros sin nombre real)
        org_lc = organismo.strip().lower()
        if not org_lc or len(organismo.strip()) < 6:
            continue
        if org_lc in {"primera instancia", "segunda instancia", "cámara", "camara",
                      "penal", "civil", "laboral", "comercial", "(**)", "penal "}:
            continue
        if org_lc.startswith(("referencia:", "(**)")):
            continue

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

    # FIX #2: contar usando bool puro — sin comparar emojis (falla en consola Windows cp1252)
    con_sin_datos    = sum(1 for r in lista if r.get("sin_datos_estadisticos"))
    con_datos        = [r for r in lista if not r.get("sin_datos_estadisticos")]
    con_ira_rojo     = sum(1 for r in con_datos if r.get("ira_score", 0) >= 60)
    con_ira_amarillo = sum(1 for r in con_datos if 30 <= r.get("ira_score", 0) < 60)
    con_ira_verde    = len(con_datos) - con_ira_rojo - con_ira_amarillo
    con_mag          = sum(1 for r in lista if r.get("magistrado"))
    con_oral         = sum(1 for r in lista if r.get("total_causas_oral", 0) > 0)
    con_pjn          = sum(1 for r in lista if r.get("pendientes_cierre", 0) > 0 or r.get("dictadas_def", 0) > 0)

    log.info(
        "\n=================================================="
        f"\n  Juzgados totales        : {len(lista)}"
        f"\n  Con datos oralidad      : {con_oral}"
        f"\n  Con datos PJN CSV/JSON  : {con_pjn}"
        f"\n  Con magistrado cruzado  : {con_mag}"
        f"\n  IRA Alto riesgo  (>=60) : {con_ira_rojo}"
        f"\n  IRA Riesgo medio (>=30) : {con_ira_amarillo}"
        f"\n  IRA Normal       (<30)  : {con_ira_verde}"
        f"\n  IRA (sin datos)         : {con_sin_datos}"
        "\n=================================================="
        f"\n  Salida: {OUT_JSON}"
        f"\n  Salida: {OUT_CSV}"
        "\n=================================================="
    )


if __name__ == "__main__":
    main()
