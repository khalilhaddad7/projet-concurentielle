from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import DATABASE_URL

# L'URL de connexion (avec identifiants) provient UNIQUEMENT de la variable
# d'environnement DATABASE_URL, jamais codée en dur ici.
SQLALCHEMY_DATABASE_URL = DATABASE_URL

# Options de connexion :
#  - "options" : force l'encodage client en UTF-8 (évite les problèmes d'accents).
#  - "connect_timeout" : délai maximal (en secondes) pour établir la connexion TCP
#    à PostgreSQL. Sans cela, si le serveur est injoignable (service arrêté,
#    mauvais host...), psycopg2 peut rester bloqué très longtemps. On limite ici
#    à 5 secondes pour échouer rapidement et proprement.
connect_args = {
    "options": "-c client_encoding=utf8",
    "connect_timeout": 5,
}

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args=connect_args
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()