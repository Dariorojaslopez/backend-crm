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


def aplicar_patch_contactos_opcional_una_vez() -> dict[str, object]:
    """
    Hace opcionales columnas históricas de ``contactos`` si aún tienen NOT NULL.

    Es idempotente: en arranques posteriores no aplica cambios si ya están en NULLABLE.
    """
    objetivos: tuple[str, ...] = (
        "nombre",
        "apellidos",
        "municipio_id",
        "provincia_id",
        "cargo_id",
        "partido_id",
        "tipo_id",
        "relacion_id",
        "afinidad",
        "influencia",
        "prioridad",
        "periodo",
        # Columna legacy de esquemas antiguos (reemplazada por relacion_id).
        "relacion",
    )

    eng = get_engine()
    aplicadas: list[str] = []
    ya_ok: list[str] = []
    cambios_estructura: list[str] = []

    with eng.begin() as conn:
        tabla_contactos = conn.execute(text("SELECT to_regclass('contactos')")).scalar_one_or_none()
        if tabla_contactos is None:
            return {
                "columnas_objetivo": list(objetivos),
                "columnas_actualizadas": aplicadas,
                "columnas_ya_opcionales": ya_ok,
                "cambios_estructura": cambios_estructura,
            }

        # Compatibilidad con esquemas antiguos: si falta relacion_id, la crea.
        relacion_id_nullable = conn.execute(
            text(
                """
                SELECT is_nullable
                FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = 'contactos'
                  AND column_name = 'relacion_id'
                """
            )
        ).scalar_one_or_none()
        if relacion_id_nullable is None:
            conn.execute(text("ALTER TABLE contactos ADD COLUMN relacion_id INTEGER NULL"))
            cambios_estructura.append("add_column:contactos.relacion_id")

        # FK + índice de relacion_id (idempotente).
        tabla_relaciones = conn.execute(text("SELECT to_regclass('relaciones')")).scalar_one_or_none()
        if tabla_relaciones is not None:
            fk_existe = conn.execute(
                text(
                    """
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname = 'contactos_relacion_id_fkey'
                      AND conrelid = 'contactos'::regclass
                    """
                )
            ).scalar_one_or_none()
            if fk_existe is None:
                conn.execute(
                    text(
                        """
                        ALTER TABLE contactos
                        ADD CONSTRAINT contactos_relacion_id_fkey
                        FOREIGN KEY (relacion_id) REFERENCES relaciones(id) ON DELETE RESTRICT
                        """
                    )
                )
                cambios_estructura.append("add_fk:contactos.relacion_id->relaciones.id")

        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_contactos_relacion_id ON contactos (relacion_id)"
            )
        )
        cambios_estructura.append("ensure_index:ix_contactos_relacion_id")

        for col in objetivos:
            is_nullable = conn.execute(
                text(
                    """
                    SELECT is_nullable
                    FROM information_schema.columns
                    WHERE table_schema = current_schema()
                      AND table_name = 'contactos'
                      AND column_name = :column_name
                    """
                ),
                {"column_name": col},
            ).scalar_one_or_none()

            if is_nullable is None:
                continue

            if str(is_nullable).upper() == "YES":
                ya_ok.append(col)
                continue

            conn.execute(text(f"ALTER TABLE contactos ALTER COLUMN {col} DROP NOT NULL"))
            aplicadas.append(col)

    return {
        "columnas_objetivo": list(objetivos),
        "columnas_actualizadas": aplicadas,
        "columnas_ya_opcionales": ya_ok,
        "cambios_estructura": cambios_estructura,
    }


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
