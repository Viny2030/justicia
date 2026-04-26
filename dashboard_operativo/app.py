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
    Carga datos operativos y normaliza al formato interno:
      juzgado, latencia, resueltos, pendientes, recursos, tasa_resolucion,
      jurisdiccion, fuero, estado, anio

    Soporta tres formatos de fuente:
      1. juzgados_nacional.json  — pre-procesado por scraper_juzgados_nacional.py
      2. estadisticas_causas.json — formato organismo (reshape por fuero/tipo)
      3. otros JSON               — pasa tal cual
    """
    data = _cargar(nombre)
    if not data:
        return data

    # ── FIX: juzgados_nacional.json (tiene 'juzgado' + 'ira_score') ──────────
    if "juzgado" in data[0] and "ira_score" in data[0]:
        result = []
        for r in data:
            dt = r.get("disposition_time") or 0
            result.append({
                "juzgado":         r.get("juzgado", ""),
                "latencia":        dt,
                "resueltos":       r.get("dictadas_def") or 0,
                "pendientes":      r.get("pendientes_cierre") or 0,
                "recursos":        0,
                "tasa_resolucion": r.get("clearance_rate") or 0,
                "jurisdiccion":    r.get("jurisdiccion", ""),
                "fuero":           r.get("fuero", ""),
                "estado":          r.get("ira_semaforo", ""),
                "anio":            r.get("anio", ""),
            })
        return result

    # ── estadisticas_causas.json (tiene 'organismo') ──────────────────────────
    if "organismo" not in data[0]:
        return data

    grupos = defaultdict(list)
    for r in data:
        org = r.get("organismo", "").strip()
        if not org or "total" in org.lower() or org.startswith("(*"):
            continue
        grupos[org].append(r)

    result = []
    for org, recs in sorted(grupos.items()):
        es_cam = _es_camara(org)

        sent = [r for r in recs if r.get("tipo_csv") in ("sentencias", "tramite_camara")]
        latest_sent = sorted(sent, key=lambda r: str(r.get("anio", "")))[-1] if sent else {}

        tram = [r for r in recs if r.get("tipo_csv") == "tramite_camara"]
        latest_tram = sorted(tram, key=lambda r: str(r.get("anio", "")))[-1] if tram else {}

        rec_recs = [r for r in recs if r.get("tipo_csv") == "recursos"]
        total_recursos = sum(
            (r.get("recursos_apelacion") or 0) + (r.get("otros_recursos") or 0)
            for r in rec_recs
        )

        latencia   = latest_tram.get("permanencia_breve") or latest_tram.get("permanencia_extensa") or 0
        resueltos  = latest_tram.get("resueltos") or latest_sent.get("resueltos") or 0
        pendientes = latest_sent.get("pendientes_cierre") or latest_sent.get("en_tramite_cierre") or 0
        tasa       = latest_tram.get("tasa_resolucion_pct") or latest_sent.get("tasa_resolucion_pct") or 0

        result.append({
            "juzgado":         org,
            "latencia":        latencia,
            "resueltos":       resueltos,
            "pendientes":      pendientes,
            "recursos":        total_recursos,
            "tasa_resolucion": tasa,
            "jurisdiccion":    (latest_sent or latest_tram).get("jurisdiccion", ""),
            "anio":            (latest_sent or latest_tram).get("anio", ""),
            "estado":          "camara" if es_cam else "activo",
        })
    return result


# ── HTML helpers ──────────────────────────────────────────────────────────────
def _head(titulo):
    return f"""<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8">
<title>{titulo}</title>{PLOTLY_JS}
<style>{BASE_CSS}
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
def api_kpis(instancia: str = Query("todas"), fuente: str = Query("juzgados_nacional.json")):
    try:
        registros = _cargar_operativo(fuente)
        col_org = _col(registros, "juzgado", "organo", "tribunal", "camara")
        col_lat = _col(registros, "latencia", "dias", "tiempo_proceso", "duracion")
        col_est = _col(registros, "estado", "situac", "resolucion")

        todos = registros[:]
        n_cam = sum(1 for r in todos if col_org and _es_camara(str(r.get(col_org, ""))))
        n_juz = len(todos) - n_cam

        if instancia != "todas" and col_org:
            if instancia == "camaras":
                registros = [r for r in registros if _es_camara(str(r.get(col_org, "")))]
            else:
                registros = [r for r in registros if not _es_camara(str(r.get(col_org, "")))]

        total = len(registros)
        lats  = _lats(registros, col_lat)
        lat_prom  = round(sum(lats) / len(lats), 1) if lats else 0
        criticos  = sum(1 for l in lats if l >= 365)
        kpi_op    = calcular_kpi_eficiencia(45_000_000_000, max(total, 1))

        resueltos = 0
        if col_est:
            palabras_ok = ("resuelto", "sentencia", "archivado", "cerrado", "concluido", "finalizado", "🟢")
            resueltos = sum(
                1 for r in registros
                if any(p in str(r.get(col_est, "")).lower() for p in palabras_ok)
            )
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
def api_tiempos(fuente: str = Query("juzgados_nacional.json")):
    try:
        registros = _cargar_operativo(fuente)
        col_org = _col(registros, "juzgado", "organo", "tribunal", "camara")
        col_lat = _col(registros, "latencia", "dias", "tiempo_proceso", "duracion")

        juzgados = [r for r in registros if col_org and not _es_camara(str(r.get(col_org, "")))]
        camaras  = [r for r in registros if col_org and _es_camara(str(r.get(col_org, "")))]

        lats_juz = _lats(juzgados, col_lat)
        lats_cam = _lats(camaras, col_lat)
        lats_all = _lats(registros, col_lat)

        prom_juz = round(sum(lats_juz) / len(lats_juz), 1) if lats_juz else None
        prom_cam = round(sum(lats_cam) / len(lats_cam), 1) if lats_cam else None

        mora_2 = sum(1 for l in lats_all if l >= 730)
        pct_mora = round(mora_2 / max(len(lats_all), 1) * 100, 1)

        if lats_all:
            lats_sorted = sorted(lats_all)
            n = len(lats_sorted)
            p50 = lats_sorted[int(n * 0.5)]
            p75 = lats_sorted[int(n * 0.75)]
            p90 = lats_sorted[int(n * 0.90)]
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
            "tiene_latencia":       col_lat is not None and len(lats_all) > 0,
        }
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/api/juzgados")
def api_juzgados(
    instancia: str = Query("todas"),
    fuente: str = Query("juzgados_nacional.json"),
    top: int = Query(20),
):
    try:
        registros = _cargar_operativo(fuente)
        col_org = _col(registros, "juzgado", "organo", "tribunal", "camara")
        col_lat = _col(registros, "latencia", "dias", "tiempo_proceso", "duracion")

        if instancia != "todas" and col_org:
            if instancia == "camaras":
                registros = [r for r in registros if _es_camara(str(r.get(col_org, "")))]
            else:
                registros = [r for r in registros if not _es_camara(str(r.get(col_org, "")))]

        if not col_org:
            return {"juzgados": [], "col_detectada": None}

        conteo = Counter()
        lat_sum = defaultdict(float)
        lat_cnt = defaultdict(int)
        for r in registros:
            org = str(r.get(col_org, "Sin dato"))
            conteo[org] += 1
            if col_lat:
                try:
                    v = float(r.get(col_lat, 0) or 0)
                    if v > 0:
                        lat_sum[org] += v
                        lat_cnt[org] += 1
                except:
                    pass

        result = []
        for org, cant in conteo.most_common(top):
            lp = round(lat_sum[org] / lat_cnt[org], 0) if lat_cnt[org] else 0
            result.append({
                "juzgado": org,
                "cantidad": cant,
                "latencia_prom": lp,
                "es_camara": _es_camara(org),
            })
        return {"juzgados": result, "col_detectada": col_org, "total": len(registros)}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/api/estados")
def api_estados(fuente: str = Query("juzgados_nacional.json")):
    try:
        registros = _cargar(fuente)
        col = _col(registros, "estado", "situac", "activ", "resolucion", "fuero")
        if not col:
            return {"labels": [], "values": []}
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
  const fuente='juzgados_nacional.json';
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
    <div class="kpi"><label>Total Juzgados/Cámaras</label>
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
      <option value="juzgados_nacional.json" selected>juzgados_nacional.json ✓ (recomendado)</option>
      <option value="estadisticas_causas.json">estadisticas_causas.json (federales)</option>
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
    <h2>📊 Distribución por Fuero</h2>
    <div id="graf-estados" style="height:340px"></div>
  </div>
  <div class="chart-box">
    <h2>🏆 Ranking por Disposition Time <span>(top 20)</span></h2>
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
  const nd=sinDatos?'<span class="sub">Sin datos de latencia</span>':null;
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
    <div class="kpi"><label>Total Juzgados</label>
      <div class="val">${{fmt(kpis.total)}}</div></div>
    <div class="kpi ${{kpis.latencia_promedio>180?'rojo':'verde'}}">
      <label>Disposition Time prom.</label>
      <div class="val">${{fmt(kpis.latencia_promedio)}}</div>
      <div class="sub">días · obj. &lt;180</div></div>
    <div class="kpi rojo"><label>Causas en mora (+1 año)</label>
      <div class="val">${{fmt(kpis.causas_criticas)}}</div>
      <div class="sub">${{kpis.pct_criticas}}%</div></div>
    <div class="kpi gold"><label>Costo Operativo x Causa</label>
      <div class="val" style="font-size:1.2rem">${{fmt(kpis.costo_por_causa)}}</div>
      <div class="sub">ARS estimado</div></div>
  `;

  // Gráfico de fueros (donut si hay fuero, barras si no)
  if(estados.labels&&estados.labels.length){{
    const hasFuero = estados.labels.some(l=>['Civil','Comercial','Laboral','Penal','Federal','Familia'].includes(l));
    if(hasFuero){{
      Plotly.newPlot('graf-estados',[{{
        type:'pie',labels:estados.labels,values:estados.values,
        hole:.4,
        marker:{{colors:['#3b82f6','#c9a227','#22c55e','#e63946','#8b5cf6','#f59e0b']}},
        textinfo:'label+percent',
        hovertemplate:'<b>%{{label}}</b><br>%{{value}} juzgados<extra></extra>'
      }}],L({{showlegend:true,legend:{{orientation:'h'}},margin:{{t:10,b:10}}}}),{{responsive:true,displayModeBar:false}});
    }} else {{
      Plotly.newPlot('graf-estados',[{{
        type:'bar',x:estados.labels,y:estados.values,
        marker:{{color:C.gold,opacity:.85}},
      }}],L({{xaxis:{{tickangle:-35,gridcolor:C.grid}}}}),{{responsive:true,displayModeBar:false}});
    }}
  }} else document.getElementById('graf-estados').innerHTML=
    '<p style="color:#4a5568;padding:20px">Sin datos de fuero</p>';

  rankData=ranking.juzgados||[];
  renderRanking(rankData);
}}

function renderRanking(data){{
  if(!data.length){{
    document.getElementById('graf-ranking').innerHTML=
      '<p style="color:#4a5568;padding:20px">Sin datos</p>';
    return;
  }}
  Plotly.newPlot('graf-ranking',[{{
    type:'bar',orientation:'h',
    x:data.map(d=>d.latencia_prom||d.cantidad),
    y:data.map(d=>d.juzgado),
    marker:{{color:data.map(d=>d.es_camara?C.gold:C.blue)}},
    hovertemplate:'<b>%{{y}}</b><br>Días: %{{x}}<extra></extra>',
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


# ═══════════════════════════════════════════════════════════════════════════════
# DASHBOARD NACIONAL — todos los juzgados PJN con métricas CEPEJ/WJP/IRA
# ═══════════════════════════════════════════════════════════════════════════════

def _cargar_nacional() -> list:
    """Lee juzgados_nacional.json generado por scraper_juzgados_nacional.py."""
    path = os.path.join(ROOT, "juzgados_nacional.json")
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    return data.get("juzgados", data.get("data", []))


@router.get("/api/nacional", response_class=JSONResponse)
def api_nacional(fuero: str = Query(""), semaforo: str = Query("")):
    """JSON: todos los juzgados PJN con métricas completas."""
    try:
        rows = _cargar_nacional()
        if fuero:
            rows = [r for r in rows if fuero.lower() in (r.get("fuero", "") or "").lower()]
        if semaforo:
            rows = [r for r in rows if (r.get("ira_semaforo", "") or "") == semaforo]

        total = len(rows)
        cr_vals  = [r["clearance_rate"] for r in rows if r.get("clearance_rate") is not None]
        dt_vals  = [r["disposition_time"] for r in rows if r.get("disposition_time") and r["disposition_time"] > 0]
        mora_sum = sum(r.get("mora_2anios") or 0 for r in rows)
        pend_sum = sum(r.get("pendientes_cierre") or 0 for r in rows)
        sent_sum = sum(r.get("dictadas_def") or 0 for r in rows)
        costo_sum= sum(r.get("costo_anual_estimado") or 0 for r in rows)

        cr_prom  = round(sum(cr_vals) / len(cr_vals), 1) if cr_vals else 0
        dt_prom  = round(sum(dt_vals) / len(dt_vals), 0) if dt_vals else 0

        semaf_cnt = Counter(r.get("ira_semaforo", "⬜") for r in rows)
        fueros    = sorted(set(r.get("fuero", "") or "" for r in rows if r.get("fuero")))

        top_mora = sorted(
            [r for r in rows if r.get("pct_mora") is not None],
            key=lambda r: r["pct_mora"], reverse=True
        )[:20]

        top_pend = sorted(
            [r for r in rows if r.get("pendientes_cierre") is not None],
            key=lambda r: r["pendientes_cierre"], reverse=True
        )[:20]

        return JSONResponse({
            "total": total,
            "kpis": {
                "clearance_rate_prom": cr_prom,
                "disposition_time_prom": int(dt_prom),
                "pendientes_total": pend_sum,
                "sentencias_total": sent_sum,
                "mora_total": mora_sum,
                "costo_total": costo_sum,
                "semaforo": dict(semaf_cnt),
            },
            "fueros": fueros,
            "top_mora": [
                {"juzgado": r.get("juzgado",""), "fuero": r.get("fuero",""),
                 "pct_mora": r.get("pct_mora", 0), "mora_2anios": r.get("mora_2anios", 0)}
                for r in top_mora
            ],
            "top_pendientes": [
                {"juzgado": r.get("juzgado",""), "fuero": r.get("fuero",""),
                 "pendientes": r.get("pendientes_cierre", 0), "cr": r.get("clearance_rate", 0)}
                for r in top_pend
            ],
            "tabla": rows,
        })
    except Exception as e:
        return JSONResponse({"error": str(e), "total": 0}, status_code=500)


@router.get("/nacional", response_class=HTMLResponse)
def pagina_nacional():
    """Dashboard completo por juzgado — todos los nacionales PJN."""

    html_body = r"""
<div class="scope">
  🗺️ <strong>Juzgados Nacionales (PJN)</strong> —
  Estadísticas completas por órgano: mora, clearance rate, disposition time, costo,
  comparación WJP / CEPEJ / CEJAS e Índice de Riesgo Algorítmico.
  Datos: <em>scraper_juzgados_nacional.py</em> sobre estadisticas.pjn.gov.ar
</div>

<!-- KPIs ─────────────────────────────────────── -->
<div class="kpi-grid" id="nac-kpis">
  <div class="kpi"><label>Juzgados relevados</label><div class="val" id="nac-total">—</div></div>
  <div class="kpi" id="kpi-cr">
    <label>Clearance Rate promedio</label>
    <div class="val" id="nac-cr">—</div>
    <div class="sub">CEPEJ objetivo ≥100%</div>
  </div>
  <div class="kpi" id="kpi-dt">
    <label>Disposition Time promedio</label>
    <div class="val" id="nac-dt">—</div><div class="sub">días · CEPEJ obj. ≤230</div>
  </div>
  <div class="kpi rojo">
    <label>Causas en mora (&gt;2 años)</label>
    <div class="val" id="nac-mora">—</div>
  </div>
  <div class="kpi gold">
    <label>Costo operativo total</label>
    <div class="val" id="nac-costo" style="font-size:1.1rem">—</div>
    <div class="sub">ARS/año estimado</div>
  </div>
</div>

<!-- Semáforos IRA -->
<div style="display:flex;gap:12px;margin:12px 0;flex-wrap:wrap" id="nac-semaf"></div>

<!-- Filtros ──────────────────────────────────── -->
<div class="controles">
  <label>Fuero:
    <select id="fil-fuero" onchange="cargarNacional()">
      <option value="">Todos</option>
    </select>
  </label>
  <label>IRA:
    <select id="fil-semaf" onchange="cargarNacional()">
      <option value="">Todos</option>
      <option value="🟢">🟢 Bajo riesgo</option>
      <option value="🟡">🟡 Riesgo medio</option>
      <option value="🔴">🔴 Alto riesgo</option>
    </select>
  </label>
  <label>Buscar: <input id="fil-buscar" type="text" placeholder="juzgado, magistrado…"
         oninput="filtrarTabla()" style="width:240px"></label>
  <label>Ordenar:
    <select id="fil-orden" onchange="filtrarTabla()">
      <option value="ira_score">IRA ↑</option>
      <option value="pct_mora">% mora ↑</option>
      <option value="pendientes_cierre">Pendientes ↑</option>
      <option value="disposition_time">Disp. time ↑</option>
      <option value="clearance_rate_asc">Clearance rate ↑</option>
    </select>
  </label>
</div>

<!-- Gráficos ─────────────────────────────────── -->
<div class="charts">
  <div class="chart-box">
    <h2>🔴 Top 20 — % Mora (&gt;2 años)</h2>
    <div id="graf-mora" style="height:360px"></div>
  </div>
  <div class="chart-box">
    <h2>📦 Top 20 — Causas pendientes</h2>
    <div id="graf-pend" style="height:360px"></div>
  </div>
</div>

<div class="chart-full" style="margin-top:16px">
  <h2 style="color:var(--muted);margin:0 0 8px">📊 Distribución Clearance Rate</h2>
  <div id="graf-cr" style="height:300px"></div>
</div>

<!-- Tabla ────────────────────────────────────── -->
<div class="seccion">📋 Detalle por Juzgado</div>
<div style="overflow-x:auto;margin-top:8px">
<table id="nac-tabla" style="width:100%;border-collapse:collapse;font-size:.78rem;min-width:1200px">
  <thead>
  <tr style="background:var(--card2);color:var(--muted);text-align:left;white-space:nowrap">
    <th style="padding:8px 10px">IRA</th>
    <th style="padding:8px 10px">Juzgado</th>
    <th style="padding:8px 10px">Fuero</th>
    <th style="padding:8px 10px">Magistrado</th>
    <th style="padding:8px 10px;text-align:right">Pendientes</th>
    <th style="padding:8px 10px;text-align:right">Sent./año</th>
    <th style="padding:8px 10px;text-align:right">Disp.Time</th>
    <th style="padding:8px 10px;text-align:right">Clear.Rate</th>
    <th style="padding:8px 10px;text-align:right">% Mora</th>
    <th style="padding:8px 10px;text-align:right">Costo/causa</th>
    <th style="padding:8px 10px;text-align:right">vs WJP</th>
    <th style="padding:8px 10px;text-align:right">vs CEPEJ CR</th>
    <th style="padding:8px 10px;text-align:right">vs CEPEJ DT</th>
    <th style="padding:8px 10px">Estado</th>
  </tr>
  </thead>
  <tbody id="nac-tbody"></tbody>
</table>
</div>
"""

    script = r"""
const cfg = {responsive:true, displayModeBar:false};
let _tablaData = [];

async function cargarNacional() {
  const fuero   = document.getElementById('fil-fuero').value;
  const semaforo= document.getElementById('fil-semaf').value;
  const url = `/operativo/api/nacional?fuero=${encodeURIComponent(fuero)}&semaforo=${encodeURIComponent(semaforo)}`;
  let d;
  try { d = await fetch(url).then(r=>r.json()); }
  catch(e) { console.error(e); return; }

  if(d.error) {
    document.getElementById('nac-total').textContent = 'Sin datos';
    document.getElementById('nac-tbody').innerHTML =
      '<tr><td colspan="14" style="padding:20px;color:#94a3b8;text-align:center">' +
      '⚠️ Archivo juzgados_nacional.json no encontrado.<br>' +
      'Corré <code>python scraper_juzgados_nacional.py --skip-crawl</code> para generarlo.</td></tr>';
    return;
  }

  // KPIs
  document.getElementById('nac-total').textContent = (d.total||0).toLocaleString('es-AR');
  const cr = d.kpis.clearance_rate_prom;
  document.getElementById('nac-cr').textContent = cr + '%';
  document.getElementById('kpi-cr').className = 'kpi ' + (cr>=100?'verde':'rojo');
  const dt = d.kpis.disposition_time_prom;
  document.getElementById('nac-dt').textContent = dt > 0 ? fmt(dt) + ' d' : '—';
  document.getElementById('kpi-dt').className = 'kpi ' + (dt>0 && dt<=230?'verde':dt>230?'rojo':'');
  document.getElementById('nac-mora').textContent = fmt(d.kpis.mora_total);
  document.getElementById('nac-costo').textContent = '$' + fmt(Math.round(d.kpis.costo_total/1e6)) + 'M';

  // Semáforos
  const sf = d.kpis.semaforo||{};
  document.getElementById('nac-semaf').innerHTML = ['🟢','🟡','🔴'].map(s=>`
    <div style="background:#1a2744;border-radius:8px;padding:10px 18px;text-align:center">
      <div style="font-size:1.6rem">${s}</div>
      <div style="font-size:1.4rem;font-weight:700;color:#e2e8f0">${sf[s]||0}</div>
      <div style="font-size:.75rem;color:#64748b">${s==='🟢'?'Bajo riesgo':s==='🟡'?'Riesgo medio':'Alto riesgo'}</div>
    </div>`).join('');

  // Fueros selector
  const sel = document.getElementById('fil-fuero');
  const cur = sel.value;
  const opts = ['<option value="">Todos</option>',
    ...(d.fueros||[]).map(f=>`<option${f===cur?' selected':''}>${f}</option>`)
  ];
  sel.innerHTML = opts.join('');

  // Gráfico mora
  if(d.top_mora && d.top_mora.length) {
    const tm = d.top_mora;
    Plotly.newPlot('graf-mora',[{
      type:'bar', orientation:'h',
      x: tm.map(r=>r.pct_mora), y: tm.map(r=>r.juzgado),
      text: tm.map(r=>r.pct_mora+'%'), textposition:'outside',
      marker:{color:'#e63946',opacity:.85},
      hovertemplate:'<b>%{y}</b><br>Mora: %{x}%<extra></extra>'
    }],{
      plot_bgcolor:'#1a2744', paper_bgcolor:'#1a2744',
      font:{color:'#e2e8f0',size:10},
      margin:{l:10,r:60,t:10,b:30},
      xaxis:{gridcolor:'#2d4a7a'},
      yaxis:{autorange:'reversed',automargin:true,gridcolor:'#2d4a7a'}
    },cfg);
  }

  // Gráfico pendientes
  if(d.top_pendientes && d.top_pendientes.length) {
    const tp = d.top_pendientes;
    Plotly.newPlot('graf-pend',[{
      type:'bar', orientation:'h',
      x: tp.map(r=>r.pendientes), y: tp.map(r=>r.juzgado),
      text: tp.map(r=>fmt(r.pendientes)), textposition:'outside',
      marker:{color:'#3b82f6',opacity:.85},
      hovertemplate:'<b>%{y}</b><br>Pendientes: %{x}<extra></extra>'
    }],{
      plot_bgcolor:'#1a2744', paper_bgcolor:'#1a2744',
      font:{color:'#e2e8f0',size:10},
      margin:{l:10,r:60,t:10,b:30},
      xaxis:{gridcolor:'#2d4a7a'},
      yaxis:{autorange:'reversed',automargin:true,gridcolor:'#2d4a7a'}
    },cfg);
  }

  // Histograma clearance rate
  const crVals = (d.tabla||[]).map(r=>r.clearance_rate).filter(v=>v!=null && v>0);
  if(crVals.length) {
    Plotly.newPlot('graf-cr',[{
      type:'histogram', x:crVals, nbinsx:30,
      marker:{color:'#22c55e',opacity:.7},
      hovertemplate:'CR %{x}%: %{y} juzgados<extra></extra>'
    },{
      type:'scatter', mode:'lines',
      x:[100,100], y:[0, Math.ceil(crVals.length/3)],
      line:{color:'#c9a227',dash:'dot',width:2},
      name:'CEPEJ obj. (100%)'
    }],{
      plot_bgcolor:'#1a2744', paper_bgcolor:'#1a2744',
      font:{color:'#e2e8f0',size:11},
      margin:{l:50,r:20,t:10,b:40},
      xaxis:{title:'Clearance Rate (%)',gridcolor:'#2d4a7a'},
      yaxis:{title:'Juzgados',gridcolor:'#2d4a7a'},
      showlegend:true
    },cfg);
  }

  _tablaData = d.tabla || [];
  filtrarTabla();
}

function filtrarTabla() {
  const q = (document.getElementById('fil-buscar').value||'').toLowerCase();
  const orden = document.getElementById('fil-orden').value;
  let rows = q
    ? _tablaData.filter(r=>(r.juzgado||'').toLowerCase().includes(q)||(r.magistrado||'').toLowerCase().includes(q)||(r.fuero||'').toLowerCase().includes(q))
    : [..._tablaData];

  rows.sort((a,b)=>{
    if(orden==='clearance_rate_asc') return (a.clearance_rate||0)-(b.clearance_rate||0);
    const k = orden==='ira_score'?'ira_score':orden==='pct_mora'?'pct_mora':orden==='pendientes_cierre'?'pendientes_cierre':'disposition_time';
    return (b[k]||0)-(a[k]||0);
  });

  const tbody = document.getElementById('nac-tbody');
  if(!rows.length) {
    tbody.innerHTML = '<tr><td colspan="14" style="padding:20px;color:#94a3b8;text-align:center">Sin resultados</td></tr>';
    return;
  }

  const color_cr  = v => !v||v===0?'#64748b':v>=100?'#22c55e':v>=80?'#f59e0b':'#e63946';
  const color_dt  = v => !v||v===0?'#64748b':v<=180?'#22c55e':v<=230?'#f59e0b':'#e63946';
  const color_mora= v => v==null?'#64748b':v<5?'#22c55e':v<15?'#f59e0b':'#e63946';
  const fmt_dt    = v => (!v||v===0)?'—':fmt(v)+' d';
  const fmt_cr    = v => (!v||v===0)?'—':v+'%';
  const fmt_cepej = v => (!v||v==='—'||v===0)?'<span style="color:#64748b">—</span>'
                        :v==='OK'?'<span style="color:#22c55e">✓ OK</span>'
                        :'<span style="color:#e63946">✗ '+v+'</span>';

  tbody.innerHTML = rows.map(r=>`
    <tr style="border-bottom:1px solid #1e3058">
      <td style="padding:6px 10px;font-size:1.1rem;text-align:center">${r.ira_semaforo||'⬜'} <span style="font-size:.72rem;color:#64748b">${r.ira_score||0}</span></td>
      <td style="padding:6px 10px;color:#e2e8f0;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"
          title="${r.juzgado||''}">${r.juzgado||'—'}</td>
      <td style="padding:6px 10px;color:#64748b;font-size:.75rem">${r.fuero||'—'}</td>
      <td style="padding:6px 10px;color:#93c5fd;font-size:.78rem">${r.magistrado||'<span style="color:#475569">Sin designación</span>'}${r.antiguedad_anos?'<br><span style="color:#64748b;font-size:.72rem">'+r.antiguedad_anos+' años</span>':''}</td>
      <td style="padding:6px 10px;text-align:right;color:#e2e8f0">${fmt(r.pendientes_cierre)}</td>
      <td style="padding:6px 10px;text-align:right;color:#e2e8f0">${fmt(r.dictadas_def)}</td>
      <td style="padding:6px 10px;text-align:right;color:${color_dt(r.disposition_time)}">${fmt_dt(r.disposition_time)}</td>
      <td style="padding:6px 10px;text-align:right;color:${color_cr(r.clearance_rate)};font-weight:600">${fmt_cr(r.clearance_rate)}</td>
      <td style="padding:6px 10px;text-align:right;color:${color_mora(r.pct_mora)}">${r.pct_mora!=null?r.pct_mora+'%':'—'}</td>
      <td style="padding:6px 10px;text-align:right;color:#94a3b8">${r.costo_por_causa?'$'+fmt(r.costo_por_causa):'—'}</td>
      <td style="padding:6px 10px;text-align:right;font-size:.75rem">${r.vs_wjp_civil!=null&&r.vs_wjp_civil!==0?r.vs_wjp_civil:'<span style="color:#64748b">—</span>'}</td>
      <td style="padding:6px 10px;text-align:right;font-size:.75rem">${fmt_cepej(r.vs_cepej_cr)}</td>
      <td style="padding:6px 10px;text-align:right;font-size:.75rem">${fmt_cepej(r.vs_cepej_dt)}</td>
      <td style="padding:6px 10px;text-align:center">${r.vacante?'<span style="color:#e63946">Vacante</span>':r.en_licencia?'<span style="color:#f59e0b">Licencia</span>':'<span style="color:#22c55e">Activo</span>'}</td>
    </tr>`).join('');
}

cargarNacional();
"""

    parts = [
        _head("Juzgados Nacionales — Monitor Judicial"),
        nav_html("nacional"),
        "<div class='contenido'>",
        DISCLAIMER,
        html_body,
        "</div>",
        FOOTER,
        PLOTLY_JS,
        "<script>", PLOTLY_BASE, script, "</script></body></html>",
    ]
    return HTMLResponse("".join(parts))