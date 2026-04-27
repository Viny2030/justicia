# main.py  —  Entry point FastAPI
# uvicorn main:app --reload --port 8000

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, FileResponse
import sys, os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from shared import BASE_CSS, DISCLAIMER, FOOTER, PLOTLY_JS, nav_html

app = FastAPI(title="Monitor Judicial — Ph.D. Monteverde", version="2.0")

from dashboard_estrategico.app import router as router_estrategico
from dashboard_operativo.app   import router as router_operativo
app.include_router(router_estrategico, prefix="/estrategico", tags=["Estratégico"])
app.include_router(router_operativo,   prefix="/operativo",   tags=["Operativo"])

ROOT = os.path.dirname(os.path.abspath(__file__))

# ── Página de inicio ──────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
def inicio():
    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8">
<title>Monitor Judicial — Ph.D. Monteverde</title>
<style>{BASE_CSS}
.hero{{text-align:center;padding:40px 24px 28px}}
.hero h1{{font-size:2rem;font-weight:800}}
.hero h1 span{{color:var(--gold)}}
.hero p{{color:var(--muted);font-size:.95rem;margin-top:8px}}
.grid{{display:flex;gap:24px;flex-wrap:wrap;justify-content:center;padding:0 24px 32px}}
.card{{background:var(--card);border-radius:14px;padding:28px 32px;width:220px;
       border-top:4px solid var(--blue);text-decoration:none;color:inherit;
       transition:transform .2s,box-shadow .2s;text-align:center}}
.card:hover{{transform:translateY(-5px);box-shadow:0 14px 40px rgba(0,0,0,.5)}}
.card.gold-t{{border-color:var(--gold)}}
.card.red-t{{border-color:var(--red)}}
.card .icon{{font-size:2.2rem;margin-bottom:12px}}
.card h2{{font-size:1rem;margin-bottom:6px}}
.card p{{color:var(--muted);font-size:.8rem;line-height:1.5}}
.disclaimer{{margin:0 24px 24px}}
</style></head><body>
{nav_html("inicio")}
<div class="hero">
  <h1>Sistema de Monitoreo <span>Judicial</span></h1>
  <p>Ph.D. Vicente H. Monteverde · Auditoría del Poder Judicial de la Nación Argentina</p>
</div>
<div class="disclaimer">{DISCLAIMER}</div>
<div class="grid">
  <a class="card" href="/estrategico/corte">
    <div class="icon">⚖️</div><h2>Corte Suprema</h2>
    <p>CSJN · Fallos de alto impacto · Tiempos de resolución</p>
  </a>
  <a class="card gold-t" href="/estrategico/consejo">
    <div class="icon">🏛️</div><h2>Consejo</h2>
    <p>Magistratura · Vacancia · Designaciones · Concursos</p>
  </a>
  <a class="card red-t" href="/operativo/camaras">
    <div class="icon">🏢</div><h2>Cámaras</h2>
    <p>Instancia de apelación · Carga y latencia federal</p>
  </a>
  <a class="card blue-t" href="/operativo/nacional">
    <div class="icon">🗺️</div><h2>Nacional PJN</h2>
    <p>Todos los juzgados · IRA · CEPEJ · WJP · Costo</p>
  </a>
  <a class="card" href="/operativo">
    <div class="icon">📋</div><h2>Juzgados</h2>
    <p>1ª Instancia · Mora · Ranking · Cuellos de botella</p>
  </a>
  <a class="card" href="/manual" style="border-color:#7c3aed">
    <div class="icon">📖</div><h2>Manual</h2>
    <p>Indicadores · Fuentes · Instrucciones de uso</p>
  </a>
</div>
{FOOTER}
</body></html>""")


# ── Foto del autor (archivo estático) ────────────────────────────────────────
@app.get("/foto_autor")
def foto_autor():
    path = os.path.join(ROOT, "foto_autor.jpg")
    if os.path.exists(path):
        return FileResponse(path, media_type="image/jpeg")
    path_png = os.path.join(ROOT, "foto_autor.png")
    if os.path.exists(path_png):
        return FileResponse(path_png, media_type="image/png")
    # SVG placeholder si no hay foto
    svg = """<svg xmlns="http://www.w3.org/2000/svg" width="160" height="160" viewBox="0 0 160 160">
      <rect width="160" height="160" rx="80" fill="#1a2744"/>
      <circle cx="80" cy="60" r="30" fill="#3b82f6"/>
      <ellipse cx="80" cy="130" rx="46" ry="30" fill="#3b82f6"/>
    </svg>"""
    from fastapi.responses import Response
    return Response(content=svg, media_type="image/svg+xml")


# ── Página Acerca del Autor ───────────────────────────────────────────────────
@app.get("/acerca", response_class=HTMLResponse)
def acerca():
    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8">
<title>Autor — Monitor Judicial</title>
<style>{BASE_CSS}
.wrap{{max-width:860px;margin:0 auto;padding:32px 24px}}
.perfil{{display:flex;gap:32px;align-items:flex-start;
         background:var(--card);border-radius:14px;padding:28px;
         margin-bottom:24px;flex-wrap:wrap}}
.perfil img{{width:160px;height:160px;border-radius:50%;
             object-fit:cover;border:3px solid var(--gold);flex-shrink:0}}
.perfil-info h1{{font-size:1.5rem;font-weight:800;margin-bottom:4px}}
.perfil-info h1 span{{color:var(--gold)}}
.perfil-info .titulo{{color:var(--blue);font-size:.9rem;font-weight:600;margin-bottom:12px}}
.perfil-info p{{color:var(--muted);font-size:.88rem;line-height:1.75}}
.chips{{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0 0}}
.chip{{background:#0f1e3a;border:1px solid var(--border);color:#93c5fd;
       font-size:.72rem;padding:4px 12px;border-radius:99px;font-weight:600}}
.chip.gold{{background:#1a1500;border-color:#3a2f00;color:var(--gold)}}
.seccion-titulo{{font-size:.72rem;text-transform:uppercase;letter-spacing:2px;
                 color:var(--gold);margin:28px 0 12px;padding-left:2px}}
.bloque{{background:var(--card);border-radius:12px;padding:22px 26px;margin-bottom:16px}}
.bloque h3{{font-size:.85rem;font-weight:700;margin-bottom:10px;color:var(--text)}}
.bloque p,.bloque li{{font-size:.87rem;color:var(--muted);line-height:1.8}}
.bloque ul{{padding-left:18px}}
.bloque a{{color:var(--gold2);text-decoration:none;font-weight:600}}
.bloque a:hover{{text-decoration:underline}}
.contact-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px}}
.cbox{{background:var(--card);border-radius:10px;padding:18px 20px;
       border-left:4px solid var(--blue)}}
.cbox.gold{{border-color:var(--gold)}}
.cbox label{{font-size:.68rem;text-transform:uppercase;letter-spacing:1px;
             color:var(--muted);display:block;margin-bottom:6px}}
.cbox a,.cbox span{{font-size:.9rem;color:var(--text);word-break:break-all}}
.cbox a{{color:var(--gold2)}}
.donate{{background:var(--card);border-radius:12px;padding:22px 26px;
         border-left:4px solid var(--gold);margin-bottom:16px}}
.donate h3{{font-size:.85rem;text-transform:uppercase;letter-spacing:2px;
            color:var(--gold);margin-bottom:16px}}
.tag{{display:inline-block;font-size:.72rem;padding:3px 10px;border-radius:4px;
      font-weight:600;margin-bottom:10px}}
.tag.ars{{background:#1a1500;color:var(--gold)}}
.tag.usd{{background:#0f2a10;color:#86efac}}
.tag.ext{{background:#0f1e3a;color:#93c5fd}}
.row{{margin-bottom:7px;display:flex;gap:12px;align-items:baseline;flex-wrap:wrap}}
.row .lbl{{font-size:.72rem;text-transform:uppercase;color:var(--muted);
           letter-spacing:1px;min-width:80px}}
.row .val{{font-family:monospace;font-size:.86rem;background:#0a1628;
           padding:3px 10px;border-radius:4px;color:var(--text);word-break:break-all}}
.divider{{border-top:1px solid var(--border);margin:12px 0}}
</style></head><body>
{nav_html("")}
<div class="wrap">

  <!-- PERFIL -->
  <div class="perfil">
    <img src="/foto_autor" alt="Ph.D. Vicente H. Monteverde" onerror="this.style.background='#1a2744'">
    <div class="perfil-info">
      <h1>Ph.D. Vicente <span>Humberto Monteverde</span></h1>
      <div class="titulo">Doctor en Ciencias — Investigador en Transparencia Judicial</div>
      <p>
        Especialista en análisis algorítmico del Poder Judicial argentino. Desarrolla
        herramientas de auditoría basadas en datos públicos oficiales para promover la
        transparencia, el debate académico y el control ciudadano del sistema judicial.
      </p>
      <div class="chips">
        <span class="chip gold">Ph.D.</span>
        <span class="chip">Transparencia Judicial</span>
        <span class="chip">Análisis de Datos</span>
        <span class="chip">Derecho Público</span>
        <span class="chip">Indicadores Internacionales</span>
      </div>
    </div>
  </div>

  <!-- ANTECEDENTES -->
  <div class="seccion-titulo">📋 Antecedentes Académicos y Profesionales</div>

  <div class="bloque">
    <h3>Formación</h3>
    <ul>
      <li>Doctor (Ph.D.) — <em>[Universidad · Año]</em></li>
      <li>Maestría en <em>[disciplina]</em> — <em>[Universidad · Año]</em></li>
      <li>Licenciatura en <em>[disciplina]</em> — <em>[Universidad · Año]</em></li>
    </ul>
  </div>

  <div class="bloque">
    <h3>Actividad Académica y de Investigación</h3>
    <ul>
      <li>Investigador en transparencia y eficiencia del Poder Judicial de la Nación Argentina</li>
      <li>Desarrollador del Sistema de Monitoreo Judicial — indicadores IRA, CEPEJ, WJP adaptados al contexto argentino</li>
      <li>Análisis de datos judiciales con fuentes públicas: datos.jus.gob.ar, estadisticas.pjn.gov.ar, CSJN</li>
      <li><em>[Publicaciones, docencia, cargos — completar]</em></li>
    </ul>
  </div>

  <div class="bloque">
    <h3>Sobre este Proyecto</h3>
    <p>
      El <strong>Sistema de Monitoreo Judicial</strong> es un desarrollo independiente de carácter
      académico construido sobre datos públicos oficiales del Estado argentino. Aplica metodologías
      internacionales (WJP Rule of Law Index, CEPEJ, V-Dem, ODS 16) para producir indicadores
      algorítmicos comparables y auditables sobre el funcionamiento del Poder Judicial Nacional.
      No implica juicio de valor ni determinación de responsabilidades sobre personas u organismos.
    </p>
  </div>

  <!-- CONTACTO -->
  <div class="seccion-titulo">✉️ Contacto</div>
  <div class="contact-grid" style="margin-bottom:24px">
    <div class="cbox">
      <label>Email académico</label>
      <a href="mailto:vhmonte@retina.ar">vhmonte@retina.ar</a>
    </div>
    <div class="cbox">
      <label>Email personal</label>
      <a href="mailto:viny01958@gmail.com">viny01958@gmail.com</a>
    </div>
    <div class="cbox gold">
      <label>Repositorio del proyecto</label>
      <a href="https://github.com/Viny2030/justicia" target="_blank">github.com/Viny2030/justicia</a>
    </div>
  </div>

  <!-- DONACIÓN -->
  <div class="seccion-titulo">💛 Apoyar el Proyecto</div>
  <div class="donate">
    <h3>Datos para Donación</h3>
    <div class="tag ars">🇦🇷 Pesos — Argentina</div>
    <div class="row"><span class="lbl">CBU</span><span class="val">0140005203400552652310</span></div>
    <div class="row"><span class="lbl">Alias</span><span class="val">ALGORIT.MONTE.PESOS</span></div>
    <div class="row"><span class="lbl">Titular</span><span class="val">Vicente Humberto Monteverde</span></div>
    <div class="row"><span class="lbl">CUIL</span><span class="val">20-12034411-1</span></div>
    <div class="divider"></div>
    <div class="tag usd">💵 Dólares — Argentina</div>
    <div class="row"><span class="lbl">CBU</span><span class="val">0140005204400550329709</span></div>
    <div class="row"><span class="lbl">Alias</span><span class="val">ALGO.MONTE.DOLARES</span></div>
    <div class="divider"></div>
    <div class="tag ext">🌐 Desde el Exterior</div>
    <div class="row"><span class="lbl">Banco</span><span class="val">Banco Santander Montevideo</span></div>
    <div class="row"><span class="lbl">Cuenta USD</span><span class="val">005200183500</span></div>
    <div class="row"><span class="lbl">Swift</span><span class="val">BSCHUYMM</span></div>
  </div>

</div>
{FOOTER}
</body></html>""")


# ── Manual de Usuario ─────────────────────────────────────────────────────────
@app.get("/manual", response_class=HTMLResponse)
def manual():
    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8">
<title>Manual de Usuario — Monitor Judicial</title>
<style>{BASE_CSS}
.wrap{{max-width:900px;margin:0 auto;padding:32px 24px}}
.hero-manual{{text-align:center;padding:28px 0 20px}}
.hero-manual h1{{font-size:1.7rem;font-weight:800}}
.hero-manual h1 span{{color:var(--gold)}}
.hero-manual p{{color:var(--muted);font-size:.88rem;margin-top:6px}}

/* Índice lateral */
.layout{{display:grid;grid-template-columns:210px 1fr;gap:28px;align-items:start}}
@media(max-width:750px){{.layout{{grid-template-columns:1fr}}}}
.sidebar{{position:sticky;top:62px;background:var(--card);border-radius:10px;
          padding:16px;font-size:.81rem}}
.sidebar h3{{font-size:.68rem;text-transform:uppercase;letter-spacing:2px;
             color:var(--gold);margin-bottom:10px}}
.sidebar a{{display:block;color:var(--muted);text-decoration:none;
            padding:5px 8px;border-radius:5px;margin-bottom:2px}}
.sidebar a:hover{{background:var(--card2);color:var(--text)}}
.sidebar .sep{{border-top:1px solid var(--border);margin:8px 0}}

/* Secciones */
.seccion{{margin-bottom:36px;scroll-margin-top:70px}}
.sec-titulo{{font-size:.72rem;text-transform:uppercase;letter-spacing:2px;
             color:var(--gold);margin-bottom:14px;padding-left:2px;
             border-left:3px solid var(--gold);padding-left:10px}}
.bloque{{background:var(--card);border-radius:10px;padding:20px 24px;margin-bottom:14px}}
.bloque h3{{font-size:.95rem;font-weight:700;margin-bottom:10px;color:var(--text)}}
.bloque h4{{font-size:.82rem;font-weight:700;color:var(--gold2);margin:14px 0 6px}}
.bloque p,.bloque li{{font-size:.86rem;color:var(--muted);line-height:1.8}}
.bloque ul{{padding-left:18px}}
.bloque strong{{color:var(--text)}}
.bloque code{{background:#0a1628;color:#86efac;padding:2px 7px;border-radius:4px;font-size:.83rem}}

/* Indicador card */
.ind-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px;margin-bottom:14px}}
.ind{{background:var(--card);border-radius:10px;padding:18px 20px;border-top:3px solid var(--blue)}}
.ind.gold{{border-color:var(--gold)}}
.ind.red{{border-color:var(--red)}}
.ind.green{{border-color:var(--green)}}
.ind.purple{{border-color:#7c3aed}}
.ind h4{{font-size:.85rem;font-weight:700;margin-bottom:6px}}
.ind .formula{{font-family:monospace;font-size:.78rem;background:#0a1628;
               color:#86efac;padding:5px 10px;border-radius:4px;margin:8px 0}}
.ind p{{font-size:.8rem;color:var(--muted);line-height:1.65}}
.ind .bench{{font-size:.75rem;margin-top:8px;padding:4px 10px;border-radius:4px;
             background:#0f1e3a;color:#93c5fd}}

/* Semáforo */
.semaforo-tabla{{width:100%;border-collapse:collapse;font-size:.83rem;margin-top:10px}}
.semaforo-tabla th{{text-align:left;padding:8px 12px;background:#0a1628;color:var(--muted);
                    font-size:.72rem;text-transform:uppercase;letter-spacing:1px}}
.semaforo-tabla td{{padding:9px 12px;border-bottom:1px solid var(--border);color:var(--muted)}}
.semaforo-tabla tr:last-child td{{border-bottom:none}}
.s-rojo{{color:#fca5a5;font-weight:700}} .s-amarillo{{color:#fde68a;font-weight:700}}
.s-verde{{color:#86efac;font-weight:700}}

/* Pasos */
.paso{{display:flex;gap:16px;margin-bottom:14px;align-items:flex-start}}
.paso .num{{background:var(--gold);color:#000;font-weight:800;font-size:.85rem;
            width:28px;height:28px;border-radius:50%;display:flex;align-items:center;
            justify-content:center;flex-shrink:0;margin-top:2px}}
.paso .txt h4{{font-size:.88rem;font-weight:700;margin-bottom:4px}}
.paso .txt p{{font-size:.83rem;color:var(--muted);line-height:1.65}}
</style></head><body>
{nav_html("manual")}
<div class="wrap">
  <div class="hero-manual">
    <h1>📖 Manual de <span>Usuario</span></h1>
    <p>Guía de uso e interpretación de indicadores — Sistema de Monitoreo Judicial PJN</p>
  </div>

  <div class="layout">
    <!-- SIDEBAR -->
    <div class="sidebar">
      <h3>Índice</h3>
      <a href="#que-es">¿Qué es el sistema?</a>
      <a href="#navegacion">Cómo navegar</a>
      <div class="sep"></div>
      <a href="#indicadores">Indicadores</a>
      <a href="#ira">↳ IRA</a>
      <a href="#clearance">↳ Clearance Rate</a>
      <a href="#disposition">↳ Disposition Time</a>
      <a href="#mora">↳ % Mora</a>
      <a href="#wjp">↳ WJP</a>
      <a href="#cepej">↳ CEPEJ</a>
      <a href="#vacancia">↳ Vacancia</a>
      <a href="#costo">↳ Costo por Causa</a>
      <div class="sep"></div>
      <a href="#fuentes">Fuentes de datos</a>
      <a href="#limitaciones">Limitaciones</a>
    </div>

    <!-- CONTENIDO -->
    <div>

      <!-- ¿Qué es? -->
      <div class="seccion" id="que-es">
        <div class="sec-titulo">¿Qué es el Sistema de Monitoreo Judicial?</div>
        <div class="bloque">
          <p>
            Es una plataforma de auditoría académica del <strong>Poder Judicial de la Nación Argentina</strong>
            que construye indicadores algorítmicos sobre datos públicos oficiales.
            Su objetivo es proveer métricas objetivas y comparables para promover la
            transparencia y el debate informado sobre el funcionamiento judicial.
          </p>
          <br>
          <p>
            Los indicadores se construyen aplicando metodologías internacionales reconocidas
            (WJP, CEPEJ, V-Dem, ODS 16 ONU) adaptadas al contexto argentino.
            <strong>No implican juicio de valor ni determinación de responsabilidades</strong>
            sobre personas u organismos judiciales.
          </p>
        </div>
      </div>

      <!-- Navegación -->
      <div class="seccion" id="navegacion">
        <div class="sec-titulo">Cómo Navegar el Dashboard</div>
        <div class="paso">
          <div class="num">1</div>
          <div class="txt">
            <h4>⚖️ Corte Suprema</h4>
            <p>Indicadores estratégicos de la CSJN: fallos de alto impacto, tiempos de resolución, composición. Datos del WJP, V-Dem y rankings internacionales de independencia judicial.</p>
          </div>
        </div>
        <div class="paso">
          <div class="num">2</div>
          <div class="txt">
            <h4>🏛️ Consejo de la Magistratura</h4>
            <p>Vacancia de cargos, designaciones recientes, concursos en trámite, índice de subrogancia. Cruce con impacto en latencia operativa.</p>
          </div>
        </div>
        <div class="paso">
          <div class="num">3</div>
          <div class="txt">
            <h4>🌐 Indicadores Internacionales</h4>
            <p>WJP Rule of Law Index, IPC Transparencia Internacional, World Bank WGI, V-Dem. Comparativos regionales LAC y OCDE.</p>
          </div>
        </div>
        <div class="paso">
          <div class="num">4</div>
          <div class="txt">
            <h4>🏢 Cámaras de Apelación</h4>
            <p>Instancia de segunda instancia federal y nacional. Latencia, clearance rate, recursos interpuestos.</p>
          </div>
        </div>
        <div class="paso">
          <div class="num">5</div>
          <div class="txt">
            <h4>🗺️ Nacional PJN</h4>
            <p>Vista completa de los 301 juzgados relevados. Tabla filtrable por fuero, semáforo IRA, buscador por nombre o magistrado. Exportable a CSV.</p>
          </div>
        </div>
        <div class="paso">
          <div class="num">6</div>
          <div class="txt">
            <h4>📋 Juzgados (1ª Instancia)</h4>
            <p>Dashboard operativo detallado: ranking de mora, pendientes, latencia por percentil (P50/P75/P90), panel lateral con detalle por juzgado.</p>
          </div>
        </div>
      </div>

      <!-- Indicadores -->
      <div class="seccion" id="indicadores">
        <div class="sec-titulo">Indicadores — Referencia Completa</div>

        <!-- IRA -->
        <div class="bloque" id="ira">
          <h3>🔴 IRA — Índice de Riesgo Algorítmico</h3>
          <p>Score compuesto (0–100) que combina cinco dimensiones de riesgo operativo para cada juzgado. A mayor IRA, mayor urgencia de intervención.</p>
          <div class="formula">IRA = mora(30) + clearance(25) + latencia(20) + acumulación(15) + vacancia(10)</div>
          <h4>Componentes</h4>
          <ul>
            <li><strong>% Mora (máx. 30 pts):</strong> Causas con más de 2 años sin resolución. Ponderado × 1.2.</li>
            <li><strong>Clearance Rate (máx. 25 pts):</strong> Penaliza cuando CR &lt; 100% (no se resuelve todo lo que ingresa).</li>
            <li><strong>Latencia/Disposition Time (máx. 20 pts):</strong> Exceso sobre el benchmark CEPEJ de 230 días.</li>
            <li><strong>Acumulación de pendientes (máx. 15 pts):</strong> Ratio cierre/inicio &gt; 1 indica desborde.</li>
            <li><strong>Vacancia sin concurso (10 pts):</strong> Juzgado vacante sin proceso de cobertura activo.</li>
          </ul>
          <table class="semaforo-tabla" style="margin-top:14px">
            <tr><th>Semáforo</th><th>Rango IRA</th><th>Significado</th></tr>
            <tr><td class="s-rojo">🔴 Alto riesgo</td><td>≥ 60</td><td>Intervención prioritaria recomendada</td></tr>
            <tr><td class="s-amarillo">🟡 Riesgo medio</td><td>30–59</td><td>Monitoreo reforzado</td></tr>
            <tr><td class="s-verde">🟢 Normal</td><td>&lt; 30</td><td>Funcionamiento dentro de parámetros</td></tr>
          </table>
        </div>

        <!-- Clearance Rate -->
        <div class="bloque" id="clearance">
          <h3>📊 Clearance Rate (Tasa de Resolución)</h3>
          <p>Mide la capacidad del juzgado para resolver causas en relación a las que ingresan. Indicador central del <strong>CEPEJ</strong> (Consejo de Europa) y del <strong>WJP</strong>.</p>
          <div class="formula">CR = Causas resueltas / Causas ingresadas × 100</div>
          <ul>
            <li><strong>CR = 100%:</strong> Se resuelve exactamente lo que ingresa — equilibrio perfecto.</li>
            <li><strong>CR &gt; 100%:</strong> Se reduce el stock de pendientes (situación ideal).</li>
            <li><strong>CR &lt; 100%:</strong> Se acumula mora — cada punto por debajo es aumento de la deuda judicial.</li>
          </ul>
          <div class="bench">📌 Benchmark CEPEJ: ≥ 100% · Promedio Argentina: 16.5% · WJP Factor 7 (Justicia Civil): 0.42/1.00</div>
        </div>

        <!-- Disposition Time -->
        <div class="bloque" id="disposition">
          <h3>⏱️ Disposition Time (Tiempo de Resolución)</h3>
          <p>Tiempo promedio en días que tarda un juzgado en resolver una causa desde su ingreso. Calculado sobre causas civiles con fecha de ingreso y resolución en los datos de oralidad.</p>
          <div class="formula">DT = Promedio de (fecha_resolución − fecha_ingreso) en días</div>
          <ul>
            <li>Incluye tanto causas resueltas como causas activas (estimando desde hoy).</li>
            <li>Se reportan percentiles <code>P50</code> (mediana), <code>P75</code> y <code>P90</code> para entender la distribución.</li>
          </ul>
          <div class="bench">📌 Benchmark CEPEJ: ≤ 230 días · Promedio Argentina: 2.314 días (~6.3 años) · 100% de juzgados con datos está por encima del benchmark</div>
        </div>

        <!-- % Mora -->
        <div class="bloque" id="mora">
          <h3>⚠️ % Mora (&gt; 2 años)</h3>
          <p>Porcentaje de causas que llevan más de 730 días sin resolución desde su ingreso. Indicador de "cola crítica" del sistema.</p>
          <div class="formula">% Mora = Causas &gt; 730 días activas / Total causas × 100</div>
          <div class="bench">📌 Alerta: &gt; 15% · Fuente: datos_jus/oralidad — causas civiles individuales (75.894 causas relevadas)</div>
        </div>

        <!-- WJP -->
        <div class="bloque" id="wjp">
          <h3>🌐 WJP Rule of Law Index</h3>
          <p>Índice anual del <strong>World Justice Project</strong> que mide el estado de derecho en 142 países. Escala 0–1 (mayor = mejor). Argentina 2023: <strong>0.47</strong>.</p>
          <h4>Los 4 factores más relevantes para el PJN</h4>
          <ul>
            <li><strong>Factor 1 — Límites al Poder Gubernamental:</strong> ARG 0.56 · LAC 0.52 · OCDE 0.72</li>
            <li><strong>Factor 2 — Ausencia de Corrupción:</strong> ARG 0.39 · LAC 0.43 · OCDE 0.71</li>
            <li><strong>Factor 7 — Justicia Civil:</strong> ARG 0.42 · LAC 0.44 · OCDE 0.68</li>
            <li><strong>Factor 8 — Justicia Penal:</strong> ARG 0.38 · LAC 0.40 · OCDE 0.62</li>
          </ul>
          <h4>vs_wjp_civil en el dashboard</h4>
          <p>Para cada juzgado muestra el Clearance Rate normalizado a escala 0–1. El <code>gap_wjp_civil</code> indica la distancia al benchmark WJP de 0.42: valores negativos significan que el juzgado está por debajo del estándar internacional.</p>
          <div class="bench">📌 Fuente: worldjusticeproject.org · Datos 2023</div>
        </div>

        <!-- CEPEJ -->
        <div class="bloque" id="cepej">
          <h3>🏛️ CEPEJ — Benchmarks Europeos</h3>
          <p>La <strong>Comisión Europea para la Eficacia de la Justicia</strong> establece estándares de referencia adoptados en evaluaciones judiciales de América Latina (RECPJ/CEJAS).</p>
          <ul>
            <li><strong>vs_cepej_cr:</strong> <code>OK</code> si CR ≥ 100%, <code>BAJO</code> si CR &lt; 100%.</li>
            <li><strong>vs_cepej_dt:</strong> <code>OK</code> si DT ≤ 230 días, <code>ALTO</code> si supera el benchmark, <code>—</code> sin datos.</li>
          </ul>
          <div class="bench">📌 Benchmark Clearance Rate: 100% · Benchmark Disposition Time: 230 días (procesos civiles)</div>
        </div>

        <!-- Vacancia -->
        <div class="bloque" id="vacancia">
          <h3>⬜ Tasa de Vacancia</h3>
          <p>Porcentaje de cargos de magistratura sin titular designado sobre el total de cargos previstos por ley.</p>
          <div class="formula">Tasa Vacancia = (Cargos totales − Activos) / Cargos totales × 100</div>
          <ul>
            <li>Fuente: magistrados.json (datos.jus.gob.ar)</li>
            <li>Un cargo vacante sin concurso activo suma 10 pts al IRA del juzgado.</li>
            <li>Un cargo en subrogancia (cubierto temporalmente) no suma pts de IRA pero se registra.</li>
          </ul>
          <div class="bench">📌 Tasa actual PJN: 32.9% (540/1.643 cargos vacantes) · Fuente: CSJN 2024</div>
        </div>

        <!-- Costo -->
        <div class="bloque" id="costo">
          <h3>💰 Costo por Causa</h3>
          <p>Estimación del costo fiscal por causa tramitada en cada juzgado. Se calcula dividiendo el presupuesto anual estimado por juzgado sobre su volumen total de causas.</p>
          <div class="formula">Costo/Causa = Presupuesto anual estimado / (Pendientes + Resueltas)</div>
          <ul>
            <li><strong>Presupuesto base:</strong> $500.000.000 ARS/año por juzgado (PJN 2024: ~$1.1 billones ARS / ~1.400 juzgados).</li>
            <li>Juzgados con alta carga procesal tienen costo por causa menor.</li>
            <li>Juzgados con pocas causas muestran costo/causa elevado — posible ineficiencia de escala.</li>
          </ul>
          <div class="bench">📌 Rango actual: $78.000 – $500.000.000 ARS/causa · Mediana: $7.7M ARS/causa</div>
        </div>

      </div><!-- /indicadores -->

      <!-- Fuentes -->
      <div class="seccion" id="fuentes">
        <div class="sec-titulo">Fuentes de Datos</div>
        <div class="bloque">
          <ul>
            <li><strong>datos.jus.gob.ar</strong> — Magistrados, oralidad civil (75.894 causas), vacantes</li>
            <li><strong>estadisticas.pjn.gov.ar</strong> — CSVs de sentencias, trámite y recursos por jurisdicción</li>
            <li><strong>csjn.gov.ar</strong> — Fallos CSJN, composición, acordadas</li>
            <li><strong>mpf.gov.ar / mpd.gov.ar</strong> — Fiscales y defensores</li>
            <li><strong>worldjusticeproject.org</strong> — WJP Rule of Law Index 2023</li>
            <li><strong>transparency.org</strong> — IPC 2023</li>
            <li><strong>databank.worldbank.org</strong> — World Bank WGI 2022</li>
            <li><strong>v-dem.net</strong> — V-Dem Institute JCI 2023</li>
            <li><strong>coe.int/cepej</strong> — CEPEJ benchmarks 2022</li>
          </ul>
          <br>
          <p>Todos los datos son de acceso público. Los scrapers se ejecutan sobre las APIs oficiales y no modifican ni alteran las fuentes.</p>
        </div>
      </div>

      <!-- Limitaciones -->
      <div class="seccion" id="limitaciones">
        <div class="sec-titulo">Limitaciones y Advertencias</div>
        <div class="bloque">
          <ul>
            <li>Los datos de oralidad cubren <strong>causas civiles individuales</strong> de juzgados que adhirieron al programa de oralidad — no representan la totalidad del sistema.</li>
            <li>El <strong>clearance rate</strong> promedio de 16.5% es bajo en parte porque muchos juzgados tienen causas históricas no resueltas que pesan en el denominador.</li>
            <li>El <strong>costo por causa</strong> es una estimación basada en presupuesto promedio; no refleja diferencias de tamaño, jurisdicción ni dotación de personal.</li>
            <li>Los <strong>indicadores internacionales</strong> (WJP, CEPEJ) fueron diseñados para sistemas judiciales completos — su aplicación a juzgados individuales es una adaptación metodológica del autor.</li>
            <li>El sistema no tiene acceso a <strong>expedientes individuales</strong> ni a datos de gestión interna de cada juzgado.</li>
          </ul>
        </div>
      </div>

    </div><!-- /contenido -->
  </div><!-- /layout -->
</div>
{FOOTER}
</body></html>""")


# ── Redireccciones legacy ─────────────────────────────────────────────────────
@app.get("/apoyar", response_class=HTMLResponse)
def apoyar_legacy():
    return HTMLResponse('<meta http-equiv="refresh" content="0; url=/acerca">')

@app.get("/juzgados", response_class=HTMLResponse)
def legacy():
    return HTMLResponse('<meta http-equiv="refresh" content="0; url=/operativo">')
