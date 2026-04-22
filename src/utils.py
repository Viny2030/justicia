# src/utils.py

def calcular_kpi_eficiencia(presupuesto, produccion):
    """
    Calcula el 'Costo por Sentencia/Trámite'.
    
    Args:
        presupuesto (float): Monto asignado (del Dashboard Estratégico).
        produccion (int/float): Cantidad de sentencias o trámites (del Dashboard Operativo).
        
    Returns:
        float: El costo unitario o 0 si no hay producción para evitar división por cero.
    """
    try:
        # Validar que los valores sean numéricos
        presupuesto = float(presupuesto)
        produccion = float(produccion)
        
        if produccion <= 0:
            return 0.0
            
        return round(presupuesto / produccion, 2)
    
    except (ValueError, TypeError):
        return 0.0

def calcular_tasa_vacancia(jueces_activos, cargos_totales):
    """
    Calcula el porcentaje de vacancia para el Dashboard 1.
    """
    if cargos_totales <= 0:
        return 0.0
    vacantes = cargos_totales - jueces_activos
    return round((vacantes / cargos_totales) * 100, 2)
