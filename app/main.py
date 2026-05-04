"""
API CRM Boyacá — FastAPI + SQLAlchemy + PostgreSQL.

Ejecución típica (Render / local):
    uvicorn app.main:app --host 0.0.0.0 --port 10000
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import (
    aplicar_patch_contactos_opcional_una_vez,
    get_db_connection,
    get_session_factory,
    try_get_engine,
)
from app.routers import (
    cargos,
    contactos,
    import_excel,
    municipios,
    partidos,
    provincias,
    relaciones,
    seed_boyaca,
    seed_cargos,
    seed_partidos,
    seed_relaciones,
    seed_tipos,
    tipos,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
log = logging.getLogger("crm.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Arranque API version=%s", app.version)
    ok, msg = get_db_connection()
    if ok:
        log.info("Base de datos accesible: %s", msg)
        try:
            try:
                patch = aplicar_patch_contactos_opcional_una_vez()
                log.info(
                    "Patch contactos opcional aplicado=%s ya_opcionales=%s cambios_estructura=%s",
                    len(patch.get("columnas_actualizadas", [])),
                    len(patch.get("columnas_ya_opcionales", [])),
                    len(patch.get("cambios_estructura", [])),
                )
            except Exception:
                log.exception("No se pudo aplicar patch opcional de contactos al arranque")

            from app.services.relacion_service import bootstrap_relaciones

            factory = get_session_factory()
            db = factory()
            try:
                resultado = bootstrap_relaciones(db)
                db.commit()
                log.info(
                    "Esquema y relaciones por defecto listos (nuevas en este arranque: %s)",
                    resultado.get("relaciones_creadas", 0),
                )
            except Exception:
                db.rollback()
                log.exception("No se pudo asegurar catálogo relaciones al arranque")
            finally:
                db.close()
        except Exception:
            log.exception("Bootstrap de base de datos al arranque falló")
    else:
        log.warning("Base de datos no verificada al arranque: %s", msg)
    yield
    log.info("Apagado API")


app = FastAPI(
    title="CRM Contactos Políticos Boyacá",
    description="Backend limpio para gestión de contactos con PostgreSQL.",
    version="1.0.0",
    lifespan=lifespan,
)

_origins = os.getenv("CORS_ORIGINS", "*").strip()
_allow_origins = [o.strip() for o in _origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins if _allow_origins else ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(contactos.router, prefix="/contactos", tags=["contactos"])
app.include_router(provincias.router)
app.include_router(municipios.router)
app.include_router(cargos.router)
app.include_router(partidos.router)
app.include_router(tipos.router)
app.include_router(relaciones.router)
app.include_router(seed_boyaca.router)
app.include_router(seed_relaciones.router)
app.include_router(seed_cargos.router)
app.include_router(seed_partidos.router)
app.include_router(seed_tipos.router)
app.include_router(import_excel.router)


@app.get("/")
def read_root():
    return {"message": "API CRM Boyacá", "docs": "/docs"}


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/test-db")
def test_db():
    eng = try_get_engine()
    if eng is None:
        return {"error": "DATABASE_URL no está definida en el entorno."}

    conn = None
    try:
        conn = eng.connect()
        return {"status": "conexion exitosa"}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}
    finally:
        if conn is not None:
            conn.close()
