"""
Punto de entrada de la API CRM.

Render (y otros hosts) ejecutan el servidor con:
    uvicorn app.main:app --host 0.0.0.0 --port 10000

La variable `app` debe existir en este módulo para que uvicorn la resuelva.
"""

from fastapi import FastAPI

# Importamos el motor definido en database.py (misma capa de paquete `app`).
# No usamos modelos ORM; solo comprobamos conectividad con el pool del engine.
from app.database import engine

# Instancia principal de FastAPI: aquí se registran rutas, middlewares, etc.
app = FastAPI(
    title="Backend CRM",
    description="API con comprobación de PostgreSQL (Render) vía SQLAlchemy, sin ORM.",
    version="0.1.0",
)


@app.get("/")
def read_root():
    """
    Ruta raíz: comprobación rápida de que el servicio responde.
    """
    return {"message": "API funcionando 🔥"}


@app.get("/health")
def health_check():
    """
    Health check para balanceadores y monitoreo (Render, Kubernetes, etc.).
    """
    return {"status": "ok"}


@app.get("/test-db")
def test_db():
    """
    Comprueba que la app puede abrir y cerrar una conexión real al PostgreSQL de Render.

    Flujo:
    1. Verifica que ``engine`` exista (``DATABASE_URL`` configurada).
    2. Abre conexión con ``engine.connect()``.
    3. La cierra en un ``finally`` para liberar el recurso aunque falle el handshake.
    4. Devuelve JSON de éxito o de error según el resultado.
    """
    # Sin URL no hay motor: evitamos llamar a SQLAlchemy con un engine inexistente.
    if engine is None:
        return {"error": "DATABASE_URL no está definida en el entorno."}

    conn = None
    try:
        # Intenta establecer la conexión TCP + TLS + autenticación con Postgres.
        conn = engine.connect()
        return {"status": "conexion exitosa"}
    except Exception as exc:  # noqa: BLE001 — exponemos el mensaje al cliente de prueba
        return {"error": str(exc)}
    finally:
        # Siempre cerramos la conexión si se llegó a abrir (libera socket y recursos del pool).
        if conn is not None:
            conn.close()
