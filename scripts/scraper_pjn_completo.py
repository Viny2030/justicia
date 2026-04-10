import requests
from bs4 import BeautifulSoup
import pandas as pd
import time

class ScraperPJN:
    def __init__(self):
        self.url_base = "https://scw.pjn.gov.ar/scw/home.seam"
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0"})

    def get_view_state(self):
        r = self.session.get(self.url_base)
        soup = BeautifulSoup(r.text, 'html.parser')
        return soup.find("input", {"name": "javax.faces.ViewState"})['value']

    def extraer_instancias(self, fuero, numero, anio):
        vs = self.get_view_state()
        # El payload debe replicar los campos del formulario ASP.NET del PJN
        payload = {
            "javax.faces.ViewState": vs,
            "j_id_fuero": fuero,
            "nro_causa": numero,
            "anio_causa": anio,
            "btnBuscar": "Buscar"
        }
        
        response = self.session.post(self.url_base, data=payload)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        actuaciones = []
        # Buscamos la tabla de movimientos del expediente
        tabla = soup.find("table", {"id": "formCausa:tablaActuaciones"}) 
        
        if tabla:
            for fila in tabla.find_all("tr")[1:]:
                cols = fila.find_all("td")
                actuaciones.append({
                    "fecha": cols[0].get_text(strip=True),
                    "instancia": cols[1].get_text(strip=True),
                    "descripcion": cols[2].get_text(strip=True),
                    "url_escrito": cols[3].find("a")["href"] if cols[3].find("a") else None
                })
        
        return pd.DataFrame(actuaciones)

# Ejemplo: Fuero 10 (Criminal y Corr. Fed.), Causa 1234, Año 2023
# bot = ScraperPJN()
# df = bot.extraer_instancias("10", "1234", "2023")
