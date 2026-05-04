"""
Capa de persistencia: motor PostgreSQL (psycopg2), sesiones y creación manual de esquema.

``init_db()`` debe invocarse explícitamente (CLI, script de despliegue o migraciones),
no en cada petición HTTP.
"""

from __future__ import annotations

import os
from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

DATABASE_URL: str | None = os.getenv("DATABASE_URL")
# Render usa TLS; en Postgres local puedes exportar DATABASE_SSLMODE=disable
DATABASE_SSLMODE: str | None = os.getenv("DATABASE_SSLMODE", "require")

_engine: Engine | None = None
SessionLocal: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    """Devuelve el motor singleton; exige ``DATABASE_URL`` definida."""
    global _engine
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL no está definida en el entorno.")
    if _engine is None:
        connect_args: dict[str, str] = {}
        if DATABASE_SSLMODE:
            connect_args["sslmode"] = DATABASE_SSLMODE
        _engine = create_engine(
            DATABASE_URL,
            connect_args=connect_args,
            pool_pre_ping=True,
        )
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """Factory de sesiones ligada al motor actual."""
    global SessionLocal
    if SessionLocal is None:
        SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=get_engine(),
            expire_on_commit=False,
        )
    return SessionLocal


def get_db() -> Generator[Session, None, None]:
    """
    Dependencia FastAPI: abre sesión por request y cierra al terminar.

    No ejecuta ``create_all``; solo lectura/escritura sobre tablas existentes.
    """
    factory = get_session_factory()
    db = factory()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db_seed_boyaca() -> Generator[Session, None, None]:
    """
    Igual que ``get_db``, pero ejecuta ``init_db()`` **antes** de abrir la sesión.

    Así el DDL queda confirmado y la conexión del ORM no queda abierta antes de existir
    ``provincias`` / ``municipios`` (evita ``UndefinedTable`` en PostgreSQL).
    """
    init_db()
    factory = get_session_factory()
    db = factory()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db() -> None:
    """
    Crea todas las tablas según los modelos importados (equivalente a DDL inicial).

    Usa una transacción explícita en el motor para que el COMMIT deje visible el esquema
    a conexiones posteriores del pool.

    Invocar una vez por entorno o sustituir por Alembic en producción madura.
    """
    import app.models  # noqa: F401 — registra metadatos de tablas

    from app.models.base import Base

    eng = get_engine()
    with eng.begin() as conn:
        Base.metadata.create_all(bind=conn)


def get_db_connection() -> tuple[bool, str]:
    """Prueba rápida de conectividad (health / diagnóstico)."""
    try:
        eng = get_engine()
    except RuntimeError as exc:
        return False, str(exc)

    try:
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, "Conexión verificada correctamente."
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def try_get_engine() -> Engine | None:
    try:
        return get_engine()
    except RuntimeError:
        return None
