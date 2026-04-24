# dashboard_estrategico/app.py  —  VERSIÓN COMPLETA CON INDICADORES INTERNACIONALES
# Reemplaza el archivo original.
#
# CAMBIOS:
#   1. pagina_consejo() con try/except — muestra el traceback en pantalla si hay error
#   2. NUEVA RUTA: /estrategico/indicadores — WJP, WGI, IPC, ODS 16, OCDE
#   3. nav_html debe actualizarse en shared.py (ver comentario al final)

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
# DATOS ESTÁTICOS — Indicadores Internacionales 2022-2023
# Fuente: WJP 2023, World Bank WGI 2022, Transparencia Internacional IPC 2023,
#         ONU SDG 16, OCDE Justice at a Glance 2023
# ══════════════════════════════════════════════════════════════════════════════

# World Justice Project Rule of Law Index 2023 (escala 0–1)
_WJP_RANKING = {
    "Perú":         0.40, "México":    0.41, "Colombia":  0.46,
    "Argentina":    0.47, "Brasil":    0.48, "Costa Rica":0.55,
    "Chile":        0.59, "Uruguay":   0.64, "OCDE (prom.)": 0.68,
}
_WJP_COLORS = {
    "Perú":"#e63946","México":"#e63946","Colombia":"#f97316",
    "Argentina":"#c9a227","Brasil":"#f97316","Costa Rica":"#22c55e",
    "Chile":"#22c55e","Uruguay":"#22c55e","OCDE (prom.)":"#3b82f6",
}

# WJP 8 dimensiones para Argentina, LAC y OCDE
_WJP_DIMS = [
    "Límites al Poder Gub.","Ausencia de Corrupción","Gobierno Abierto",
    "Derechos Fundamentales","Orden y Seguridad","Cumplimiento Regulatorio",
    "Justicia Civil","Justicia Penal"
]
_WJP_ARG  = [0.56, 0.39, 0.47, 0.53, 0.59, 0.45, 0.42, 0.38]
_WJP_LAC  = [0.52, 0.43, 0.45, 0.55, 0.57, 0.44, 0.44, 0.40]
_WJP_OCDE = [0.72, 0.71, 0.63, 0.75, 0.78, 0.68, 0.68, 0.62]

# Evolución WJP Argentina
_WJP_HIST = {2015:0.50,2016:0.50,2017:0.49,2018:0.48,2019:0.49,2020:0.48,2021:0.47,2022:0.47,2023:0.47}

# World Bank WGI 2022 (escala -2.5 a +2.5)
_WGI_DIM = [
    "Estado de Derecho","Control de Corrupción","Efectividad Gubernamental",
    "Calidad Regulatoria","Estabilidad Política","Voz y Rendición de Cuentas"
]
_WGI_ARG = [-0.21, -0.35, -0.22, -0.06, -0.28, 0.32]

# WGI Rule of Law — comparativa regional
_WGI_ROL = {
    "Uruguay":1.12,"Chile":0.97,"Costa Rica":0.58,"Brasil":0.03,
    "Argentina":-0.21,"Colombia":-0.31,"Perú":-0.44,"México":-0.60,"Bolivia":-0.73,
}

# IPC Transparencia Internacional 2023 (0–100)
_IPC_LAC = {
    "Uruguay":74,"Chile":63,"Costa Rica":55,"Brasil":36,"Argentina":37,
    "Ecuador":33,"Colombia":34,"Perú":33,"Bolivia":31,"México":31,"Paraguay":25,
}
_IPC_HIST = {
    2013:34,2014:34,2015:32,2016:36,2017:39,2018:40,
    2019:45,2020:42,2021:38,2022:38,2023:37,
}

# OCDE — Duración promedio procedimientos civiles 1ª instancia (días, 2023)
_OCDE_DUR = {
    "Noruega":98,"Dinamarca":110,"Países Bajos":115,"Alemania":184,
    "España":253,"Italia":527,"Colombia":1340,"Argentina (est.)":420,"OCDE prom.":240,
}

# ODS 16 — Argentina
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

# ── Constantes CSJN ───────────────────────────────────────────────────────────
PRESUPUESTO_CSJN_ARS = 28_500_000_000
PRESUPUESTO_PJN_ARS  = 280_000_000_000
SENTENCIAS_PJN_ANIO  = 85_000
POBLACION_ARGENTINA  = 46_000_000

# ── Helpers ───────────────────────────────────────────────────────────────────
def _cargar(nombre):
    path = os.path.join(ROOT, nombre)
    with open(path, "r", encoding="utf-8") as f:
        data = _json.load(f)
    if isinstance(data, list):
        return data
    for k in ("data","magistrados","vacantes","designaciones","causas","results"):
        if k in data:
            return data[k]
    return list(data.values())[0] if data else []

def _cargar_safe(nombre):
    try: return _cargar(nombre)
    except: return []

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
# PESTAÑA: CONSEJO  (con try/except para debugging)
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
const fmt = n => n==null?'S/D':Number(n).toLocaleString('es-AR');
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
# ══════════════════════════════════════════════════════════════════════════════
@router.get("/indicadores", response_class=HTMLResponse)
def pagina_indicadores():
    """Indicadores Comparativos Internacionales: WJP, WGI, IPC, ODS 16, OCDE."""

    # Serializar datos a JSON para inyectar como variables JS
    j = _json.dumps  # alias corto

    wjp_labels  = list(_WJP_RANKING.keys())
    wjp_scores  = list(_WJP_RANKING.values())
    wjp_colors  = [_WJP_COLORS[p] for p in wjp_labels]
    wgi_colors  = ["#e63946" if v < -0.2 else "#f97316" if v < 0 else "#22c55e" for v in _WGI_ARG]
    rol_colors  = ["#22c55e" if v > 0 else "#e63946" for v in _WGI_ROL.values()]
    ipc_colors  = ["#22c55e" if v >= 50 else "#f97316" if v >= 35 else "#e63946" for v in _IPC_LAC.values()]
    ocde_vals   = list(_OCDE_DUR.values())
    ocde_colors = ["#22c55e" if v <= 240 else "#f97316" if v <= 500 else "#e63946" for v in ocde_vals]

    # Script de datos (JS vars, no usa f-string para evitar conflictos con braces JS)
    data_script = (
        "const wjpLabels=" + j(wjp_labels) + ";\n"
        "const wjpScores=" + j(wjp_scores) + ";\n"
        "const wjpColors=" + j(wjp_colors) + ";\n"
        "const wjpDimLabels=" + j(_WJP_DIMS) + ";\n"
        "const wjpDimArg=" + j(_WJP_ARG) + ";\n"
        "const wjpDimLac=" + j(_WJP_LAC) + ";\n"
        "const wjpDimOcde=" + j(_WJP_OCDE) + ";\n"
        "const wjpHistAnios=" + j(list(_WJP_HIST.keys())) + ";\n"
        "const wjpHistScores=" + j(list(_WJP_HIST.values())) + ";\n"
        "const wgiLabels=" + j(_WGI_DIM) + ";\n"
        "const wgiArg=" + j(_WGI_ARG) + ";\n"
        "const wgiColors=" + j(wgi_colors) + ";\n"
        "const rolLabels=" + j(list(_WGI_ROL.keys())) + ";\n"
        "const rolValues=" + j(list(_WGI_ROL.values())) + ";\n"
        "const rolColors=" + j(rol_colors) + ";\n"
        "const ipcLabels=" + j(list(_IPC_LAC.keys())) + ";\n"
        "const ipcValues=" + j(list(_IPC_LAC.values())) + ";\n"
        "const ipcColors=" + j(ipc_colors) + ";\n"
        "const ipcHistAnios=" + j(list(_IPC_HIST.keys())) + ";\n"
        "const ipcHistScores=" + j(list(_IPC_HIST.values())) + ";\n"
        "const ocdeLabels=" + j(list(_OCDE_DUR.keys())) + ";\n"
        "const ocdeValues=" + j(ocde_vals) + ";\n"
        "const ocdeColors=" + j(ocde_colors) + ";\n"
        "const odsData=" + j(_ODS16) + ";\n"
    )

    # Lógica JS (sin f-string, no hay conflictos de braces)
    chart_script = r"""
const C2={bg:'#0a1628',card:'#1a2744',gold:'#c9a227',blue:'#3b82f6',red:'#e63946',green:'#22c55e',text:'#e2e8f0',muted:'#94a3b8',grid:'#2d4a7a'};
const Lx=(x={})=>Object.assign({plot_bgcolor:C2.card,paper_bgcolor:C2.card,font:{color:C2.text,family:'Segoe UI',size:12},margin:{l:10,r:10,t:20,b:40},xaxis:{gridcolor:C2.grid,linecolor:C2.grid},yaxis:{gridcolor:C2.grid,linecolor:C2.grid}},x);
const fmt=n=>n==null?'S/D':Number(n).toLocaleString('es-AR');
const cfg={responsive:true,displayModeBar:false};

// ── WJP Ranking ──
Plotly.newPlot('graf-wjp-rank',[{type:'bar',orientation:'h',x:wjpScores,y:wjpLabels,
  text:wjpScores.map(v=>v.toFixed(2)),textposition:'outside',
  marker:{color:wjpColors,opacity:.9},
  hovertemplate:'<b>%{y}</b><br>Score WJP: %{x}<extra></extra>'}],
  Lx({xaxis:{range:[0,0.82],gridcolor:C2.grid,title:{text:'Score (0–1)',font:{size:11}}},
    yaxis:{autorange:'reversed',gridcolor:C2.grid},margin:{l:10,r:60,t:10,b:40},
    shapes:[{type:'line',x0:0.47,x1:0.47,y0:-0.5,y1:wjpLabels.length-0.5,
             line:{color:'#c9a227',width:2,dash:'dot'}}],
    annotations:[{x:0.47,y:0.3,xanchor:'left',text:'ARG 0.47',
                  font:{color:'#c9a227',size:11},showarrow:false}]}),cfg);

// ── WJP Radar ──
const radarLabels=[...wjpDimLabels,wjpDimLabels[0]];
Plotly.newPlot('graf-wjp-radar',[
  {type:'scatterpolar',fill:'toself',name:'Argentina',
   r:[...wjpDimArg,wjpDimArg[0]],theta:radarLabels,
   line:{color:'#c9a227',width:2},fillcolor:'rgba(201,162,39,0.15)'},
  {type:'scatterpolar',fill:'toself',name:'LAC prom.',
   r:[...wjpDimLac,wjpDimLac[0]],theta:radarLabels,
   line:{color:'#3b82f6',width:1.5,dash:'dot'},fillcolor:'rgba(59,130,246,0.06)'},
  {type:'scatterpolar',fill:'toself',name:'OCDE prom.',
   r:[...wjpDimOcde,wjpDimOcde[0]],theta:radarLabels,
   line:{color:'#22c55e',width:1.5,dash:'dash'},fillcolor:'rgba(34,197,94,0.06)'},
],{polar:{bgcolor:C2.card,
   radialaxis:{range:[0,1],gridcolor:C2.grid,tickfont:{size:10,color:C2.muted}},
   angularaxis:{gridcolor:C2.grid,tickfont:{size:9,color:C2.text}}},
  paper_bgcolor:C2.card,plot_bgcolor:C2.card,font:{color:C2.text,family:'Segoe UI',size:11},
  legend:{bgcolor:'rgba(0,0,0,0)',font:{color:C2.text,size:11}},
  margin:{l:50,r:50,t:20,b:20}},cfg);

// ── WJP Histórico ──
Plotly.newPlot('graf-wjp-hist',[{type:'scatter',mode:'lines+markers',
  x:wjpHistAnios,y:wjpHistScores,line:{color:'#c9a227',width:2.5},
  marker:{color:'#c9a227',size:7},fill:'tozeroy',fillcolor:'rgba(201,162,39,0.08)',
  hovertemplate:'<b>%{x}</b><br>Score: %{y:.2f}<extra></extra>'}],
  Lx({yaxis:{range:[0.35,0.65],gridcolor:C2.grid,tickformat:'.2f'},
     xaxis:{gridcolor:C2.grid,dtick:2},margin:{l:50,r:10,t:10,b:30}}),cfg);

// ── IPC Regional ──
Plotly.newPlot('graf-ipc-reg',[{type:'bar',x:ipcLabels,y:ipcValues,
  text:ipcValues,textposition:'outside',marker:{color:ipcColors,opacity:.9},
  hovertemplate:'<b>%{x}</b><br>IPC: %{y}/100<extra></extra>'}],
  Lx({yaxis:{range:[0,90],gridcolor:C2.grid,title:{text:'Score IPC (0–100)',font:{size:11}}},
     xaxis:{gridcolor:C2.grid,tickangle:-30},margin:{l:50,r:10,t:10,b:80},
     shapes:[{type:'line',x0:-0.5,x1:ipcLabels.length-0.5,y0:50,y1:50,
              line:{color:'#22c55e',width:1.5,dash:'dot'}}],
     annotations:[{x:5,y:53,text:'Umbral "limpio" ≥ 50',
                   font:{color:'#22c55e',size:11},showarrow:false}]}),cfg);

// ── IPC Histórico ──
Plotly.newPlot('graf-ipc-hist',[{type:'scatter',mode:'lines+markers',
  x:ipcHistAnios,y:ipcHistScores,line:{color:'#e63946',width:2.5},
  marker:{color:'#e63946',size:7},fill:'tozeroy',fillcolor:'rgba(230,57,70,0.08)',
  hovertemplate:'<b>%{x}</b><br>IPC: %{y}<extra></extra>'}],
  Lx({yaxis:{range:[25,55],gridcolor:C2.grid},xaxis:{gridcolor:C2.grid,dtick:2},
     margin:{l:40,r:10,t:10,b:30}}),cfg);

// ── WGI Dimensiones Argentina ──
Plotly.newPlot('graf-wgi-dim',[{type:'bar',orientation:'h',
  x:wgiArg,y:wgiLabels,text:wgiArg.map(v=>v.toFixed(2)),textposition:'outside',
  marker:{color:wgiColors,opacity:.9},
  hovertemplate:'<b>%{y}</b><br>Score: %{x}<extra></extra>'}],
  Lx({xaxis:{range:[-0.65,0.65],gridcolor:C2.grid,title:{text:'Score (-2.5 a +2.5)',font:{size:11}}},
     yaxis:{autorange:'reversed',gridcolor:C2.grid},margin:{l:10,r:60,t:10,b:40},
     shapes:[{type:'line',x0:0,x1:0,y0:-0.5,y1:5.5,line:{color:C2.muted,width:1,dash:'dot'}}]}),cfg);

// ── WGI Rule of Law Regional ──
Plotly.newPlot('graf-wgi-rol',[{type:'bar',orientation:'h',
  x:rolValues,y:rolLabels,text:rolValues.map(v=>v.toFixed(2)),textposition:'outside',
  marker:{color:rolColors,opacity:.9},
  hovertemplate:'<b>%{y}</b><br>Rule of Law: %{x}<extra></extra>'}],
  Lx({xaxis:{range:[-1.0,1.5],gridcolor:C2.grid,title:{text:'Score WGI Rule of Law',font:{size:11}}},
     yaxis:{autorange:'reversed',gridcolor:C2.grid},margin:{l:10,r:60,t:10,b:40},
     shapes:[{type:'line',x0:0,x1:0,y0:-0.5,y1:rolLabels.length-0.5,
              line:{color:C2.muted,width:1,dash:'dot'}}]}),cfg);

// ── OCDE Duración Civil ──
Plotly.newPlot('graf-ocde',[{type:'bar',x:ocdeLabels,y:ocdeValues,
  text:ocdeValues.map(v=>v+'d'),textposition:'outside',marker:{color:ocdeColors,opacity:.9},
  hovertemplate:'<b>%{x}</b><br>Duración: %{y} días<extra></extra>'}],
  Lx({yaxis:{gridcolor:C2.grid,title:{text:'Días (1ª instancia)',font:{size:11}}},
     xaxis:{gridcolor:C2.grid},margin:{l:60,r:10,t:10,b:40},
     shapes:[{type:'line',x0:-0.5,x1:ocdeLabels.length-0.5,y0:240,y1:240,
              line:{color:'#22c55e',width:1.5,dash:'dot'}}],
     annotations:[{x:4,y:260,text:'Promedio OCDE: 240 días',
                   font:{color:'#22c55e',size:11},showarrow:false}]}),cfg);

// ── ODS 16 cards ──
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

    html_body = (
        "<div class='contenido'>"
        + DISCLAIMER
        + """
<div class="scope">
  🌐 <strong>Indicadores Comparativos Internacionales</strong> —
  Argentina en el contexto regional y global.
  <a href="#fuentes" style="color:var(--gold);margin-left:8px">Ver fuentes →</a>
</div>

<div class="seccion">⚖️ World Justice Project — Índice Estado de Derecho 2023</div>
<div class="inst-badges">
  <div class="badge blue">Escala 0–1 · Mayor = mejor Estado de Derecho</div>
  <div class="badge gold">Argentina: 0.47 · Puesto 65/142 países</div>
  <div class="badge red">LAC prom.: 0.50 · OCDE prom.: 0.68</div>
</div>
<div class="charts">
  <div class="chart-box"><h2>🌎 Ranking Regional WJP 2023</h2>
    <div id="graf-wjp-rank" style="height:340px"></div></div>
  <div class="chart-box"><h2>📊 Argentina vs. LAC vs. OCDE — 8 Dimensiones</h2>
    <div id="graf-wjp-radar" style="height:340px"></div></div>
</div>
<div class="chart-full"><h2>📅 Evolución WJP Argentina 2015–2023</h2>
  <div id="graf-wjp-hist" style="height:200px"></div></div>

<div class="seccion">🔍 IPC Transparencia Internacional 2023 — Corrupción Percibida</div>
<div class="inst-badges">
  <div class="badge blue">Escala 0–100 · Mayor = menor corrupción percibida</div>
  <div class="badge gold">Argentina: 37/100 · Puesto 99/180</div>
</div>
<div class="charts">
  <div class="chart-box"><h2>🌎 IPC Comparativo Regional 2023</h2>
    <div id="graf-ipc-reg" style="height:340px"></div></div>
  <div class="chart-box"><h2>📅 Evolución IPC Argentina 2013–2023</h2>
    <div id="graf-ipc-hist" style="height:340px"></div></div>
</div>

<div class="seccion">🏦 Banco Mundial — Indicadores de Gobernanza 2022 (WGI)</div>
<div class="inst-badges">
  <div class="badge blue">Escala -2.5 a +2.5 · Mayor valor = mejor gobernanza</div>
  <div class="badge red">Argentina negativo en 5 de 6 dimensiones</div>
</div>
<div class="charts">
  <div class="chart-box"><h2>📊 Argentina — 6 Dimensiones WGI</h2>
    <div id="graf-wgi-dim" style="height:340px"></div></div>
  <div class="chart-box"><h2>🌎 Rule of Law Regional</h2>
    <div id="graf-wgi-rol" style="height:340px"></div></div>
</div>

<div class="seccion">🇺🇳 ODS 16 — Paz, Justicia e Instituciones Sólidas (Argentina)</div>
<div class="kpi-grid" id="kpi-ods" style="grid-template-columns:repeat(auto-fit,minmax(260px,1fr))"></div>

<div class="seccion">🏛️ OCDE — Duración Procedimientos Civiles (días, 1ª instancia)</div>
<div class="chart-full"><div id="graf-ocde" style="height:260px"></div></div>

<div class="seccion" id="fuentes">📚 Fuentes y Metodología</div>
<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px;margin-bottom:24px">

  <div style="background:var(--card);border-radius:10px;padding:18px;border-top:3px solid var(--gold)">
    <div style="font-size:.7rem;text-transform:uppercase;letter-spacing:2px;color:var(--gold);margin-bottom:8px">⚖️ WJP Rule of Law Index</div>
    <div style="font-size:.82rem;color:var(--muted);line-height:1.7">
      Encuestas a hogares y cuestionarios a expertos en 142 países.<br>
      8 factores: límites al poder, corrupción, gobierno abierto, derechos, seguridad, regulación, justicia civil y penal.<br>
      <a href="https://worldjusticeproject.org" target="_blank" style="color:var(--gold2)">worldjusticeproject.org</a>
    </div>
  </div>

  <div style="background:var(--card);border-radius:10px;padding:18px;border-top:3px solid #3b82f6">
    <div style="font-size:.7rem;text-transform:uppercase;letter-spacing:2px;color:#3b82f6;margin-bottom:8px">🏦 World Bank — WGI</div>
    <div style="font-size:.82rem;color:var(--muted);line-height:1.7">
      Agregación de 30 fuentes: ONG, think tanks, organismos internacionales. 6 dimensiones, escala -2.5 a +2.5.<br>
      <a href="https://databank.worldbank.org" target="_blank" style="color:#93c5fd">databank.worldbank.org</a>
    </div>
  </div>

  <div style="background:var(--card);border-radius:10px;padding:18px;border-top:3px solid var(--red)">
    <div style="font-size:.7rem;text-transform:uppercase;letter-spacing:2px;color:var(--red);margin-bottom:8px">🔍 Transparencia Internacional — IPC</div>
    <div style="font-size:.82rem;color:var(--muted);line-height:1.7">
      Indicador compuesto de percepción de corrupción en sector público. 13 fuentes de datos. Escala 0–100.<br>
      <a href="https://www.transparency.org/en/cpi" target="_blank" style="color:#fca5a5">transparency.org/en/cpi</a>
    </div>
  </div>

  <div style="background:var(--card);border-radius:10px;padding:18px;border-top:3px solid var(--green)">
    <div style="font-size:.7rem;text-transform:uppercase;letter-spacing:2px;color:var(--green);margin-bottom:8px">🇺🇳 ONU — ODS 16 / UNODC</div>
    <div style="font-size:.82rem;color:var(--muted);line-height:1.7">
      Marco Agenda 2030. Reportes nacionales + UNODC + PNUD. Indicadores: presos preventivos, acceso a mecanismos, soborno, discriminación.<br>
      <a href="https://sdgs.un.org/goals/goal16" target="_blank" style="color:#86efac">sdgs.un.org/goals/goal16</a>
    </div>
  </div>

  <div style="background:var(--card);border-radius:10px;padding:18px;border-top:3px solid #8b5cf6">
    <div style="font-size:.7rem;text-transform:uppercase;letter-spacing:2px;color:#8b5cf6;margin-bottom:8px">🏛️ OCDE — Justice at a Glance</div>
    <div style="font-size:.82rem;color:var(--muted);line-height:1.7">
      Datos directos de Ministerios de Justicia. Eficiencia de tribunales, independencia, digitalización procesal.<br>
      <a href="https://www.oecd.org/governance/justice" target="_blank" style="color:#c4b5fd">oecd.org/governance/justice</a>
    </div>
  </div>

  <div style="background:var(--card);border-radius:10px;padding:18px;border-top:3px solid #f97316">
    <div style="font-size:.7rem;text-transform:uppercase;letter-spacing:2px;color:#f97316;margin-bottom:8px">📊 Latinobarómetro / GCB</div>
    <div style="font-size:.82rem;color:var(--muted);line-height:1.7">
      Encuestas de opinión pública en 18 países de América Latina. Confianza institucional, experiencias directas de corrupción.<br>
      <a href="https://www.latinobarometro.org" target="_blank" style="color:#fdba74">latinobarometro.org</a>
    </div>
  </div>

</div>

<div style="background:#0f1e3a;border:1px solid var(--gold);border-radius:8px;padding:14px 18px;font-size:.82rem;color:#94a3b8;line-height:1.7;margin-bottom:24px">
  <strong style="color:var(--gold)">🔬 Nota para análisis algorítmico:</strong>
  WJP y World Bank ofrecen microdatos en CSV/JSON para Python.
  El IPC incluye los intervalos de confianza (margen de error) necesarios para modelos de regresión.
  UNODC provee el marco estadístico de la UNCAC con series temporales por país.
  Estos datos son compatibles con análisis de anomalías institucionales y modelos de detección de corrupción.
</div>
</div>"""
        + FOOTER
    )

    parts = [
        _head("Indicadores Internacionales — Monitor Judicial"),
        nav_html("indicadores"),
        html_body,
        "<script>",
        PLOTLY_BASE,
        "\n",
        data_script,
        chart_script,
        "</script></body></html>",
    ]
    return HTMLResponse("".join(parts))


# ══════════════════════════════════════════════════════════════════════════════
# REDIRECT /estrategico → /estrategico/consejo
# ══════════════════════════════════════════════════════════════════════════════
@router.get("/", response_class=HTMLResponse)
def redirect_estrategico():
    return HTMLResponse('<meta http-equiv="refresh" content="0; url=/estrategico/consejo">')


# ══════════════════════════════════════════════════════════════════════════════
# INSTRUCCIÓN: actualizar nav_html() en shared.py
# ══════════════════════════════════════════════════════════════════════════════
# En shared.py, función nav_html(), reemplazar la lista `tabs` por:
#
# tabs = [
#     ("/",                        "🏛️ Inicio",       "inicio"),
#     ("/estrategico/corte",       "⚖️ Corte",        "corte"),
#     ("/estrategico/consejo",     "🏛 Consejo",      "consejo"),
#     ("/estrategico/indicadores", "🌐 Indicadores",  "indicadores"),
#     ("/operativo/camaras",       "🏢 Cámaras",      "camaras"),
#     ("/operativo",               "📋 Juzgados",     "juzgados"),
# ]