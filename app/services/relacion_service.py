"""CRUD y utilidades para el catálogo ``relaciones``."""

from __future__ import annotations

import logging
import re
from typing import Any, Sequence

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Relacion
from app.schemas.relacion import RelacionCreate, RelacionUpdate

log = logging.getLogger(__name__)


def normalizar_nombre_relacion(nombre: str) -> str:
    """Mayúsculas y espacios colapsados (coherente con Excel ``sin_contacto`` → ``SIN CONTACTO``)."""
    s = str(nombre).strip().lower().replace("_", " ")
    s = re.sub(r"\s+", " ", s)
    return s.upper()


def listar_relaciones(db: Session, nombre: str | None = None) -> Sequence[Relacion]:
    stmt = select(Relacion).order_by(Relacion.nombre.asc())
    if nombre and nombre.strip():
        stmt = stmt.where(Relacion.nombre.ilike(f"%{nombre.strip()}%"))
    return db.scalars(stmt).all()


def obtener_relacion(db: Session, relacion_id: int) -> Relacion | None:
    return db.get(Relacion, relacion_id)


def crear_relacion(db: Session, data: RelacionCreate) -> Relacion:
    n = normalizar_nombre_relacion(data.nombre)
    if db.scalar(select(Relacion).where(Relacion.nombre == n)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe una relación con ese nombre",
        )
    r = Relacion(nombre=n)
    db.add(r)
    db.flush()
    log.info("Relación creada id=%s nombre=%s", r.id, n)
    return r


def actualizar_relacion(db: Session, relacion_id: int, data: RelacionUpdate) -> Relacion:
    r = db.get(Relacion, relacion_id)
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Relación no encontrada")
    if data.nombre is None:
        return r
    n = normalizar_nombre_relacion(data.nombre)
    existente = db.scalar(select(Relacion).where(Relacion.nombre == n, Relacion.id != relacion_id))
    if existente:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe otra relación con ese nombre",
        )
    r.nombre = n
    db.flush()
    log.info("Relación actualizada id=%s", relacion_id)
    return r


def eliminar_relacion(db: Session, relacion_id: int) -> None:
    r = db.get(Relacion, relacion_id)
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Relación no encontrada")
    try:
        db.delete(r)
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se puede eliminar: hay contactos que referencian esta relación",
        ) from exc
    log.info("Relación eliminada id=%s", relacion_id)


def obtener_o_crear_relacion(db: Session, nombre_raw: str) -> Relacion:
    """Para importación Excel: busca por nombre normalizado o crea."""
    n = normalizar_nombre_relacion(nombre_raw)
    r = db.scalar(select(Relacion).where(Relacion.nombre == n))
    if r:
        return r
    r = Relacion(nombre=n)
    db.add(r)
    db.flush()
    log.info("Relación creada (import): %s", n)
    return r


# Valores por defecto del seed (POST /seed/relaciones y arranque de la API)
RELACIONES_SEED: tuple[str, ...] = (
    "DEBIL",
    "MEDIA",
    "FUERTE",
    "SIN CONTACTO",
)


def seed_relaciones(db: Session) -> dict[str, Any]:
    """Inserta DEBIL, MEDIA, FUERTE y SIN CONTACTO si no existen (idempotente)."""
    creadas = 0
    for etiqueta in RELACIONES_SEED:
        n = normalizar_nombre_relacion(etiqueta)
        if db.scalar(select(Relacion).where(Relacion.nombre == n)):
            continue
        db.add(Relacion(nombre=n))
        creadas += 1
    db.flush()
    log.info("seed_relaciones: creadas=%s", creadas)
    return {"relaciones_creadas": creadas}


def bootstrap_relaciones(db: Session) -> dict[str, Any]:
    """
    Crea tablas si faltan (``init_db``) y garantiza las cuatro relaciones por defecto.

    Pensado para arranque en Render u otros entornos donde no se ejecutó migración/seed manual.
    """
    from app.database import init_db

    init_db()
    return seed_relaciones(db)
