import logging
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from api.models_justicia import Base

log = logging.getLogger(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL")

# Railway a veces usa "postgres://" en lugar de "postgresql://"
# SQLAlchemy requiere "postgresql://"
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Antes: create_engine(DATABASE_URL) con DATABASE_URL=None reventaba
# ArgumentError apenas se importaba este módulo — main.py llama a
# init_db() en la primera línea, así que sin Postgres configurado
# (por ejemplo corriendo el dashboard local sin DB) la app entera no
# arrancaba. api.database no lo usa nadie más que init_db(), así que
# si no hay DATABASE_URL simplemente no creamos el engine real.
engine = create_engine(DATABASE_URL) if DATABASE_URL else None
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine) if engine else None


def init_db():
    """Crea las tablas si no existen. No hace nada (ni rompe el arranque)
    si no hay DATABASE_URL configurada."""
    if not engine:
        log.warning("DATABASE_URL no configurada — se omite init_db() (Postgres deshabilitado)")
        return
    Base.metadata.create_all(bind=engine)