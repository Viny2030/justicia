# shared.py  —  Constantes compartidas entre todos los routers
# Importar en cada app.py:  from shared import NAV_CSS, nav_html, DISCLAIMER, BASE_CSS

DISCLAIMER = """<div class="disclaimer">
  ⚠️ <strong>Nota:</strong> Esta herramienta es de carácter experimental y académico.
  Los datos provienen de fuentes públicas oficiales del Estado argentino.
  Los resultados son indicadores algorítmicos de riesgo — no implican juicio de valor,
  acusación ni determinación de responsabilidad sobre ninguna empresa, organismo o persona.
  El objetivo es promover la transparencia y el debate informado sobre el gasto público.
</div>"""

BASE_CSS = """
  :root {
    --bg:#0a1628; --card:#1a2744; --card2:#1e3058;
    --gold:#c9a227; --gold2:#f0c040;
    --blue:#3b82f6; --red:#e63946; --green:#22c55e;
    --text:#e2e8f0; --muted:#94a3b8; --border:#2d4a7a;
  }
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:'Segoe UI',sans-serif;background:var(--bg);color:var(--text);
       padding:0 0 40px}

  /* ── Nav top ── */
  .topnav{display:flex;align-items:center;justify-content:space-between;
          background:#060f1e;border-bottom:2px solid var(--gold);
          padding:0 24px;position:sticky;top:0;z-index:100;height:52px}
  .topnav .brand{color:var(--gold);font-weight:800;text-decoration:none;
                 font-size:1rem;white-space:nowrap;margin-right:24px}
  .topnav .links{display:flex;gap:2px;align-items:center}
  .topnav .links a{color:var(--muted);text-decoration:none;padding:6px 13px;
                   border-radius:6px;font-size:.83rem;transition:all .2s;white-space:nowrap}
  .topnav .links a:hover{background:var(--card2);color:var(--text)}
  .topnav .links a.active{background:var(--card2);color:var(--text);
                           border-bottom:2px solid var(--gold)}
  .topnav .links a.apoyar{background:#1a1500;color:var(--gold);
                           border:1px solid #3a2f00;margin-left:8px}
  .topnav .links a.apoyar:hover{background:#2a2000}

  /* ── Contenido ── */
  .contenido{padding:24px}

  .disclaimer{background:#0f1e3a;border:1px solid var(--gold);border-radius:8px;
              padding:11px 16px;font-size:.78rem;color:#94a3b8;
              margin-bottom:20px;line-height:1.65}
  .disclaimer strong{color:var(--gold)}

  .seccion{font-size:.75rem;text-transform:uppercase;letter-spacing:2px;
           color:var(--gold);margin:22px 0 12px;padding-left:2px}

  .kpi-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));
            gap:14px;margin-bottom:24px}
  .kpi{background:var(--card);border-radius:10px;padding:16px 18px;
       border-left:4px solid var(--blue)}
  .kpi.gold{border-color:var(--gold)}.kpi.rojo{border-color:var(--red)}
  .kpi.verde{border-color:var(--green)}
  .kpi label{font-size:.68rem;text-transform:uppercase;letter-spacing:1px;
             color:var(--muted);display:block;margin-bottom:5px}
  .kpi .val{font-size:1.7rem;font-weight:700;color:var(--text)}
  .kpi .sub{font-size:.74rem;color:var(--muted);margin-top:3px}

  .kpi-t{background:var(--card);border-radius:10px;padding:16px 18px;
          border-top:3px solid var(--gold)}
  .kpi-t label{font-size:.68rem;text-transform:uppercase;letter-spacing:1px;
               color:var(--muted);display:block;margin-bottom:5px}
  .kpi-t .val{font-size:1.7rem;font-weight:700;color:var(--gold)}
  .kpi-t .uni{font-size:.78rem;color:var(--muted);margin-left:3px}
  .kpi-t .sub{font-size:.74rem;color:var(--muted);margin-top:3px}
  .kpi-t .alerta{color:var(--red)}.kpi-t .ok{color:var(--green)}

  .charts{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:20px}
  .chart-box{background:var(--card);border-radius:10px;padding:20px}
  .chart-box h2{font-size:.88rem;margin-bottom:12px;color:var(--text)}
  .chart-box h2 span{color:var(--gold)}
  .chart-full{background:var(--card);border-radius:10px;padding:20px;margin-bottom:20px}
  .chart-full h2{font-size:.88rem;margin-bottom:12px}

  .scope{background:#0f1e3a;border-left:4px solid var(--blue);padding:10px 14px;
         border-radius:6px;font-size:.83rem;color:#93c5fd;margin-bottom:20px}
  .scope a{color:var(--gold);text-decoration:none}
  .info-box{background:#0f1e0f;border-left:4px solid var(--green);padding:10px 14px;
            border-radius:6px;font-size:.81rem;color:#86efac;margin-top:14px}

  .badge{display:inline-block;padding:4px 11px;border-radius:4px;
         font-size:.73rem;font-weight:600;margin-bottom:8px}
  .badge.blue{background:#0f2a50;color:#93c5fd}
  .badge.gold{background:#1a1500;color:var(--gold)}
  .badge.red{background:#3a0f0f;color:#fca5a5}

  .inst-badges{display:flex;gap:12px;margin-bottom:20px;flex-wrap:wrap}
  .controles{display:flex;gap:16px;margin-bottom:20px;flex-wrap:wrap;align-items:center}
  .controles label{font-size:.81rem;color:var(--muted)}
  .controles select,.controles input{background:var(--card);border:1px solid var(--border);
    color:var(--text);padding:6px 12px;border-radius:6px;font-size:.83rem;outline:none}
  .controles select:focus,.controles input:focus{border-color:var(--gold)}

  footer{color:var(--muted);font-size:.76rem;text-align:center;
         line-height:1.8;padding:20px 24px 0;border-top:1px solid var(--border);
         margin-top:8px}
  .loading{color:var(--muted);font-style:italic;padding:8px}
  @media(max-width:700px){.charts{grid-template-columns:1fr}
    .topnav .links a{padding:5px 8px;font-size:.76rem}}
"""

PLOTLY_JS = '<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>'

PLOTLY_BASE = """
const C={bg:'#0a1628',card:'#1a2744',gold:'#c9a227',blue:'#3b82f6',
         red:'#e63946',green:'#22c55e',text:'#e2e8f0',muted:'#94a3b8',grid:'#2d4a7a'};
const L=(x={})=>Object.assign({
  plot_bgcolor:C.card,paper_bgcolor:C.card,
  font:{color:C.text,family:'Segoe UI',size:12},
  margin:{l:10,r:10,t:30,b:40},
  xaxis:{gridcolor:C.grid,linecolor:C.grid},
  yaxis:{gridcolor:C.grid,linecolor:C.grid},
},x);
const fmt=n=>n==null?'S/D':Number(n).toLocaleString('es-AR');
const dias=n=>n==null?'<span class="sub">Sin datos</span>':n+'<span class="uni">días</span>';
"""

FOOTER = """<footer>
  Datos: datos.jus.gob.ar · PJN · CSJN · Consejo de la Magistratura · Ph.D. Monteverde<br>
  Fuente pública oficial del Estado argentino
</footer>"""


def nav_html(activo: str = "") -> str:
    """Genera la barra de navegación top con la pestaña activa marcada."""
    tabs = [
        ("/",                    "🏛️ Inicio",   "inicio"),
        ("/estrategico/corte",   "⚖️ Corte",    "corte"),
        ("/estrategico/consejo", "🏛 Consejo",  "consejo"),
        ("/estrategico/indicadores", "🌐 Indicadores", "indicadores"),
        ("/estrategico/candidatos", "📋 Candidatos", "candidatos"),
        ("/operativo/camaras",   "🏢 Cámaras",  "camaras"),
        ("/operativo",           "📋 Juzgados", "juzgados"),
    ]
    links = ""
    for url, label, key in tabs:
        cls = "active" if activo == key else ""
        links += f'<a href="{url}" class="{cls}">{label}</a>'
    links += '<a href="/apoyar" class="apoyar">💛 Apoyar</a>'
    return f"""<nav class="topnav">
  <a class="brand" href="/">⚖️ Monitor Judicial</a>
  <div class="links">{links}</div>
</nav>"""
