# dashboard_operativo/app.py
# Rutas: /operativo  /operativo/camaras
#        + APIs JSON

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse, JSONResponse
import json, os, sys
from collections import Counter, defaultdict

router = APIRouter()
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(ROOT)

from src.utils import calcular_kpi_eficiencia
from shared import BASE_CSS, DISCLAIMER, FOOTER, PLOTLY_JS, PLOTLY_BASE, nav_html

# ── Helpers ───────────────────────────────────────────────────────────────────
def _cargar(nombre: str) -> list:
    path = os.path.join(ROOT, nombre)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    for key in ("data", "juzgados", "causas", "estadisticas", "registros", "results"):
        if key in data:
            return data[key]
    return list(data.values())[0] if data else []

def _col(registros: list, *kws: str):
    if not registros: return None
    keys = registros[0].keys()
    for kw in kws:
        m = next((k for k in keys if kw.lower() in k.lower()), None)
        if m: return m
    return None

def _es_camara(nombre: str) -> bool:
    return any(p in nombre.lower() for p in ("cámara", "camara", "cam."))

def _lats(registros, col_lat):
    vals = []
    if not col_lat: return vals
    for r in registros:
        try: vals.append(float(r.get(col_lat, 0) or 0))
        except: pass
    return [v for v in vals if v > 0]

def _cargar_operativo(nombre: str) -> list:
    """
    Carga datos operativos. Si detecta formato estadisticas_causas.json
    (con columna 'organismo'), reshapea a una fila por organismo combinando
    métricas de todos los tipo_csv disponibles.
    """
    data = _cargar(nombre)
    if not data or 'organismo' not in data[0]:
        return data

    grupos = defaultdict(list)
    for r in data:
        org = r.get('organismo', '').strip()
        if not org or 'total' in org.lower() or org.startswith('(*'):
            continue
        grupos[org].append(r)

    result = []
    for org, recs in sorted(grupos.items()):
        es_cam = _es_camara(org)

        # Métricas de sentencias/movimiento
        sent = [r for r in recs if r.get('tipo_csv') in ('sentencias', 'tramite_camara')]
        latest_sent = sorted(sent, key=lambda r: str(r.get('anio','')))[-1] if sent else {}

        # Métricas de trámite (tiene permanencia y resueltos)
        tram = [r for r in recs if r.get('tipo_csv') == 'tramite_camara']
        latest_tram = sorted(tram, key=lambda r: str(r.get('anio','')))[-1] if tram else {}

        # Métricas de recursos
        rec_recs = [r for r in recs if r.get('tipo_csv') == 'recursos']
        total_recursos = sum((r.get('recursos_apelacion') or 0) + (r.get('otros_recursos') or 0)
                             for r in rec_recs)

        latencia   = latest_tram.get('permanencia_breve') or latest_tram.get('permanencia_extensa') or 0
        resueltos  = latest_tram.get('resueltos') or latest_sent.get('resueltos') or 0
        pendientes = latest_sent.get('pendientes_cierre') or latest_sent.get('en_tramite_cierre') or 0
        tasa       = latest_tram.get('tasa_resolucion_pct') or latest_sent.get('tasa_resolucion_pct') or 0

        result.append({
            'juzgado':         org,
            'latencia':        latencia,
            'resueltos':       resueltos,
            'pendientes':      pendientes,
            'recursos':        total_recursos,
            'tasa_resolucion': tasa,
            'jurisdiccion':    (latest_sent or latest_tram).get('jurisdiccion', ''),
            'anio':            (latest_sent or latest_tram).get('anio', ''),
            'estado':          'camara' if es_cam else 'activo',
        })
    return result



# ── HTML helpers ──────────────────────────────────────────────────────────────
def _head(titulo):
    return f"""<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8">
<title>{titulo}</title>{PLOTLY_JS}
<style>{BASE_CSS}
/* Extras operativo */
.tiempos-titulo{{font-size:.75rem;text-transform:uppercase;letter-spacing:2px;
                 color:var(--gold);margin:22px 0 12px;padding-left:2px}}
.kpi-tiempos{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));
              gap:14px;margin-bottom:28px}}
.controles{{display:flex;gap:16px;margin-bottom:20px;flex-wrap:wrap;align-items:center}}
.controles label{{font-size:.81rem;color:var(--muted)}}
.controles select,.controles input{{background:var(--card);border:1px solid var(--border);
  color:var(--text);padding:6px 12px;border-radius:6px;font-size:.83rem;outline:none}}
.controles select:focus,.controles input:focus{{border-color:var(--gold)}}
</style></head><body>"""

def _foot(): return f"{FOOTER}</body></html>"


# ═══════════════════════════════════════════════════════════════════════════════
# APIS JSON
# ═══════════════════════════════════════════════════════════════════════════════
@router.get("/api/kpis")
def api_kpis(instancia: str = Query("todas"), fuente: str = Query("estadisticas_causas.json")):
    try:
        registros = _cargar_operativo(fuente)
        col_org = _col(registros, "juzgado", "organo", "tribunal", "camara")
        col_lat = _col(registros, "latencia", "dias", "tiempo_proceso", "duracion")
        col_est = _col(registros, "estado", "situac", "resolucion")

        todos = registros[:]
        n_cam = sum(1 for r in todos if col_org and _es_camara(str(r.get(col_org,""))))
        n_juz = len(todos) - n_cam

        if instancia != "todas" and col_org:
            if instancia == "camaras":
                registros = [r for r in registros if _es_camara(str(r.get(col_org,"")))]
            else:
                registros = [r for r in registros if not _es_camara(str(r.get(col_org,"")))]

        total = len(registros)
        lats  = _lats(registros, col_lat)
        lat_prom  = round(sum(lats)/len(lats), 1) if lats else 0
        criticos  = sum(1 for l in lats if l >= 365)
        kpi_op    = calcular_kpi_eficiencia(45_000_000_000, max(total, 1))

        resueltos = 0
        if col_est:
            palabras_ok = ("resuelto","sentencia","archivado","cerrado","concluido","finalizado")
            resueltos = sum(1 for r in registros
                            if any(p in str(r.get(col_est,"")).lower() for p in palabras_ok))
        tasa_res = round(resueltos / max(total, 1) * 100, 1)

        return {
            "total": total, "n_juzgados": n_juz, "n_camaras": n_cam,
            "latencia_promedio": lat_prom,
            "causas_criticas": criticos,
            "pct_criticas": round(criticos / max(total, 1) * 100, 1),
            "costo_por_causa": round(kpi_op, 0),
            "tasa_resolucion": tasa_res,
            "resueltos": resueltos,
        }
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/api/tiempos")
def api_tiempos(fuente: str = Query("estadisticas_causas.json")):
    try:
        registros = _cargar_operativo(fuente)
        col_org = _col(registros, "juzgado", "organo", "tribunal", "camara")
        col_lat = _col(registros, "latencia", "dias", "tiempo_proceso", "duracion")

        juzgados = [r for r in registros if col_org and not _es_camara(str(r.get(col_org,"")))]
        camaras  = [r for r in registros if col_org and _es_camara(str(r.get(col_org,"")))]

        lats_juz = _lats(juzgados, col_lat)
        lats_cam = _lats(camaras,  col_lat)
        lats_all = _lats(registros, col_lat)

        prom_juz = round(sum(lats_juz)/len(lats_juz), 1) if lats_juz else None
        prom_cam = round(sum(lats_cam)/len(lats_cam), 1) if lats_cam else None

        mora_2 = sum(1 for l in lats_all if l >= 730)
        pct_mora = round(mora_2 / max(len(lats_all), 1) * 100, 1)

        if lats_all:
            lats_sorted = sorted(lats_all)
            n = len(lats_sorted)
            p50 = lats_sorted[int(n*0.5)]
            p75 = lats_sorted[int(n*0.75)]
            p90 = lats_sorted[int(n*0.90)]
        else:
            p50 = p75 = p90 = 0

        return {
            "tiempo_prom_primera":  prom_juz,
            "tiempo_prom_camaras":  prom_cam,
            "mora_2anios":          mora_2,
            "pct_mora_2anios":      pct_mora,
            "p50_dias":             round(p50, 0),
            "p75_dias":             round(p75, 0),
            "p90_dias":             round(p90, 0),
            "tiene_latencia":       col_lat is not None,
        }
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/api/juzgados")
def api_juzgados(instancia: str = Query("todas"),
                 fuente: str = Query("estadisticas_causas.json"),
                 top: int = Query(20)):
    try:
        registros = _cargar_operativo(fuente)
        col_org = _col(registros, "juzgado", "organo", "tribunal", "camara")
        col_lat = _col(registros, "latencia", "dias", "tiempo_proceso", "duracion")

        if instancia != "todas" and col_org:
            if instancia == "camaras":
                registros = [r for r in registros if _es_camara(str(r.get(col_org,"")))]
            else:
                registros = [r for r in registros if not _es_camara(str(r.get(col_org,"")))]

        if not col_org:
            return {"juzgados": [], "col_detectada": None}

        conteo = Counter(); lat_sum = defaultdict(float); lat_cnt = defaultdict(int)
        for r in registros:
            org = str(r.get(col_org, "Sin dato"))
            conteo[org] += 1
            if col_lat:
                try:
                    v = float(r.get(col_lat, 0) or 0)
                    if v > 0: lat_sum[org] += v; lat_cnt[org] += 1
                except: pass

        result = []
        for org, cant in conteo.most_common(top):
            lp = round(lat_sum[org]/lat_cnt[org], 0) if lat_cnt[org] else 0
            result.append({"juzgado": org, "cantidad": cant,
                           "latencia_prom": lp, "es_camara": _es_camara(org)})
        return {"juzgados": result, "col_detectada": col_org, "total": len(registros)}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/api/estados")
def api_estados(fuente: str = Query("estadisticas_causas.json")):
    try:
        registros = _cargar(fuente)
        col = _col(registros, "estado", "situac", "activ", "resolucion")
        if not col: return {"labels": [], "values": []}
        conteo = Counter(str(r.get(col, "Sin dato")) for r in registros)
        top = conteo.most_common(12)
        return {"labels": [x[0] for x in top], "values": [x[1] for x in top]}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ═══════════════════════════════════════════════════════════════════════════════
# PESTAÑA: CÁMARAS FEDERALES
# ═══════════════════════════════════════════════════════════════════════════════
@router.get("/camaras", response_class=HTMLResponse)
def pagina_camaras():
    html = _head("Cámaras Federales — Monitor Judicial")
    html += nav_html("camaras")
    html += f"""<div class="contenido">
{DISCLAIMER}
<div class="scope">
  🏢 <strong>Cámaras Federales de Apelación</strong> —
  Instancia revisora de las sentencias de primera instancia.
  Datos filtrados automáticamente por nombre de órgano (contiene "cámara" / "camara" / "cam.").
</div>

<div class="seccion">⏱ Tiempos de Resolución — Cámaras</div>
<div class="kpi-tiempos" id="kpi-tiempos-cam"><div class="loading">Calculando…</div></div>

<div class="seccion">📊 Indicadores Operativos</div>
<div class="kpi-grid" id="kpi-cam"><div class="loading">Cargando…</div></div>

<div class="charts">
  <div class="chart-box">
    <h2>📊 Estado de Causas — Cámaras</h2>
    <div id="graf-estados-cam" style="height:340px"></div>
  </div>
  <div class="chart-box">
    <h2>🏆 Ranking Cámaras por Carga</h2>
    <div id="graf-ranking-cam" style="height:340px"></div>
  </div>
</div>
</div>
{FOOTER}
<script>
{PLOTLY_BASE}
async function cargar(){{
  const fuente='estadisticas_causas.json';
  const[kpis,tiempos,estados,ranking]=await Promise.all([
    fetch('/operativo/api/kpis?fuente='+fuente+'&instancia=camaras').then(r=>r.json()),
    fetch('/operativo/api/tiempos?fuente='+fuente).then(r=>r.json()),
    fetch('/operativo/api/estados?fuente='+fuente).then(r=>r.json()),
    fetch('/operativo/api/juzgados?fuente='+fuente+'&instancia=camaras&top=20').then(r=>r.json()),
  ]);

  const sinLat=!tiempos.tiene_latencia;
  const nd=sinLat?'<span class="sub">Sin col. latencia</span>':null;
  const pc=tiempos.tiempo_prom_camaras;
  const moraC=tiempos.pct_mora_2anios>10?'alerta':'ok';

  document.getElementById('kpi-tiempos-cam').innerHTML=`
    <div class="kpi-t">
      <label>🏛️ Tiempo prom. Cámaras</label>
      <div class="val">${{nd||pc+'<span class="uni">días</span>'}}</div>
      <div class="sub">${{pc&&pc>90?'🔴 Supera objetivo de 90 días':pc?'🟢 Dentro del objetivo':''}}</div>
    </div>
    <div class="kpi-t">
      <label>✅ Tasa de Resolución</label>
      <div class="val">${{fmt(kpis.tasa_resolucion)}}<span class="uni">%</span></div>
      <div class="sub">${{fmt(kpis.resueltos)}} causas resueltas</div>
    </div>
    <div class="kpi-t">
      <label>⏳ Mora Judicial (+2 años)</label>
      <div class="val ${{moraC}}">${{nd||fmt(tiempos.mora_2anios)}}</div>
      <div class="sub ${{moraC}}">${{nd||tiempos.pct_mora_2anios+'% del total'}}</div>
    </div>
    <div class="kpi-t">
      <label>📈 Percentiles P50/P75/P90</label>
      <div class="val" style="font-size:1.1rem">${{nd||fmt(tiempos.p50_dias)+'d'}}</div>
      <div class="sub">${{nd||'P75: '+fmt(tiempos.p75_dias)+'d · P90: '+fmt(tiempos.p90_dias)+'d'}}</div>
    </div>
  `;

  document.getElementById('kpi-cam').innerHTML=`
    <div class="kpi"><label>Total Causas Cámaras</label>
      <div class="val">${{fmt(kpis.total)}}</div></div>
    <div class="kpi ${{kpis.latencia_promedio>90?'rojo':'verde'}}">
      <label>Latencia Promedio</label>
      <div class="val">${{fmt(kpis.latencia_promedio)}}</div>
      <div class="sub">días · obj. &lt;90</div></div>
    <div class="kpi rojo"><label>Causas Críticas (&gt;1 año)</label>
      <div class="val">${{fmt(kpis.causas_criticas)}}</div>
      <div class="sub">${{kpis.pct_criticas}}%</div></div>
    <div class="kpi gold"><label>Costo Operativo x Causa</label>
      <div class="val" style="font-size:1.2rem">${{fmt(kpis.costo_por_causa)}}</div>
      <div class="sub">ARS estimado</div></div>
  `;

  if(estados.labels&&estados.labels.length)
    Plotly.newPlot('graf-estados-cam',[{{
      type:'bar',x:estados.labels,y:estados.values,
      marker:{{color:C.gold,opacity:.85}}
    }}],L({{xaxis:{{tickangle:-35,gridcolor:C.grid}}}}),{{responsive:true,displayModeBar:false}});
  else document.getElementById('graf-estados-cam').innerHTML=
    '<p style="color:#4a5568;padding:20px">Sin columna de estado detectada</p>';

  const data=ranking.juzgados||[];
  if(data.length)
    Plotly.newPlot('graf-ranking-cam',[{{
      type:'bar',orientation:'h',
      x:data.map(d=>d.cantidad),y:data.map(d=>d.juzgado),
      marker:{{color:C.gold,opacity:.85}},
      hovertemplate:'<b>%{{y}}</b><br>Causas: %{{x}}<extra></extra>',
    }}],L({{yaxis:{{autorange:'reversed',gridcolor:C.grid,tickfont:{{size:10}}}},
           margin:{{l:10,r:10,t:10,b:10}}}}),{{responsive:true,displayModeBar:false}});
  else document.getElementById('graf-ranking-cam').innerHTML=
    '<p style="color:#4a5568;padding:20px">Sin columna de órgano detectada</p>';
}}
cargar().catch(e=>{{
  document.getElementById('kpi-cam').innerHTML=
    '<div style="color:var(--red)">Error: '+e.message+'</div>';
}});
</script></body></html>"""
    return HTMLResponse(html)


# ═══════════════════════════════════════════════════════════════════════════════
# PESTAÑA: JUZGADOS DE PRIMERA INSTANCIA
# ═══════════════════════════════════════════════════════════════════════════════
@router.get("/", response_class=HTMLResponse)
def pagina_juzgados():
    html = _head("Juzgados — Monitor Judicial")
    html += nav_html("juzgados")
    html += f"""<div class="contenido">
{DISCLAIMER}
<div class="scope">
  📋 <strong>Juzgados de Primera Instancia</strong> —
  Mora judicial, tiempos de resolución y ranking por carga.
  Las Cámaras de Apelación tienen su
  <a href="/operativo/camaras">propia pestaña →</a>
</div>

<div class="controles">
  <div>
    <label>Fuente &nbsp;</label>
    <select id="sel-fuente" onchange="recargar()">
      <option value="estadisticas_causas.json">estadisticas_causas.json</option>
      <option value="pjn_checkpoint.json">pjn_checkpoint.json</option>
    </select>
  </div>
  <div>
    <label>Instancia &nbsp;</label>
    <select id="sel-instancia" onchange="recargar()">
      <option value="todas">Todas</option>
      <option value="juzgados">Juzgados (1ª Instancia)</option>
      <option value="camaras">Cámaras Federales</option>
    </select>
  </div>
  <div>
    <input type="text" id="busqueda" placeholder="🔎 Buscar juzgado / cámara…"
           oninput="filtrarRanking()" style="width:260px">
  </div>
</div>

<div class="inst-badges">
  <div class="badge blue" id="badge-juz">Juzgados: —</div>
  <div class="badge gold" id="badge-cam">Cámaras: —</div>
</div>

<div class="seccion">⏱ Tiempos de Resolución Judicial</div>
<div class="kpi-tiempos" id="kpi-tiempos"><div class="loading">Calculando tiempos…</div></div>

<div class="seccion">📊 Indicadores Operativos</div>
<div class="kpi-grid" id="kpi-grid"><div class="loading">Cargando…</div></div>

<div class="charts">
  <div class="chart-box">
    <h2>📊 Estado de las Causas</h2>
    <div id="graf-estados" style="height:340px"></div>
  </div>
  <div class="chart-box">
    <h2>🏆 Ranking por Carga <span>(azul=Juzgado · dorado=Cámara)</span></h2>
    <div id="graf-ranking" style="height:340px"></div>
  </div>
</div>
</div>
{FOOTER}
<script>
{PLOTLY_BASE}
let rankData=[];

function params(){{
  return `fuente=${{document.getElementById('sel-fuente').value}}&instancia=${{document.getElementById('sel-instancia').value}}`;
}}

async function recargar(){{
  const p=params();
  const fuente=document.getElementById('sel-fuente').value;

  const[kpis,tiempos,estados,ranking]=await Promise.all([
    fetch('/operativo/api/kpis?'+p).then(r=>r.json()),
    fetch('/operativo/api/tiempos?fuente='+fuente).then(r=>r.json()),
    fetch('/operativo/api/estados?fuente='+fuente).then(r=>r.json()),
    fetch('/operativo/api/juzgados?'+p+'&top=20').then(r=>r.json()),
  ]);

  document.getElementById('badge-juz').textContent=`Juzgados: ${{fmt(kpis.n_juzgados)}}`;
  document.getElementById('badge-cam').textContent=`Cámaras: ${{fmt(kpis.n_camaras)}}`;

  const sinDatos=!tiempos.tiene_latencia;
  const nd=sinDatos?'<span class="sub">Sin col. latencia</span>':null;
  const p1c=tiempos.tiempo_prom_primera;
  const p1cam=tiempos.tiempo_prom_camaras;
  const moraClass=tiempos.pct_mora_2anios>10?'alerta':'ok';

  document.getElementById('kpi-tiempos').innerHTML=`
    <div class="kpi-t">
      <label>⚖️ Tiempo prom. 1ª Instancia</label>
      <div class="val">${{nd||p1c+'<span class="uni">días</span>'}}</div>
      <div class="sub">${{p1c&&p1c>180?'🔴 Supera objetivo de 180 días':p1c?'🟢 Dentro del objetivo':''}}</div>
    </div>
    <div class="kpi-t">
      <label>🏛️ Tiempo prom. Cámaras</label>
      <div class="val">${{nd||p1cam+'<span class="uni">días</span>'}}</div>
      <div class="sub">${{p1cam&&p1cam>90?'🔴 Supera objetivo de 90 días':p1cam?'🟢 Dentro del objetivo':''}}</div>
    </div>
    <div class="kpi-t">
      <label>✅ Tasa de Resolución</label>
      <div class="val">${{fmt(kpis.tasa_resolucion)}}<span class="uni">%</span></div>
      <div class="sub">${{fmt(kpis.resueltos)}} causas resueltas</div>
    </div>
    <div class="kpi-t">
      <label>⏳ Mora Judicial (+2 años)</label>
      <div class="val ${{moraClass}}">${{nd||fmt(tiempos.mora_2anios)}}</div>
      <div class="sub ${{moraClass}}">${{nd||tiempos.pct_mora_2anios+'% del total'}}</div>
    </div>
    <div class="kpi-t">
      <label>📈 Percentiles de Latencia</label>
      <div class="val" style="font-size:1.1rem">${{nd||'P50: '+fmt(tiempos.p50_dias)+'d'}}</div>
      <div class="sub">${{nd||'P75: '+fmt(tiempos.p75_dias)+'d · P90: '+fmt(tiempos.p90_dias)+'d'}}</div>
    </div>
  `;

  document.getElementById('kpi-grid').innerHTML=`
    <div class="kpi"><label>Total Registros</label>
      <div class="val">${{fmt(kpis.total)}}</div></div>
    <div class="kpi ${{kpis.latencia_promedio>180?'rojo':'verde'}}">
      <label>Latencia Promedio</label>
      <div class="val">${{fmt(kpis.latencia_promedio)}}</div>
      <div class="sub">días · obj. &lt;180</div></div>
    <div class="kpi rojo"><label>Causas Críticas (&gt;1 año)</label>
      <div class="val">${{fmt(kpis.causas_criticas)}}</div>
      <div class="sub">${{kpis.pct_criticas}}%</div></div>
    <div class="kpi gold"><label>Costo Operativo x Causa</label>
      <div class="val" style="font-size:1.2rem">${{fmt(kpis.costo_por_causa)}}</div>
      <div class="sub">ARS estimado</div></div>
  `;

  if(estados.labels&&estados.labels.length)
    Plotly.newPlot('graf-estados',[{{
      type:'bar',x:estados.labels,y:estados.values,
      marker:{{color:C.gold,opacity:.85}},
    }}],L({{xaxis:{{tickangle:-35,gridcolor:C.grid}}}}),{{responsive:true,displayModeBar:false}});
  else document.getElementById('graf-estados').innerHTML=
    '<p style="color:#4a5568;padding:20px">Sin columna de estado detectada</p>';

  rankData=ranking.juzgados||[];
  renderRanking(rankData);
}}

function renderRanking(data){{
  if(!data.length){{
    document.getElementById('graf-ranking').innerHTML=
      '<p style="color:#4a5568;padding:20px">Sin columna de juzgado detectada</p>';
    return;
  }}
  Plotly.newPlot('graf-ranking',[{{
    type:'bar',orientation:'h',
    x:data.map(d=>d.cantidad),y:data.map(d=>d.juzgado),
    marker:{{color:data.map(d=>d.es_camara?C.gold:C.blue)}},
    hovertemplate:'<b>%{{y}}</b><br>Causas: %{{x}}<extra></extra>',
  }}],L({{yaxis:{{autorange:'reversed',gridcolor:C.grid,tickfont:{{size:10}}}},
         margin:{{l:10,r:10,t:10,b:10}}}}),{{responsive:true,displayModeBar:false}});
}}

function filtrarRanking(){{
  const q=document.getElementById('busqueda').value.toLowerCase();
  renderRanking(q?rankData.filter(d=>d.juzgado.toLowerCase().includes(q)):rankData);
}}

recargar();
</script></body></html>"""
    return HTMLResponse(html)
