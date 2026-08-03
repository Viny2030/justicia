"""
agentic_ai.py — Agentic AI para el Monitor Judicial (justicia1).

Mismo patrón que se usa en el repo hermano monitor_contratos: usa la API de
Anthropic (Claude) para generar explicaciones narrativas en lenguaje natural
sobre los indicadores que ya calcula el resto del sistema (IRA, vacancia,
clearance rate, etc.), sin volver a tocar los datos.

Genérico por diseño: en vez de una función por sección, expone
`explicar(tipo, datos)` con una plantilla de prompt por `tipo`, para poder
sumar botones "Explicar con IA" en cualquier pantalla (Corte, Consejo,
Cámaras, Nacional PJN, Juzgados) sin duplicar código.

Degradación elegante: si no está configurada ANTHROPIC_API_KEY, o falla la
librería `anthropic`, todas las llamadas devuelven
{"disponible": False, "motivo": "..."} en vez de romper el endpoint.
"""

import os

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")

try:
    import anthropic
    _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None
except ImportError:
    anthropic = None
    _client = None


def ia_disponible() -> bool:
    """True si hay librería `anthropic` instalada Y ANTHROPIC_API_KEY configurada."""
    return _client is not None


def _no_disponible(motivo: str) -> dict:
    return {"disponible": False, "motivo": motivo}


def _pedir_a_claude(system: str, prompt: str, max_tokens: int = 500) -> dict:
    if not ia_disponible():
        if anthropic is None:
            return _no_disponible(
                "La librería 'anthropic' no está instalada en este entorno."
            )
        return _no_disponible(
            "ANTHROPIC_API_KEY no está configurada — el asistente de IA está deshabilitado."
        )
    try:
        resp = _client.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        texto = "".join(
            bloque.text for bloque in resp.content if getattr(bloque, "type", "") == "text"
        )
        return {"disponible": True, "explicacion": texto.strip()}
    except Exception as e:
        return _no_disponible(f"Error al consultar la IA: {e}")


_SYSTEM_BASE = (
    "Sos un analista de transparencia judicial que explica, en español rioplatense "
    "claro y sin tecnicismos innecesarios, indicadores algorítmicos sobre el "
    "funcionamiento del Poder Judicial de la Nación Argentina (magistrados, vacancia, "
    "carga procesal, mora, clearance rate) según la metodología del Ph.D. Vicente "
    "Monteverde. No acusás a nadie de mal desempeño: describís qué significa el "
    "patrón detectado, por qué es relevante para la eficiencia o la transparencia "
    "judicial (no una determinación de responsabilidad), y qué preguntas de control "
    "ciudadano o auditoría ayudarían a contextualizarlo. Sé concreto y breve (4-8 líneas)."
)

# ── Plantillas por tipo de pantalla ──────────────────────────────────────────
# Cada entrada arma el prompt específico a partir del dict `datos` que ya
# calculó el endpoint correspondiente (mismo payload que usa el frontend para
# pintar el panel/tabla). Agregar una pantalla nueva = agregar una entrada acá.

def _prompt_juzgado(d: dict) -> str:
    return f"""Perfil del juzgado/cámara "{d.get('juzgado', '—')}" ({d.get('fuero', '—')}, {d.get('jurisdiccion', '—')}):

- IRA (Índice de Riesgo Algorítmico): {d.get('ira_score', '—')} ({d.get('ira_semaforo', '—')})
- Clearance Rate: {d.get('clearance_rate', '—')}%
- Disposition Time: {d.get('disposition_time', '—')} días
- % Mora (+2 años): {d.get('pct_mora', '—')}%
- Pendientes al cierre: {d.get('pendientes_cierre', '—')}
- Estado del cargo: {"Vacante" if d.get('vacante') else ("Licencia" if d.get('en_licencia') else "Activo")}
- Magistrado: {d.get('magistrado', 'sin designación')}

Explicá qué indica este perfil sobre la eficiencia operativa del juzgado y qué habría que mirar primero."""


def _prompt_consejo(d: dict) -> str:
    return f"""Estado del Consejo de la Magistratura / cargo "{d.get('organo_nombre', d.get('cargo_tipo', '—'))}":

- Tasa de vacancia: {d.get('indice_vacancia_pct', d.get('tasa_vacancia', '—'))}%
- Cargos activos: {d.get('magistrados_activos', '—')}
- Cargos vacantes: {d.get('vacantes', '—')}
- Concurso en trámite: {d.get('concurso_en_tramite', '—')} (Nº {d.get('concurso_numero', '—')})
- Provincia: {d.get('provincia', '—')}
- Último titular: {d.get('ultimo_titular', d.get('nombre_completo', '—'))}

Explicá qué implica este nivel de vacancia/subrogancia para el funcionamiento del fuero y qué pregunta de auditoría ciudadana ayudaría a seguirlo."""


def _prompt_corte(d: dict) -> str:
    return f"""Indicador de la Corte Suprema de Justicia de la Nación:

{d}

Explicá qué indica este dato sobre el funcionamiento de la CSJN y qué contexto adicional ayudaría a interpretarlo."""


def _prompt_candidatos(d: dict) -> str:
    return f"""Base de candidatos a magistrados (CVs presentados en concursos del Consejo de la Magistratura):

- Total de candidatos: {d.get('total', '—')}
- Top universidades de egreso: {d.get('universidades', [])}
- Top provincias de origen: {d.get('provincias', [])}
- Distribución por ámbito de concurso: {d.get('ambitos', [])}

Explicá qué indica esta composición sobre la diversidad geográfica e institucional de los candidatos a magistrados, y qué pregunta de transparencia ayudaría a profundizarlo."""


def _prompt_generico(d: dict) -> str:
    return f"""Datos del indicador:

{d}

Explicá en términos simples qué indica este dato dentro del contexto de transparencia y eficiencia judicial, y qué pregunta de control ciudadano permitiría profundizarlo."""


_PLANTILLAS = {
    "juzgado":     _prompt_juzgado,
    "camara":      _prompt_juzgado,
    "consejo":     _prompt_consejo,
    "corte":       _prompt_corte,
    "candidatos":  _prompt_candidatos,
}


def explicar(tipo: str, datos: dict) -> dict:
    """Punto de entrada único para todas las pantallas.

    tipo  : "juzgado" | "camara" | "consejo" | "corte" | cualquier otro
            (cae a una plantilla genérica en vez de fallar)
    datos : el dict de la fila/perfil tal cual lo usa el frontend para pintar
            la pantalla (no hace falta transformarlo).
    """
    armar_prompt = _PLANTILLAS.get(tipo, _prompt_generico)
    prompt = armar_prompt(datos or {})
    return _pedir_a_claude(_SYSTEM_BASE, prompt)
