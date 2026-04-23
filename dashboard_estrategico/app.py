# dashboard_estrategico/app.py
# Rutas: /estrategico  /estrategico/corte  /estrategico/consejo
#        + APIs JSON

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse
import json, os, sys
from collections import Counter

router = APIRouter()
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(ROOT)

from src.utils import calcular_tasa_vacancia, calcular_costo_por_sentencia
from shared import BASE_CSS, DISCLAIMER, FOOTER, PLOTLY_JS, PLOTLY_BASE, nav_html

# ── Helpers ───────────────────────────────────────────────────────────────────
def _cargar(nombre):
    path = os.path.join(ROOT, nombre)
    with open(path, "r", encoding="utf-8") as f: data = json.load(f)
    if isinstance(data, list): return data
    for k in ("data","magistrados","vacantes","designaciones","results"):
        if k in data: return data[k]
    return list(data.values())[0] if data else []

def _col(recs, *kws):
    if not recs: return None
    keys = recs[0].keys()
    for kw in kws:
        m = next((k for k in keys if kw.lower() in k.lower()), None)
        if m: return m
    return None

# ── APIs JSON ─────────────────────────────────────────────────────────────────
@router.get("/api/kpis")
def api_kpis():
    try:
        mag = _cargar("magistrados.json"); vac = _cargar("vacantes.json")
        des = _cargar("designaciones.json")
        tm = len(mag); tv = len(vac); cu = tm - tv
        return {"total_magistrados":tm,"total_vacantes":tv,"cargos_cubiertos":cu,
                "tasa_vacancia_pct":calcular_tasa_vacancia(cu,tm),
                "total_designaciones":len(des),
                "costo_por_sentencia":calcular_costo_por_sentencia(280_000_000_000,85_000),
                "ministros_csjn":5}
    except Exception as e: return JSONResponse({"error":str(e)},status_code=500)

@router.get("/api/vacancia")
def api_vacancia():
    try:
        vac = _cargar("vacantes.json")
        col = _col(vac,"jurisdic","provincia","lugar","sede")
        if not col: return {"labels":[],"values":[],"col_detectada":None}
        top = Counter(str(r.get(col,"Sin dato")) for r in vac).most_common(15)
        return {"labels":[x[0] for x in top],"values":[x[1] for x in top],
                "col_detectada":col,"total":len(vac)}
    except Exception as e: return JSONResponse({"error":str(e)},status_code=500)

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
                if a.isdigit() and 2000<=int(a)<=2026: c[a]+=1
            s=sorted(c.items())
            por_anio={"labels":[x[0] for x in s],"values":[x[1] for x in s]}
        return {"por_fuero":fueros,"por_anio":por_anio,"total":len(des)}
    except Exception as e: return JSONResponse({"error":str(e)},status_code=500)

# ── HTML helpers ──────────────────────────────────────────────────────────────
def _head(titulo):
    return f"""<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8">
<title>{titulo}</title>{PLOTLY_JS}
<style>{BASE_CSS}</style></head><body>"""

def _foot(): return f"{FOOTER}</body></html>"

# ═══════════════════════════════════════════════════════════════════════════════
# PESTAÑA: CORTE SUPREMA
# ═══════════════════════════════════════════════════════════════════════════════
@router.get("/corte", response_class=HTMLResponse)
def pagina_corte():
    html = _head("Corte Suprema — CSJN")
    html += nav_html("corte")
    html += f"""<div class="contenido">
{DISCLAIMER}
<div class="scope">
  ⚖️ <strong>Corte Suprema de Justicia de la Nación (CSJN)</strong> —
  Máxima instancia judicial. Los datos de fallos requieren integración NLP
  (<code>src/nlp_corte_suprema.py</code> — próxima etapa).
</div>

<div class="seccion">⚖️ Composición actual</div>
<div class="kpi-grid">
  <div class="kpi gold"><label>Ministros en ejercicio</label>
    <div class="val">5</div></div>
  <div class="kpi"><label>Fallos alto impacto</label>
    <div class="val" style="font-size:1.1rem">N/D</div>
    <div class="sub">Requiere NLP sobre PDFs cij.gov.ar</div></div>
  <div class="kpi"><label>Tiempo prom. resolución</label>
    <div class="val" style="font-size:1.1rem">N/D</div>
    <div class="sub">Requiere scraping de acordadas</div></div>
  <div class="kpi rojo"><label>Costo macro x sentencia</label>
    <div class="val" style="font-size:1.1rem" id="costo-csjn">—</div>
    <div class="sub">ARS · Presupuesto 2024</div></div>
</div>

<div class="seccion">📅 Vacancia que impacta en la CSJN (Consejo)</div>
<div class="chart-full">
  <h2>Evolución de Designaciones — Vista desde la Corte</h2>
  <div id="graf-anio" style="height:240px"></div>
</div>

<div class="info-box">
  🔧 <strong>Próxima integración:</strong> <code>src/nlp_corte_suprema.py</code>
  extraerá fecha de fallo, partes, materia y tiempo de resolución desde los PDFs
  de <strong>cij.gov.ar</strong>. Output: <code>data/processed/fallos_csjn.parquet</code>
</div>
</div>
{FOOTER}
<script>
{PLOTLY_BASE}
async function cargar(){{
  const k=await fetch('/estrategico/api/kpis').then(r=>r.json());
  document.getElementById('costo-csjn').textContent='$'+fmt(Math.round(k.costo_por_sentencia));
  const d=await fetch('/estrategico/api/designaciones').then(r=>r.json());
  if(d.por_anio&&d.por_anio.labels&&d.por_anio.labels.length)
    Plotly.newPlot('graf-anio',[{{type:'scatter',mode:'lines',fill:'tozeroy',
      x:d.por_anio.labels,y:d.por_anio.values,
      line:{{color:C.gold,width:2}},fillcolor:'rgba(201,162,39,0.12)'}}],
      L(),{{responsive:true,displayModeBar:false}});
  else document.getElementById('graf-anio').innerHTML=
    '<p style="color:#4a5568;padding:16px">Sin datos de fecha en designaciones.json</p>';
}}
cargar();
</script></body></html>"""
    return HTMLResponse(html)


# ═══════════════════════════════════════════════════════════════════════════════
# PESTAÑA: CONSEJO DE LA MAGISTRATURA
# ═══════════════════════════════════════════════════════════════════════════════
@router.get("/consejo", response_class=HTMLResponse)
def pagina_consejo():
    html = _head("Consejo de la Magistratura")
    html += nav_html("consejo")
    html += f"""<div class="contenido">
{DISCLAIMER}
<div class="scope">
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
</div>
{FOOTER}
<script>
{PLOTLY_BASE}
async function cargar(){{
  const[k,v,d]=await Promise.all([
    fetch('/estrategico/api/kpis').then(r=>r.json()),
    fetch('/estrategico/api/vacancia').then(r=>r.json()),
    fetch('/estrategico/api/designaciones').then(r=>r.json()),
  ]);
  document.getElementById('kpi-consejo').innerHTML=`
    <div class="kpi"><label>Total Magistrados</label>
      <div class="val">${{fmt(k.total_magistrados)}}</div></div>
    <div class="kpi rojo"><label>Vacantes Detectadas</label>
      <div class="val">${{fmt(k.total_vacantes)}}</div>
      <div class="sub">${{k.tasa_vacancia_pct}}% del sistema</div></div>
    <div class="kpi verde"><label>Cargos Cubiertos</label>
      <div class="val">${{fmt(k.cargos_cubiertos)}}</div></div>
    <div class="kpi gold"><label>Designaciones totales</label>
      <div class="val">${{fmt(k.total_designaciones)}}</div></div>
    <div class="kpi"><label>Costo macro x sentencia</label>
      <div class="val" style="font-size:1.1rem">${{fmt(Math.round(k.costo_por_sentencia))}}</div>
      <div class="sub">ARS · Presupuesto 2024</div></div>
  `;
  if(v.labels&&v.labels.length)
    Plotly.newPlot('graf-vacancia',[{{type:'bar',orientation:'h',
      x:v.values,y:v.labels,marker:{{color:C.gold,opacity:.85}}}}],
      L({{yaxis:{{autorange:'reversed',gridcolor:C.grid}}}}),
      {{responsive:true,displayModeBar:false}});
  else document.getElementById('graf-vacancia').innerHTML=
    '<p style="color:#4a5568;padding:16px">Sin columna de jurisdicción en vacantes.json</p>';

  if(d.por_fuero&&d.por_fuero.labels&&d.por_fuero.labels.length)
    Plotly.newPlot('graf-fuero',[{{type:'pie',hole:.5,
      labels:d.por_fuero.labels,values:d.por_fuero.values,textinfo:'label+percent',
      marker:{{colors:['#c9a227','#3b82f6','#22c55e','#e63946','#8b5cf6','#f97316','#06b6d4','#ec4899'],
               line:{{color:'#1a2744',width:2}}}}}}],
      L({{showlegend:false,margin:{{l:10,r:10,t:10,b:10}}}}),
      {{responsive:true,displayModeBar:false}});

  if(d.por_anio&&d.por_anio.labels&&d.por_anio.labels.length)
    Plotly.newPlot('graf-anio',[{{type:'bar',
      x:d.por_anio.labels,y:d.por_anio.values,
      marker:{{color:C.gold,opacity:.85}}}}],
      L(),{{responsive:true,displayModeBar:false}});
}}
cargar().catch(e=>{{
  document.getElementById('kpi-consejo').innerHTML=
    '<div style="color:var(--red)">Error: '+e.message+'</div>';
}});
</script></body></html>"""
    return HTMLResponse(html)


# ═══════════════════════════════════════════════════════════════════════════════
# REDIRECT /estrategico → /estrategico/consejo
# ═══════════════════════════════════════════════════════════════════════════════
@router.get("/", response_class=HTMLResponse)
def redirect_estrategico():
    return HTMLResponse('<meta http-equiv="refresh" content="0; url=/estrategico/consejo">')
