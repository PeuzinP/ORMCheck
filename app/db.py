from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, sessionmaker
import mysql.connector

from app.settings import (
    APP_STORAGE_BACKEND,
    DATABASE_URL,
    MYSQL_DATABASE,
    MYSQL_HOST,
    MYSQL_PASSWORD,
    MYSQL_PORT,
    MYSQL_SQL_ECHO,
    MYSQL_USER,
)


def storage_usa_banco() -> bool:
    return APP_STORAGE_BACKEND == "mysql"


class Base(DeclarativeBase):
    pass


def _montar_database_url() -> str:
    # Em vez de tentar tratar a string do DATABASE_URL e arriscar quebras de caracteres,
    # montamos a URL de forma nativa e segura usando as variáveis tratadas do seu .env
    return URL.create(
        drivername="mysql+pymysql",
        username=MYSQL_USER,      # Puxa 'omrcheck'
        password=MYSQL_PASSWORD,  # Puxa 'Pensar2026@root' puro, sem precisar mascarar com %40
        host=MYSQL_HOST,          # Puxa '127.0.0.1'
        port=MYSQL_PORT,          # Puxa 3306
        database=MYSQL_DATABASE,  # Puxa 'omrcheck'
        query={"charset": "utf8mb4"},
    ).render_as_string(hide_password=False)


ENGINE = None
SessionLocal = None

if storage_usa_banco():
    ENGINE = create_engine(
        _montar_database_url(),
        pool_pre_ping=True,
        pool_recycle=3600,
        future=True,
        echo=MYSQL_SQL_ECHO,
    )
    SessionLocal = sessionmaker(bind=ENGINE, autoflush=False, autocommit=False, expire_on_commit=False)


@contextmanager
def get_db_session():
    if not storage_usa_banco() or SessionLocal is None:
        raise RuntimeError("Banco de dados MySQL não está habilitado.")

    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db():
    if not storage_usa_banco() or ENGINE is None:
        return

    from app.db_models import JobModel  # noqa: F401

    Base.metadata.create_all(bind=ENGINE)
    
def get_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="SUA_SENHA",
        database="omrcheck"
    )
