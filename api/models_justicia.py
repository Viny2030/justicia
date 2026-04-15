cat <<EOF > api/models_justicia.py
from sqlalchemy import Column, Integer, String, Date, JSON
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Actuacion(Base):
    __tablename__ = 'actuaciones'
    id = Column(Integer, primary_key=True)
    fecha = Column(String)
    instancia = Column(String)
    descripcion = Column(String)
    analisis_nlp = Column(JSON)
    url_documento = Column(String)
EOF
