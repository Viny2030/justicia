"""
scraper_datos_jus_resiliente.py
─────────────────────────────────────────────────────────────────────
Wrapper NO invasivo sobre scraper_datos_jus_completo.py (no lo modifica,
sólo lo importa). Se agregó después de que el workflow scraper_datos_jus_refresh.yml
falló con timeouts consistentes contra datos.jus.gob.ar:

    HTTPSConnectionPool(host='datos.jus.gob.ar', port=443):
    Read timed out. (read timeout=30)

Se confirmó por fuera del repo (curl directo, otra red distinta a GitHub
Actions) que datos.jus.gob.ar no respondía en absoluto en ese momento —
o sea el problema es del portal, no del scraper ni de la config de red
de Actions. Este wrapper no puede arreglar que el sitio esté caído, pero
sube el timeout de 30s a 90s (por si sólo estaba lento, no caído) y agrega
reintentos con espera creciente por si fue un corte momentáneo.

Uso (igual que el script original):
  python scraper_datos_jus_resiliente.py
  python scraper_datos_jus_resiliente.py --solo magistrados designaciones
"""
import sys
import time
import logging

import scraper_datos_jus_completo as base

log = logging.getLogger("resiliente")

TIMEOUT_NUEVO = 90          # antes: 30s (base.TIMEOUT)
INTENTOS      = 3
ESPERA_BASE_S = 30          # backoff: 30s, 60s, 90s entre intentos


def main():
    # Sube el timeout del módulo base sin tocar su archivo — TIMEOUT se lee
    # como global dentro de ckan_get() Y dentro de descargar_recurso() en
    # cada llamada, así que alcanza con pisar el atributo del módulo antes
    # de correr main() (descargar_recurso ya no tiene el 60s hardcodeado).
    base.TIMEOUT = TIMEOUT_NUEVO

    import json
    mejor_meta = None

    for intento in range(1, INTENTOS + 1):
        log.info(f"=== Intento {intento}/{INTENTOS} (timeout={base.TIMEOUT}s) ===")
        try:
            base.main()
        except SystemExit:
            raise
        except Exception as e:
            log.warning(f"Intento {intento} falló con excepción: {e}")

        # Chequear resultado leyendo el meta que el propio script ya escribió
        meta_path = base.OUT_DIR / "datos_jus_meta.json"
        meta = None
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))

        if meta:
            ok, fallidos = meta.get("datasets_ok", 0), meta.get("datasets_fallidos", 0)
            log.info(f"Intento {intento}: {ok} OK / {fallidos} fallidos")

            # Antes: con 1 solo dataset OK ya se daba la corrida entera por
            # buena y se cortaban los reintentos, aunque quedaran datasets
            # fallidos por errores transitorios (503 / timeout) que un
            # segundo intento podía resolver. Ahora solo se corta apenas si
            # la corrida fue perfecta (0 fallidos); si no, sigue reintentando
            # mientras queden intentos.
            if ok > 0 and fallidos == 0:
                log.info(f"OK en intento {intento}: {ok} datasets, 0 fallidos.")
                return 0

            if mejor_meta is None or ok > mejor_meta.get("datasets_ok", 0):
                mejor_meta = meta

        if intento < INTENTOS:
            espera = ESPERA_BASE_S * intento
            log.warning(f"Quedaron datasets fallidos — reintentando en {espera}s "
                        f"(puede ser que datos.jus.gob.ar siga inestable)")
            time.sleep(espera)

    if mejor_meta and mejor_meta.get("datasets_ok", 0) > 0:
        log.warning(
            f"Se agotaron los {INTENTOS} intentos sin lograr una corrida "
            f"perfecta. Mejor resultado: {mejor_meta.get('datasets_ok', 0)} OK / "
            f"{mejor_meta.get('datasets_fallidos', 0)} fallidos — se commitea "
            f"igual (el workflow solo aborta con 0 datasets OK). Revisar el "
            f"log de cada intento para ver qué datasets siguen fallando."
        )
        return 0

    log.error("Los 3 intentos fallaron con 0 datasets OK. "
              "Es muy probable que datos.jus.gob.ar esté caído/inaccesible "
              "en este momento — no es un problema del scraper. Reintentá "
              "más tarde (workflow_dispatch manual) o revisá el estado del portal.")
    return 1


if __name__ == "__main__":
    sys.exit(main())

