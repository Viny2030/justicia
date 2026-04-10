from sqlalchemy import Column, Integer, String, Date, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Expediente(Base):
    __tablename__ = 'expedientes'
    id = Column(Integer, primary_key=True)
    nro_expediente = Column(String, unique=True)
    caratula = Column(String)
    juzgado = Column(String)
    fuero = Column(String)

class InstanciaActuacion(Base):
    __tablename__ = 'actuaciones'
    id = Column(Integer, primary_key=True)
    expediente_id = Column(Integer, ForeignKey('expedientes.id'))
    fecha = Column(Date)
    descripcion_corta = Column(String)
    analisis_nlp = Column(JSON) # Aquí guardamos el dict del ParserJudicial
    url_documento = Column(String)
