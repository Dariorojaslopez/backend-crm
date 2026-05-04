"""
Conexión a PostgreSQL con SQLAlchemy (solo motor, sin ORM).

En Render, vincula la base PostgreSQL al servicio web para que inyecte
DATABASE_URL en el entorno. Este módulo lee esa URL y configura el engine
con SSL obligatorio, que Render suele exigir para conexiones externas.
"""

import os

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

# ---------------------------------------------------------------------------
# URL de conexión: Render la define automáticamente al enlazar Postgres.
# En local, exporta DATABASE_URL o úsala en un archivo .env cargado por tu runner.
# ---------------------------------------------------------------------------
DATABASE_URL: str | None = os.getenv("DATABASE_URL")

# ---------------------------------------------------------------------------
# Motor SQLAlchemy: gestiona el pool de conexiones hacia PostgreSQL.
# - connect_args["sslmode"] = "require": cifrado TLS (típico en Render).
# - pool_pre_ping: antes de usar una conexión del pool, verifica que siga viva
#   (útil tras idle timeouts o rotaciones de certificados en la nube).
# Si DATABASE_URL no existe (p. ej. desarrollo sin .env), engine queda en None
# y los endpoints pueden responder con un error claro en lugar de fallar al importar.
# ---------------------------------------------------------------------------
engine: Engine | None = (
    create_engine(
        DATABASE_URL,
        connect_args={"sslmode": "require"},
        pool_pre_ping=True,
    )
    if DATABASE_URL
    else None
)


def get_db_connection() -> tuple[bool, str]:
    """
    Prueba opcional de conectividad: abre una conexión y ejecuta ``SELECT 1``.

    Returns:
        (True, mensaje de éxito) si la conexión y la consulta funcionan.
        (False, texto del error) si falta configuración o la base rechaza la conexión.
    """
    if engine is None:
        return False, "DATABASE_URL no está definida; no se puede conectar."

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, "Conexión verificada correctamente."
    except Exception as exc:  # noqa: BLE001 — queremos devolver cualquier fallo de red/SSL/auth
        return False, str(exc)
