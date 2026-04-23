#!/usr/bin/env python3
# main.py  —  Entry point para lanzar cualquiera de los dos dashboards desde PyCharm
#
# USO desde terminal (en la raíz del proyecto):
#   python main.py estrategico      → lanza Dashboard 1 (Alta Gerencia)
#   python main.py operativo        → lanza Dashboard 2 (Juzgados)
#   python main.py                  → muestra menú interactivo
#
# USO desde PyCharm:
#   Run > Edit Configurations > Parameters: "estrategico" o "operativo"

import subprocess
import sys
import os

DASHBOARDS = {
    "1": ("estrategico", "dashboard_estrategico/app.py", "⚖️  Monitor de Alta Gerencia (CSJN · Consejo · Cámaras)"),
    "2": ("operativo",   "dashboard_operativo/app.py",   "📊  Monitor de Juzgados Federales (1103 registros)"),
}

ALIAS = {
    "estrategico": "1",
    "estratégico": "1",
    "alta":        "1",
    "gerencia":    "1",
    "operativo":   "2",
    "juzgados":    "2",
    "operacional": "2",
}


def lanzar_streamlit(ruta_app: str, port: int = 8501) -> None:
    """Ejecuta streamlit run en un subproceso."""
    cmd = [
        sys.executable, "-m", "streamlit", "run",
        ruta_app,
        "--server.port", str(port),
        "--server.headless", "false",
        "--browser.gatherUsageStats", "false",
    ]
    print(f"\n🚀 Lanzando: {ruta_app}  →  http://localhost:{port}\n")
    subprocess.run(cmd)


def menu_interactivo() -> str:
    """Muestra menú en consola y retorna la clave elegida."""
    print("\n" + "═" * 60)
    print("  🏛️  SISTEMA DE MONITOREO JUDICIAL — Ph.D. Monteverde")
    print("═" * 60)
    for key, (_, _, desc) in DASHBOARDS.items():
        print(f"  [{key}]  {desc}")
    print("  [q]  Salir")
    print("═" * 60)
    return input("\nElegí un dashboard (1/2): ").strip().lower()


def main() -> None:
    arg = sys.argv[1].lower() if len(sys.argv) > 1 else None

    if arg in ALIAS:
        arg = ALIAS[arg]

    if arg not in DASHBOARDS:
        arg = menu_interactivo()

    if arg == "q":
        print("Saliendo...")
        return

    if arg not in DASHBOARDS:
        print(f"❌ Opción inválida: '{arg}'. Usá 1, 2, estrategico u operativo.")
        sys.exit(1)

    _, ruta, desc = DASHBOARDS[arg]
    ruta_abs = os.path.join(os.path.dirname(os.path.abspath(__file__)), ruta)

    if not os.path.exists(ruta_abs):
        print(f"❌ No se encontró: {ruta_abs}")
        print("   Asegurate de haber creado los archivos de cada dashboard.")
        sys.exit(1)

    # Puerto diferente para cada dashboard (útil si los corrés en paralelo)
    port = 8501 if arg == "1" else 8502
    lanzar_streamlit(ruta, port)


if __name__ == "__main__":
    main()
