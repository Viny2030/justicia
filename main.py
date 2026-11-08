# main.py  —  Entry point FastAPI
# uvicorn main:app --reload --port 8000
from api.database import init_db
init_db()  # crea tablas automáticamente al arrancar
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
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
.card-stats{{display:flex;justify-content:center;gap:16px;margin:10px 0 12px;flex-wrap:wrap}}
.card-stats .stat{{text-align:center;min-width:44px}}
.card-stats .stat-val{{font-size:1.2rem;font-weight:800;color:var(--gold2);line-height:1}}
.card-stats .stat-lbl{{font-size:.6rem;color:var(--muted);text-transform:uppercase;
                       letter-spacing:.5px;margin-top:3px}}
.disclaimer{{margin:0 24px 24px}}
</style></head><body>
{nav_html("inicio")}
<div id="frescura-ficha" data-api="/api/frescura" style="padding:0 24px"></div><script src="/frescura.js" defer></script>
<div class="hero">
  <h1>Sistema de Monitoreo <span>Judicial</span></h1>
  <p>Ph.D. Vicente H. Monteverde · Auditoría del Poder Judicial de la Nación Argentina</p>
</div>
<div class="disclaimer">{DISCLAIMER}</div>
<div class="disclaimer" style="margin-top:12px">
  <div style="background:#e8f4fd;border-left:4px solid #003f8a;border-radius:6px;padding:1rem 1.2rem;font-size:.82rem;color:#333;line-height:1.75;">
    <strong>⚖️ Marco Legal y Transparencia</strong><br><br>
    Los datos publicados en este monitor provienen exclusivamente de fuentes oficiales del Estado argentino.
    Su reutilización está amparada por la <strong>Ley 27.275 de Acceso a la Información Pública</strong>,
    que obliga a los organismos públicos a publicar activamente la información que producen, obtienen, transforman o controlan,
    y por el <strong>Decreto 1172/2003</strong> sobre libre acceso a la información pública en el Poder Ejecutivo Nacional.<br><br>
    Los datos curriculares de magistrados corresponden a declaración obligatoria ante el Consejo de la Magistratura
    conforme al <strong>art. 16 de la Ley 27.275</strong>. Este portal procesa únicamente información de funcionarios públicos
    en ejercicio de sus funciones, excluida del ámbito de protección individual conforme al art. 2 de la
    <strong>Ley 25.326 de Protección de Datos Personales</strong> y a la doctrina consolidada de la
    <strong>Agencia de Acceso a la Información Pública (AAIP)</strong>.<br><br>
    Los indicadores, índices y alertas son el resultado de <strong>análisis algorítmico sobre datos oficiales</strong> y no constituyen
    imputaciones, acusaciones ni determinaciones de responsabilidad penal, civil o administrativa.
    No reemplazan los mecanismos formales de control del Estado (AGN · SIGEN · Ministerio Público Fiscal).
    Para consultas sobre el tratamiento de datos: <a href="mailto:vhmonte@retina.ar" style="color:#003f8a;">vhmonte@retina.ar</a>
  </div>
</div>
<div class="grid">
  <a class="card" href="/estrategico/corte">
    <div class="icon">⚖️</div><h2>Corte Suprema</h2>
    <div class="card-stats">
      <div class="stat"><div class="stat-val" id="kpi-corte-ministros">—</div><div class="stat-lbl">Ministros</div></div>
    </div>
    <p>CSJN · Fallos de alto impacto · Tiempos de resolución</p>
  </a>
  <a class="card gold-t" href="/estrategico/consejo">
    <div class="icon">🏛️</div><h2>Consejo</h2>
    <div class="card-stats">
      <div class="stat"><div class="stat-val" id="kpi-consejo-vacantes">—</div><div class="stat-lbl">Vacantes</div></div>
      <div class="stat"><div class="stat-val" id="kpi-consejo-tasa">—</div><div class="stat-lbl">% Vacancia</div></div>
    </div>
    <p>Magistratura · Vacancia · Designaciones · Concursos</p>
  </a>
  <a class="card red-t" href="/operativo/camaras">
    <div class="icon">🏢</div><h2>Cámaras</h2>
    <div class="card-stats">
      <div class="stat"><div class="stat-val" id="kpi-camaras-total">—</div><div class="stat-lbl">Relevadas</div></div>
    </div>
    <p>Instancia de apelación · Carga y latencia federal</p>
  </a>
  <a class="card blue-t" href="/operativo/nacional">
    <div class="icon">🗺️</div><h2>Nacional PJN</h2>
    <div class="card-stats">
      <div class="stat"><div class="stat-val" id="kpi-nacional-total">—</div><div class="stat-lbl">Juzgados</div></div>
      <div class="stat"><div class="stat-val" id="kpi-nacional-alto" style="color:#fca5a5">—</div><div class="stat-lbl">Alto riesgo</div></div>
    </div>
    <p>Todos los juzgados · IRA · CEPEJ · WJP · Costo</p>
  </a>
  <a class="card" href="/operativo">
    <div class="icon">📋</div><h2>Juzgados</h2>
    <div class="card-stats">
      <div class="stat"><div class="stat-val" id="kpi-juzgados-tasa">—</div><div class="stat-lbl">% Resolución</div></div>
      <div class="stat"><div class="stat-val" id="kpi-juzgados-mora" style="color:#fca5a5">—</div><div class="stat-lbl">Mora crítica</div></div>
    </div>
    <p>1ª Instancia · Mora · Ranking · Cuellos de botella</p>
  </a>
  <a class="card" href="/manual" style="border-color:#7c3aed">
    <div class="icon">📖</div><h2>Manual</h2>
    <p>Indicadores · Fuentes · Instrucciones de uso</p>
  </a>
</div>
{FOOTER}
<script>
(function() {{
  function setTxt(id, val) {{ var el = document.getElementById(id); if (el) el.textContent = val; }}
  function fmtPct(n) {{ return (n === null || n === undefined || isNaN(n)) ? 'S/D' : n + '%'; }}
  function fmtInt(n) {{ return (n === null || n === undefined || isNaN(n)) ? 'S/D' : Number(n).toLocaleString('es-AR'); }}

  fetch('/estrategico/api/kpis').then(function(r){{ return r.json(); }}).then(function(d) {{
    setTxt('kpi-corte-ministros', fmtInt(d.ministros_csjn));
    setTxt('kpi-consejo-vacantes', fmtInt(d.total_vacantes));
    setTxt('kpi-consejo-tasa', fmtPct(d.tasa_vacancia_pct));
  }}).catch(function(){{}});

  fetch('/operativo/api/camaras').then(function(r){{ return r.json(); }}).then(function(d) {{
    setTxt('kpi-camaras-total', fmtInt(d.n_camaras));
  }}).catch(function(){{}});

  fetch('/operativo/api/nacional').then(function(r){{ return r.json(); }}).then(function(d) {{
    setTxt('kpi-nacional-total', fmtInt(d.total));
    setTxt('kpi-nacional-alto', fmtInt(d.kpis && d.kpis.semaforo ? d.kpis.semaforo['🔴'] : null));
  }}).catch(function(){{}});

  fetch('/operativo/api/kpis').then(function(r){{ return r.json(); }}).then(function(d) {{
    setTxt('kpi-juzgados-tasa', fmtPct(d.tasa_resolucion));
    setTxt('kpi-juzgados-mora', fmtInt(d.causas_criticas));
  }}).catch(function(){{}});
}})();
</script>
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
      <div class="titulo">Ph.D. in Economics</div>
      <p>
        Especialista en análisis algorítmico y el control ciudadano de la transparencia.
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
      <li><strong>Ph.D. of Philosophy, Major in Economics</strong> — Atlantic International University, USA · 2015</li>
      <li><strong>Master en Administración Estratégica</strong> — Universidad de Belgrano · 1997</li>
      <li><strong>Master in International Business</strong> — École Nationale des Ponts et Chaussées, Francia · 1995</li>
      <li><strong>Contador Público Nacional</strong> — Universidad de Morón · 1984</li>
      <li>Diploma en Business Data Science · Diploma en Business Analytics — Universidad de Aconcagua</li>
      <li>Perito Judicial en Delitos Económicos · Master en Compliance Officer — ESNECA Business School</li>
    </ul>
  </div>

  <div class="bloque">
    <h3>Actividad Académica y de Investigación</h3>
    <ul>
      <li>Co-director de la Diplomatura en Data Science — Universidad del Museo Social Argentino</li>
      <li>Profesor de la Diplomatura en Business Analytics — Universidad de Aconcagua</li>
      <li>Desarrollador del Sistema de Monitoreo Judicial — indicadores IRA, CEPEJ, WJP adaptados al contexto argentino</li>
      <li>Análisis de datos judiciales con fuentes públicas: datos.jus.gob.ar, estadisticas.pjn.gov.ar, CSJN</li>
      <li>ORCID: <a href="https://orcid.org/0000-0001-8884-4811" target="_blank">0000-0001-8884-4811</a> · Scopus: 57210103809 · ResearchGate: <a href="https://www.researchgate.net/profile/Vincenzo-Monteverde" target="_blank">perfil</a></li>
    </ul>
  </div>

  <div class="bloque">
    <h3>Publicaciones</h3>
    <ul>
      <li>
        <strong><a href="https://www.amazon.com/-/es/vicente-monteverde-ebook/dp/B0FKN699R1/" target="_blank">
          Algorithms for Fraud and Corruption: Detection
        </a></strong> — Kindle Edition · 219 págs. · Inglés · Agosto 2025<br>
        <span style="font-size:.81rem;color:var(--muted)">
          Aplicación práctica de algoritmos avanzados (machine learning, detección de anomalías)
          para detectar, prevenir y mitigar fraude y corrupción en escenarios reales.
          JEL: C45, C53, D73, G28, K42.
        </span>
      </li>
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
_MANUAL_CSS = """
.wrap{max-width:900px;margin:0 auto;padding:32px 24px}
.hero-manual{text-align:center;padding:28px 0 20px}
.hero-manual h1{font-size:1.7rem;font-weight:800}
.hero-manual h1 span{color:var(--gold)}
.hero-manual p{color:var(--muted);font-size:.88rem;margin-top:6px}

/* Índice lateral */
.layout{display:grid;grid-template-columns:210px 1fr;gap:28px;align-items:start}
@media(max-width:750px){.layout{grid-template-columns:1fr}}
.sidebar{position:sticky;top:62px;background:var(--card);border-radius:10px;
          padding:16px;font-size:.81rem}
.sidebar h3{font-size:.68rem;text-transform:uppercase;letter-spacing:2px;
             color:var(--gold);margin-bottom:10px}
.sidebar a{display:block;color:var(--muted);text-decoration:none;
            padding:5px 8px;border-radius:5px;margin-bottom:2px}
.sidebar a:hover{background:var(--card2);color:var(--text)}
.sidebar .sep{border-top:1px solid var(--border);margin:8px 0}

/* Secciones */
.seccion{margin-bottom:36px;scroll-margin-top:70px;text-transform:none;letter-spacing:normal}
.sec-titulo{font-size:.72rem;text-transform:uppercase;letter-spacing:2px;
             color:var(--gold);margin-bottom:14px;padding-left:2px;
             border-left:3px solid var(--gold);padding-left:10px}
.bloque{background:var(--card);border-radius:10px;padding:20px 24px;margin-bottom:14px}
.bloque h3{font-size:.95rem;font-weight:700;margin-bottom:10px;color:var(--text)}
.bloque h4{font-size:.82rem;font-weight:700;color:var(--gold2);margin:14px 0 6px}
.bloque p,.bloque li{font-size:.86rem;color:var(--muted);line-height:1.8}
.bloque ul{padding-left:18px}
.bloque strong{color:var(--text)}
.bloque code{background:#0a1628;color:#86efac;padding:2px 7px;border-radius:4px;font-size:.83rem}

/* Indicador card */
.ind-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px;margin-bottom:14px}
.ind{background:var(--card);border-radius:10px;padding:18px 20px;border-top:3px solid var(--blue)}
.ind.gold{border-color:var(--gold)}
.ind.red{border-color:var(--red)}
.ind.green{border-color:var(--green)}
.ind.purple{border-color:#7c3aed}
.ind h4{font-size:.85rem;font-weight:700;margin-bottom:6px}
.ind .formula{font-family:monospace;font-size:.78rem;background:#0a1628;
               color:#86efac;padding:5px 10px;border-radius:4px;margin:8px 0}
.ind p{font-size:.8rem;color:var(--muted);line-height:1.65}
.ind .bench{font-size:.75rem;margin-top:8px;padding:4px 10px;border-radius:4px;
             background:#0f1e3a;color:#93c5fd}

/* Semáforo */
.semaforo-tabla{width:100%;border-collapse:collapse;font-size:.83rem;margin-top:10px}
.semaforo-tabla th{text-align:left;padding:8px 12px;background:#0a1628;color:var(--muted);
                    font-size:.72rem;text-transform:uppercase;letter-spacing:1px}
.semaforo-tabla td{padding:9px 12px;border-bottom:1px solid var(--border);color:var(--muted)}
.semaforo-tabla tr:last-child td{border-bottom:none}
.s-rojo{color:#fca5a5;font-weight:700} .s-amarillo{color:#fde68a;font-weight:700}
.s-verde{color:#86efac;font-weight:700}

/* Pasos */
.paso{display:flex;gap:16px;margin-bottom:14px;align-items:flex-start}
.paso .num{background:var(--gold);color:#000;font-weight:800;font-size:.85rem;
            width:28px;height:28px;border-radius:50%;display:flex;align-items:center;
            justify-content:center;flex-shrink:0;margin-top:2px}
.paso .txt h4{font-size:.88rem;font-weight:700;margin-bottom:4px}
.paso .txt p{font-size:.83rem;color:var(--muted);line-height:1.65}
"""


@app.get("/manual", response_class=HTMLResponse)
def manual():
    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8">
<title>Manual de Usuario — Monitor Judicial</title>
<style>{BASE_CSS}{_MANUAL_CSS}</style></head><body>
{nav_html("manual")}
<div class="wrap">
  <div class="hero-manual">
    <h1>📖 Manual de <span>Usuario</span></h1>
    <p>Guía de uso e interpretación de indicadores — Sistema de Monitoreo Judicial PJN</p>
    <p><a href="/manual/en" style="color:var(--gold)">🌐 Read in English</a></p>
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
      <a href="#grafos">Red de vacantes</a>
      <a href="#funcionamiento">Cómo funciona</a>
      <a href="#relaciones">Relación con otros sitios</a>
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

<div id="grafos" class="seccion bloque">
  <h2>🕸️ Grafo de información: red de vacantes</h2>
  <p>Es el grafo de los datos del sitio (página <a href="/red">Red de vacantes</a>). Cada <strong>círculo</strong> es una de las 30 cámaras, con sus juzgados y tribunales: su tamaño depende de la cantidad de cargos y su color de la vacancia (verde, menor al 25 %; ámbar, de 25 % a 50 %; rojo, mayor al 50 %). Cada <strong>cuadrado</strong> es el ámbito en el que figura el concurso de esas vacantes. Una <strong>línea</strong> une una cámara con un ámbito cuando tiene vacantes allí, y es más gruesa cuantas más tiene.</p>
  <p>Al hacer clic en una cámara se ven sus cargos, cuántas vacantes tienen subrogante y en qué ámbito están sus concursos; al hacer clic en un ámbito, sus cámaras. El ámbito es el que publica datos.jus.gob.ar: no indica cuánto tiempo lleva el concurso ni si está demorado. La red no incluye nombres de personas.</p>
</div>

<div id="funcionamiento" class="seccion bloque">
  <h2>⚙️ Grafo de funcionamiento: cómo trabaja este sitio</h2>
  <p>Muestra de qué fuentes toma los datos, qué procesos automáticos los transforman, dónde se guardan y qué publica. Cada nodo lleva su nombre; hacé clic en uno para ver de dónde recibe datos y a qué alimenta.</p>
  <iframe class="grafo-func" src="https://mapa.ecosistematransparencia.com.ar/funcionamiento?sitio=justicia&amp;embed=1" title="Cómo funciona este sitio" loading="lazy" style="width:100%;height:640px;border:1px solid #cbd5e1;border-radius:10px;background:#fff"></iframe>
  <p style="font-size:.85em"><a href="https://mapa.ecosistematransparencia.com.ar/funcionamiento?sitio=justicia" target="_blank" rel="noopener">Abrir en pantalla completa ↗</a></p>
  <script>window.addEventListener("message", e => {{ if (e.origin !== "https://mapa.ecosistematransparencia.com.ar" || !e.data || !e.data.grafoAltura) return; document.querySelectorAll("iframe.grafo-func").forEach(f => {{ if (f.contentWindow === e.source) f.style.height = (e.data.grafoAltura + 4) + "px"; }}); }});</script>
</div>

<div id="relaciones" class="seccion bloque">
  <h2>🕸️ Relación con los otros sitios del ecosistema</h2>
  <p>Este sitio es parte del <strong>Ecosistema de Transparencia</strong>: once monitores que se consultan entre sí. Abajo, con qué sitios intercambia datos (<em>usa →</em> = toma datos de ese sitio; <em>← lo usa</em> = ese sitio toma datos de este) y de qué fuentes oficiales se alimenta. El grafo es interactivo: hacé clic en cualquier sitio para ver su ficha.</p>
  <iframe src="https://mapa.ecosistematransparencia.com.ar/grafo?embed=1&amp;nodo=justicia" title="Relación con los otros sitios del ecosistema" loading="lazy"
          style="width:100%;height:560px;border:1px solid #cbd5e1;border-radius:10px;background:#fff"></iframe>
  <p style="font-size:.85em"><a href="https://mapa.ecosistematransparencia.com.ar/grafo" target="_blank" rel="noopener">Abrir el grafo completo ↗</a></p>
  <h3>Conexiones</h3>
  <ul><li><strong>← lo usa Monitor IRI</strong>: Toma magistrados y vacantes para el riesgo financiero, operativo y de datos.</li><li><strong>← lo usa Mapa</strong>: Enlace y estado en vivo del sitio.</li></ul>
  <h3>Fuentes oficiales</h3>
  <ul><li>datos.jus.gob.ar</li><li>CSJN</li><li>Estadísticas PJN</li></ul>
  <p style="font-size:.85em">Detalle de todas las conexiones y de cómo se verifican las cifras entre sitios: <a href="https://mapa.ecosistematransparencia.com.ar/manual#conexiones" target="_blank" rel="noopener">mapa.ecosistematransparencia.com.ar/manual#conexiones</a></p>
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


# ── User manual (English) ─────────────────────────────────────────────────────
@app.get("/manual/en", response_class=HTMLResponse)
def manual_en():
    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<title>User Manual — Judicial Monitor</title>
<style>{BASE_CSS}{_MANUAL_CSS}</style></head><body>
{nav_html("manual")}
<div class="wrap">
  <div class="hero-manual">
    <h1>📖 User <span>Manual</span></h1>
    <p>Guide to using the dashboard and reading its indicators — PJN Judicial Monitoring System</p>
    <p><a href="/manual" style="color:var(--gold)">🌐 Leer en español</a></p>
  </div>

  <div class="layout">
    <!-- SIDEBAR -->
    <div class="sidebar">
      <h3>Contents</h3>
      <a href="#que-es">What is the system?</a>
      <a href="#navegacion">How to navigate</a>
      <div class="sep"></div>
      <a href="#indicadores">Indicators</a>
      <a href="#ira">↳ IRA</a>
      <a href="#clearance">↳ Clearance Rate</a>
      <a href="#disposition">↳ Disposition Time</a>
      <a href="#mora">↳ % Backlog</a>
      <a href="#wjp">↳ WJP</a>
      <a href="#cepej">↳ CEPEJ</a>
      <a href="#vacancia">↳ Vacancy</a>
      <a href="#costo">↳ Cost per Case</a>
      <div class="sep"></div>
      <a href="#fuentes">Data sources</a>
      <a href="#grafos">Vacancies network</a>
      <a href="#funcionamiento">How it works</a>
      <a href="#relaciones">Other sites</a>
      <a href="#limitaciones">Limitations</a>
    </div>

    <!-- CONTENT -->
    <div>

      <!-- What is it? -->
      <div class="seccion" id="que-es">
        <div class="sec-titulo">What is the Judicial Monitoring System?</div>
        <div class="bloque">
          <p>
            It is an academic audit platform for the <strong>Judiciary of the Argentine Nation (PJN)</strong>
            that builds algorithmic indicators from official public data.
            Its goal is to provide objective, comparable metrics that promote
            transparency and informed debate about how the judiciary works.
          </p>
          <br>
          <p>
            The indicators apply recognized international methodologies
            (WJP, CEPEJ, V-Dem, UN SDG 16) adapted to the Argentine context.
            <strong>They imply no value judgment or finding of responsibility</strong>
            about any judicial person or body.
          </p>
        </div>
      </div>

      <!-- Navigation -->
      <div class="seccion" id="navegacion">
        <div class="sec-titulo">How to Navigate the Dashboard</div>
        <div class="paso">
          <div class="num">1</div>
          <div class="txt">
            <h4>⚖️ Supreme Court (Corte Suprema)</h4>
            <p>Strategic indicators for the CSJN: high-impact rulings, resolution times, composition. Data from WJP, V-Dem and international judicial independence rankings.</p>
          </div>
        </div>
        <div class="paso">
          <div class="num">2</div>
          <div class="txt">
            <h4>🏛️ Council of the Magistracy (Consejo de la Magistratura)</h4>
            <p>Vacant positions, recent appointments, ongoing selection contests, substitution index. Cross-checked against the impact on operational latency.</p>
          </div>
        </div>
        <div class="paso">
          <div class="num">3</div>
          <div class="txt">
            <h4>🌐 International Indicators</h4>
            <p>WJP Rule of Law Index, Transparency International CPI, World Bank WGI, V-Dem. Regional comparisons with Latin America &amp; the Caribbean (LAC) and the OECD.</p>
          </div>
        </div>
        <div class="paso">
          <div class="num">4</div>
          <div class="txt">
            <h4>🏢 Courts of Appeals (Cámaras de Apelación)</h4>
            <p>Federal and national second instance. Latency, clearance rate, appeals filed.</p>
          </div>
        </div>
        <div class="paso">
          <div class="num">5</div>
          <div class="txt">
            <h4>🗺️ National PJN</h4>
            <p>Full view of the 301 courts surveyed. Table filterable by jurisdiction, IRA traffic light, search by name or judge. Exportable to CSV.</p>
          </div>
        </div>
        <div class="paso">
          <div class="num">6</div>
          <div class="txt">
            <h4>📋 Trial Courts (Juzgados, 1st instance)</h4>
            <p>Detailed operational dashboard: backlog ranking, pending cases, latency by percentile (P50/P75/P90), side panel with per-court detail.</p>
          </div>
        </div>
      </div>

      <!-- Indicators -->
      <div class="seccion" id="indicadores">
        <div class="sec-titulo">Indicators — Full Reference</div>

        <!-- IRA -->
        <div class="bloque" id="ira">
          <h3>🔴 IRA — Algorithmic Risk Index</h3>
          <p>Composite score (0–100) combining five dimensions of operational risk for each court. The higher the IRA, the more urgent an intervention.</p>
          <div class="formula">IRA = backlog(30) + clearance(25) + latency(20) + accumulation(15) + vacancy(10)</div>
          <h4>Components</h4>
          <ul>
            <li><strong>% Backlog (max. 30 pts):</strong> Cases unresolved for more than 2 years. Weighted × 1.2.</li>
            <li><strong>Clearance Rate (max. 25 pts):</strong> Penalizes CR &lt; 100% (not everything that comes in is resolved).</li>
            <li><strong>Latency/Disposition Time (max. 20 pts):</strong> Excess over the CEPEJ benchmark of 230 days.</li>
            <li><strong>Accumulation of pending cases (max. 15 pts):</strong> A closing/opening ratio &gt; 1 indicates overflow.</li>
            <li><strong>Vacancy without a selection contest (10 pts):</strong> Vacant court with no active process to fill it.</li>
          </ul>
          <table class="semaforo-tabla" style="margin-top:14px">
            <tr><th>Traffic light</th><th>IRA range</th><th>Meaning</th></tr>
            <tr><td class="s-rojo">🔴 High risk</td><td>≥ 60</td><td>Priority intervention recommended</td></tr>
            <tr><td class="s-amarillo">🟡 Medium risk</td><td>30–59</td><td>Enhanced monitoring</td></tr>
            <tr><td class="s-verde">🟢 Normal</td><td>&lt; 30</td><td>Operating within parameters</td></tr>
          </table>
        </div>

        <!-- Clearance Rate -->
        <div class="bloque" id="clearance">
          <h3>📊 Clearance Rate</h3>
          <p>Measures a court's ability to resolve cases relative to the cases it receives. A core indicator of the <strong>CEPEJ</strong> (Council of Europe) and the <strong>WJP</strong>.</p>
          <div class="formula">CR = Cases resolved / Cases filed × 100</div>
          <ul>
            <li><strong>CR = 100%:</strong> Exactly what comes in is resolved — perfect balance.</li>
            <li><strong>CR &gt; 100%:</strong> The stock of pending cases goes down (ideal situation).</li>
            <li><strong>CR &lt; 100%:</strong> Backlog builds up — every point below is an increase in judicial debt.</li>
          </ul>
          <div class="bench">📌 CEPEJ benchmark: ≥ 100% · Argentina average: 16.5% · WJP Factor 7 (Civil Justice): 0.42/1.00</div>
        </div>

        <!-- Disposition Time -->
        <div class="bloque" id="disposition">
          <h3>⏱️ Disposition Time</h3>
          <p>Average time in days a court takes to resolve a case from filing. Computed on civil cases with filing and resolution dates in the orality (<em>oralidad</em>) program data.</p>
          <div class="formula">DT = Average of (resolution_date − filing_date) in days</div>
          <ul>
            <li>Includes both resolved and active cases (active ones estimated up to today).</li>
            <li>Percentiles <code>P50</code> (median), <code>P75</code> and <code>P90</code> are reported to show the distribution.</li>
          </ul>
          <div class="bench">📌 CEPEJ benchmark: ≤ 230 days · Argentina average: 2,314 days (~6.3 years) · 100% of courts with data are above the benchmark</div>
        </div>

        <!-- % Backlog -->
        <div class="bloque" id="mora">
          <h3>⚠️ % Backlog (&gt; 2 years)</h3>
          <p>Percentage of cases that have gone more than 730 days without resolution since filing. An indicator of the system's "critical queue".</p>
          <div class="formula">% Backlog = Active cases &gt; 730 days / Total cases × 100</div>
          <div class="bench">📌 Alert: &gt; 15% · Source: datos_jus/oralidad — individual civil cases (75,894 cases surveyed)</div>
        </div>

        <!-- WJP -->
        <div class="bloque" id="wjp">
          <h3>🌐 WJP Rule of Law Index</h3>
          <p>Annual index of the <strong>World Justice Project</strong> measuring the rule of law in 142 countries. Scale 0–1 (higher = better). Argentina 2023: <strong>0.47</strong>.</p>
          <h4>The 4 factors most relevant to the PJN</h4>
          <ul>
            <li><strong>Factor 1 — Constraints on Government Powers:</strong> ARG 0.56 · LAC 0.52 · OECD 0.72</li>
            <li><strong>Factor 2 — Absence of Corruption:</strong> ARG 0.39 · LAC 0.43 · OECD 0.71</li>
            <li><strong>Factor 7 — Civil Justice:</strong> ARG 0.42 · LAC 0.44 · OECD 0.68</li>
            <li><strong>Factor 8 — Criminal Justice:</strong> ARG 0.38 · LAC 0.40 · OECD 0.62</li>
          </ul>
          <h4>vs_wjp_civil in the dashboard</h4>
          <p>For each court it shows the Clearance Rate normalized to a 0–1 scale. <code>gap_wjp_civil</code> is the distance to the WJP benchmark of 0.42: negative values mean the court is below the international standard.</p>
          <div class="bench">📌 Source: worldjusticeproject.org · 2023 data</div>
        </div>

        <!-- CEPEJ -->
        <div class="bloque" id="cepej">
          <h3>🏛️ CEPEJ — European Benchmarks</h3>
          <p>The <strong>European Commission for the Efficiency of Justice</strong> sets reference standards that are used in judicial evaluations in Latin America (RECPJ/CEJAS).</p>
          <ul>
            <li><strong>vs_cepej_cr:</strong> <code>OK</code> if CR ≥ 100%, <code>BAJO</code> (low) if CR &lt; 100%.</li>
            <li><strong>vs_cepej_dt:</strong> <code>OK</code> if DT ≤ 230 days, <code>ALTO</code> (high) if it exceeds the benchmark, <code>—</code> no data.</li>
          </ul>
          <div class="bench">📌 Clearance Rate benchmark: 100% · Disposition Time benchmark: 230 days (civil proceedings)</div>
        </div>

        <!-- Vacancy -->
        <div class="bloque" id="vacancia">
          <h3>⬜ Vacancy Rate</h3>
          <p>Percentage of judicial positions without an appointed holder out of all positions established by law.</p>
          <div class="formula">Vacancy Rate = (Total positions − Active) / Total positions × 100</div>
          <ul>
            <li>Source: magistrados.json (datos.jus.gob.ar)</li>
            <li>A vacant position with no active selection contest adds 10 pts to the court's IRA.</li>
            <li>A position covered by a substitute (temporarily filled) adds no IRA points but is recorded.</li>
          </ul>
          <div class="bench">📌 Current PJN rate: 32.9% (540/1,643 vacant positions) · Source: CSJN 2024</div>
        </div>

        <!-- Cost -->
        <div class="bloque" id="costo">
          <h3>💰 Cost per Case</h3>
          <p>Estimate of the fiscal cost per case handled in each court. It divides the estimated annual budget per court by its total case volume.</p>
          <div class="formula">Cost/Case = Estimated annual budget / (Pending + Resolved)</div>
          <ul>
            <li><strong>Base budget:</strong> ARS 500,000,000/year per court (PJN 2024: ~ARS 1.1 trillion / ~1,400 courts).</li>
            <li>Courts with a high caseload have a lower cost per case.</li>
            <li>Courts with few cases show a high cost per case — possible scale inefficiency.</li>
          </ul>
          <div class="bench">📌 Current range: ARS 78,000 – 500,000,000/case · Median: ARS 7.7M/case</div>
        </div>

      </div><!-- /indicators -->

      <!-- Sources -->
      <div class="seccion" id="fuentes">
        <div class="sec-titulo">Data Sources</div>
        <div class="bloque">
          <ul>
            <li><strong>datos.jus.gob.ar</strong> — Judges, civil orality program (75,894 cases), vacancies</li>
            <li><strong>estadisticas.pjn.gov.ar</strong> — CSVs of rulings, proceedings and appeals by jurisdiction</li>
            <li><strong>csjn.gov.ar</strong> — Supreme Court rulings, composition, decisions (acordadas)</li>
            <li><strong>mpf.gov.ar / mpd.gov.ar</strong> — Prosecutors and public defenders</li>
            <li><strong>worldjusticeproject.org</strong> — WJP Rule of Law Index 2023</li>
            <li><strong>transparency.org</strong> — CPI 2023</li>
            <li><strong>databank.worldbank.org</strong> — World Bank WGI 2022</li>
            <li><strong>v-dem.net</strong> — V-Dem Institute JCI 2023</li>
            <li><strong>coe.int/cepej</strong> — CEPEJ benchmarks 2022</li>
          </ul>
          <br>
          <p>All data is publicly accessible. The scrapers run against the official APIs and do not modify or alter the sources.</p>
        </div>
      </div>

<div id="grafos" class="seccion bloque">
  <h2>🕸️ Information graph: vacancies network</h2>
  <p>This is the graph of the data on this site (the <a href="/red?lang=en">Vacancies network</a> page). Each <strong>circle</strong> is one of the 30 courts of appeals with its lower courts and tribunals: its size depends on the number of posts and its colour on the vacancy rate (green, below 25%; amber, 25% to 50%; red, above 50%). Each <strong>square</strong> is the body listed for the selection process of those vacancies. A <strong>line</strong> joins a court of appeals to a body when it has vacancies there, and it is thicker the more it has.</p>
  <p>Clicking a court of appeals shows its posts, how many vacancies have an acting judge and which body handles its selection processes; clicking a body shows its courts. The body is the one published by datos.jus.gob.ar: it does not show how long the process has taken or whether it is delayed. The network does not include names of individuals.</p>
</div>

<div id="funcionamiento" class="seccion bloque">
  <h2>⚙️ Workflow graph: how this site works</h2>
  <p>It shows where the site gets its data, which automated processes transform it, where it is stored and what it publishes. Every node carries its name; click one to see where it gets data from and what it feeds.</p>
  <iframe class="grafo-func" src="https://mapa.ecosistematransparencia.com.ar/funcionamiento?sitio=justicia&amp;embed=1&amp;lang=en" title="How this site works" loading="lazy" style="width:100%;height:640px;border:1px solid #cbd5e1;border-radius:10px;background:#fff"></iframe>
  <p style="font-size:.85em"><a href="https://mapa.ecosistematransparencia.com.ar/funcionamiento?sitio=justicia&amp;lang=en" target="_blank" rel="noopener">Open full screen ↗</a></p>
  <script>window.addEventListener("message", e => {{ if (e.origin !== "https://mapa.ecosistematransparencia.com.ar" || !e.data || !e.data.grafoAltura) return; document.querySelectorAll("iframe.grafo-func").forEach(f => {{ if (f.contentWindow === e.source) f.style.height = (e.data.grafoAltura + 4) + "px"; }}); }});</script>
</div>

<div id="relaciones" class="seccion bloque">
  <h2>🕸️ How this site connects to the rest of the ecosystem</h2>
  <p>This site is part of the <strong>Transparency Ecosystem</strong>: eleven monitors that query each other. Below, which sites it exchanges data with (<em>uses →</em> = takes data from that site; <em>← used by</em> = that site takes data from this one) and which official sources feed it. The graph is interactive: click any site to see its profile.</p>
  <iframe src="https://mapa.ecosistematransparencia.com.ar/grafo?embed=1&amp;nodo=justicia&amp;lang=en" title="How this site connects to the rest of the ecosystem" loading="lazy"
          style="width:100%;height:560px;border:1px solid #cbd5e1;border-radius:10px;background:#fff"></iframe>
  <p style="font-size:.85em"><a href="https://mapa.ecosistematransparencia.com.ar/grafo?lang=en" target="_blank" rel="noopener">Open the full graph ↗</a></p>
  <h3>Connections</h3>
  <ul><li><strong>← used by Monitor IRI</strong>: Pulls judges and vacancies for financial, operational and data risk.</li><li><strong>← used by Mapa</strong>: Link and live status of the site.</li></ul>
  <h3>Official sources</h3>
  <ul><li>datos.jus.gob.ar</li><li>Supreme Court (CSJN)</li><li>PJN statistics</li></ul>
  <p style="font-size:.85em">Every connection in detail, and how figures are cross-checked between sites: <a href="https://mapa.ecosistematransparencia.com.ar/en/manual#conexiones" target="_blank" rel="noopener">mapa.ecosistematransparencia.com.ar/en/manual#conexiones</a></p>
</div>

      <!-- Limitations -->
      <div class="seccion" id="limitaciones">
        <div class="sec-titulo">Limitations and Warnings</div>
        <div class="bloque">
          <ul>
            <li>The orality data covers <strong>individual civil cases</strong> from courts that joined the orality program — it does not represent the whole system.</li>
            <li>The average <strong>clearance rate</strong> of 16.5% is low partly because many courts carry unresolved historical cases that weigh on the denominator.</li>
            <li><strong>Cost per case</strong> is an estimate based on an average budget; it does not reflect differences in size, jurisdiction or staffing.</li>
            <li>The <strong>international indicators</strong> (WJP, CEPEJ) were designed for whole judicial systems — applying them to individual courts is a methodological adaptation by the author.</li>
            <li>The system has no access to <strong>individual case files</strong> or to each court's internal management data.</li>
          </ul>
        </div>
      </div>

    </div><!-- /content -->
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


# ─────────────────────────────────────────────────────────────────────────────
# API — AGENTIC AI (explicaciones narrativas vía Claude)
# ─────────────────────────────────────────────────────────────────────────────
# Endpoint genérico único: cualquier pantalla (Corte, Consejo, Cámaras,
# Nacional PJN, Juzgados) manda su `tipo` + el dict que ya usa para pintarse,
# y agentic_ai.py arma el prompt correspondiente. Sumar IA a una pantalla
# nueva no requiere un endpoint nuevo, solo un botón que llame a este.

class ExplicarIARequest(BaseModel):
    tipo: str = "generico"
    datos: dict = {}


# ── Límites de uso del asistente de IA ───────────────────────────────────────
# 2026-10-09: /api/ia/explicar era público y sin límite: cualquiera podía
# llamarlo en bucle y cada llamada se cobra en la ANTHROPIC_API_KEY del
# proyecto. Ahora:
#   · máximo IA_LIMITE_POR_IP_HORA consultas por IP por hora (default 10)
#   · máximo IA_LIMITE_DIARIO consultas en total por día (default 200)
#   · `tipo` debe ser una pantalla conocida y `datos` no puede superar 8 KB
# Los contadores viven en memoria: se reinician si Railway reinicia la app,
# lo cual es aceptable para este uso. Ajustables con variables de entorno.
import json as _json, threading, time
from collections import defaultdict, deque
from fastapi import Request
from fastapi.responses import JSONResponse

IA_LIMITE_POR_IP_HORA = int(os.getenv("IA_LIMITE_POR_IP_HORA", "10"))
IA_LIMITE_DIARIO      = int(os.getenv("IA_LIMITE_DIARIO", "200"))
IA_MAX_BYTES_DATOS    = 8_000
IA_TIPOS_VALIDOS      = {"juzgado", "camara", "consejo", "corte", "candidatos", "generico"}

_ia_lock = threading.Lock()
_ia_por_ip = defaultdict(deque)   # ip -> timestamps de la última hora
_ia_global = deque()              # timestamps de las últimas 24 h


def _ip_cliente(request: Request) -> str:
    # Railway pone la IP real del visitante en X-Forwarded-For
    xff = request.headers.get("x-forwarded-for", "")
    return xff.split(",")[0].strip() if xff else (request.client.host if request.client else "?")


def _ia_rechazo(motivo: str, status: int) -> JSONResponse:
    # Mismo formato que agentic_ai._no_disponible → el frontend lo muestra tal cual
    return JSONResponse({"disponible": False, "motivo": motivo}, status_code=status)


def _ia_registrar(ip: str):
    """Devuelve None si la consulta entra en los límites (y la cuenta),
    o un mensaje de error si no."""
    ahora = time.time()
    with _ia_lock:
        while _ia_global and ahora - _ia_global[0] > 86_400:
            _ia_global.popleft()
        cola = _ia_por_ip[ip]
        while cola and ahora - cola[0] > 3_600:
            cola.popleft()
        if not cola:
            _ia_por_ip.pop(ip, None)
            cola = _ia_por_ip[ip]
        if len(_ia_global) >= IA_LIMITE_DIARIO:
            return "Se alcanzó el límite diario de consultas al asistente de IA. Probá de nuevo mañana."
        if len(cola) >= IA_LIMITE_POR_IP_HORA:
            return (f"Alcanzaste el límite de {IA_LIMITE_POR_IP_HORA} consultas por hora "
                    "al asistente de IA. Probá de nuevo más tarde.")
        cola.append(ahora)
        _ia_global.append(ahora)
    return None


@app.get("/api/red-vacantes")
def red_vacantes():
    """Grafo de información: cámaras ↔ ámbito del concurso de sus vacantes.
    Solo cifras: el nombre que figura en una vacante es el del último titular,
    no el de quien ocupa el cargo, y por eso no se usa."""
    import json
    from collections import Counter, defaultdict

    def leer(nombre):
        with open(os.path.join(ROOT, nombre), encoding="utf-8") as f:
            return json.load(f)

    cargos, vacantes = leer("magistrados.json"), leer("vacantes.json")
    camaras, por_arista, por_ambito = {}, Counter(), Counter()
    for c in cargos:
        n = c.get("camara") or "Sin cámara"
        d = camaras.setdefault(n, {"cargos": 0, "vacantes": 0, "subrogadas": 0, "sin_subrogante": 0, "no_corresponde": 0,
                                   "tipo": c.get("tipo_justicia"), "provincias": set()})
        d["cargos"] += 1
        if c.get("provincia"):
            d["provincias"].add(c["provincia"])
        if c.get("vacante"):
            d["vacantes"] += 1
            cobertura = c.get("cargo_cobertura")
            if cobertura == "Subrogante":
                d["subrogadas"] += 1
            elif cobertura == "Sin subrogante designado":
                d["sin_subrogante"] += 1
            elif cobertura == "No corresponde":
                d["no_corresponde"] += 1
    for v in vacantes:
        camara, ambito = v.get("camara") or "Sin cámara", v.get("concurso_ambito") or "Sin dato"
        por_arista[(camara, ambito)] += 1
        por_ambito[ambito] += 1
    ids = {n: f"c{i}" for i, n in enumerate(sorted(camaras))}
    nodos = [{"id": ids[n], "tipo": "camara", "label": n, "tipo_justicia": d["tipo"], "cargos": d["cargos"], "vacantes": d["vacantes"],
              "vacancia_pct": round(d["vacantes"] * 100 / d["cargos"], 1), "subrogadas": d["subrogadas"],
              "sin_subrogante": d["sin_subrogante"], "no_corresponde": d["no_corresponde"], "provincias": sorted(d["provincias"])}
             for n, d in sorted(camaras.items())]
    nodos += [{"id": f"a:{a}", "tipo": "ambito", "label": a, "vacantes": n} for a, n in por_ambito.most_common()]
    aristas = [{"from": ids[c], "to": f"a:{a}", "vacantes": n} for (c, a), n in sorted(por_arista.items()) if c in ids]
    total = sum(d["cargos"] for d in camaras.values())
    vac = sum(d["vacantes"] for d in camaras.values())
    return {"nodos": nodos, "aristas": aristas,
            "resumen": {"cargos": total, "vacantes": vac, "vacancia_pct": round(vac * 100 / total, 1) if total else 0,
                        "camaras": len(camaras), "ambitos": len(por_ambito), "fuente": "datos.jus.gob.ar"}}


@app.get("/red", response_class=HTMLResponse)
def pagina_red():
    with open(os.path.join(ROOT, "red_vacantes.html"), encoding="utf-8") as f:
        return HTMLResponse(f.read())


@app.get("/frescura.js", include_in_schema=False)
def frescura_js():
    return FileResponse(os.path.join(ROOT, "frescura.js"), media_type="application/javascript")


@app.get("/api/frescura")
def frescura():
    """Ficha de frescura (formato común del ecosistema, ver frescura.py): de
    dónde sale cada dato, qué período cubre, cuándo se cargó y si está atrasado."""
    import json
    from frescura import evaluar

    def leer(*partes):
        try:
            with open(os.path.join(ROOT, *partes), encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    meta = leer("meta_justicia.json")
    abiertos = leer("datos_jus", "datos_jus_meta.json")
    csjn = leer("datos_csjn.json")
    return evaluar("justicia", [
        {"id": "magistrados", "dato": "Magistrados, vacantes y renuncias", "fuente": "datos.jus.gob.ar",
         "fuente_url": meta.get("url_fuente"), "periodo": f"al {meta['fecha_datos']}" if meta.get("fecha_datos") else "sin dato",
         "periodo_fin": meta.get("fecha_datos"), "ultima_carga": meta.get("ultima_actualizacion"),
         "frecuencia": "diaria", "max_dias_carga": 3, "max_dias_periodo": 3},
        {"id": "datos_abiertos", "dato": "Otros datasets de Justicia", "fuente": "datos.jus.gob.ar",
         "periodo": f"{abiertos.get('datasets_ok', 0)} datasets", "ultima_carga": abiertos.get("fin"),
         "frecuencia": "mensual", "max_dias_carga": 40,
         "nota": f"{abiertos['datasets_fallidos']} datasets fallaron en la última descarga." if abiertos.get("datasets_fallidos") else None},
        {"id": "csjn", "dato": "Corte Suprema: composición, anuarios y presupuesto", "fuente": "CSJN (carga manual)",
         "periodo": f"revisado el {csjn['actualizado']}" if csjn.get("actualizado") else "sin dato",
         "periodo_fin": csjn.get("actualizado"), "ultima_carga": None, "frecuencia": "manual, con aviso semanal de cambios",
         "max_dias_periodo": 180},
    ])


@app.get("/api/ia/status")
def ia_status():
    from agentic_ai import ia_disponible
    return {"disponible": ia_disponible()}


@app.post("/api/ia/explicar")
def ia_explicar(req: ExplicarIARequest, request: Request):
    from agentic_ai import explicar
    if req.tipo not in IA_TIPOS_VALIDOS:
        return _ia_rechazo("Tipo de consulta no válido.", 400)
    if len(_json.dumps(req.datos, ensure_ascii=False)) > IA_MAX_BYTES_DATOS:
        return _ia_rechazo("Los datos enviados son demasiado grandes.", 413)
    error = _ia_registrar(_ip_cliente(request))
    if error:
        return _ia_rechazo(error, 429)
    return explicar(req.tipo, req.datos)