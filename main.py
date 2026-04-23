# main.py  —  Entry point FastAPI
# uvicorn main:app --reload --port 8000

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import sys, os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from shared import BASE_CSS, DISCLAIMER, FOOTER, PLOTLY_JS, nav_html

app = FastAPI(title="Monitor Judicial — Ph.D. Monteverde", version="2.0")

from dashboard_estrategico.app import router as router_estrategico
from dashboard_operativo.app   import router as router_operativo
app.include_router(router_estrategico, prefix="/estrategico", tags=["Estratégico"])
app.include_router(router_operativo,   prefix="/operativo",   tags=["Operativo"])


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
.grid{{display:flex;gap:24px;flex-wrap:wrap;justify-content:center;
       padding:0 24px 32px}}
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
  <a class="card" href="/operativo">
    <div class="icon">📋</div><h2>Juzgados</h2>
    <p>1ª Instancia · Mora · Ranking · Cuellos de botella</p>
  </a>
</div>
{FOOTER}
</body></html>""")


# ── Página Apoyar ─────────────────────────────────────────────────────────────
@app.get("/apoyar", response_class=HTMLResponse)
def apoyar():
    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8">
<title>Apoyar el Proyecto — Monitor Judicial</title>
<style>{BASE_CSS}
.apoyar-wrap{{max-width:820px;margin:0 auto;padding:32px 24px}}
.apoyar-wrap h1{{font-size:1.5rem;font-weight:700;margin-bottom:6px}}
.apoyar-wrap h1 span{{color:var(--gold)}}
.apoyar-wrap .sub{{color:var(--muted);font-size:.9rem;margin-bottom:28px;line-height:1.6}}
.contact{{background:var(--card);border-radius:12px;padding:22px 26px;
          border-left:4px solid var(--blue);margin-bottom:20px}}
.contact h2{{font-size:.85rem;text-transform:uppercase;letter-spacing:2px;
             color:var(--blue);margin-bottom:14px}}
.contact p{{font-size:.9rem;color:var(--muted);line-height:1.8}}
.contact a{{color:var(--gold2);text-decoration:none;font-weight:600}}
.donate-block{{background:var(--card);border-radius:12px;padding:22px 26px;
               border-left:4px solid var(--gold);margin-bottom:20px}}
.donate-block h2{{font-size:.85rem;text-transform:uppercase;letter-spacing:2px;
                  color:var(--gold);margin-bottom:16px}}
.tag{{display:inline-block;font-size:.72rem;padding:3px 10px;border-radius:4px;
      font-weight:600;margin-bottom:10px}}
.tag.ars{{background:#1a1500;color:var(--gold)}}
.tag.usd{{background:#0f2a10;color:#86efac}}
.tag.ext{{background:#0f1e3a;color:#93c5fd}}
.row{{margin-bottom:8px;display:flex;gap:12px;align-items:baseline;flex-wrap:wrap}}
.row .lbl{{font-size:.72rem;text-transform:uppercase;color:var(--muted);
           letter-spacing:1px;min-width:80px}}
.row .val{{font-family:monospace;font-size:.88rem;background:#0a1628;
           padding:4px 10px;border-radius:4px;color:var(--text);
           word-break:break-all}}
.divider{{border-top:1px solid var(--border);margin:14px 0}}
.mision{{background:#0f1e3a;border:1px solid var(--gold);border-radius:8px;
         padding:16px 20px;font-size:.85rem;color:#94a3b8;line-height:1.7;
         margin-bottom:20px}}
.mision strong{{color:var(--gold)}}
</style></head><body>
{nav_html("apoyar")}
<div class="apoyar-wrap">
  <h1>💛 Apoyar el <span>Proyecto</span></h1>
  <p class="sub">
    Este sistema de auditoría judicial es desarrollado de forma independiente con
    fines académicos y de transparencia pública. Si el trabajo te resulta útil,
    podés contribuir a su continuidad.
  </p>

  <div class="mision">
    <strong>Misión:</strong> Promover la transparencia y el debate informado sobre
    el funcionamiento del Poder Judicial argentino mediante indicadores algorítmicos
    construidos sobre datos públicos oficiales del Estado.
  </div>

  <div class="contact">
    <h2>✉️ Contacto</h2>
    <p>
      <strong>Ph.D. Vicente Humberto Monteverde</strong><br>
      📧 <a href="mailto:vhmonte@retina.ar">vhmonte@retina.ar</a><br>
      📧 <a href="mailto:viny01958@gmail.com">viny01958@gmail.com</a><br><br>
      Consultas académicas, colaboraciones institucionales y
      acceso a datos ampliados sobre el Poder Judicial.
    </p>
  </div>

  <div class="donate-block">
    <h2>🏦 Datos para Donación</h2>

    <div class="tag ars">🇦🇷 Pesos — Argentina</div>
    <div class="row"><span class="lbl">Tipo</span><span class="val">Caja de Ahorro</span></div>
    <div class="row"><span class="lbl">CBU</span><span class="val">0140005203400552652310</span></div>
    <div class="row"><span class="lbl">Alias</span><span class="val">ALGORIT.MONTE.PESOS</span></div>
    <div class="row"><span class="lbl">Titular</span><span class="val">Vicente Humberto Monteverde</span></div>
    <div class="row"><span class="lbl">CUIL</span><span class="val">20-12034411-1</span></div>

    <div class="divider"></div>
    <div class="tag usd">💵 Dólares — Argentina</div>
    <div class="row"><span class="lbl">Tipo</span><span class="val">Caja de Ahorro Dólares</span></div>
    <div class="row"><span class="lbl">CBU</span><span class="val">0140005204400550329709</span></div>
    <div class="row"><span class="lbl">Alias</span><span class="val">ALGO.MONTE.DOLARES</span></div>
    <div class="row"><span class="lbl">Titular</span><span class="val">Vicente Humberto Monteverde</span></div>

    <div class="divider"></div>
    <div class="tag ext">🌐 Desde el Exterior</div>
    <div class="row"><span class="lbl">Banco</span><span class="val">Banco Santander Montevideo</span></div>
    <div class="row"><span class="lbl">Beneficiario</span><span class="val">Vicente Humberto Monteverde</span></div>
    <div class="row"><span class="lbl">Dirección</span><span class="val">Av. Directorio 3024-PB-Dto 04</span></div>
    <div class="row"><span class="lbl">Cuenta USD</span><span class="val">005200183500</span></div>
    <div class="row"><span class="lbl">Swift</span><span class="val">BSCHUYMM</span></div>
    <div class="row"><span class="lbl">CUIL</span><span class="val">20-12034411-1</span></div>
  </div>
</div>
{FOOTER}
</body></html>""")


# ── Compatibilidad legacy ─────────────────────────────────────────────────────
@app.get("/juzgados", response_class=HTMLResponse)
def legacy():
    return HTMLResponse('<meta http-equiv="refresh" content="0; url=/operativo">')
