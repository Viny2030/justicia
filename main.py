from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import pandas as pd
import os

app = FastAPI(title="Auditoría Judicial - Ph.D. Monteverde")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "pjn_estadisticas_completo.csv")

@app.get("/juzgados", response_class=HTMLResponse)
def salida_auditoria_visual():
    try:
        df = pd.read_csv(DATA_PATH)
        df = df.fillna(0) # Para cálculos, mejor 0 que vacío
        
        # --- CÁLCULO DE KPI (Simulación basada en Auditoría) ---
        total_juzgados = len(df)
        promedio_puntaje = 0
        if 'puntaje_jurado' in df.columns:
            df['puntaje_jurado'] = pd.to_numeric(df['puntaje_jurado'], errors='coerce').fillna(0)
            promedio_puntaje = round(df['puntaje_jurado'].mean(), 2)

        # --- GENERACIÓN DE HTML CON ESTILOS (CSS) ---
        html_content = f"""
        <html>
            <head>
                <title>Auditoría Operativa - Ph.D. Monteverde</title>
                <style>
                    body {{ font-family: Arial, sans-serif; background-color: #f4f4f9; padding: 20px; }}
                    .kpi-container {{ display: flex; gap: 20px; margin-bottom: 30px; }}
                    .kpi-card {{ background: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); flex: 1; text-align: center; }}
                    .kpi-card h2 {{ margin: 0; color: #555; font-size: 14px; }}
                    .kpi-card p {{ font-size: 24px; font-weight: bold; margin: 10px 0; color: #2c3e50; }}
                    table {{ width: 100%; border-collapse: collapse; background: white; }}
                    th {{ background: #2c3e50; color: white; padding: 12px; text-align: left; }}
                    td {{ padding: 10px; border-bottom: 1px solid #ddd; font-size: 12px; }}
                    .status-eficiente {{ background-color: #d4edda; color: #155724; }} /* Verde */
                    .status-alerta {{ background-color: #fff3cd; color: #856404; }}    /* Amarillo */
                    .status-critico {{ background-color: #f8d7da; color: #721c24; }}    /* Rojo */
                </style>
            </head>
            <body>
                <h1>📊 Auditoría Operativa: {total_juzgados} Registros</h1>
                
                <div class="kpi-container">
                    <div class="kpi-card"><h2>TOTAL JUZGADOS</h2><p>{total_juzgados}</p></div>
                    <div class="kpi-card"><h2>PROMEDIO PUNTAJE</h2><p>{promedio_puntaje}</p></div>
                    <div class="kpi-card"><h2>ESTADO GLOBAL</h2><p style="color: green;">OPERATIVO</p></div>
                </div>

                <table>
                    <tr>
                        <th>FUERO</th><th>JURISDICCIÓN</th><th>POSTULANTE</th><th>PUNTAJE</th><th>ESTADO</th>
                    </tr>
        """

        # Agregar filas con lógica de colores
        for _, row in df.head(200).iterrows(): # Mostramos 200 para velocidad
            puntaje = float(row.get('puntaje_jurado', 0))
            clase = "status-eficiente" if puntaje > 150 else ("status-alerta" if puntaje > 100 else "status-critico")
            
            html_content += f"""
            <tr class="{clase}">
                <td>{row.get('ambito_origen_concurso_descripcion', '')}</td>
                <td>{row.get('jurisdiccion', '')}</td>
                <td>{row.get('nombre_postulante', '')}</td>
                <td>{puntaje}</td>
                <td><strong>{'OK' if puntaje > 100 else 'REVISAR'}</strong></td>
            </tr>
            """

        html_content += "</table></body></html>"
        return HTMLResponse(content=html_content)
        
    except Exception as e:
        return f"<h1>Error: {str(e)}</h1>"
