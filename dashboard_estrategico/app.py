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
/* Panel detalle */
.panel-overlay{{display:none;position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:999;backdrop-filter:blur(2px)}}
.panel-overlay.visible{{display:block}}
.panel-detalle{{position:fixed;top:0;right:-460px;width:440px;height:100vh;
  background:#0d1b2e;border-left:1px solid #2d4a7a;overflow-y:auto;
  transition:right .28s cubic-bezier(.4,0,.2,1);z-index:1000;padding:24px 20px}}
.panel-detalle.abierto{{right:0}}
.pd-row{{display:flex;justify-content:space-between;align-items:flex-start;
  padding:7px 0;border-bottom:1px solid #1a2e50;font-size:.82rem;gap:8px}}
.pd-label{{color:#64748b;flex-shrink:0}}
.pd-val{{color:#e2e8f0;font-weight:500;text-align:right;word-break:break-word}}
.pd-sec{{font-size:.7rem;text-transform:uppercase;letter-spacing:1.8px;
  color:#c9a227;margin:18px 0 6px;padding-bottom:4px;border-bottom:1px solid #1e3058}}
.nac-tr-click{{cursor:pointer;transition:background .15s}}
.nac-tr-click:hover{{background:rgba(45,74,122,.35)!important}}
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
        # criticos: juzgados cuyo disposition_time promedio supera 365 dias
        criticos  = sum(1 for l in lats if l >= 365)

        # Costo estimado por juzgado (presupuesto PJN / total juzgados)
        kpi_costo_juzgado = calcular_kpi_eficiencia(45_000_000_000, max(total, 1))

        # Costo real por causa: mediana de juzgados con datos reales (excluye cap $500M)
        CAP_DEFAULT = 500_000_000
        costos_reales = []
        try:
            raw = _cargar(fuente)
            if raw and isinstance(raw, list) and raw and "costo_por_causa" in raw[0]:
                costos_reales = [
                    float(r["costo_por_causa"])
                    for r in raw
                    if r.get("costo_por_causa") and 0 < float(r["costo_por_causa"]) < CAP_DEFAULT
                ]
        except Exception:
            costos_reales = []
        if costos_reales:
            costos_reales.sort()
            mediana_costo = costos_reales[len(costos_reales) // 2]
            promedio_costo = round(sum(costos_reales) / len(costos_reales), 0)
        else:
            mediana_costo = None
            promedio_costo = None

        resueltos = 0
        if col_est:
            palabras_ok = ("resuelto", "sentencia", "archivado", "cerrado", "concluido", "finalizado", "\U0001f7e2")
            resueltos = sum(
                1 for r in registros
                if any(p in str(r.get(col_est, "")).lower() for p in palabras_ok)
            )
        tasa_res = round(resueltos / max(total, 1) * 100, 1)

        return {
            "total": total, "n_juzgados": n_juz, "n_camaras": n_cam,
            "latencia_promedio": lat_prom,
            # juzgados con DT >= 365 dias (no causas individuales)
            "causas_criticas": criticos,
            "pct_criticas": round(criticos / max(total, 1) * 100, 1),
            # costo_por_causa legacy (presupuesto / N juzgados - NO es por causa)
            "costo_por_causa": round(kpi_costo_juzgado, 0),
            # costos reales calculados desde datos oralidad
            "costo_mediana_causa": round(mediana_costo, 0) if mediana_costo else None,
            "costo_promedio_causa": round(promedio_costo, 0) if promedio_costo else None,
            "n_juzgados_con_costo_real": len(costos_reales),
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


<<<<<<< Updated upstream
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
if(document.getElementById('graf-cepej-cr')){
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
}

// Disposition Time comparativa
if(document.getElementById('graf-cepej-dt')){
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
}

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

    # ── new_api_js vacío — ya integrado en chart_script
    new_api_js = ""

    # ── HTML body ──────────────────────────────────────────────────────
    html_body = """

=======
# ═══════════════════════════════════════════════════════════════════════════════
# PESTAÑA: CÁMARAS FEDERALES
# ═══════════════════════════════════════════════════════════════════════════════
@router.get("/camaras", response_class=HTMLResponse)
def pagina_camaras():
    html = _head("Cámaras Federales — Monitor Judicial")
    html += nav_html("camaras")
    html += f"""<div class="contenido">
{DISCLAIMER}
>>>>>>> Stashed changes
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
    <div class="kpi rojo"><label>Órganos con DT &gt;1 año</label>
      <div class="val">${{fmt(kpis.causas_criticas)}}</div>
      <div class="sub">${{kpis.pct_criticas}}% de órganos relevados</div></div>
    <div class="kpi gold"><label>Costo estimado x juzgado</label>
      <div class="val" style="font-size:1.2rem">${{fmt(kpis.costo_por_causa)}}</div>
      <div class="sub">ARS · presupuesto PJN / N órganos</div></div>
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
    <div class="kpi rojo"><label>Juzgados con mora (&gt;1 año DT)</label>
      <div class="val">${{fmt(kpis.causas_criticas)}}</div>
      <div class="sub">${{kpis.pct_criticas}}% de juzgados relevados</div></div>
    <div class="kpi gold"><label>Costo estimado x juzgado</label>
      <div class="val" style="font-size:1.2rem">${{fmt(kpis.costo_por_causa)}}</div>
      <div class="sub">ARS · presupuesto PJN / N juzgados${{kpis.costo_mediana_causa ? ' · mediana/causa: $'+fmt(kpis.costo_mediana_causa) : ''}}</div></div>
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
        cr_vals  = [r["clearance_rate"] for r in rows if r.get("clearance_rate")]  # excluye 0 = sin datos
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
      <option value="alfabetico" selected>A → Z</option>
      <option value="ira_score">IRA ↑</option>
      <option value="pct_mora">% mora ↑</option>
      <option value="pendientes_cierre">Pendientes ↑</option>
      <option value="disposition_time">Disp. time ↑</option>
      <option value="clearance_rate_asc">Clearance rate ↑</option>
    </select>
  </label>
  <button onclick="exportarCSV()" title="Descargar tabla filtrada"
    style="background:#1a3a6e;border:1px solid #2d4a7a;color:#e2e8f0;padding:6px 14px;
           border-radius:6px;font-size:.83rem;cursor:pointer;white-space:nowrap">
    ⬇ Exportar CSV
  </button>
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
  <div class="chart-box">
    <h2>🎯 Distribución IRA</h2>
    <div id="graf-ira-donut" style="height:360px"></div>
  </div>
</div>

<div class="chart-full" style="margin-top:16px">
  <h2 style="color:var(--muted);margin:0 0 8px">📊 Distribución Clearance Rate</h2>
  <div id="graf-cr" style="height:300px"></div>
</div>

<div class="chart-full" style="margin-top:16px">
  <h2 style="color:var(--muted);margin:0 0 8px">
    🔵 Scatter — Clearance Rate vs Disposition Time
    <span style="font-size:.75rem;font-weight:400;margin-left:8px">
      Cuadrante ideal: CR≥100% · DT≤230 días (líneas punteadas = benchmarks CEPEJ)
    </span>
  </h2>
  <div id="graf-scatter" style="height:440px"></div>
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

<!-- Overlay + panel detalle -->
<div class="panel-overlay" id="panel-overlay" onclick="cerrarPanel()"></div>
<div class="panel-detalle" id="panel-detalle">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px">
    <span style="color:#64748b;font-size:.78rem;letter-spacing:1px;text-transform:uppercase">Detalle del juzgado</span>
    <button onclick="cerrarPanel()"
      style="background:none;border:1px solid #2d4a7a;color:#94a3b8;font-size:1rem;
             cursor:pointer;padding:3px 10px;border-radius:5px;line-height:1.4">✕</button>
  </div>
  <div id="panel-content"></div>
</div>

<!-- Paginación -->
<div id="nac-paginacion"
     style="display:flex;gap:10px;align-items:center;justify-content:center;
            margin:16px 0;flex-wrap:wrap"></div>
"""

    script = r"""
const cfg = {responsive:true, displayModeBar:false};
let _tablaData = [];
let _currentPage = 1;
const _rowsPerPage = 50;

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

  // ── Donut IRA ───────────────────────────────────────────────────────────────
  const sfData = [
    {label:'🟢 Bajo riesgo',  val: sf['🟢']||0, color:'#22c55e'},
    {label:'🟡 Riesgo medio', val: sf['🟡']||0, color:'#f59e0b'},
    {label:'🔴 Alto riesgo',  val: sf['🔴']||0, color:'#e63946'},
  ];
  Plotly.newPlot('graf-ira-donut',[{
    type:'pie',
    labels: sfData.map(s=>s.label),
    values: sfData.map(s=>s.val),
    hole: 0.52,
    marker:{colors: sfData.map(s=>s.color), line:{color:'#0d1b2e',width:2}},
    textinfo:'label+value',
    textfont:{size:11},
    hovertemplate:'<b>%{label}</b><br>%{value} juzgados · %{percent}<extra></extra>'
  }],{
    plot_bgcolor:'#1a2744', paper_bgcolor:'#1a2744',
    font:{color:'#e2e8f0', size:11},
    showlegend:false,
    margin:{l:10,r:10,t:20,b:20},
    annotations:[{
      text:`<b>${(d.total||0).toLocaleString('es-AR')}</b><br>juzgados`,
      x:0.5, y:0.5, showarrow:false,
      font:{size:14, color:'#e2e8f0'}
    }]
  }, cfg);

  // ── Scatter CR vs DT ────────────────────────────────────────────────────────
  const scPts = (d.tabla||[]).filter(r=>r.clearance_rate>0 && r.disposition_time>0);
  const scColors = {'🟢':'#22c55e','🟡':'#f59e0b','🔴':'#e63946'};
  const scLabels = {'🟢':'Bajo riesgo','🟡':'Riesgo medio','🔴':'Alto riesgo'};
  const scTraces = ['🟢','🟡','🔴'].map(sem => {
    const pts = scPts.filter(r=>r.ira_semaforo===sem);
    return {
      type:'scatter', mode:'markers',
      name: sem+' '+scLabels[sem]+' ('+pts.length+')',
      x: pts.map(r=>r.clearance_rate),
      y: pts.map(r=>r.disposition_time),
      text: pts.map(r=>r.juzgado),
      customdata: pts.map(r=>[
        r.magistrado||'Sin designación',
        r.fuero||'—',
        r.pct_mora!=null?r.pct_mora+'%':'—',
        r.ira_score||0
      ]),
      hovertemplate:
        '<b>%{text}</b><br>' +
        'CR: <b>%{x}%</b> · DT: <b>%{y} días</b><br>' +
        'Magistrado: %{customdata[0]}<br>' +
        'Fuero: %{customdata[1]} · Mora: %{customdata[2]}<br>' +
        'IRA Score: %{customdata[3]}<extra></extra>',
      marker:{color:scColors[sem], size:8, opacity:0.78,
              line:{color:'#0d1b2e', width:0.5}}
    };
  });

  if(scPts.length) {
    const maxDT = Math.min(Math.max(...scPts.map(r=>r.disposition_time), 500), 3000);
    const maxCR = Math.max(...scPts.map(r=>r.clearance_rate), 120);
    scTraces.push({
      type:'scatter', mode:'lines', name:'CEPEJ CR = 100%',
      x:[100,100], y:[0, maxDT+100],
      line:{color:'#c9a227', dash:'dot', width:1.5}, showlegend:true
    });
    scTraces.push({
      type:'scatter', mode:'lines', name:'CEPEJ DT = 230d',
      x:[0, maxCR+10], y:[230,230],
      line:{color:'#94a3b8', dash:'dot', width:1.5}, showlegend:true
    });
    Plotly.newPlot('graf-scatter', scTraces, {
      plot_bgcolor:'#1a2744', paper_bgcolor:'#1a2744',
      font:{color:'#e2e8f0', size:11},
      margin:{l:65,r:20,t:30,b:55},
      xaxis:{title:'Clearance Rate (%)', gridcolor:'#2d4a7a', zeroline:false, range:[0, maxCR+10]},
      yaxis:{title:'Disposition Time (días)', gridcolor:'#2d4a7a', zeroline:false, range:[0, maxDT+100]},
      legend:{orientation:'h', y:1.06, font:{size:10}},
      annotations:[
        {x:maxCR*0.85, y:180, text:'✓ Zona CEPEJ', showarrow:false,
         font:{size:11,color:'#22c55e'}, bgcolor:'rgba(34,197,94,0.12)',
         borderpad:5, bordercolor:'#22c55e', borderwidth:1},
        {x:40, y:maxDT*0.8, text:'⚠ Alto backlog', showarrow:false,
         font:{size:10,color:'#e63946'}, bgcolor:'rgba(230,57,70,0.08)', borderpad:4}
      ]
    }, cfg);
  } else {
    document.getElementById('graf-scatter').innerHTML =
      '<p style="color:#4a5568;padding:20px;text-align:center">'+
      'Sin datos suficientes — se requieren juzgados con CR > 0 y DT > 0</p>';
  }

  _tablaData = d.tabla || [];
  filtrarTabla();
}

function _sortRows(rows, orden) {
  return rows.sort((a,b)=>{
    if(orden==='alfabetico')        return (a.juzgado||'').localeCompare(b.juzgado||'', 'es');
    if(orden==='clearance_rate_asc') return (a.clearance_rate||0)-(b.clearance_rate||0);
    const k = orden==='ira_score'?'ira_score':orden==='pct_mora'?'pct_mora':orden==='pendientes_cierre'?'pendientes_cierre':'disposition_time';
    return (b[k]||0)-(a[k]||0);
  });
}

function _filtrarRows() {
  const q = (document.getElementById('fil-buscar').value||'').toLowerCase();
  const orden = document.getElementById('fil-orden').value;
  let rows = q
    ? _tablaData.filter(r=>(r.juzgado||'').toLowerCase().includes(q)||(r.magistrado||'').toLowerCase().includes(q)||(r.fuero||'').toLowerCase().includes(q))
    : [..._tablaData];
  return _sortRows(rows, orden);
}

function renderPaginacion(total, totalPages) {
  const el = document.getElementById('nac-paginacion');
  const btnStyle = 'background:#1a3a6e;border:1px solid #2d4a7a;color:#e2e8f0;padding:5px 14px;border-radius:6px;cursor:pointer;font-size:.82rem;';
  const btnDisabled = 'background:#111d33;border:1px solid #1e3058;color:#475569;padding:5px 14px;border-radius:6px;cursor:default;font-size:.82rem;';
  if(totalPages <= 1) {
    el.innerHTML = `<span style="color:#64748b;font-size:.82rem">${total.toLocaleString('es-AR')} juzgados</span>`;
    return;
  }
  const pages = [];
  // siempre mostrar primera, última, y ventana de 2 alrededor de la actual
  const visible = new Set([1, totalPages]);
  for(let p = Math.max(1, _currentPage-2); p <= Math.min(totalPages, _currentPage+2); p++) visible.add(p);
  let prev = 0;
  for(const p of [...visible].sort((a,b)=>a-b)) {
    if(prev && p - prev > 1) pages.push('<span style="color:#475569">…</span>');
    const active = p === _currentPage ? 'background:#2d4a7a;border-color:#4a6fa5;' : '';
    pages.push(`<button onclick="cambiarPagina(${p})" style="${btnStyle}${active}">${p}</button>`);
    prev = p;
  }
  el.innerHTML = `
    <button onclick="cambiarPagina(${_currentPage-1})" ${_currentPage===1?'disabled style="'+btnDisabled+'"':'style="'+btnStyle+'"'}>← Ant.</button>
    ${pages.join('')}
    <button onclick="cambiarPagina(${_currentPage+1})" ${_currentPage===totalPages?'disabled style="'+btnDisabled+'"':'style="'+btnStyle+'"'}>Sig. →</button>
    <span style="color:#64748b;font-size:.82rem">&nbsp;${total.toLocaleString('es-AR')} juzgados · pág. ${_currentPage}/${totalPages}</span>
  `;
}

function cambiarPagina(page) {
  _currentPage = page;
  filtrarTabla(false);
  document.getElementById('nac-tabla').scrollIntoView({behavior:'smooth', block:'start'});
}

function exportarCSV() {
  const rows = _filtrarRows();
  const cols = ['juzgado','fuero','magistrado','antiguedad_anos','ira_semaforo','ira_score',
                'pendientes_cierre','dictadas_def','disposition_time','clearance_rate',
                'pct_mora','mora_2anios','costo_por_causa','vs_cepej_cr','vs_cepej_dt',
                'vacante','en_licencia','jurisdiccion','anio'];
  const headers = ['Juzgado','Fuero','Magistrado','Antigüedad (años)','IRA Semáforo','IRA Score',
                   'Pendientes cierre','Sent./año','Disp.Time (días)','Clearance Rate (%)',
                   '% Mora','Causas mora +2años','Costo/causa (ARS)','vs CEPEJ CR','vs CEPEJ DT',
                   'Vacante','En Licencia','Jurisdicción','Año'];
  const esc = v => {
    if(v==null) return '';
    const s = String(v);
    return s.includes(',') || s.includes('"') || s.includes('\n') ? '"'+s.replace(/"/g,'""')+'"' : s;
  };
  const lines = [headers.map(esc).join(',')];
  for(const r of rows) lines.push(cols.map(c=>esc(r[c]??'')).join(','));
  const blob = new Blob(['﻿'+lines.join('\n')], {type:'text/csv;charset=utf-8'});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `juzgados_pjn_${new Date().toISOString().slice(0,10)}.csv`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function filtrarTabla(resetPage=true) {
  if(resetPage) _currentPage = 1;
  const rows = _filtrarRows();
  const totalRows = rows.length;
  const totalPages = Math.max(1, Math.ceil(totalRows / _rowsPerPage));
  if(_currentPage > totalPages) _currentPage = totalPages;
  const pageRows = rows.slice((_currentPage-1)*_rowsPerPage, _currentPage*_rowsPerPage);

  const tbody = document.getElementById('nac-tbody');
  if(!pageRows.length) {
    tbody.innerHTML = '<tr><td colspan="14" style="padding:20px;color:#94a3b8;text-align:center">Sin resultados</td></tr>';
    renderPaginacion(0, 0);
    return;
  }

  renderPaginacion(totalRows, totalPages);

  const color_cr  = v => !v||v===0?'#64748b':v>=100?'#22c55e':v>=80?'#f59e0b':'#e63946';
  const color_dt  = v => !v||v===0?'#64748b':v<=180?'#22c55e':v<=230?'#f59e0b':'#e63946';
  const color_mora= v => v==null?'#64748b':v<5?'#22c55e':v<15?'#f59e0b':'#e63946';
  const fmt_dt    = v => (!v||v===0)?'—':fmt(v)+' d';
  const fmt_cr    = v => (!v||v===0)?'—':v+'%';
  const fmt_cepej = v => (!v||v==='—'||v===0)?'<span style="color:#64748b">—</span>'
                        :v==='OK'?'<span style="color:#22c55e">✓ OK</span>'
                        :'<span style="color:#e63946">✗ '+v+'</span>';

  tbody.innerHTML = pageRows.map(r=>`
    <tr class="nac-tr-click" style="border-bottom:1px solid #1e3058"
        onclick='abrirDetalle(${JSON.stringify(r).replace(/'/g,"&#39;")})'>
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

// ── Panel detalle ────────────────────────────────────────────────────────────
function cerrarPanel() {
  document.getElementById('panel-overlay').classList.remove('visible');
  document.getElementById('panel-detalle').classList.remove('abierto');
}

document.addEventListener('keydown', e => { if(e.key==='Escape') cerrarPanel(); });

function abrirDetalle(r) {
  const cc  = v => !v||v===0?'#64748b':v>=100?'#22c55e':v>=80?'#f59e0b':'#e63946';
  const cdt = v => !v||v===0?'#64748b':v<=180?'#22c55e':v<=230?'#f59e0b':'#e63946';
  const cm  = v => v==null?'#64748b':v<5?'#22c55e':v<15?'#f59e0b':'#e63946';
  const ci  = s => s==='🟢'?'#22c55e':s==='🟡'?'#f59e0b':'#e63946';
  const fmtN= v => v!=null&&v!==''&&v!==0 ? Number(v).toLocaleString('es-AR') : null;
  const fmtCepej = v => !v||v==='—'?null
    : v==='OK'?'<span style="color:#22c55e">✓ OK</span>'
    : '<span style="color:#e63946">✗ '+v+'</span>';

  const row = (label, val, color) => {
    if(val===null||val===undefined||val===''||val==='—') return '';
    return `<div class="pd-row">
      <span class="pd-label">${label}</span>
      <span class="pd-val" style="color:${color||'#e2e8f0'}">${val}</span>
    </div>`;
  };

  const iraColor = ci(r.ira_semaforo||'');
  const iraLabel = r.ira_semaforo==='🟢'?'Bajo riesgo':r.ira_semaforo==='🟡'?'Riesgo medio':'Alto riesgo';

  document.getElementById('panel-content').innerHTML = `
    <!-- Cabecera -->
    <div style="margin-bottom:18px">
      <div style="font-size:1.05rem;color:#e2e8f0;font-weight:600;line-height:1.35;margin-bottom:10px">
        ${r.juzgado||'—'}
      </div>
      <div style="display:flex;gap:12px;align-items:center;background:#1a2744;
                  border-radius:8px;padding:10px 14px">
        <span style="font-size:2.2rem;line-height:1">${r.ira_semaforo||'⬜'}</span>
        <div>
          <div style="color:${iraColor};font-size:1.25rem;font-weight:700">IRA ${r.ira_score||0}</div>
          <div style="color:#64748b;font-size:.75rem">${iraLabel}</div>
        </div>
        ${r.fuero?`<div style="margin-left:auto;background:#0d1b2e;border:1px solid #2d4a7a;
                       border-radius:5px;padding:3px 10px;font-size:.75rem;color:#94a3b8">
                       ${r.fuero}</div>`:''}
      </div>
    </div>

    <!-- Magistrado -->
    <div class="pd-sec">👤 Magistrado</div>
    ${row('Nombre', r.magistrado||'<span style="color:#475569">Sin designación</span>')}
    ${row('Antigüedad', r.antiguedad_anos!=null?r.antiguedad_anos+' años':null)}
    ${row('Fecha de jura', r.fecha_jura||null, '#94a3b8')}
    ${row('Estado', r.vacante
        ? '<span style="color:#e63946">⚠ Vacante</span>'
        : r.en_licencia
          ? '<span style="color:#f59e0b">Licencia</span>'
          : '<span style="color:#22c55e">Activo</span>')}
    ${r.concurso_activo ? row('Concurso activo N°', r.concurso_numero||'Sí', '#f59e0b') : ''}

    <!-- Causas -->
    <div class="pd-sec">📋 Causas</div>
    ${row('Jurisdicción', r.jurisdiccion||null, '#94a3b8')}
    ${row('Año de datos', r.anio||null, '#94a3b8')}
    ${row('Pendientes al cierre', fmtN(r.pendientes_cierre))}
    ${row('Pendientes al inicio', fmtN(r.pendientes_inicio))}
    ${row('Dictadas definitivas / año', fmtN(r.dictadas_def))}
    ${row('Ingresos', fmtN(r.ingresos))}
    ${row('Causas oralidad civil', fmtN(r.total_causas_oral))}
    ${row('Mora +2 años', r.mora_2anios!=null?fmtN(r.mora_2anios)+' causas':null, cm(r.pct_mora||0))}

    <!-- Eficiencia -->
    <div class="pd-sec">⚡ Eficiencia judicial</div>
    ${row('Clearance Rate',
          r.clearance_rate!=null&&r.clearance_rate>0 ? r.clearance_rate+'%' : null,
          cc(r.clearance_rate))}
    ${row('Disposition Time',
          r.disposition_time&&r.disposition_time>0 ? r.disposition_time+' días' : null,
          cdt(r.disposition_time))}
    ${row('% Mora',
          r.pct_mora!=null ? r.pct_mora+'%' : null,
          cm(r.pct_mora||0))}
    ${row('Costo / causa (est.)',
          r.costo_por_causa ? '$ '+fmtN(r.costo_por_causa) : null, '#94a3b8')}

    <!-- Benchmarks -->
    <div class="pd-sec">🌐 Benchmarks internacionales</div>
    ${row('vs WJP Civil Factor 7',
          r.vs_wjp_civil!=null&&r.vs_wjp_civil!==0 ? r.vs_wjp_civil : null, '#64748b')}
    ${row('vs CEPEJ Clearance Rate', fmtCepej(r.vs_cepej_cr))}
    ${row('vs CEPEJ Disposition Time', fmtCepej(r.vs_cepej_dt))}

    ${r.objeto_principal ? `
    <div class="pd-sec">📁 Litigio principal</div>
    ${row('Objeto más frecuente', r.objeto_principal, '#94a3b8')}` : ''}
  `;

  document.getElementById('panel-overlay').classList.add('visible');
  document.getElementById('panel-detalle').classList.add('abierto');
  document.getElementById('panel-detalle').scrollTop = 0;
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
