import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from api.models_justicia import Base

DATABASE_URL = os.environ.get("DATABASE_URL")

# Railway a veces usa "postgres://" en lugar de "postgresql://"
# SQLAlchemy requiere "postgresql://"
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """Crea las tablas si no existen."""
    Base.metadata.create_all(bind=engine)