# dashboard_estrategico/app.py  —  VERSIÓN COMPLETA CON INDICADORES INTERNACIONALES
# ─────────────────────────────────────────────────────────────────────────────
# MÓDULOS INCLUIDOS:
#   1. WJP Rule of Law Index 2023 — ranking, radar 8 dims, histórico
#   2. IPC Transparencia Internacional 2023 — regional + histórico
#   3. World Bank WGI 2022 — 6 dims Argentina + Rule of Law regional
#   4. V-Dem Institute 2023 — JCI histórico, High Court Independence, Nombramientos
#   5. RECPJ / CEPEJ — Clearance Rate, Disposition Time, concursos, disciplinarios
#   6. CEJAS — Independencia Personal de Magistrados
#   7. ODS 16 (ONU) — 5 indicadores con semáforo
#   8. OCDE — Duración procedimientos civiles comparativa
# ─────────────────────────────────────────────────────────────────────────────

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse
import json as _json
import os, sys, traceback
from collections import Counter
from datetime import datetime

router = APIRouter()
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(ROOT)

from src.utils import calcular_tasa_vacancia, calcular_costo_por_sentencia
from shared import BASE_CSS, DISCLAIMER, FOOTER, PLOTLY_JS, PLOTLY_BASE, nav_html

# ══════════════════════════════════════════════════════════════════════════════
# DATOS ESTÁTICOS — WJP (World Justice Project Rule of Law Index 2023)
# Fuente: worldjusticeproject.org — escala 0–1
# ══════════════════════════════════════════════════════════════════════════════
_WJP_RANKING = {
    "Perú":0.40,"México":0.41,"Colombia":0.46,"Argentina":0.47,
    "Brasil":0.48,"Costa Rica":0.55,"Chile":0.59,"Uruguay":0.64,"OCDE (prom.)":0.68,
}
_WJP_COLORS = {
    "Perú":"#e63946","México":"#e63946","Colombia":"#f97316",
    "Argentina":"#c9a227","Brasil":"#f97316","Costa Rica":"#22c55e",
    "Chile":"#22c55e","Uruguay":"#22c55e","OCDE (prom.)":"#3b82f6",
}
_WJP_DIMS = [
    "Límites al Poder Gub.","Ausencia de Corrupción","Gobierno Abierto",
    "Derechos Fundamentales","Orden y Seguridad","Cumplimiento Regulatorio",
    "Justicia Civil","Justicia Penal",
]
_WJP_ARG  = [0.56, 0.39, 0.47, 0.53, 0.59, 0.45, 0.42, 0.38]
_WJP_LAC  = [0.52, 0.43, 0.45, 0.55, 0.57, 0.44, 0.44, 0.40]
_WJP_OCDE = [0.72, 0.71, 0.63, 0.75, 0.78, 0.68, 0.68, 0.62]
_WJP_HIST = {2015:0.50,2016:0.50,2017:0.49,2018:0.48,2019:0.49,
             2020:0.48,2021:0.47,2022:0.47,2023:0.47}

# WJP Factores clave para Cortes Superiores (1, 2, 7, 8)
_WJP_FACTORES_KEY = {
    "Factor 1 — Límites al Poder Gubernamental": {
        "arg":0.56,"lac":0.52,"ocde":0.72,
        "desc":"Capacidad legal y técnica del PJ para auditar y frenar al Ejecutivo.",
        "subfactores":["Controles legislativos","Controles judiciales","Controles independientes","Sanciones no gubernamentales","Transición no violenta de poder"],
        "sub_arg":[0.63,0.52,0.55,0.61,0.49],
    },
    "Factor 2 — Ausencia de Corrupción": {
        "arg":0.39,"lac":0.43,"ocde":0.71,
        "desc":"Jueces y funcionarios de altas cortes libres de sobornos e influencias privadas.",
        "subfactores":["Corrupción en ejecutivo","Corrupción en legislativo","Corrupción en judicial","Corrupción en policía"],
        "sub_arg":[0.38,0.35,0.41,0.43],
    },
    "Factor 7 — Justicia Civil": {
        "arg":0.42,"lac":0.44,"ocde":0.68,
        "desc":"Procesos accesibles, expeditos, sin discriminación e independientes.",
        "subfactores":["Accesibilidad","Sin discriminación","Sin corrupción","Sin influencia indebida","Sin demoras irrazonables","Ejecución efectiva"],
        "sub_arg":[0.44,0.48,0.39,0.40,0.35,0.47],
    },
    "Factor 8 — Justicia Penal": {
        "arg":0.38,"lac":0.40,"ocde":0.62,
        "desc":"Sistema penal efectivo, imparcial y sin detenciones preventivas abusivas.",
        "subfactores":["Efectividad investigativa","Adjudicación imparcial","Sin detención preventiva excesiva","Sin influencia política","Sin corrupción","Sin trato degradante"],
        "sub_arg":[0.44,0.37,0.30,0.36,0.41,0.42],
    },
}

# ══════════════════════════════════════════════════════════════════════════════
# DATOS ESTÁTICOS — World Bank WGI 2022
# Fuente: databank.worldbank.org — escala -2.5 a +2.5
# ══════════════════════════════════════════════════════════════════════════════
_WGI_DIM = [
    "Estado de Derecho","Control de Corrupción","Efectividad Gubernamental",
    "Calidad Regulatoria","Estabilidad Política","Voz y Rendición de Cuentas",
]
_WGI_ARG  = [-0.21, -0.35, -0.22, -0.06, -0.28, 0.32]
_WGI_ROL  = {
    "Uruguay":1.12,"Chile":0.97,"Costa Rica":0.58,"Brasil":0.03,
    "Argentina":-0.21,"Colombia":-0.31,"Perú":-0.44,"México":-0.60,"Bolivia":-0.73,
}

# ══════════════════════════════════════════════════════════════════════════════
# DATOS ESTÁTICOS — IPC Transparencia Internacional 2023
# Fuente: transparency.org/en/cpi — escala 0–100
# ══════════════════════════════════════════════════════════════════════════════
_IPC_LAC  = {
    "Uruguay":74,"Chile":63,"Costa Rica":55,"Brasil":36,"Argentina":37,
    "Ecuador":33,"Colombia":34,"Perú":33,"Bolivia":31,"México":31,"Paraguay":25,
}
_IPC_HIST = {
    2013:34,2014:34,2015:32,2016:36,2017:39,2018:40,
    2019:45,2020:42,2021:38,2022:38,2023:37,
}

# ══════════════════════════════════════════════════════════════════════════════
# DATOS ESTÁTICOS — V-Dem Institute (Varieties of Democracy) 2023
# Fuente: v-dem.net — escala 0–1; mayor valor = más democrático/independiente
# ══════════════════════════════════════════════════════════════════════════════

# Judicial Constraints on the Executive Index — Argentina histórico
_VDEM_JCI_HIST = {
    2000:0.74,2002:0.70,2004:0.72,2006:0.73,2008:0.72,2010:0.71,
    2012:0.72,2014:0.69,2016:0.67,2018:0.64,2020:0.61,2022:0.59,2023:0.58,
}

# JCI comparativa regional (2023)
_VDEM_JCI_REG = {
    "Uruguay":0.89,"Chile":0.87,"Costa Rica":0.84,"Brasil":0.72,
    "Colombia":0.68,"Argentina":0.59,"Perú":0.55,"México":0.52,"Bolivia":0.42,
}

# High Court Independence — Argentina histórico
_VDEM_HCI_HIST = {
    2000:0.71,2002:0.66,2004:0.68,2006:0.69,2008:0.69,2010:0.68,
    2012:0.70,2014:0.67,2016:0.65,2018:0.63,2020:0.60,2022:0.58,2023:0.57,
}

# Judicial Appointments — calidad del proceso (escala 0–4, CEPEJ/V-Dem cruzado)
_VDEM_APPT_DIMS   = [
    "Concurso meritocrático","Independencia política del proceso",
    "Transparencia de puntajes","Paridad de género","Fiscalización ciudadana",
]
_VDEM_APPT_ARG    = [3.2, 2.8, 2.5, 2.1, 2.3]
_VDEM_APPT_LAC    = [3.3, 3.0, 2.9, 2.7, 2.6]
_VDEM_APPT_OCDE   = [4.1, 4.3, 4.2, 3.9, 3.8]

# ══════════════════════════════════════════════════════════════════════════════
# DATOS ESTÁTICOS — RECPJ / CEPEJ Benchmarks
# Fuente: CEPEJ (Comisión Europea para la Eficacia de la Justicia)
#         Red Europea de Consejos del Poder Judicial — Justice at a Glance
# ══════════════════════════════════════════════════════════════════════════════

# Benchmarks objetivo (CEPEJ/OCDE)
_CEPEJ_BENCH = {
    "Clearance Rate (%)":      {"objetivo":100.0, "alerta":95.0,  "unidad":"%",    "desc":"Casos resueltos / casos ingresados × 100. <100% = acumulación de rezago."},
    "Disposition Time (días)": {"objetivo":240,   "alerta":400,   "unidad":"días", "desc":"Tiempo promedio estimado para resolver un caso (casos pendientes / tasa de resolución × 365)."},
    "% Vacantes por concurso": {"objetivo":100.0, "alerta":80.0,  "unidad":"%",    "desc":"Porcentaje de cargos vacantes que tienen concurso en trámite o completado."},
    "Presupuesto autónomo":    {"objetivo":1,     "alerta":0,     "unidad":"bool", "desc":"El Consejo gestiona presupuesto sin intervención del Ejecutivo (1=Sí / 0=Parcial)."},
}

# Valores de referencia de países LAC/OCDE para Clearance Rate
_CEPEJ_CR_COMP = {
    "Alemania":105,"Francia":101,"España":97,"Chile":95,
    "Uruguay":93,"Colombia":87,"Argentina (est.)":82,"Perú":78,"México":74,
}

# Valores de referencia Disposition Time (días) para fuero civil 1ª instancia
_CEPEJ_DT_COMP = {
    "Noruega":98,"Dinamarca":110,"Países Bajos":115,"Alemania":184,
    "España":253,"Chile":310,"Uruguay":340,"Colombia":520,
    "Argentina (est.)":420,"OCDE prom.":240,
}

# ══════════════════════════════════════════════════════════════════════════════
# DATOS ESTÁTICOS — CEJAS (Centro de Estudios de Justicia de las Américas)
# Fuente: cejamericas.org — Índice de Independencia Personal de Magistrados
# Escala 0–1; mayor valor = mayor independencia
# ══════════════════════════════════════════════════════════════════════════════
_CEJAS_DIMS = [
    "Inamovilidad real en el cargo",
    "Protección contra remoción arbitraria",
    "Inmunidad frente a presión del Ejecutivo",
    "Protección contra campañas de desprestigio",
    "Remuneración adecuada y protegida",
    "Autonomía en asignación de causas",
]
_CEJAS_ARG    = [0.58, 0.52, 0.54, 0.41, 0.67, 0.55]
_CEJAS_LAC    = [0.62, 0.59, 0.57, 0.53, 0.61, 0.60]
_CEJAS_TARGET = [0.80, 0.80, 0.80, 0.80, 0.80, 0.80]

# CEJAS histórico compuesto (Índice agregado de Independencia Personal)
_CEJAS_HIST = {
    2012:0.63,2014:0.62,2016:0.60,2018:0.58,2020:0.55,2022:0.54,2023:0.54,
}

# ══════════════════════════════════════════════════════════════════════════════
# DATOS ESTÁTICOS — ODS 16 (ONU)
# ══════════════════════════════════════════════════════════════════════════════
_ODS16 = [
    {"id":"16.3.2","titulo":"Presos sin condena",
     "valor":48.5,"meta":30.0,"unidad":"%","anio":2022,
     "fuente":"UNODC / SNEEP Argentina","semaforo":"rojo",
     "desc":"Casi la mitad de los detenidos están en prisión preventiva sin sentencia firme."},
    {"id":"16.3.1","titulo":"Víctimas que denunciaron",
     "valor":24.2,"meta":60.0,"unidad":"%","anio":2021,
     "fuente":"INDEC / Encuesta de Victimización","semaforo":"rojo",
     "desc":"3 de cada 4 víctimas de delito no acuden al sistema formal de justicia."},
    {"id":"16.6.2","titulo":"Satisfacción con justicia",
     "valor":42.1,"meta":70.0,"unidad":"%","anio":2022,
     "fuente":"Latinobarómetro 2023","semaforo":"alerta",
     "desc":"Porcentaje de ciudadanos satisfechos con el funcionamiento del sistema judicial."},
    {"id":"16.5.1","titulo":"Soborno en administración pública",
     "valor":11.3,"meta":0.0,"unidad":"%","anio":2021,
     "fuente":"UNODC / GCB Latinoamérica","semaforo":"alerta",
     "desc":"Personas que pagaron un soborno al interactuar con instituciones públicas."},
    {"id":"16.b.1","titulo":"Discriminación en acceso a justicia",
     "valor":18.7,"meta":0.0,"unidad":"%","anio":2022,
     "fuente":"WJP Factor 7 — Justicia Civil","semaforo":"alerta",
     "desc":"Reporte de discriminación (género, etnia, nivel socioeconómico) al acceder al sistema."},
]

# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTES INSTITUCIONALES
# ══════════════════════════════════════════════════════════════════════════════
PRESUPUESTO_CSJN_ARS = 28_500_000_000
PRESUPUESTO_PJN_ARS  = 280_000_000_000
SENTENCIAS_PJN_ANIO  = 85_000
POBLACION_ARGENTINA  = 46_000_000


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════
def _cargar(nombre):
    """Busca el archivo en data/ primero (versiones más ricas), luego en root."""
    for prefix in ("data", ""):
        path = os.path.join(ROOT, prefix, nombre) if prefix else os.path.join(ROOT, nombre)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = _json.load(f)
            if isinstance(data, list):
                return data
            for k in ("data","magistrados","vacantes","designaciones","causas","results"):
                if k in data:
                    return data[k]
            return list(data.values())[0] if data else []
    raise FileNotFoundError(nombre)

def _cargar_safe(nombre):
    try: return _cargar(nombre)
    except: return []

def _cargar_datos_jus(keyword: str) -> list:
    """
    Carga el primer archivo JSON en datos_jus/ cuyo nombre contenga `keyword`.
    Devuelve lista de registros o [] si no encuentra nada.
    """
    dj_dir = os.path.join(ROOT, "datos_jus")
    if not os.path.isdir(dj_dir):
        return []
    for fname in sorted(os.listdir(dj_dir)):
        if keyword in fname and fname.endswith(".json"):
            try:
                with open(os.path.join(dj_dir, fname), encoding="utf-8") as f:
                    d = _json.load(f)
                if isinstance(d, list):
                    return d
                for k in ("data","results","records","rows"):
                    if k in d:
                        return d[k]
                return list(d.values())[0] if d else []
            except Exception:
                pass
    return []

def _cargar_oralidad_all() -> list:
    """
    Concatena todos los archivos de oralidad en datos_jus/.
    Columnas clave: causa_fecha_ingreso/recepcion, proceso_finalización_fecha,
                    proceso_resultado_descripcion, provincia_nombre.
    """
    dj_dir = os.path.join(ROOT, "datos_jus")
    if not os.path.isdir(dj_dir):
        return []
    rows = []
    for fname in sorted(os.listdir(dj_dir)):
        if "oralidad-en-los-procesos-civiles" in fname and fname.endswith(".json"):
            # skip encuestas de satisfacción (no tienen causas)
            if "encuesta" in fname:
                continue
            try:
                with open(os.path.join(dj_dir, fname), encoding="utf-8") as f:
                    d = _json.load(f)
                chunk = d if isinstance(d, list) else d.get("data", d.get("results", []))
                rows.extend(chunk)
            except Exception:
                pass
    return rows


def _cargar_cvs_stats() -> dict:
    """
    Lee el JSON de curriculums vitae de candidatos a magistrados desde datos_jus/.
    Devuelve estadísticas agregadas listas para serializar a JSON.
    """
    from collections import Counter as _Counter
    registros = _cargar_datos_jus("curriculums-vitae")
    if not registros:
        return {"total": 0, "universidades": [], "provincias": [], "ambitos": [], "tabla": []}

    total = len(registros)

    univs = _Counter(r.get("universidad", "Sin datos") or "Sin datos" for r in registros)
    top_univs = [{"nombre": k, "cantidad": v}
                 for k, v in univs.most_common(15) if k and k != "Sin datos"]

    provs = _Counter(r.get("provincia_nacimiento_magistrado", "Sin datos") or "Sin datos"
                     for r in registros)
    top_provs = [{"provincia": k, "cantidad": v}
                 for k, v in sorted(provs.items(), key=lambda x: -x[1])
                 if k and k != "Sin datos"][:20]

    ambitos = _Counter(r.get("ambito_origen_concurso_descripcion", "Sin datos") or "Sin datos"
                       for r in registros)
    top_ambitos = [{"ambito": k, "cantidad": v} for k, v in ambitos.most_common(10)]

    tabla = [{"nombre":    r.get("nombre_magistrado", ""),
              "concurso":  r.get("numero_concurso", ""),
              "ambito":    r.get("ambito_origen_concurso_descripcion", ""),
              "universidad": r.get("universidad", ""),
              "provincia": r.get("provincia_nacimiento_magistrado", ""),
              "link_cv":   r.get("link_html_curriculum_magistrado", "")}
             for r in registros[:200]]

    return {"total": total, "universidades": top_univs,
            "provincias": top_provs, "ambitos": top_ambitos, "tabla": tabla}

def _col(recs, *kws):
    if not recs: return None
    keys = recs[0].keys()
    for kw in kws:
        m = next((k for k in keys if kw.lower() in k.lower()), None)
        if m: return m
    return None

def _es_csjn(val):
    v = val.lower()
    return any(p in v for p in ("corte suprema","csjn","suprema","corte"))

def _antiguedad_bucket(dias):
    if dias < 365:  return "< 1 año"
    if dias < 730:  return "1–2 años"
    if dias < 1460: return "2–4 años"
    if dias < 2920: return "4–8 años"
    return "> 8 años"

BUCKET_ORDER = ["< 1 año","1–2 años","2–4 años","4–8 años","> 8 años"]

def _head(titulo):
    return (
        "<!DOCTYPE html><html lang='es'><head><meta charset='UTF-8'>"
        f"<title>{titulo}</title>{PLOTLY_JS}"
        f"<style>{BASE_CSS}</style></head><body>"
    )


# ══════════════════════════════════════════════════════════════════════════════
# APIs JSON
# ══════════════════════════════════════════════════════════════════════════════
@router.get("/api/kpis")
def api_kpis():
    try:
        mag = _cargar("magistrados.json")
        vac = _cargar("vacantes.json")
        des = _cargar("designaciones.json")
        tm = len(mag); tv = len(vac); cu = tm - tv
        return {
            "total_magistrados": tm, "total_vacantes": tv, "cargos_cubiertos": cu,
            "tasa_vacancia_pct": calcular_tasa_vacancia(cu, tm),
            "total_designaciones": len(des),
            "costo_por_sentencia": calcular_costo_por_sentencia(PRESUPUESTO_PJN_ARS, SENTENCIAS_PJN_ANIO),
            "ministros_csjn": 5,
        }
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/api/vacancia")
def api_vacancia():
    try:
        vac = _cargar("vacantes.json")
        col = _col(vac, "jurisdic","provincia","lugar","sede")
        if not col:
            return {"labels":[],"values":[],"col_detectada": None}
        top = Counter(str(r.get(col,"Sin dato")) for r in vac).most_common(15)
        return {"labels":[x[0] for x in top],"values":[x[1] for x in top],
                "col_detectada": col,"total": len(vac)}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/api/designaciones")
def api_designaciones():
    try:
        des = _cargar("designaciones.json")
        cf = _col(des,"fuero","ambito","organo","tipo_cargo")
        cd = _col(des,"fecha","anio","año","date","periodo")
        fueros = {}
        if cf:
            top = Counter(str(r.get(cf,"")) for r in des).most_common(8)
            fueros = {"labels":[x[0] for x in top],"values":[x[1] for x in top]}
        por_anio = {}
        if cd:
            c: Counter = Counter()
            for r in des:
                a = str(r.get(cd,""))[:4]
                if a.isdigit() and 2000 <= int(a) <= 2026:
                    c[a] += 1
            s = sorted(c.items())
            por_anio = {"labels":[x[0] for x in s],"values":[x[1] for x in s]}
        return {"por_fuero": fueros,"por_anio": por_anio,"total": len(des)}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/api/corte")
def api_corte():
    try:
        causas_raw = _cargar_safe("estadisticas_causas.json") or _cargar_safe("pjn_checkpoint.json")
        col_org  = _col(causas_raw,"juzgado","organo","tribunal","camara","instancia")
        col_lat  = _col(causas_raw,"latencia","dias","tiempo_proceso","duracion","antiguedad")
        col_est  = _col(causas_raw,"estado","situac","resolucion","resultado")
        col_fech = _col(causas_raw,"fecha_inicio","inicio","ingreso","fecha_radicacion","fecha")

        csjn = ([r for r in causas_raw if _es_csjn(str(r.get(col_org,"")))]
                if col_org else [])
        tiene_datos_reales = len(csjn) > 0
        buckets: Counter = Counter()
        sentencias = pendientes = 0

        if tiene_datos_reales:
            palabras_ok = ("resuelto","sentencia","archivado","cerrado","concluido","finalizado","acuerdo")
            for r in csjn:
                est_val = str(r.get(col_est,"")).lower() if col_est else ""
                if any(p in est_val for p in palabras_ok):
                    sentencias += 1
                else:
                    pendientes += 1
                    dias = 0
                    if col_lat:
                        try: dias = float(r.get(col_lat, 0) or 0)
                        except: pass
                    elif col_fech:
                        try:
                            fecha = datetime.strptime(str(r.get(col_fech,""))[:10], "%Y-%m-%d")
                            dias = (datetime.now() - fecha).days
                        except: pass
                    buckets[_antiguedad_bucket(dias) if dias > 0 else "Sin fecha"] += 1
            total_csjn = len(csjn)
        else:
            total_csjn = 25_000; sentencias = 4_800; pendientes = total_csjn - sentencias
            buckets = Counter({"< 1 año":3200,"1–2 años":4500,"2–4 años":6800,"4–8 años":5900,"> 8 años":4600})

        ant_labels = [b for b in BUCKET_ORDER if b in buckets] + [b for b in buckets if b not in BUCKET_ORDER]
        return {
            "tiene_datos_reales": tiene_datos_reales,
            "total_expedientes": total_csjn, "pendientes": pendientes, "sentencias": sentencias,
            "eficiencia_pct": round(sentencias / max(total_csjn,1) * 100, 1),
            "costo_x_sentencia": round(PRESUPUESTO_CSJN_ARS / max(sentencias,1), 0),
            "costo_x_habitante": round(PRESUPUESTO_CSJN_ARS / POBLACION_ARGENTINA, 2),
            "presupuesto_csjn": PRESUPUESTO_CSJN_ARS, "poblacion": POBLACION_ARGENTINA,
            "antiguedad": {"labels": ant_labels, "values": [buckets[b] for b in ant_labels]},
            "ministros": 5,
        }
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/api/cepej")
def api_cepej():
    """
    Métricas RECPJ/CEPEJ desde fuentes reales:
    - Clearance Rate + Disposition Time ← datos_jus/oralidad (causas reales)
    - % concurso_en_tramite ← datos_jus/magistrados_b12bdbb7 (columna directa)
    - Género magistratura ← datos_jus/estadistica_genero (serie 2000-2025)
    - Designaciones recientes ← datos_jus/designaciones_d4fd21f4
    - Renuncias recientes ← datos_jus/renuncias_e0e6483e (data/ si no está en root)
    """
    try:
        # ── 1. Clearance Rate y Disposition Time — fuente: oralidad ─────────
        #    proceso_resultado_descripcion: valor no vacío = causa resuelta
        #    causa_fecha_ingreso / proceso_finalización_fecha → Disposition Time real
        oralidad = _cargar_oralidad_all()
        total_causas_oral = len(oralidad)

        col_res  = _col(oralidad, "proceso_resultado","resultado","finalizacion_tipo")
        col_ing  = _col(oralidad, "causa_fecha_ingreso","causa_fecha_recepcion","fecha_ingreso","fecha_recepcion")
        col_fin  = _col(oralidad, "proceso_finalización_fecha","proceso_finalizacion_fecha","fecha_finalizacion")

        resueltos_oral = 0
        tiempos_oral   = []
        if oralidad:
            for r in oralidad:
                res_val = str(r.get(col_res,"")).strip() if col_res else ""
                if res_val and res_val.lower() not in ("","nan","none","sin dato"):
                    resueltos_oral += 1
                # Disposition Time real (ingreso → fin)
                if col_ing and col_fin:
                    try:
                        t_in  = datetime.strptime(str(r.get(col_ing,""))[:10], "%Y-%m-%d")
                        t_fin = datetime.strptime(str(r.get(col_fin,""))[:10], "%Y-%m-%d")
                        dias  = (t_fin - t_in).days
                        if 0 < dias < 5000:
                            tiempos_oral.append(dias)
                    except Exception:
                        pass

        clearance_rate = round(resueltos_oral / max(total_causas_oral,1) * 100, 1) if total_causas_oral > 0 else None
        disp_time_real = round(sum(tiempos_oral) / len(tiempos_oral), 0) if tiempos_oral else None

        # ── 2. % Vacantes con concurso_en_tramite — datos_jus magistrados ───
        #    columna exacta: concurso_en_tramite = "SI"/"NO"
        dj_mag = _cargar_datos_jus("magistrados-justicia-federal")
        vacantes_dj     = [r for r in dj_mag if str(r.get("cargo_vacante","")).upper() in ("SI","SÍ","S","TRUE","1","YES")]
        con_concurso_dj = sum(1 for r in vacantes_dj if str(r.get("concurso_en_tramite","")).upper() in ("SI","SÍ","S","TRUE","1","YES"))
        total_vac_dj    = len(vacantes_dj)
        pct_concurso    = round(con_concurso_dj / max(total_vac_dj,1) * 100, 1) if total_vac_dj > 0 else None

        # Género desde mismo dataset magistrados datos_jus
        fem = masc = 0
        for r in dj_mag:
            g = str(r.get("magistrado_genero","")).upper()
            if g in ("F","FEMENINO"):    fem  += 1
            elif g in ("M","MASCULINO"): masc += 1
        pct_fem = round(fem / max(fem+masc,1) * 100, 1) if (fem+masc) > 0 else None

        # ── 3. Designaciones recientes — datos_jus designaciones ────────────
        dj_des = _cargar_datos_jus("designaciones-de-magistrados")
        des_recientes = sum(
            1 for r in dj_des
            if str(r.get("fecha_desginacion","") or r.get("fecha_designacion",""))[:4].lstrip("0") in ("2023","2024","2025","2026")
        )

        # ── 4. Renuncias recientes — datos_jus renuncias ────────────────────
        dj_ren = _cargar_datos_jus("renuncias-de-magistrados")
        # fallback: data/renuncias.json si datos_jus vacío
        if not dj_ren:
            dj_ren = _cargar_safe("renuncias.json")
        ren_recientes = sum(
            1 for r in dj_ren
            if str(r.get("fecha_renuncia",""))[:4] in ("2023","2024","2025","2026")
        )

        return {
            "tiene_datos_reales": total_causas_oral > 0,
            # Clearance Rate / Disposition Time — fuente: oralidad real
            "clearance_rate":         clearance_rate,
            "disposition_time_dias":  int(disp_time_real) if disp_time_real else None,
            "total_causas_oralidad":  total_causas_oral,
            "causas_resueltas":       resueltos_oral,
            "tiempos_computados":     len(tiempos_oral),
            # Concursos — fuente: datos_jus magistrados
            "total_vacantes":         total_vac_dj,
            "vacantes_con_concurso":  con_concurso_dj,
            "pct_vacantes_concurso":  pct_concurso,
            # Género — fuente: datos_jus magistrados
            "magistradas_femenino":   fem,
            "magistrados_masculino":  masc,
            "pct_magistradas_mujeres": pct_fem,
            # Dinámica reciente
            "designaciones_recientes": des_recientes,
            "renuncias_recientes":     ren_recientes,
        }
    except Exception as e:
        return JSONResponse({"error": str(e), "traceback": traceback.format_exc()}, status_code=500)


@router.get("/api/oralidad")
def api_oralidad():
    """
    Clearance Rate y Disposition Time por provincia, desde datos_jus/oralidad.
    Fuente: Programa Oralidad Civil — Ministerio de Justicia.
    ~60.000 causas reales de 11 provincias.
    """
    try:
        oralidad = _cargar_oralidad_all()
        if not oralidad:
            return {"error": "No se encontraron archivos de oralidad en datos_jus/"}

        col_res  = _col(oralidad, "proceso_resultado","resultado","finalizacion_tipo")
        col_ing  = _col(oralidad, "causa_fecha_ingreso","causa_fecha_recepcion","fecha_ingreso")
        col_fin  = _col(oralidad, "proceso_finalización_fecha","proceso_finalizacion_fecha","fecha_finalizacion")
        col_prov = _col(oralidad, "provincia_nombre","provincia","jurisdiccion")
        col_tipo = _col(oralidad, "clase_proceso_descripcion","tipo_proceso","clase_proceso")

        por_provincia: dict = {}
        tipos_proceso: Counter = Counter()

        for r in oralidad:
            prov = str(r.get(col_prov,"Sin dato")) if col_prov else "Sin dato"
            if prov not in por_provincia:
                por_provincia[prov] = {"total":0,"resueltos":0,"tiempos":[]}
            por_provincia[prov]["total"] += 1

            res_val = str(r.get(col_res,"")).strip() if col_res else ""
            if res_val and res_val.lower() not in ("","nan","none","sin dato"):
                por_provincia[prov]["resueltos"] += 1

            if col_ing and col_fin:
                try:
                    t_in  = datetime.strptime(str(r.get(col_ing,""))[:10], "%Y-%m-%d")
                    t_fin = datetime.strptime(str(r.get(col_fin,""))[:10], "%Y-%m-%d")
                    dias  = (t_fin - t_in).days
                    if 0 < dias < 5000:
                        por_provincia[prov]["tiempos"].append(dias)
                except Exception:
                    pass

            if col_tipo:
                t = str(r.get(col_tipo,"")).strip()
                if t:
                    tipos_proceso[t] += 1

        # Construir resumen por provincia
        resumen = []
        for prov, d in sorted(por_provincia.items()):
            cr  = round(d["resueltos"] / max(d["total"],1) * 100, 1)
            dt  = round(sum(d["tiempos"]) / len(d["tiempos"]), 0) if d["tiempos"] else None
            resumen.append({
                "provincia":        prov,
                "total_causas":     d["total"],
                "causas_resueltas": d["resueltos"],
                "clearance_rate":   cr,
                "disposition_time": int(dt) if dt else None,
            })

        top_tipos = tipos_proceso.most_common(8)

        return {
            "total_causas":       len(oralidad),
            "provincias":         resumen,
            "tipos_proceso":      {"labels":[x[0] for x in top_tipos],
                                   "values":[x[1] for x in top_tipos]},
            "col_resultado_detectada": col_res,
            "col_fecha_fin_detectada": col_fin,
        }
    except Exception as e:
        return JSONResponse({"error": str(e), "traceback": traceback.format_exc()}, status_code=500)


@router.get("/api/traslados")
def api_traslados():
    """
    Traslados de jueces — indicador RECPJ de protección contra traslados arbitrarios.
    Fuente: datos_jus/traslados_ade07cd0.json — 113 registros.
    Columnas: magistrado_nombre, fecha_traslado, motivo_traslado,
              organo_nombre_desde/hacia, provincia_nombre_desde/hacia.
    """
    try:
        traslados = _cargar_datos_jus("traslados-de-jueces")
        if not traslados:
            return {"total": 0, "error": "No se encontró archivo de traslados en datos_jus/"}

        total = len(traslados)

        # Por motivo
        por_motivo: Counter = Counter()
        for r in traslados:
            m = str(r.get("motivo_traslado","Sin dato")).strip() or "Sin dato"
            por_motivo[m] += 1

        # Por año
        por_anio: Counter = Counter()
        for r in traslados:
            fecha = str(r.get("fecha_traslado","") or r.get("norma_fecha",""))[:4]
            if fecha.isdigit() and 2000 <= int(fecha) <= 2026:
                por_anio[fecha] += 1
        por_anio_sorted = sorted(por_anio.items())

        # Por provincia destino
        por_prov_destino: Counter = Counter()
        for r in traslados:
            p = str(r.get("provincia_nombre_hacia","Sin dato")).strip() or "Sin dato"
            por_prov_destino[p] += 1

        # Por género
        fem = masc = 0
        for r in traslados:
            g = str(r.get("magistrado_genero","")).upper()
            if g in ("F","FEMENINO"):    fem  += 1
            elif g in ("M","MASCULINO"): masc += 1

        return {
            "total":           total,
            "por_motivo":      {"labels":list(por_motivo.keys()), "values":list(por_motivo.values())},
            "por_anio":        {"labels":[x[0] for x in por_anio_sorted],
                                "values":[x[1] for x in por_anio_sorted]},
            "por_prov_destino":{"labels":[x[0] for x in por_prov_destino.most_common(10)],
                                "values":[x[1] for x in por_prov_destino.most_common(10)]},
            "genero":          {"femenino": fem, "masculino": masc},
        }
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/api/genero")
def api_genero():
    """
    Serie temporal de designaciones por género 2000–2025.
    Fuente: datos_jus/estadistica_genero_84a9215b.json — 429 registros.
    Columnas: designacion_anio, cargo_tipo, instancia_tipo,
              cantidad_varones, cantidad_mujeres.
    """
    try:
        gen_data = _cargar_datos_jus("estadistica-de-designaciones")
        if not gen_data:
            return {"error": "No se encontró archivo de estadística por género en datos_jus/"}

        # Serie anual agregada
        por_anio: dict = {}
        por_cargo: dict = {}
        for r in gen_data:
            anio = str(r.get("designacion_anio",""))[:4]
            if not (anio.isdigit() and 2000 <= int(anio) <= 2026):
                continue
            v = int(r.get("cantidad_varones",  0) or 0)
            m = int(r.get("cantidad_mujeres",  0) or 0)
            if anio not in por_anio:
                por_anio[anio] = {"varones":0,"mujeres":0}
            por_anio[anio]["varones"] += v
            por_anio[anio]["mujeres"] += m

            cargo = str(r.get("cargo_tipo","Otro")).strip()
            if cargo not in por_cargo:
                por_cargo[cargo] = {"varones":0,"mujeres":0}
            por_cargo[cargo]["varones"] += v
            por_cargo[cargo]["mujeres"] += m

        anios_sorted = sorted(por_anio.keys())
        total_v = sum(d["varones"] for d in por_anio.values())
        total_m = sum(d["mujeres"] for d in por_anio.values())

        return {
            "total_varones": total_v,
            "total_mujeres": total_m,
            "pct_mujeres":   round(total_m / max(total_v+total_m,1) * 100, 1),
            "serie_anual": {
                "anios":   anios_sorted,
                "varones": [por_anio[a]["varones"] for a in anios_sorted],
                "mujeres": [por_anio[a]["mujeres"] for a in anios_sorted],
            },
            "por_cargo": [
                {"cargo": k, "varones": v["varones"], "mujeres": v["mujeres"],
                 "pct_mujeres": round(v["mujeres"]/max(v["varones"]+v["mujeres"],1)*100,1)}
                for k,v in sorted(por_cargo.items())
            ],
        }
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/api/seleccion")
def api_seleccion():
    """
    Calidad del proceso de nombramientos — indicador V-Dem Appointments.
    Fuente: datos_jus/seleccion_aa6bcb49.json — 4278 ternas reales.
    Columnas: numero_concurso, cargo_concursado, puntaje_jurado,
              puntaje_comision_seleccion, orden_merito_plenario.
    """
    try:
        sel = _cargar_datos_jus("seleccion-de-magistrados")
        if not sel:
            return {"error": "No se encontró archivo de selección en datos_jus/"}

        total_ternas    = len(sel)
        concursos_uniq  = len(set(str(r.get("numero_concurso","")) for r in sel))

        # Puntajes jurado
        puntajes_jurado = []
        puntajes_comision = []
        for r in sel:
            try: puntajes_jurado.append(float(r.get("puntaje_jurado",0) or 0))
            except: pass
            try: puntajes_comision.append(float(r.get("puntaje_comision_seleccion",0) or 0))
            except: pass

        pj_prom = round(sum(puntajes_jurado)/len(puntajes_jurado), 2) if puntajes_jurado else None
        pc_prom = round(sum(puntajes_comision)/len(puntajes_comision), 2) if puntajes_comision else None

        # Por cargo
        por_cargo: Counter = Counter()
        for r in sel:
            c = str(r.get("cargo_concursado","")).strip()
            if c: por_cargo[c] += 1

        # Por ámbito
        por_ambito: Counter = Counter()
        for r in sel:
            a = str(r.get("ambito_origen_concurso_descripcion","")).strip()
            if a: por_ambito[a] += 1

        # Evolución por año de publicación
        por_anio_pub: Counter = Counter()
        for r in sel:
            fecha = str(r.get("fecha_publicacion_concurso",""))[:4]
            if fecha.isdigit() and 2000 <= int(fecha) <= 2026:
                por_anio_pub[fecha] += 1
        anios_sorted = sorted(por_anio_pub.items())

        return {
            "total_ternas":        total_ternas,
            "concursos_unicos":    concursos_uniq,
            "puntaje_jurado_prom": pj_prom,
            "puntaje_comision_prom": pc_prom,
            "por_cargo":  {"labels":[x[0] for x in por_cargo.most_common(8)],
                           "values":[x[1] for x in por_cargo.most_common(8)]},
            "por_ambito": {"labels":[x[0] for x in por_ambito.most_common(10)],
                           "values":[x[1] for x in por_ambito.most_common(10)]},
            "por_anio":   {"labels":[x[0] for x in anios_sorted],
                           "values":[x[1] for x in anios_sorted]},
        }
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ══════════════════════════════════════════════════════════════════════════════
# PESTAÑA: CORTE SUPREMA
# ══════════════════════════════════════════════════════════════════════════════
@router.get("/corte", response_class=HTMLResponse)
def pagina_corte():
    parts = [
        _head("Corte Suprema — CSJN"),
        nav_html("corte"),
        "<div class='contenido'>",
        DISCLAIMER,
        """<div class="scope">
  ⚖️ <strong>Corte Suprema de Justicia de la Nación (CSJN)</strong> —
  Máxima instancia judicial. Indicadores de carga, eficiencia y costo institucional.
  Las cifras marcadas con <em>(*)</em> son estimaciones basadas en el Presupuesto
  Nacional 2024 y la Memoria Anual de la CSJN.
</div>
<div class="seccion">⚖️ Composición y Eficiencia</div>
<div class="kpi-grid" id="kpi-corte"><div class="loading">Cargando…</div></div>
<div class="seccion">💰 Costo Institucional</div>
<div class="kpi-grid" id="kpi-costo"><div class="loading">Cargando…</div></div>
<div class="seccion">📂 Expedientes Pendientes por Antigüedad</div>
<div class="chart-full"><div id="graf-antiguedad" style="height:280px"></div></div>
<div class="seccion">📅 Evolución de Designaciones</div>
<div class="chart-full"><div id="graf-anio" style="height:220px"></div></div>
</div>""",
        FOOTER,
        "<script>", PLOTLY_BASE,
        r"""
async function cargar(){
  const [c, d] = await Promise.all([
    fetch('/estrategico/api/corte').then(r=>r.json()),
    fetch('/estrategico/api/designaciones').then(r=>r.json()),
  ]);
  const tag = c.tiene_datos_reales?'':' <span style="color:var(--muted);font-size:.75rem">(*)</span>';
  const ef_color = c.eficiencia_pct>=50?'var(--green)':c.eficiencia_pct>=25?'var(--gold)':'var(--red)';
  const fmt = n => n==null?'S/D':Number(n).toLocaleString('es-AR');

  document.getElementById('kpi-corte').innerHTML=`
    <div class="kpi gold"><label>Ministros en ejercicio</label>
      <div class="val">${c.ministros}</div><div class="sub">Composición actual CSJN</div></div>
    <div class="kpi"><label>Total Expedientes${tag}</label>
      <div class="val">${fmt(c.total_expedientes)}</div><div class="sub">${fmt(c.pendientes)} pendientes</div></div>
    <div class="kpi verde"><label>Sentencias / Acuerdos${tag}</label>
      <div class="val">${fmt(c.sentencias)}</div><div class="sub">causas resueltas</div></div>
    <div class="kpi" style="border-color:${ef_color}"><label>Índice de Eficiencia${tag}</label>
      <div class="val" style="color:${ef_color}">${c.eficiencia_pct}%</div>
      <div class="sub">resueltos / total expedientes</div></div>`;

  document.getElementById('kpi-costo').innerHTML=`
    <div class="kpi rojo"><label>Presupuesto CSJN 2024</label>
      <div class="val" style="font-size:1.15rem">$ ${fmt(c.presupuesto_csjn)}</div>
      <div class="sub">ARS · Presupuesto Nacional</div></div>
    <div class="kpi rojo"><label>Costo por Sentencia${tag}</label>
      <div class="val" style="font-size:1.15rem">$ ${fmt(c.costo_x_sentencia)}</div>
      <div class="sub">ARS · presupuesto ÷ acuerdos</div></div>
    <div class="kpi gold"><label>Costo por Habitante${tag}</label>
      <div class="val" style="font-size:1.3rem">$ ${Number(c.costo_x_habitante).toLocaleString('es-AR',{minimumFractionDigits:2,maximumFractionDigits:2})}</div>
      <div class="sub">ARS/habitante</div></div>
    <div class="kpi"><label>Costo PJN x Sentencia</label>
      <div class="val" style="font-size:1.15rem" id="costo-pjn">—</div>
      <div class="sub">ARS · Presupuesto PJN 2024</div></div>`;

  fetch('/estrategico/api/kpis').then(r=>r.json()).then(k=>{
    document.getElementById('costo-pjn').textContent='$ '+fmt(Math.round(k.costo_por_sentencia));
  });

  const C2={bg:'#0a1628',card:'#1a2744',gold:'#c9a227',blue:'#3b82f6',red:'#e63946',green:'#22c55e',text:'#e2e8f0',muted:'#94a3b8',grid:'#2d4a7a'};
  const Lx=(x={})=>Object.assign({plot_bgcolor:C2.card,paper_bgcolor:C2.card,font:{color:C2.text,family:'Segoe UI',size:12},margin:{l:10,r:10,t:30,b:40},xaxis:{gridcolor:C2.grid,linecolor:C2.grid},yaxis:{gridcolor:C2.grid,linecolor:C2.grid}},x);

  if(c.antiguedad&&c.antiguedad.labels&&c.antiguedad.labels.length){
    const vals=c.antiguedad.values, maxV=Math.max(...vals);
    Plotly.newPlot('graf-antiguedad',[{type:'bar',x:c.antiguedad.labels,y:vals,
      marker:{color:vals.map(v=>v===maxV?'#e63946':'#c9a227'),opacity:.88},
      hovertemplate:'<b>%{x}</b><br>Expedientes: %{y:,}<extra></extra>'}],
      Lx({yaxis:{gridcolor:C2.grid,title:{text:'Expedientes',font:{size:11}}},margin:{l:60,r:10,t:10,b:40}}),
      {responsive:true,displayModeBar:false});
  } else {
    document.getElementById('graf-antiguedad').innerHTML='<p style="color:#4a5568;padding:20px">Sin datos de antigüedad</p>';
  }
  if(d.por_anio&&d.por_anio.labels&&d.por_anio.labels.length)
    Plotly.newPlot('graf-anio',[{type:'scatter',mode:'lines',fill:'tozeroy',
      x:d.por_anio.labels,y:d.por_anio.values,line:{color:C2.gold,width:2},
      fillcolor:'rgba(201,162,39,0.12)'}],Lx(),{responsive:true,displayModeBar:false});
  else
    document.getElementById('graf-anio').innerHTML='<p style="color:#4a5568;padding:16px">Sin datos de fecha</p>';
}
cargar().catch(e=>{
  document.getElementById('kpi-corte').innerHTML='<div style="color:var(--red)">Error: '+e.message+'</div>';
});
""",
        "</script></body></html>",
    ]
    return HTMLResponse("".join(parts))


# ══════════════════════════════════════════════════════════════════════════════
# PESTAÑA: CONSEJO DE LA MAGISTRATURA
# ══════════════════════════════════════════════════════════════════════════════
@router.get("/consejo", response_class=HTMLResponse)
def pagina_consejo():
    try:
        parts = [
            _head("Consejo de la Magistratura"),
            nav_html("consejo"),
            "<div class='contenido'>",
            DISCLAIMER,
            """<div class="scope">
  🏛️ <strong>Consejo de la Magistratura</strong> —
  Gestión de vacancia, administración de concursos y presupuesto del Poder Judicial.
</div>
<div class="seccion">📊 Indicadores del Consejo</div>
<div class="kpi-grid" id="kpi-consejo"><div class="loading">Cargando…</div></div>
<div class="charts">
  <div class="chart-box">
    <h2>📍 Vacancia por Jurisdicción</h2>
    <div id="graf-vacancia" style="height:360px"></div>
  </div>
  <div class="chart-box">
    <h2>📂 Designaciones por Fuero</h2>
    <div id="graf-fuero" style="height:360px"></div>
  </div>
</div>
<div class="chart-full">
  <h2>📅 Evolución Anual de Concursos / Designaciones</h2>
  <div id="graf-anio" style="height:240px"></div>
</div>
</div>""",
            FOOTER,
            "<script>", PLOTLY_BASE,
            r"""
const C2={bg:'#0a1628',card:'#1a2744',gold:'#c9a227',blue:'#3b82f6',red:'#e63946',green:'#22c55e',text:'#e2e8f0',muted:'#94a3b8',grid:'#2d4a7a'};
const Lx=(x={})=>Object.assign({plot_bgcolor:C2.card,paper_bgcolor:C2.card,font:{color:C2.text,family:'Segoe UI',size:12},margin:{l:10,r:10,t:30,b:40},xaxis:{gridcolor:C2.grid,linecolor:C2.grid},yaxis:{gridcolor:C2.grid,linecolor:C2.grid}},x);

async function cargar(){
  const[k,v,d]=await Promise.all([
    fetch('/estrategico/api/kpis').then(r=>r.json()),
    fetch('/estrategico/api/vacancia').then(r=>r.json()),
    fetch('/estrategico/api/designaciones').then(r=>r.json()),
  ]);
  document.getElementById('kpi-consejo').innerHTML=`
    <div class="kpi"><label>Total Magistrados</label>
      <div class="val">${fmt(k.total_magistrados)}</div></div>
    <div class="kpi rojo"><label>Vacantes Detectadas</label>
      <div class="val">${fmt(k.total_vacantes)}</div>
      <div class="sub">${k.tasa_vacancia_pct}% del sistema</div></div>
    <div class="kpi verde"><label>Cargos Cubiertos</label>
      <div class="val">${fmt(k.cargos_cubiertos)}</div></div>
    <div class="kpi gold"><label>Designaciones totales</label>
      <div class="val">${fmt(k.total_designaciones)}</div></div>
    <div class="kpi"><label>Costo macro x sentencia</label>
      <div class="val" style="font-size:1.1rem">$ ${fmt(Math.round(k.costo_por_sentencia))}</div>
      <div class="sub">ARS · Presupuesto PJN 2024</div></div>`;

  if(v.labels&&v.labels.length)
    Plotly.newPlot('graf-vacancia',[{type:'bar',orientation:'h',
      x:v.values,y:v.labels,marker:{color:C2.gold,opacity:.85}}],
      Lx({yaxis:{autorange:'reversed',gridcolor:C2.grid}}),
      {responsive:true,displayModeBar:false});
  else
    document.getElementById('graf-vacancia').innerHTML='<p style="color:#4a5568;padding:16px">Sin columna de jurisdicción</p>';

  if(d.por_fuero&&d.por_fuero.labels&&d.por_fuero.labels.length)
    Plotly.newPlot('graf-fuero',[{type:'pie',hole:.5,
      labels:d.por_fuero.labels,values:d.por_fuero.values,textinfo:'label+percent',
      marker:{colors:['#c9a227','#3b82f6','#22c55e','#e63946','#8b5cf6','#f97316','#06b6d4','#ec4899'],
              line:{color:'#1a2744',width:2}}}],
      Lx({showlegend:false,margin:{l:10,r:10,t:10,b:10}}),
      {responsive:true,displayModeBar:false});

  if(d.por_anio&&d.por_anio.labels&&d.por_anio.labels.length)
    Plotly.newPlot('graf-anio',[{type:'bar',
      x:d.por_anio.labels,y:d.por_anio.values,
      marker:{color:C2.gold,opacity:.85}}],
      Lx(),{responsive:true,displayModeBar:false});
}
cargar().catch(e=>{
  document.getElementById('kpi-consejo').innerHTML='<div style="color:var(--red)">Error: '+e.message+'</div>';
});
""",
            "</script></body></html>",
        ]
        return HTMLResponse("".join(parts))

    except Exception as exc:
        tb = traceback.format_exc()
        debug_html = (
            "<!DOCTYPE html><html lang='es'><head><meta charset='UTF-8'>"
            f"<title>Error — Consejo</title>"
            "<style>body{background:#0a1628;color:#e2e8f0;font-family:monospace;padding:24px}"
            "h1{color:#e63946;margin-bottom:16px}"
            "pre{background:#1a2744;padding:16px;border-radius:8px;overflow-x:auto;"
            "font-size:.85rem;line-height:1.6;border-left:4px solid #e63946}"
            "a{color:#c9a227}</style></head><body>"
            "<h1>⚠️ Error en pagina_consejo()</h1>"
            f"<pre>{tb}</pre>"
            "<p style='color:#94a3b8;margin-top:12px'>Copiá este traceback para identificar la causa exacta.</p>"
            "<p><a href='/'>← Volver al inicio</a></p>"
            "</body></html>"
        )
        return HTMLResponse(debug_html, status_code=200)


# ══════════════════════════════════════════════════════════════════════════════
# PESTAÑA: INDICADORES INTERNACIONALES
# Módulos: WJP · IPC · WGI · V-DEM · RECPJ/CEPEJ · CEJAS · ODS16 · OCDE
# ══════════════════════════════════════════════════════════════════════════════
@router.get("/indicadores", response_class=HTMLResponse)
def pagina_indicadores():

    j = _json.dumps  # alias corto

    # ── Serializar datos para JS ───────────────────────────────────────────
    wjp_labels  = list(_WJP_RANKING.keys())
    wjp_scores  = list(_WJP_RANKING.values())
    wjp_colors  = [_WJP_COLORS[p] for p in wjp_labels]
    wgi_colors  = ["#e63946" if v < -0.2 else "#f97316" if v < 0 else "#22c55e" for v in _WGI_ARG]
    rol_colors  = ["#22c55e" if v > 0 else "#e63946" for v in _WGI_ROL.values()]
    ipc_colors  = ["#22c55e" if v >= 50 else "#f97316" if v >= 35 else "#e63946" for v in _IPC_LAC.values()]

    vdem_jci_colors = ["#22c55e" if v >= 0.7 else "#f97316" if v >= 0.5 else "#e63946"
                       for v in _VDEM_JCI_REG.values()]
    vdem_appt_bg = ["#e63946" if (a/o) < 0.7 else "#f97316" if (a/o) < 0.85 else "#22c55e"
                    for a, o in zip(_VDEM_APPT_ARG, _VDEM_APPT_OCDE)]

    cepej_cr_colors = ["#22c55e" if v >= 100 else "#f97316" if v >= 90 else "#e63946"
                       for v in _CEPEJ_CR_COMP.values()]
    cepej_dt_colors = ["#22c55e" if v <= 240 else "#f97316" if v <= 450 else "#e63946"
                       for v in _CEPEJ_DT_COMP.values()]
    ocde_vals   = list(_CEPEJ_DT_COMP.values())

    data_script = (
        # WJP
        "const wjpLabels="     + j(wjp_labels)                        + ";\n"
        "const wjpScores="     + j(wjp_scores)                        + ";\n"
        "const wjpColors="     + j(wjp_colors)                        + ";\n"
        "const wjpDimLabels="  + j(_WJP_DIMS)                         + ";\n"
        "const wjpDimArg="     + j(_WJP_ARG)                          + ";\n"
        "const wjpDimLac="     + j(_WJP_LAC)                          + ";\n"
        "const wjpDimOcde="    + j(_WJP_OCDE)                         + ";\n"
        "const wjpHistAnios="  + j(list(_WJP_HIST.keys()))            + ";\n"
        "const wjpHistScores=" + j(list(_WJP_HIST.values()))          + ";\n"
        # WJP Factores clave
        "const wjpFactores="   + j(list(_WJP_FACTORES_KEY.keys()))    + ";\n"
        "const wjpFactArg="    + j([v["arg"]  for v in _WJP_FACTORES_KEY.values()]) + ";\n"
        "const wjpFactLac="    + j([v["lac"]  for v in _WJP_FACTORES_KEY.values()]) + ";\n"
        "const wjpFactOcde="   + j([v["ocde"] for v in _WJP_FACTORES_KEY.values()]) + ";\n"
        "const wjpFactDesc="   + j({k:v["desc"] for k,v in _WJP_FACTORES_KEY.items()}) + ";\n"
        # IPC
        "const ipcLabels="     + j(list(_IPC_LAC.keys()))             + ";\n"
        "const ipcValues="     + j(list(_IPC_LAC.values()))           + ";\n"
        "const ipcColors="     + j(ipc_colors)                        + ";\n"
        "const ipcHistAnios="  + j(list(_IPC_HIST.keys()))            + ";\n"
        "const ipcHistScores=" + j(list(_IPC_HIST.values()))          + ";\n"
        # WGI
        "const wgiLabels="     + j(_WGI_DIM)                          + ";\n"
        "const wgiArg="        + j(_WGI_ARG)                          + ";\n"
        "const wgiColors="     + j(wgi_colors)                        + ";\n"
        "const rolLabels="     + j(list(_WGI_ROL.keys()))             + ";\n"
        "const rolValues="     + j(list(_WGI_ROL.values()))           + ";\n"
        "const rolColors="     + j(rol_colors)                        + ";\n"
        # V-Dem
        "const vdemJciAnios="  + j(list(_VDEM_JCI_HIST.keys()))       + ";\n"
        "const vdemJciScores=" + j(list(_VDEM_JCI_HIST.values()))     + ";\n"
        "const vdemHciAnios="  + j(list(_VDEM_HCI_HIST.keys()))       + ";\n"
        "const vdemHciScores=" + j(list(_VDEM_HCI_HIST.values()))     + ";\n"
        "const vdemRegLabels=" + j(list(_VDEM_JCI_REG.keys()))        + ";\n"
        "const vdemRegValues=" + j(list(_VDEM_JCI_REG.values()))      + ";\n"
        "const vdemRegColors=" + j(vdem_jci_colors)                   + ";\n"
        "const vdemApptDims="  + j(_VDEM_APPT_DIMS)                   + ";\n"
        "const vdemApptArg="   + j(_VDEM_APPT_ARG)                    + ";\n"
        "const vdemApptLac="   + j(_VDEM_APPT_LAC)                    + ";\n"
        "const vdemApptOcde="  + j(_VDEM_APPT_OCDE)                   + ";\n"
        "const vdemApptBg="    + j(vdem_appt_bg)                      + ";\n"
        # CEPEJ
        "const cepejCrLabels=" + j(list(_CEPEJ_CR_COMP.keys()))       + ";\n"
        "const cepejCrValues=" + j(list(_CEPEJ_CR_COMP.values()))     + ";\n"
        "const cepejCrColors=" + j(cepej_cr_colors)                   + ";\n"
        "const cepejDtLabels=" + j(list(_CEPEJ_DT_COMP.keys()))       + ";\n"
        "const cepejDtValues=" + j(list(_CEPEJ_DT_COMP.values()))     + ";\n"
        "const cepejDtColors=" + j(cepej_dt_colors)                   + ";\n"
        # CEJAS
        "const cejasDims="     + j(_CEJAS_DIMS)                        + ";\n"
        "const cejasArg="      + j(_CEJAS_ARG)                         + ";\n"
        "const cejasLac="      + j(_CEJAS_LAC)                         + ";\n"
        "const cejasTarget="   + j(_CEJAS_TARGET)                      + ";\n"
        "const cejasHistAnios="+ j(list(_CEJAS_HIST.keys()))           + ";\n"
        "const cejasHistScores="+ j(list(_CEJAS_HIST.values()))        + ";\n"
        # ODS 16
        "const odsData="       + j(_ODS16)                             + ";\n"
    )

    # ── Script de gráficos (sin f-string para evitar conflicto de llaves) ──
    chart_script = r"""
const C2={bg:'#0a1628',card:'#1a2744',gold:'#c9a227',blue:'#3b82f6',red:'#e63946',
          green:'#22c55e',text:'#e2e8f0',muted:'#94a3b8',grid:'#2d4a7a',purple:'#8b5cf6',orange:'#f97316'};
const Lx=(x={})=>Object.assign({
  plot_bgcolor:C2.card,paper_bgcolor:C2.card,
  font:{color:C2.text,family:'Segoe UI',size:12},
  margin:{l:10,r:10,t:20,b:40},
  xaxis:{gridcolor:C2.grid,linecolor:C2.grid},
  yaxis:{gridcolor:C2.grid,linecolor:C2.grid},
},x);
const cfg={responsive:true,displayModeBar:false};

// ═══════════════════════════════════════════════
// 1. WJP — Ranking Regional
// ═══════════════════════════════════════════════
Plotly.newPlot('graf-wjp-rank',[{type:'bar',orientation:'h',x:wjpScores,y:wjpLabels,
  text:wjpScores.map(v=>v.toFixed(2)),textposition:'outside',
  marker:{color:wjpColors,opacity:.9},
  hovertemplate:'<b>%{y}</b><br>Score WJP: %{x}<extra></extra>'}],
  Lx({xaxis:{range:[0,0.82],title:{text:'Score (0–1)',font:{size:11}}},
    yaxis:{autorange:'reversed'},margin:{l:10,r:60,t:10,b:40},
    shapes:[{type:'line',x0:0.47,x1:0.47,y0:-0.5,y1:wjpLabels.length-0.5,
             line:{color:C2.gold,width:2,dash:'dot'}}],
    annotations:[{x:0.47,y:0.3,xanchor:'left',text:'ARG 0.47',
                  font:{color:C2.gold,size:11},showarrow:false}]}),cfg);

// ─── WJP Radar 8 dimensiones ───
const radarLabels=[...wjpDimLabels,wjpDimLabels[0]];
Plotly.newPlot('graf-wjp-radar',[
  {type:'scatterpolar',fill:'toself',name:'Argentina',
   r:[...wjpDimArg,wjpDimArg[0]],theta:radarLabels,
   line:{color:C2.gold,width:2},fillcolor:'rgba(201,162,39,0.15)'},
  {type:'scatterpolar',fill:'toself',name:'LAC prom.',
   r:[...wjpDimLac,wjpDimLac[0]],theta:radarLabels,
   line:{color:C2.blue,width:1.5,dash:'dot'},fillcolor:'rgba(59,130,246,0.06)'},
  {type:'scatterpolar',fill:'toself',name:'OCDE prom.',
   r:[...wjpDimOcde,wjpDimOcde[0]],theta:radarLabels,
   line:{color:C2.green,width:1.5,dash:'dash'},fillcolor:'rgba(34,197,94,0.06)'},
],{polar:{bgcolor:C2.card,
   radialaxis:{range:[0,1],gridcolor:C2.grid,tickfont:{size:10,color:C2.muted}},
   angularaxis:{gridcolor:C2.grid,tickfont:{size:9,color:C2.text}}},
  paper_bgcolor:C2.card,plot_bgcolor:C2.card,
  font:{color:C2.text,family:'Segoe UI',size:11},
  legend:{bgcolor:'rgba(0,0,0,0)',font:{color:C2.text,size:11}},
  margin:{l:50,r:50,t:20,b:20}},cfg);

// ─── WJP Factores clave (1,2,7,8) ───
Plotly.newPlot('graf-wjp-factores',[
  {type:'bar',name:'Argentina',x:wjpFactores,y:wjpFactArg,marker:{color:C2.gold,opacity:.9}},
  {type:'bar',name:'LAC prom.',x:wjpFactores,y:wjpFactLac,marker:{color:C2.blue,opacity:.7}},
  {type:'bar',name:'OCDE prom.',x:wjpFactores,y:wjpFactOcde,marker:{color:C2.green,opacity:.7}},
],Lx({barmode:'group',yaxis:{range:[0,0.9],title:{text:'Score (0–1)',font:{size:11}}},
  xaxis:{tickangle:-15},margin:{l:50,r:10,t:10,b:80},
  legend:{bgcolor:'rgba(0,0,0,0)',font:{color:C2.text,size:11}}}),cfg);

// ─── WJP Histórico ───
Plotly.newPlot('graf-wjp-hist',[{type:'scatter',mode:'lines+markers',
  x:wjpHistAnios,y:wjpHistScores,line:{color:C2.gold,width:2.5},
  marker:{color:C2.gold,size:7},fill:'tozeroy',fillcolor:'rgba(201,162,39,0.08)',
  hovertemplate:'<b>%{x}</b><br>Score: %{y:.2f}<extra></extra>'}],
  Lx({yaxis:{range:[0.35,0.65],tickformat:'.2f'},xaxis:{dtick:2},margin:{l:50,r:10,t:10,b:30}}),cfg);

// ═══════════════════════════════════════════════
// 2. IPC — Transparencia Internacional
// ═══════════════════════════════════════════════
Plotly.newPlot('graf-ipc-reg',[{type:'bar',x:ipcLabels,y:ipcValues,
  text:ipcValues,textposition:'outside',marker:{color:ipcColors,opacity:.9},
  hovertemplate:'<b>%{x}</b><br>IPC: %{y}/100<extra></extra>'}],
  Lx({yaxis:{range:[0,90],title:{text:'Score IPC (0–100)',font:{size:11}}},
     xaxis:{tickangle:-30},margin:{l:50,r:10,t:10,b:80},
     shapes:[{type:'line',x0:-0.5,x1:ipcLabels.length-0.5,y0:50,y1:50,
              line:{color:C2.green,width:1.5,dash:'dot'}}],
     annotations:[{x:5,y:53,text:'Umbral "limpio" ≥ 50',
                   font:{color:C2.green,size:11},showarrow:false}]}),cfg);

Plotly.newPlot('graf-ipc-hist',[{type:'scatter',mode:'lines+markers',
  x:ipcHistAnios,y:ipcHistScores,line:{color:C2.red,width:2.5},
  marker:{color:C2.red,size:7},fill:'tozeroy',fillcolor:'rgba(230,57,70,0.08)',
  hovertemplate:'<b>%{x}</b><br>IPC: %{y}<extra></extra>'}],
  Lx({yaxis:{range:[25,55]},xaxis:{dtick:2},margin:{l:40,r:10,t:10,b:30}}),cfg);

// ═══════════════════════════════════════════════
// 3. WGI — Banco Mundial
// ═══════════════════════════════════════════════
Plotly.newPlot('graf-wgi-dim',[{type:'bar',orientation:'h',
  x:wgiArg,y:wgiLabels,text:wgiArg.map(v=>v.toFixed(2)),textposition:'outside',
  marker:{color:wgiColors,opacity:.9},
  hovertemplate:'<b>%{y}</b><br>Score: %{x}<extra></extra>'}],
  Lx({xaxis:{range:[-0.65,0.65],title:{text:'Score (-2.5 a +2.5)',font:{size:11}}},
     yaxis:{autorange:'reversed'},margin:{l:10,r:60,t:10,b:40},
     shapes:[{type:'line',x0:0,x1:0,y0:-0.5,y1:5.5,line:{color:C2.muted,width:1,dash:'dot'}}]}),cfg);

Plotly.newPlot('graf-wgi-rol',[{type:'bar',orientation:'h',
  x:rolValues,y:rolLabels,text:rolValues.map(v=>v.toFixed(2)),textposition:'outside',
  marker:{color:rolColors,opacity:.9},
  hovertemplate:'<b>%{y}</b><br>Rule of Law: %{x}<extra></extra>'}],
  Lx({xaxis:{range:[-1.0,1.5],title:{text:'Score WGI Rule of Law',font:{size:11}}},
     yaxis:{autorange:'reversed'},margin:{l:10,r:60,t:10,b:40},
     shapes:[{type:'line',x0:0,x1:0,y0:-0.5,y1:rolLabels.length-0.5,
              line:{color:C2.muted,width:1,dash:'dot'}}]}),cfg);

// ═══════════════════════════════════════════════
// 4. V-DEM — Varieties of Democracy
// ═══════════════════════════════════════════════
// JCI + HCI Histórico dual
Plotly.newPlot('graf-vdem-hist',[
  {type:'scatter',mode:'lines+markers',name:'Judicial Constraints on Executive (JCI)',
   x:vdemJciAnios,y:vdemJciScores,line:{color:C2.gold,width:2.5},
   marker:{color:C2.gold,size:7},fill:'tozeroy',fillcolor:'rgba(201,162,39,0.08)',
   hovertemplate:'<b>%{x}</b> JCI: %{y:.2f}<extra></extra>'},
  {type:'scatter',mode:'lines+markers',name:'High Court Independence (HCI)',
   x:vdemHciAnios,y:vdemHciScores,line:{color:C2.purple,width:2.5,dash:'dot'},
   marker:{color:C2.purple,size:7},
   hovertemplate:'<b>%{x}</b> HCI: %{y:.2f}<extra></extra>'},
],Lx({yaxis:{range:[0.3,0.95],title:{text:'Score (0–1)',font:{size:11}},tickformat:'.2f'},
  xaxis:{dtick:2},margin:{l:50,r:10,t:10,b:30},
  legend:{bgcolor:'rgba(0,0,0,0)',font:{color:C2.text,size:11}}}),cfg);

// JCI Comparativa regional
Plotly.newPlot('graf-vdem-reg',[{type:'bar',orientation:'h',
  x:vdemRegValues,y:vdemRegLabels,text:vdemRegValues.map(v=>v.toFixed(2)),textposition:'outside',
  marker:{color:vdemRegColors,opacity:.9},
  hovertemplate:'<b>%{y}</b><br>JCI: %{x:.2f}<extra></extra>'}],
  Lx({xaxis:{range:[0,1.05],title:{text:'Judicial Constraints on Executive (0–1)',font:{size:11}}},
     yaxis:{autorange:'reversed'},margin:{l:10,r:70,t:10,b:40},
     shapes:[{type:'line',x0:0.59,x1:0.59,y0:-0.5,y1:vdemRegLabels.length-0.5,
              line:{color:C2.gold,width:2,dash:'dot'}}],
     annotations:[{x:0.59,y:0.3,xanchor:'left',text:'ARG 0.59',
                   font:{color:C2.gold,size:11},showarrow:false}]}),cfg);

// Judicial Appointments — Calidad del proceso
Plotly.newPlot('graf-vdem-appt',[
  {type:'bar',name:'Argentina',x:vdemApptDims,y:vdemApptArg,marker:{color:C2.gold,opacity:.9}},
  {type:'bar',name:'LAC prom.',x:vdemApptDims,y:vdemApptLac,marker:{color:C2.blue,opacity:.7}},
  {type:'bar',name:'OCDE prom.',x:vdemApptDims,y:vdemApptOcde,marker:{color:C2.green,opacity:.7}},
],Lx({barmode:'group',yaxis:{range:[0,5],title:{text:'Score (0–4)',font:{size:11}}},
  xaxis:{tickangle:-15},margin:{l:50,r:10,t:10,b:90},
  legend:{bgcolor:'rgba(0,0,0,0)',font:{color:C2.text,size:11}}}),cfg);

// ═══════════════════════════════════════════════
// 5. RECPJ / CEPEJ — Eficiencia del Consejo
// ═══════════════════════════════════════════════
// Clearance Rate comparativa
Plotly.newPlot('graf-cepej-cr',[{type:'bar',x:cepejCrLabels,y:cepejCrValues,
  text:cepejCrValues.map(v=>v+'%'),textposition:'outside',
  marker:{color:cepejCrColors,opacity:.9},
  hovertemplate:'<b>%{x}</b><br>Clearance Rate: %{y}%<extra></extra>'}],
  Lx({yaxis:{range:[60,115],title:{text:'Clearance Rate (%)',font:{size:11}}},
     xaxis:{tickangle:-25},margin:{l:60,r:10,t:10,b:70},
     shapes:[{type:'line',x0:-0.5,x1:cepejCrLabels.length-0.5,y0:100,y1:100,
              line:{color:C2.green,width:2,dash:'dot'}}],
     annotations:[{x:4,y:102,text:'Objetivo CEPEJ: 100%',
                   font:{color:C2.green,size:11},showarrow:false}]}),cfg);

// Disposition Time comparativa
Plotly.newPlot('graf-cepej-dt',[{type:'bar',x:cepejDtLabels,y:cepejDtValues,
  text:cepejDtValues.map(v=>v+'d'),textposition:'outside',
  marker:{color:cepejDtColors,opacity:.9},
  hovertemplate:'<b>%{x}</b><br>Duración: %{y} días<extra></extra>'}],
  Lx({yaxis:{title:{text:'Días (1ª instancia civil)',font:{size:11}}},
     xaxis:{tickangle:-25},margin:{l:60,r:10,t:10,b:70},
     shapes:[{type:'line',x0:-0.5,x1:cepejDtLabels.length-0.5,y0:240,y1:240,
              line:{color:C2.green,width:2,dash:'dot'}}],
     annotations:[{x:4,y:255,text:'Ref. OCDE: 240 días',
                   font:{color:C2.green,size:11},showarrow:false}]}),cfg);

// Métricas CEPEJ en vivo (desde la API)
fetch('/estrategico/api/cepej').then(r=>r.json()).then(d=>{
  const tag = d.tiene_datos_reales?'':'<span style="font-size:.7rem;color:var(--muted)">(est.)</span>';
  const crVal  = d.clearance_rate   ?? 82;
  const dtVal  = d.disposition_time_dias ?? 420;
  const pctConc = d.pct_vacantes_concurso ?? 31;
  const pctFem = d.pct_magistradas_mujeres ?? 30;
  const desRec = d.designaciones_recientes_2023_2024 ?? 0;
  const crColor = crVal >= 100 ? 'var(--green)' : crVal >= 90 ? 'var(--gold)' : 'var(--red)';
  const dtColor = dtVal <= 240 ? 'var(--green)' : dtVal <= 400 ? 'var(--gold)' : 'var(--red)';
  const ccColor = pctConc >= 80 ? 'var(--green)' : pctConc >= 50 ? 'var(--gold)' : 'var(--red)';
  document.getElementById('kpi-cepej').innerHTML=`
    <div class="kpi" style="border-color:${crColor}">
      <label>Clearance Rate ${tag}</label>
      <div class="val" style="color:${crColor}">${crVal}%</div>
      <div class="sub">Resueltos / ingresados. Objetivo ≥ 100%</div></div>
    <div class="kpi" style="border-color:${dtColor}">
      <label>Disposition Time ${tag}</label>
      <div class="val" style="color:${dtColor}">${fmt(dtVal)}</div>
      <div class="sub">Días prom. estimado. Ref. OCDE: 240</div></div>
    <div class="kpi" style="border-color:${ccColor}">
      <label>Vacantes con concurso</label>
      <div class="val" style="color:${ccColor}">${pctConc ?? 'S/D'}%</div>
      <div class="sub">${fmt(d.vacantes_con_concurso)} de ${fmt(d.total_vacantes)} vacantes</div></div>
    <div class="kpi gold">
      <label>Magistradas mujeres</label>
      <div class="val">${pctFem ?? 'S/D'}%</div>
      <div class="sub">Paridad de género CEPEJ</div></div>
    <div class="kpi">
      <label>Designaciones 2023–2024</label>
      <div class="val">${fmt(desRec)}</div>
      <div class="sub">Renovación del sistema</div></div>`;
}).catch(()=>{
  document.getElementById('kpi-cepej').innerHTML='<div style="color:var(--muted);padding:8px">No se pudo cargar API /api/cepej</div>';
});

// ═══════════════════════════════════════════════
// 6. CEJAS — Independencia Personal
// ═══════════════════════════════════════════════
// Radar independencia personal
const cejasClose=[...cejasDims,cejasDims[0]];
Plotly.newPlot('graf-cejas-radar',[
  {type:'scatterpolar',fill:'toself',name:'Argentina',
   r:[...cejasArg,cejasArg[0]],theta:cejasClose,
   line:{color:C2.gold,width:2},fillcolor:'rgba(201,162,39,0.15)'},
  {type:'scatterpolar',fill:'toself',name:'LAC prom.',
   r:[...cejasLac,cejasLac[0]],theta:cejasClose,
   line:{color:C2.blue,width:1.5,dash:'dot'},fillcolor:'rgba(59,130,246,0.06)'},
  {type:'scatterpolar',fill:'toself',name:'Estándar mínimo',
   r:[...cejasTarget,cejasTarget[0]],theta:cejasClose,
   line:{color:C2.green,width:1.5,dash:'dash'},fillcolor:'rgba(34,197,94,0.04)'},
],{polar:{bgcolor:C2.card,
   radialaxis:{range:[0,1],gridcolor:C2.grid,tickfont:{size:10,color:C2.muted}},
   angularaxis:{gridcolor:C2.grid,tickfont:{size:9,color:C2.text}}},
  paper_bgcolor:C2.card,font:{color:C2.text,family:'Segoe UI',size:11},
  legend:{bgcolor:'rgba(0,0,0,0)',font:{color:C2.text,size:11}},
  margin:{l:60,r:60,t:20,b:20}},cfg);

// Brechas por dimensión (Argentina vs Estándar)
const brechas = cejasArg.map((v,i)=>+(cejasTarget[i]-v).toFixed(2));
const brechColores = brechas.map(b=>b>0.3?C2.red:b>0.15?C2.orange:C2.gold);
Plotly.newPlot('graf-cejas-brechas',[{type:'bar',orientation:'h',
  x:brechas,y:cejasDims,text:brechas.map(v=>'-'+v.toFixed(2)),textposition:'outside',
  marker:{color:brechColores,opacity:.9},
  hovertemplate:'<b>%{y}</b><br>Brecha vs estándar: %{x:.2f}<extra></extra>'}],
  Lx({xaxis:{range:[0,0.5],title:{text:'Brecha respecto al estándar mínimo (0.80)',font:{size:11}}},
     yaxis:{autorange:'reversed'},margin:{l:10,r:70,t:10,b:40},
     shapes:[{type:'line',x0:0.3,x1:0.3,y0:-0.5,y1:cejasDims.length-0.5,
              line:{color:C2.red,width:1.5,dash:'dot'}}],
     annotations:[{x:0.3,y:0.2,xanchor:'left',text:'Umbral crítico',
                   font:{color:C2.red,size:11},showarrow:false}]}),cfg);

// CEJAS histórico compuesto
Plotly.newPlot('graf-cejas-hist',[{type:'scatter',mode:'lines+markers',
  x:cejasHistAnios,y:cejasHistScores,line:{color:C2.orange,width:2.5},
  marker:{color:C2.orange,size:7},fill:'tozeroy',fillcolor:'rgba(249,115,22,0.08)',
  hovertemplate:'<b>%{x}</b><br>Índice: %{y:.2f}<extra></extra>'}],
  Lx({yaxis:{range:[0.3,0.85],title:{text:'Índice Independencia Personal (0–1)',font:{size:11}},tickformat:'.2f'},
     margin:{l:55,r:10,t:10,b:30}}),cfg);

// ═══════════════════════════════════════════════
// 7. ODS 16
// ═══════════════════════════════════════════════
const semColor={'rojo':'#e63946','alerta':'#f97316','verde':'#22c55e'};
const odsHtml=odsData.map(o=>{
  const col=semColor[o.semaforo]||'#94a3b8';
  const barPct=o.meta>0?Math.min(100,Math.round(o.valor/o.meta*100)):Math.round(100-o.valor);
  return `<div style="background:var(--card);border-radius:10px;padding:16px 18px;border-left:4px solid ${col}">
    <div style="font-size:.68rem;text-transform:uppercase;letter-spacing:1px;color:var(--muted);margin-bottom:6px">${o.id} · ${o.titulo}</div>
    <div style="font-size:1.6rem;font-weight:700;color:${col}">${o.valor}${o.unidad}</div>
    <div style="font-size:.72rem;color:var(--muted);margin:4px 0">Meta: ${o.meta>0?o.meta+o.unidad:'Reducción progresiva'} · ${o.anio}</div>
    <div style="background:#0a1628;border-radius:4px;height:5px;margin:8px 0">
      <div style="background:${col};height:5px;border-radius:4px;width:${barPct}%;opacity:.7"></div></div>
    <div style="font-size:.78rem;color:#94a3b8;line-height:1.5">${o.desc}</div>
    <div style="font-size:.7rem;color:#475569;margin-top:6px">Fuente: ${o.fuente}</div>
  </div>`;
}).join('');
document.getElementById('kpi-ods').innerHTML=odsHtml;
"""

    # ── JS adicional: APIs reales (oralidad/traslados/genero/seleccion)
    new_api_js = r"""

// ═══════════════════════════════════════════════
// 8. RECPJ/CEPEJ — datos reales desde /api/oralidad
// ═══════════════════════════════════════════════
fetch('/estrategico/api/oralidad').then(r=>r.json()).then(d=>{
  if(!d.provincias||!d.provincias.length) return;
  const provs   = d.provincias.map(p=>p.provincia);
  const crVals  = d.provincias.map(p=>p.clearance_rate||0);
  const dtVals  = d.provincias.map(p=>p.disposition_time||0);
  const crCols  = crVals.map(v=>v>=100?C2.green:v>=90?C2.gold:C2.red);
  const dtCols  = dtVals.map(v=>v<=240?C2.green:v<=420?C2.gold:C2.red);

  if(document.getElementById('graf-oral-cr')){
    Plotly.newPlot('graf-oral-cr',[{type:'bar',x:provs,y:crVals,
      text:crVals.map(v=>v+'%'),textposition:'outside',marker:{color:crCols,opacity:.9},
      hovertemplate:'<b>%{x}</b><br>CR: %{y}%<extra></extra>'}],
      Lx({yaxis:{range:[0,115],title:{text:'Clearance Rate (%)',font:{size:11}}},
         xaxis:{tickangle:-25},margin:{l:55,r:10,t:10,b:80},
         shapes:[{type:'line',x0:-0.5,x1:provs.length-0.5,y0:100,y1:100,
                  line:{color:C2.green,width:2,dash:'dot'}}],
         annotations:[{x:1,y:102,text:'Obj. CEPEJ 100%',font:{color:C2.green,size:10},showarrow:false}]}),cfg);
  }
  if(document.getElementById('graf-oral-dt')){
    Plotly.newPlot('graf-oral-dt',[{type:'bar',x:provs,y:dtVals,
      text:dtVals.map(v=>v?v+'d':'S/D'),textposition:'outside',marker:{color:dtCols,opacity:.9},
      hovertemplate:'<b>%{x}</b><br>DT: %{y} días<extra></extra>'}],
      Lx({yaxis:{title:{text:'Disposition Time (días)',font:{size:11}}},
         xaxis:{tickangle:-25},margin:{l:55,r:10,t:10,b:80},
         shapes:[{type:'line',x0:-0.5,x1:provs.length-0.5,y0:240,y1:240,
                  line:{color:C2.green,width:2,dash:'dot'}}],
         annotations:[{x:1,y:255,text:'Ref. OCDE 240d',font:{color:C2.green,size:10},showarrow:false}]}),cfg);
  }
  if(document.getElementById('kpi-oral-total')){
    document.getElementById('kpi-oral-total').textContent=fmt(d.total_causas)+' causas';
  }
}).catch(()=>{});

// ── Traslados de jueces ───────────────────────────────────────────────────────
fetch('/estrategico/api/traslados').then(r=>r.json()).then(d=>{
  if(!d.total) return;
  if(document.getElementById('kpi-traslados-total')){
    document.getElementById('kpi-traslados-total').textContent=d.total+' traslados';
  }
  if(document.getElementById('graf-traslados-motivo')&&d.por_motivo&&d.por_motivo.labels.length){
    Plotly.newPlot('graf-traslados-motivo',[{type:'pie',hole:.45,
      labels:d.por_motivo.labels,values:d.por_motivo.values,textinfo:'label+percent',
      marker:{colors:['#c9a227','#3b82f6','#22c55e','#e63946','#8b5cf6','#f97316'],
              line:{color:'#1a2744',width:2}}}],
      Lx({showlegend:true,legend:{bgcolor:'rgba(0,0,0,0)',font:{color:C2.text,size:10}},
         margin:{l:10,r:10,t:10,b:10}}),cfg);
  }
  if(document.getElementById('graf-traslados-anio')&&d.por_anio&&d.por_anio.labels.length){
    Plotly.newPlot('graf-traslados-anio',[{type:'bar',
      x:d.por_anio.labels,y:d.por_anio.values,
      marker:{color:C2.orange,opacity:.85},
      hovertemplate:'<b>%{x}</b><br>Traslados: %{y}<extra></extra>'}],
      Lx({yaxis:{title:{text:'Traslados',font:{size:11}}},margin:{l:45,r:10,t:10,b:30}}),cfg);
  }
}).catch(()=>{});

// ── Género — serie anual de designaciones ─────────────────────────────────────
fetch('/estrategico/api/genero').then(r=>r.json()).then(d=>{
  if(!d.serie_anual||!d.serie_anual.anios.length) return;
  if(document.getElementById('graf-genero-serie')){
    Plotly.newPlot('graf-genero-serie',[
      {type:'bar',name:'Varones',x:d.serie_anual.anios,y:d.serie_anual.varones,
       marker:{color:C2.blue,opacity:.8}},
      {type:'bar',name:'Mujeres',x:d.serie_anual.anios,y:d.serie_anual.mujeres,
       marker:{color:'#ec4899',opacity:.85}},
    ],Lx({barmode:'stack',
      legend:{bgcolor:'rgba(0,0,0,0)',font:{color:C2.text,size:11}},
      yaxis:{title:{text:'Designaciones',font:{size:11}}},
      margin:{l:50,r:10,t:10,b:40}}),cfg);
  }
  if(document.getElementById('kpi-genero-pct')){
    document.getElementById('kpi-genero-pct').textContent=d.pct_mujeres+'%';
  }
}).catch(()=>{});

// ── Selección / Concursos ─────────────────────────────────────────────────────
fetch('/estrategico/api/seleccion').then(r=>r.json()).then(d=>{
  if(!d.por_anio||!d.por_anio.labels.length) return;
  if(document.getElementById('graf-seleccion-anio')){
    Plotly.newPlot('graf-seleccion-anio',[{type:'scatter',mode:'lines+markers',fill:'tozeroy',
      x:d.por_anio.labels,y:d.por_anio.values,line:{color:C2.gold,width:2},
      fillcolor:'rgba(201,162,39,0.12)',
      hovertemplate:'<b>%{x}</b><br>Ternas: %{y}<extra></extra>'}],
      Lx({yaxis:{title:{text:'Ternas publicadas',font:{size:11}}},margin:{l:50,r:10,t:10,b:30}}),cfg);
  }
  if(document.getElementById('kpi-concursos-unicos')){
    document.getElementById('kpi-concursos-unicos').textContent=fmt(d.concursos_unicos)+' concursos';
  }
}).catch(()=>{});
"""

    # ── HTML body ──────────────────────────────────────────────────────
    html_body = """

<div class="scope">
  🌐 <strong>Indicadores Comparativos Internacionales</strong> —
  Marcos WJP · IPC · WGI · V-Dem · RECPJ/CEPEJ · CEJAS · ODS 16 · OCDE.
  <a href="#fuentes" style="color:var(--gold);margin-left:8px">Ver fuentes →</a>
</div>

<!-- 1. WJP -->
<div class="seccion">⚖️ 1. World Justice Project — Índice Estado de Derecho 2023</div>
<div class="inst-badges">
  <div class="badge blue">Escala 0–1 · Mayor = mejor Estado de Derecho</div>
  <div class="badge gold">Argentina: 0.47 · Puesto 65/142 países</div>
  <div class="badge red">LAC prom.: 0.50 · OCDE prom.: 0.68</div>
</div>
<div class="charts">
  <div class="chart-box"><h2>🌎 Ranking Regional WJP 2023</h2>
    <div id="graf-wjp-rank" style="height:340px"></div></div>
  <div class="chart-box"><h2>📊 8 Dimensiones: ARG vs. LAC vs. OCDE</h2>
    <div id="graf-wjp-radar" style="height:340px"></div></div>
</div>
<div class="chart-full"><h2>🔑 Factores Clave para Cortes Superiores (1 · 2 · 7 · 8)</h2>
  <div id="graf-wjp-factores" style="height:280px"></div>
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px;margin-top:14px">
    <div style="background:#0f1e3a;border-radius:8px;padding:12px 14px;border-left:3px solid var(--gold)">
      <div style="font-size:.7rem;text-transform:uppercase;letter-spacing:1.5px;color:var(--gold);margin-bottom:5px">Factor 1 — Límites al Poder Gub.</div>
      <div style="font-size:.8rem;color:var(--muted);line-height:1.6">Capacidad del PJ para <strong style="color:var(--text)">auditar y frenar al Ejecutivo</strong>. ARG: 0.56 vs OCDE: 0.72.</div>
    </div>
    <div style="background:#0f1e3a;border-radius:8px;padding:12px 14px;border-left:3px solid var(--red)">
      <div style="font-size:.7rem;text-transform:uppercase;letter-spacing:1.5px;color:var(--red);margin-bottom:5px">Factor 2 — Ausencia de Corrupción</div>
      <div style="font-size:.8rem;color:var(--muted);line-height:1.6">Jueces libres de <strong style="color:var(--text)">sobornos e influencias privadas</strong>. ARG: 0.39 — el peor de los 4.</div>
    </div>
    <div style="background:#0f1e3a;border-radius:8px;padding:12px 14px;border-left:3px solid var(--blue)">
      <div style="font-size:.7rem;text-transform:uppercase;letter-spacing:1.5px;color:var(--blue);margin-bottom:5px">Factor 7 — Justicia Civil</div>
      <div style="font-size:.8rem;color:var(--muted);line-height:1.6">Procesos <strong style="color:var(--text)">accesibles y sin demoras</strong>. ARG: 0.42. Subfactor demoras: 0.35.</div>
    </div>
    <div style="background:#0f1e3a;border-radius:8px;padding:12px 14px;border-left:3px solid #f97316">
      <div style="font-size:.7rem;text-transform:uppercase;letter-spacing:1.5px;color:#f97316;margin-bottom:5px">Factor 8 — Justicia Penal</div>
      <div style="font-size:.8rem;color:var(--muted);line-height:1.6"><strong style="color:var(--text)">Proceso penal efectivo e imparcial</strong>. ARG: 0.38. Preventiva: 0.30.</div>
    </div>
  </div>
</div>
<div class="chart-full"><h2>📅 Evolución WJP Argentina 2015–2023</h2>
  <div id="graf-wjp-hist" style="height:200px"></div></div>

<!-- 2. IPC -->
<div class="seccion">🔍 2. IPC Transparencia Internacional 2023</div>
<div class="inst-badges">
  <div class="badge blue">Escala 0–100 · Mayor = menor corrupción percibida</div>
  <div class="badge gold">Argentina: 37/100 · Puesto 99/180 países</div>
</div>
<div class="charts">
  <div class="chart-box"><h2>🌎 IPC Comparativo Regional 2023</h2>
    <div id="graf-ipc-reg" style="height:340px"></div></div>
  <div class="chart-box"><h2>📅 Evolución IPC Argentina 2013–2023</h2>
    <div id="graf-ipc-hist" style="height:340px"></div></div>
</div>

<!-- 3. WGI -->
<div class="seccion">🏦 3. Banco Mundial — Indicadores de Gobernanza 2022 (WGI)</div>
<div class="inst-badges">
  <div class="badge blue">Escala -2.5 a +2.5 · Mayor valor = mejor gobernanza</div>
  <div class="badge red">Argentina: negativo en 5 de 6 dimensiones</div>
</div>
<div class="charts">
  <div class="chart-box"><h2>📊 Argentina — 6 Dimensiones WGI</h2>
    <div id="graf-wgi-dim" style="height:340px"></div></div>
  <div class="chart-box"><h2>🌎 Rule of Law Regional (WGI)</h2>
    <div id="graf-wgi-rol" style="height:340px"></div></div>
</div>

<!-- 4. V-DEM -->
<div class="seccion">🔬 4. V-Dem Institute (Varieties of Democracy) 2023</div>
<div class="inst-badges">
  <div class="badge blue">Escala 0–1 · Precisión académica · Series desde 1900</div>
  <div class="badge gold">ARG JCI 2023: 0.58 · Tendencia descendente desde 2012</div>
  <div class="badge red">ARG HCI 2023: 0.57 · Por debajo del promedio LAC</div>
</div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:16px">
  <div style="background:#0f1e3a;border-radius:8px;padding:12px 14px;border-left:3px solid #8b5cf6">
    <div style="font-size:.7rem;text-transform:uppercase;letter-spacing:1.5px;color:#8b5cf6;margin-bottom:5px">Índice Restricciones Judiciales al Ejecutivo (JCI)</div>
    <div style="font-size:.8rem;color:var(--muted);line-height:1.6">Mide si el Ejecutivo <strong style="color:var(--text)">respeta la Constitución y cumple los fallos</strong>. Cayó 0.13 pts desde 2012.</div>
  </div>
  <div style="background:#0f1e3a;border-radius:8px;padding:12px 14px;border-left:3px solid var(--gold)">
    <div style="font-size:.7rem;text-transform:uppercase;letter-spacing:1.5px;color:var(--gold);margin-bottom:5px">Independencia de las Altas Cortes (HCI)</div>
    <div style="font-size:.8rem;color:var(--muted);line-height:1.6">Autonomía frente a <strong style="color:var(--text)">presiones del gobierno y poderes fácticos</strong>. Declive sostenido desde 2012.</div>
  </div>
</div>
<div class="chart-full"><h2>📅 Evolución JCI y HCI — Argentina 2000–2023</h2>
  <div id="graf-vdem-hist" style="height:240px"></div></div>
<div class="charts">
  <div class="chart-box"><h2>🌎 Restricciones Judiciales al Ejecutivo — Regional</h2>
    <div id="graf-vdem-reg" style="height:340px"></div></div>
  <div class="chart-box"><h2>🏛️ Calidad de Nombramientos Judiciales (0–4)</h2>
    <div id="graf-vdem-appt" style="height:340px"></div></div>
</div>

<!-- 5. RECPJ / CEPEJ -->
<div class="seccion">🏛️ 5. RECPJ / CEPEJ — Eficiencia Institucional (datos reales PJN)</div>
<div class="inst-badges">
  <div class="badge blue">Fuente: Programa Oralidad Civil · datos.jus.gob.ar</div>
  <div class="badge gold">~60.000 causas reales · 11 provincias</div>
</div>
<div class="kpi-grid" id="kpi-cepej" style="grid-template-columns:repeat(auto-fit,minmax(200px,1fr))">
  <div class="loading">Cargando métricas CEPEJ…</div>
</div>
<div class="chart-full"><h2>📊 Clearance Rate por Provincia — datos reales Programa Oralidad</h2>
  <div id="graf-oral-cr" style="height:260px"></div>
  <div style="text-align:right;font-size:.72rem;color:var(--muted);margin-top:4px">
    Total: <span id="kpi-oral-total">cargando…</span> · Fuente: datos.jus.gob.ar/oralidad
  </div>
</div>
<div class="chart-full"><h2>⏱️ Disposition Time por Provincia (días) — datos reales</h2>
  <div id="graf-oral-dt" style="height:260px"></div></div>
<div style="background:#0f1e3a;border:1px solid #2d4a7a;border-radius:8px;padding:14px 18px;font-size:.82rem;color:#94a3b8;line-height:1.7;margin-bottom:20px">
  <strong style="color:var(--gold)">📐 Fórmulas CEPEJ:</strong><br>
  <code style="color:#93c5fd">Clearance Rate</code> = (Causas con resultado registrado / Total causas ingresadas) × 100 — CR &lt; 100%: acumulación de rezago.<br>
  <code style="color:#93c5fd">Disposition Time</code> = Promedio de (fecha_finalización − fecha_ingreso) en días para causas completadas.
</div>

<!-- Traslados -->
<div class="seccion">🚦 5b. RECPJ — Protección contra Traslados Arbitrarios</div>
<div class="inst-badges">
  <div class="badge blue">Fuente: datos_jus/traslados · 113 traslados registrados</div>
  <div class="badge red">RECPJ: protección contra traslados = prerrequisito de independencia</div>
</div>
<div class="kpi-grid" style="grid-template-columns:repeat(auto-fit,minmax(180px,1fr));margin-bottom:14px">
  <div class="kpi rojo"><label>Total Traslados registrados</label>
    <div class="val" id="kpi-traslados-total">cargando…</div>
    <div class="sub">Fuente oficial datos.jus.gob.ar</div></div>
  <div class="kpi gold"><label>Concursos únicos (Selección)</label>
    <div class="val" id="kpi-concursos-unicos">cargando…</div>
    <div class="sub">Ternas para cubrir vacantes</div></div>
  <div class="kpi"><label>Mujeres designadas (hist.)</label>
    <div class="val" id="kpi-genero-pct">cargando…</div>
    <div class="sub">% sobre total designaciones 2000–2025</div></div>
</div>
<div class="charts">
  <div class="chart-box"><h2>📂 Traslados por Motivo</h2>
    <div id="graf-traslados-motivo" style="height:300px"></div></div>
  <div class="chart-box"><h2>📅 Traslados por Año</h2>
    <div id="graf-traslados-anio" style="height:300px"></div></div>
</div>

<!-- Selección/Concursos -->
<div class="seccion">📋 5c. Nombramientos — Calidad del Proceso (datos reales)</div>
<div class="chart-full"><h2>📅 Ternas de Selección Publicadas por Año — datos reales</h2>
  <div id="graf-seleccion-anio" style="height:220px"></div>
  <div style="font-size:.75rem;color:var(--muted);margin-top:6px">Fuente: datos_jus/seleccion_magistrados · 4.278 ternas reales 2006–2026</div>
</div>

<!-- 6. CEJAS -->
<div class="seccion">🌍 6. CEJAS — Independencia Personal de Magistrados</div>
<div class="inst-badges">
  <div class="badge blue">Centro de Estudios de Justicia de las Américas</div>
  <div class="badge red">ARG: brecha crítica en protección contra desprestigio (0.41)</div>
</div>
<div style="background:#0f1e3a;border-left:4px solid #f97316;border-radius:6px;padding:12px 16px;margin-bottom:16px;font-size:.82rem;color:#94a3b8;line-height:1.6">
  <strong style="color:#f97316">⚠️ Para algoritmos de detección de corrupción:</strong>
  La protección contra campañas de desprestigio y la inamovilidad son
  <em>precursores tempranos de captura institucional</em> (CEJAS 2023).
</div>
<div class="charts">
  <div class="chart-box"><h2>🕸️ Radar Independencia Personal — ARG vs. LAC vs. Estándar</h2>
    <div id="graf-cejas-radar" style="height:380px"></div></div>
  <div class="chart-box"><h2>📊 Brechas vs. estándar mínimo (0.80)</h2>
    <div id="graf-cejas-brechas" style="height:380px"></div></div>
</div>
<div class="chart-full"><h2>📅 Índice de Independencia Personal — Argentina 2012–2023</h2>
  <div id="graf-cejas-hist" style="height:210px"></div></div>

<!-- 7. Género -->
<div class="seccion">⚧ 7. Paridad de Género en Designaciones — datos reales 2000–2025</div>
<div class="inst-badges">
  <div class="badge blue">Fuente: datos_jus/estadistica_genero · 429 registros reales</div>
</div>
<div class="chart-full"><h2>📅 Designaciones por Género — Serie Anual 2000–2025</h2>
  <div id="graf-genero-serie" style="height:260px"></div></div>

<!-- 8. ODS 16 -->
<div class="seccion">🇺🇳 8. ODS 16 — Paz, Justicia e Instituciones Sólidas</div>
<div class="kpi-grid" id="kpi-ods" style="grid-template-columns:repeat(auto-fit,minmax(260px,1fr))"></div>

<!-- Fuentes -->
<div class="seccion" id="fuentes">📚 Fuentes y Acceso a Datos</div>
<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px;margin-bottom:24px">
  <div style="background:var(--card);border-radius:10px;padding:18px;border-top:3px solid var(--gold)">
    <div style="font-size:.7rem;text-transform:uppercase;letter-spacing:2px;color:var(--gold);margin-bottom:8px">⚖️ WJP Rule of Law Index</div>
    <div style="font-size:.82rem;color:var(--muted);line-height:1.7">142 países · CSV/JSON disponible · 8 factores<br><a href="https://worldjusticeproject.org" target="_blank" style="color:var(--gold2)">worldjusticeproject.org</a></div>
  </div>
  <div style="background:var(--card);border-radius:10px;padding:18px;border-top:3px solid #3b82f6">
    <div style="font-size:.7rem;text-transform:uppercase;letter-spacing:2px;color:#3b82f6;margin-bottom:8px">🏦 World Bank — WGI</div>
    <div style="font-size:.82rem;color:var(--muted);line-height:1.7">API REST · 30 fuentes · intervalos de confianza<br><a href="https://databank.worldbank.org" target="_blank" style="color:#93c5fd">databank.worldbank.org</a></div>
  </div>
  <div style="background:var(--card);border-radius:10px;padding:18px;border-top:3px solid var(--red)">
    <div style="font-size:.7rem;text-transform:uppercase;letter-spacing:2px;color:var(--red);margin-bottom:8px">🔍 IPC — Transparencia Internacional</div>
    <div style="font-size:.82rem;color:var(--muted);line-height:1.7">180 países · API JSON · márgenes de error por país<br><a href="https://www.transparency.org/en/cpi" target="_blank" style="color:#fca5a5">transparency.org/en/cpi</a></div>
  </div>
  <div style="background:var(--card);border-radius:10px;padding:18px;border-top:3px solid #8b5cf6">
    <div style="font-size:.7rem;text-transform:uppercase;letter-spacing:2px;color:#8b5cf6;margin-bottom:8px">🔬 V-Dem Institute</div>
    <div style="font-size:.82rem;color:var(--muted);line-height:1.7">470+ indicadores desde 1789 · CSV/RData · series temporales<br><a href="https://v-dem.net" target="_blank" style="color:#c4b5fd">v-dem.net</a></div>
  </div>
  <div style="background:var(--card);border-radius:10px;padding:18px;border-top:3px solid #f97316">
    <div style="font-size:.7rem;text-transform:uppercase;letter-spacing:2px;color:#f97316;margin-bottom:8px">🌍 CEJAS — Américas</div>
    <div style="font-size:.82rem;color:var(--muted);line-height:1.7">18 países LAC · independencia personal y estructural<br><a href="https://cejamericas.org" target="_blank" style="color:#fdba74">cejamericas.org</a></div>
  </div>
  <div style="background:var(--card);border-radius:10px;padding:18px;border-top:3px solid var(--green)">
    <div style="font-size:.7rem;text-transform:uppercase;letter-spacing:2px;color:var(--green);margin-bottom:8px">🏛️ CEPEJ / RECPJ / datos.jus.gob.ar</div>
    <div style="font-size:.82rem;color:var(--muted);line-height:1.7">Oralidad civil · traslados · selección · género — datos reales PJN<br><a href="https://datos.jus.gob.ar" target="_blank" style="color:#86efac">datos.jus.gob.ar</a></div>
  </div>
</div>
<div style="background:#0f1e3a;border:1px solid var(--gold);border-radius:8px;padding:14px 18px;font-size:.82rem;color:#94a3b8;line-height:1.7;margin-bottom:24px">
  <strong style="color:var(--gold)">🔬 Nota (Ph.D. Monteverde):</strong>
  Los datos de oralidad civil (~60K causas) permiten calcular Clearance Rate y Disposition Time reales por juzgado.
  V-Dem ofrece microdatos desde 1789 ideales para <strong style="color:var(--text)">análisis de ruptura institucional</strong>.
  CEJAS es la fuente LAC más específica para <strong style="color:var(--text)">precursores de captura institucional</strong>.
  El dato de <code style="color:#93c5fd">concurso_en_tramite</code> en datos_jus/magistrados permite calcular el % real de vacantes con concurso activo.
</div>
"""

    parts = [
        _head("Indicadores Internacionales — Monitor Judicial"),
        nav_html("indicadores"),
        "<div class='contenido'>",
        DISCLAIMER,
        html_body,
        "</div>",
        FOOTER,
        "<script>",
        PLOTLY_BASE,
        "\n",
        data_script,
        chart_script,
        new_api_js,
        "</script></body></html>",
    ]
    return HTMLResponse("".join(parts))


# ══════════════════════════════════════════════════════════════════════════════
# REDIRECT /estrategico → /estrategico/consejo
# ══════════════════════════════════════════════════════════════════════════════
@router.get("/", response_class=HTMLResponse)

# ══════════════════════════════════════════════════════════════════════════════
# CANDIDATOS — CVs de candidatos a magistrados (datos_jus)
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/api/candidatos", response_class=JSONResponse)
def api_candidatos():
    try:
        return JSONResponse(_cargar_cvs_stats())
    except Exception as e:
        return JSONResponse({"error": str(e), "total": 0}, status_code=500)


@router.get("/candidatos", response_class=HTMLResponse)
def pagina_candidatos():
    html_body = """
<div class=\"scope\">
  📋 <strong>Candidatos a Magistrados</strong> &mdash;
  Base pública de CVs presentados en concursos del Consejo de la Magistratura.
  Fuente: <a href=\"https://datos.jus.gob.ar\" target=\"_blank\" style=\"color:var(--gold)\">datos.jus.gob.ar</a>
</div>
<div class=\"kpi-grid\">
  <div class=\"kpi gold\"><label>Total candidatos</label><div class=\"val\" id=\"cv-total\">&#8212;</div><div class=\"sub\">CVs presentados</div></div>
  <div class=\"kpi\"><label>Universidades representadas</label><div class=\"val\" id=\"cv-univs\">&#8212;</div><div class=\"sub\">Instituciones de egreso</div></div>
  <div class=\"kpi verde\"><label>Provincias de origen</label><div class=\"val\" id=\"cv-provs\">&#8212;</div><div class=\"sub\">Distribución geográfica</div></div>
</div>
<div class=\"seccion\">📊 Distribución por Universidad</div>
<div class=\"chart-full\"><div id=\"graf-cv-univs\" style=\"height:360px\"></div></div>
<div class=\"charts\">
  <div class=\"chart-box\"><h2>🗺️ Provincias de nacimiento</h2><div id=\"graf-cv-provs\" style=\"height:360px\"></div></div>
  <div class=\"chart-box\"><h2>⚖️ Ámbito del concurso</h2><div id=\"graf-cv-ambitos\" style=\"height:360px\"></div></div>
</div>
<div class=\"seccion\">🔍 Candidatos (primeros 200)</div>
<div class=\"controles\"><label>Buscar: <input id=\"cv-buscar\" type=\"text\" placeholder=\"nombre, universidad, provincia&hellip;\" style=\"width:280px\"></label></div>
<div style=\"overflow-x:auto\">
  <table style=\"width:100%;border-collapse:collapse;font-size:.82rem\">
    <thead><tr style=\"background:var(--card2);color:var(--muted);text-align:left\">
      <th style=\"padding:8px 12px\">Nombre</th>
      <th style=\"padding:8px 12px\">Concurso</th>
      <th style=\"padding:8px 12px\">Universidad</th>
      <th style=\"padding:8px 12px\">Provincia</th>
      <th style=\"padding:8px 12px\">Ámbito</th>
      <th style=\"padding:8px 12px\">CV</th>
    </tr></thead>
    <tbody id=\"cv-tbody\"></tbody>
  </table>
</div>
"""

    script = r"""
const cfg={responsive:true,displayModeBar:false};
fetch('/estrategico/api/candidatos').then(r=>r.json()).then(d=>{
  document.getElementById('cv-total').textContent=d.total.toLocaleString('es-AR');
  document.getElementById('cv-univs').textContent=d.universidades.length;
  document.getElementById('cv-provs').textContent=d.provincias.length;
  const uL=d.universidades.map(u=>u.nombre),uV=d.universidades.map(u=>u.cantidad);
  Plotly.newPlot('graf-cv-univs',[{type:'bar',x:uV,y:uL,orientation:'h',text:uV,textposition:'outside',
    marker:{color:'#3b82f6',opacity:.85},hovertemplate:'<b>%{y}</b><br>%{x} candidatos<extra></extra>'}],
    {plot_bgcolor:'#1a2744',paper_bgcolor:'#1a2744',font:{color:'#e2e8f0',family:'Segoe UI',size:11},
     margin:{l:220,r:60,t:20,b:40},xaxis:{gridcolor:'#2d4a7a'},yaxis:{gridcolor:'#2d4a7a',automargin:true}},cfg);
  const pL=d.provincias.map(p=>p.provincia),pV=d.provincias.map(p=>p.cantidad);
  Plotly.newPlot('graf-cv-provs',[{type:'bar',x:pL,y:pV,
    marker:{color:'#c9a227',opacity:.85},hovertemplate:'<b>%{x}</b><br>%{y}<extra></extra>'}],
    {plot_bgcolor:'#1a2744',paper_bgcolor:'#1a2744',font:{color:'#e2e8f0',family:'Segoe UI',size:11},
     margin:{l:40,r:20,t:20,b:80},xaxis:{gridcolor:'#2d4a7a',tickangle:-40},yaxis:{gridcolor:'#2d4a7a'}},cfg);
  const aL=d.ambitos.map(a=>a.ambito),aV=d.ambitos.map(a=>a.cantidad);
  Plotly.newPlot('graf-cv-ambitos',[{type:'pie',labels:aL,values:aV,hole:.35,
    textinfo:'label+percent',hovertemplate:'<b>%{label}</b><br>%{value}<extra></extra>',
    marker:{colors:['#3b82f6','#c9a227','#22c55e','#e63946','#8b5cf6','#f97316']}}],
    {plot_bgcolor:'#1a2744',paper_bgcolor:'#1a2744',font:{color:'#e2e8f0',family:'Segoe UI',size:11},
     margin:{l:10,r:10,t:20,b:10},showlegend:false},cfg);
  window._cvData=d.tabla;
  renderTabla(d.tabla);
}).catch(e=>console.error('Error candidatos:',e));
function renderTabla(rows){
  document.getElementById('cv-tbody').innerHTML=rows.map(r=>`
    <tr style="border-bottom:1px solid #2d4a7a">
      <td style="padding:7px 12px;color:#e2e8f0">${r.nombre||'&#8212;'}</td>
      <td style="padding:7px 12px;color:#94a3b8">${r.concurso||'&#8212;'}</td>
      <td style="padding:7px 12px;color:#93c5fd">${r.universidad||'&#8212;'}</td>
      <td style="padding:7px 12px;color:#94a3b8">${r.provincia||'&#8212;'}</td>
      <td style="padding:7px 12px;color:#94a3b8;font-size:.76rem">${r.ambito||'&#8212;'}</td>
      <td style="padding:7px 12px">${r.link_cv?`<a href="${r.link_cv}" target="_blank" style="color:var(--gold)">Ver CV &rarr;</a>`:'&#8212;'}</td>
    </tr>`).join('');
}
document.getElementById('cv-buscar').addEventListener('input',function(){
  const q=this.value.toLowerCase();
  if(!window._cvData)return;
  renderTabla(window._cvData.filter(r=>
    (r.nombre||'').toLowerCase().includes(q)||(r.universidad||'').toLowerCase().includes(q)||
    (r.provincia||'').toLowerCase().includes(q)||(r.ambito||'').toLowerCase().includes(q)));
});
"""

    parts = [
        _head("Candidatos a Magistrados \u2014 Monitor Judicial"),
        nav_html("candidatos"),
        "<div class='contenido'>",
        DISCLAIMER,
        html_body,
        "</div>",
        FOOTER,
        '<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>',
        "<script>", script, "</script></body></html>",
    ]
    return HTMLResponse("".join(parts))

def redirect_estrategico():
    return HTMLResponse('<meta http-equiv="refresh" content="0; url=/estrategico/consejo">')
