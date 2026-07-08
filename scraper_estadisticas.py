"""
scraper_estadisticas_pjn.py
Monitor de Transparencia Judicial - Estadísticas PJN
Fuente: estadisticas.pjn.gov.ar / CSVs descargados manualmente

4 tipos de CSV soportados:
  - tramite_camara  : Trámite de Expedientes (Cámara)
  - resumen         : Trámite de Expedientes - Resumen del período
  - sentencias      : Movimiento de Sentencias
  - recursos        : Recursos interpuestos - Competencia Penal

Encoding: cp1250 | Separador: ; | Metadata en filas 0-8

Autor: Monitor Justicia AR | github.com/Viny2030/justicia
"""

import os, re, json, glob, codecs, logging, sys
from datetime import datetime, date

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger(__name__)

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Utilidades ────────────────────────────────────────────────────────────────

def safe_num(val):
    try:
        v = str(val).strip().replace('.', '').replace(',', '.').strip()
        v = re.sub(r'[^\d\.\-]', '', v)
        if not v or v == '-': return 0
        return int(float(v))
    except:
        return 0

def decodificar(raw):
    # FIX (2026-07-08 #3): los CSV de estadisticas.pjn.gov.ar están en cp1252
    # (Windows Europa Occidental), NO cp1250 (Europa Central) como decía el
    # nombre del archivo/comentario original. El bug real: cp1250, cp1252 y
    # latin-1 son codificaciones de 1 byte — CUALQUIER byte 0x00-0xFF es válido
    # en las tres, así que .decode() nunca tira UnicodeDecodeError sea cual sea
    # el byte. Como cp1250 estaba primero en la lista, "tenía éxito" siempre
    # y el resto de la lista (incluyendo la codificación correcta) nunca se
    # llegaba a probar. La diferencia entre cp1250 y cp1252 es chica pero
    # crítica acá: el byte 0xF1 es 'ñ' en cp1252/latin-1 pero 'ń' (con tilde
    # polaca) en cp1250 — así que CADA "Año" del archivo se decodificaba como
    # "Ańo", la regex de extraer_meta (que busca "Año \d{4}") nunca matcheaba,
    # y el campo 'anio' quedaba vacío en prácticamente todos los registros.
    # Orden nuevo: primero utf-8 (la única que sí puede fallar y detectar bien
    # un archivo realmente UTF-8), después cp1252 (la real del sitio),
    # latin-1 como red de seguridad (nunca falla, coincide con cp1252 en el
    # rango acentuado), cp1250 al final por si algún archivo viejo puntual
    # resultara ser Europa Central de verdad.
    for enc in ['utf-8-sig', 'utf-8', 'cp1252', 'latin-1', 'cp1250']:
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode('latin-1', errors='replace')

# ── Detección de tipo de CSV ──────────────────────────────────────────────────

def detectar_tipo(lines):
    # FIX (2026-07-08): el título real viene partido en dos filas para el tipo
    # "resumen", ej. fila 4 "Trámite de Expedientes" + fila 5 "Resumen del
    # período". El chequeo anterior recorría línea por línea y devolvía apenas
    # encontraba CUALQUIER keyword en esa línea, así que "Trámite de
    # Expedientes" (fila 4) siempre ganaba antes de llegar a "Resumen del
    # período" (fila 5) y todo archivo "resumen" se clasificaba mal como
    # "tramite_camara" (0 registros, porque find_header_row busca "Secretaría"
    # como cells[0] exacto y en resumen ese header es "Tribunal"). Ahora se
    # busca en todo el bloque de metadata junto, con prioridad
    # sentencias > recursos > resumen > tramite_camara (el orden importa:
    # "resumen" antes que "tramite_camara" porque ambos títulos coexisten).
    # FIX (2026-07-08 #2): a partir de 2023 el título viene en minúscula
    # ("Movimiento de sentencias" en vez de "Movimiento de Sentencias"), y la
    # comparación de abajo era case-sensitive -> se perdían ~211 CSVs reales
    # de "sentencias" (caían al default tramite_camara, que no encuentra su
    # header "Secretaría" en un archivo de sentencias y devuelve 0 registros).
    # Se compara todo en minúsculas para no depender de cómo lo capitalice el
    # sitio en cada tanda de exportación.
    valores = [ (l.split(';')[0] if l else '').strip() for l in lines[:9] ]
    valores_lc = [v.lower() for v in valores]
    texto_lc = ' | '.join(valores_lc)
    if any('movimiento de sentencias' in v for v in valores_lc) or any(v == 'sentencias' for v in valores_lc):
        return 'sentencias'
    if 'recursos interpuestos' in texto_lc:
        return 'recursos'
    if 'resumen del per' in texto_lc:
        return 'resumen'
    if 'trámite de expedientes' in texto_lc or 'tramite de expedientes' in texto_lc:
        return 'tramite_camara'
    return 'tramite_camara'

# ── Extracción de metadata ────────────────────────────────────────────────────

def extraer_meta(lines):
    meta = {
        'anio': '', 'periodo': 'Anual',
        'jurisdiccion': '', 'tribunal': '', 'tipo_informe': ''
    }
    for i, line in enumerate(lines[:10]):
        cells = [c.strip() for c in line.split(';')]
        val = cells[0]
        m = re.match(r'[Aa]ño\s+(\d{4})(.*)', val)
        if m:
            meta['anio'] = m.group(1)
            p = m.group(2).strip(' -').strip()
            if 'Primer' in p:   meta['periodo'] = '1S'
            elif 'Segundo' in p: meta['periodo'] = '2S'
            else:                meta['periodo'] = 'Anual'
        elif 'Jurisdicci' in val:
            meta['jurisdiccion'] = val.replace('Jurisdicción ', '').replace('Jurisdiccion ', '').strip()
        elif i == 4 and val and 'Jurisdicci' not in val:
            meta['tribunal'] = val
        elif i == 5 and val and not meta['tribunal']:
            meta['tribunal'] = val
        elif i in [4, 5, 6] and any(kw in val for kw in ['Trámite', 'Tramite', 'Sentencias', 'Recursos', 'Resumen']):
            meta['tipo_informe'] = val
    return meta

# ── Parsers por tipo ──────────────────────────────────────────────────────────

def find_header_row(lines, keywords):
    for i, line in enumerate(lines):
        cells = [c.strip() for c in line.split(';')]
        if any(cells[0] == kw for kw in keywords):
            return i
    return None

def parse_tramite_camara(lines, meta):
    hr = find_header_row(lines, ['Secretaría', 'Secretaria'])
    if hr is None: return []
    registros = []
    for i in range(hr + 3, len(lines)):
        cells = [c.strip() for c in lines[i].split(';')]
        nombre = cells[0]
        if not nombre or 'Datos actualizados' in nombre: break
        r = {**meta, 'tipo_csv': 'tramite_camara', 'organismo': nombre,
             'es_total': nombre.startswith('Total') or nombre.startswith('Subtotal'),
             'en_tramite_inicio': safe_num(cells[1] if len(cells) > 1 else 0),
             'ingresos':          safe_num(cells[2] if len(cells) > 2 else 0),
             'reingresos':        safe_num(cells[3] if len(cells) > 3 else 0),
             'subtotal_a':        safe_num(cells[4] if len(cells) > 4 else 0),
             'resueltos':         safe_num(cells[5] if len(cells) > 5 else 0),
             'subtotal_b':        safe_num(cells[11] if len(cells) > 11 else 0),
             'en_tramite_cierre': safe_num(cells[12] if len(cells) > 12 else 0),
             'permanencia_extensa': safe_num(cells[14] if len(cells) > 14 else 0),
             'permanencia_breve':   safe_num(cells[15] if len(cells) > 15 else 0),
        }
        r['tasa_resolucion_pct'] = round(r['resueltos'] / r['subtotal_a'] * 100, 1) if r['subtotal_a'] > 0 else 0.0
        registros.append(r)
    return registros

def parse_resumen(lines, meta):
    hr = find_header_row(lines, ['Tribunal', 'tribunal'])
    if hr is None: return []
    registros = []
    tribunal_actual = ''
    for i in range(hr + 3, len(lines)):
        cells = [c.strip() for c in lines[i].split(';')]
        if not any(c for c in cells): continue
        if cells[0] and cells[0] not in ['-', '']: tribunal_actual = cells[0]
        secretaria = cells[1] if len(cells) > 1 else ''
        if 'Datos actualizados' in cells[0]: break
        if not secretaria and not tribunal_actual: continue
        registros.append({
            **meta, 'tipo_csv': 'resumen',
            'organismo': f"{tribunal_actual} | {secretaria}".strip(' |'),
            'tribunal_nombre': tribunal_actual,
            'secretaria': secretaria,
            'es_total': 'Total' in cells[0] or 'Subtotal' in cells[0],
            'en_tramite_inicio': safe_num(cells[2] if len(cells) > 2 else 0),
            'entrados':          safe_num(cells[3] if len(cells) > 3 else 0),
            'salidos':           safe_num(cells[4] if len(cells) > 4 else 0),
            'en_tramite_cierre': safe_num(cells[5] if len(cells) > 5 else 0),
        })
    return registros

def parse_sentencias(lines, meta):
    hr = find_header_row(lines, ['Tribunal', 'tribunal'])
    if hr is None: return []
    registros = []
    tribunal_actual = ''
    for i in range(hr + 3, len(lines)):
        cells = [c.strip() for c in lines[i].split(';')]
        if not any(c for c in cells): continue
        if cells[0] and cells[0] not in ['-', '']: tribunal_actual = cells[0]
        secretaria = cells[1] if len(cells) > 1 else ''
        if 'Datos actualizados' in cells[0]: break
        registros.append({
            **meta, 'tipo_csv': 'sentencias',
            'organismo': f"{tribunal_actual} | {secretaria}".strip(' |'),
            'tribunal_nombre': tribunal_actual,
            'secretaria': secretaria,
            'es_total': 'Total' in cells[0] or 'Subtotal' in cells[0],
            'pendientes_inicio':        safe_num(cells[2] if len(cells) > 2 else 0),
            'agregadas':                safe_num(cells[3] if len(cells) > 3 else 0),
            'subtotal_a':               safe_num(cells[4] if len(cells) > 4 else 0),
            'dictadas_definitivas':     safe_num(cells[5] if len(cells) > 5 else 0),
            'dictadas_interlocutorias': safe_num(cells[6] if len(cells) > 6 else 0),
            'subtotal_b':               safe_num(cells[7] if len(cells) > 7 else 0),
            'pendientes_cierre':        safe_num(cells[8] if len(cells) > 8 else 0),
        })
    return registros

def parse_recursos(lines, meta):
    hr = find_header_row(lines, ['Tribunal', 'tribunal'])
    if hr is None: return []
    registros = []
    tribunal_actual = ''
    for i in range(hr + 2, len(lines)):
        cells = [c.strip() for c in lines[i].split(';')]
        if not any(c for c in cells): continue
        if cells[0] and cells[0] not in ['-', '']: tribunal_actual = cells[0]
        secretaria = cells[1] if len(cells) > 1 else ''
        if 'Datos actualizados' in cells[0]: break
        registros.append({
            **meta, 'tipo_csv': 'recursos',
            'organismo': f"{tribunal_actual} | {secretaria}".strip(' |'),
            'tribunal_nombre': tribunal_actual,
            'secretaria': secretaria,
            'es_total': 'Total' in cells[0] or 'Subtotal' in cells[0],
            'recursos_apelacion': safe_num(cells[2] if len(cells) > 2 else 0),
            'otros_recursos':     safe_num(cells[3] if len(cells) > 3 else 0),
        })
    return registros

# ── Parser principal ──────────────────────────────────────────────────────────

def parse_csv(path):
    with open(path, 'rb') as f:
        raw = f.read()
    text = decodificar(raw)
    lines = text.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    meta = extraer_meta(lines)
    tipo = detectar_tipo(lines)
    meta['tipo'] = tipo
    meta['archivo_fuente'] = os.path.basename(path)

    if tipo == 'tramite_camara': return parse_tramite_camara(lines, meta)
    elif tipo == 'resumen':      return parse_resumen(lines, meta)
    elif tipo == 'sentencias':   return parse_sentencias(lines, meta)
    elif tipo == 'recursos':     return parse_recursos(lines, meta)
    return []

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    log.info("=" * 60)
    log.info("Monitor Justicia AR — Scraper Estadísticas PJN")
    log.info(f"Ejecución: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info("=" * 60)

    # Buscar todos los CSVs en la carpeta del repo
    patron = os.path.join(OUTPUT_DIR, "*.csv")
    csvs = sorted(glob.glob(patron))
    log.info(f"CSVs encontrados: {len(csvs)}")

    if not csvs:
        log.error("No se encontraron archivos CSV en el directorio del repo.")
        log.error("Descargá los CSVs desde estadisticas.pjn.gov.ar y ponelos en la raíz del repo.")
        raise FileNotFoundError("No hay CSVs para procesar")

    todos = []
    procesados = []
    fallidos = []

    for path in csvs:
        fname = os.path.basename(path)
        try:
            recs = parse_csv(path)
            todos.extend(recs)
            procesados.append({'archivo': fname, 'registros': len(recs)})
            log.info(f"  ✓ {fname[:55]} → {len(recs)} registros")
        except Exception as e:
            log.warning(f"  ✗ {fname}: {e}")
            fallidos.append({'archivo': fname, 'error': str(e)})

    # Guardar estadisticas_causas.json
    out_causas = os.path.join(OUTPUT_DIR, "estadisticas_causas.json")
    with codecs.open(out_causas, 'w', 'utf-8') as f:
        json.dump(todos, f, ensure_ascii=False, indent=2, default=str)
    log.info(f"✓ estadisticas_causas.json ({len(todos)} registros)")

    # Calcular resumen por jurisdicción
    jurisdicciones = {}
    for r in todos:
        j = r.get('jurisdiccion', 'Sin dato')
        if j not in jurisdicciones:
            jurisdicciones[j] = {'registros': 0, 'tipos': set()}
        jurisdicciones[j]['registros'] += 1
        jurisdicciones[j]['tipos'].add(r.get('tipo_csv', ''))
    for j in jurisdicciones:
        jurisdicciones[j]['tipos'] = list(jurisdicciones[j]['tipos'])

    # Guardar estadisticas_meta.json
    meta_out = {
        'ultima_actualizacion': datetime.now().isoformat(),
        'fecha_datos': date.today().isoformat(),
        'fuente': 'estadisticas.pjn.gov.ar — Consejo de la Magistratura de la Nación',
        'totales': {
            'registros': len(todos),
            'archivos_procesados': len(procesados),
            'archivos_fallidos': len(fallidos),
            'jurisdicciones': len(jurisdicciones),
        },
        'por_jurisdiccion': jurisdicciones,
        'archivos': procesados,
        'fallidos': fallidos,
        'generado_por': 'scraper_estadisticas_pjn.py — Monitor Justicia AR',
    }
    out_meta = os.path.join(OUTPUT_DIR, "estadisticas_meta.json")
    with codecs.open(out_meta, 'w', 'utf-8') as f:
        json.dump(meta_out, f, ensure_ascii=False, indent=2, default=str)
    log.info(f"✓ estadisticas_meta.json")

    log.info("=" * 60)
    log.info(f"✅ {len(todos)} registros | {len(procesados)} archivos | {len(jurisdicciones)} jurisdicciones")
    log.info("=" * 60)

if __name__ == "__main__":
    main()
