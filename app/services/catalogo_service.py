"""Lógica de negocio para catálogos geográficos y políticos (CRUD + listados)."""

from __future__ import annotations

import logging
from typing import Sequence

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Cargo, Municipio, Partido, Provincia, Tipo
from app.schemas.cargo import CargoCreate, CargoUpdate
from app.schemas.municipio import MunicipioCreate, MunicipioUpdate
from app.schemas.partido import PartidoCreate, PartidoUpdate
from app.schemas.provincia import ProvinciaCreate, ProvinciaUpdate
from app.schemas.tipo import TipoCreate, TipoUpdate

log = logging.getLogger(__name__)


def _fragmento_like_seguro(fragment: str) -> str:
    """Escapa ``\\``, ``%`` y ``_`` para un patrón LIKE con ESCAPE barra invertida."""
    return fragment.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def normalizar_nombre_catalogo(nombre: str) -> str:
    """Unifica nombres de catálogo en mayúsculas (consistente con importación Excel)."""
    return nombre.strip().upper()


def listar_provincias(db: Session, nombre: str | None = None) -> Sequence[Provincia]:
    log.debug("Listando provincias nombre=%s", nombre)
    stmt = select(Provincia).order_by(Provincia.nombre.asc())
    if nombre and nombre.strip():
        stmt = stmt.where(Provincia.nombre.ilike(f"%{nombre.strip()}%"))
    return db.scalars(stmt).all()


def listar_municipios(
    db: Session,
    provincia_id: int | None = None,
    nombre: str | None = None,
) -> Sequence[Municipio]:
    log.debug("Listando municipios provincia_id=%s nombre=%s", provincia_id, nombre)
    stmt = select(Municipio).order_by(Municipio.nombre.asc())
    if provincia_id is not None:
        stmt = stmt.where(Municipio.provincia_id == provincia_id)
    if nombre and nombre.strip():
        stmt = stmt.where(Municipio.nombre.ilike(f"%{nombre.strip()}%"))
    return db.scalars(stmt).all()


def listar_cargos(db: Session, nombre: str | None = None) -> Sequence[Cargo]:
    log.debug("Listando cargos nombre=%s", nombre)
    stmt = select(Cargo).order_by(Cargo.nombre.asc())
    if nombre and nombre.strip():
        stmt = stmt.where(Cargo.nombre.ilike(f"%{nombre.strip()}%"))
    return db.scalars(stmt).all()


def listar_partidos(db: Session, nombre: str | None = None) -> Sequence[Partido]:
    log.debug("Listando partidos nombre=%s", nombre)
    stmt = select(Partido).order_by(Partido.nombre.asc())
    if nombre is not None and nombre != "":
        pat = f"%{_fragmento_like_seguro(nombre)}%"
        stmt = stmt.where(Partido.nombre.like(pat, escape="\\"))
    return db.scalars(stmt).all()


def listar_tipos(db: Session, nombre: str | None = None) -> Sequence[Tipo]:
    log.debug("Listando tipos nombre=%s", nombre)
    stmt = select(Tipo).order_by(Tipo.nombre.asc())
    if nombre and nombre.strip():
        stmt = stmt.where(Tipo.nombre.ilike(f"%{nombre.strip()}%"))
    return db.scalars(stmt).all()


# --- Provincia CRUD ---


def obtener_provincia(db: Session, provincia_id: int) -> Provincia | None:
    return db.get(Provincia, provincia_id)


def crear_provincia(db: Session, data: ProvinciaCreate) -> Provincia:
    n = normalizar_nombre_catalogo(data.nombre)
    if db.scalar(select(Provincia).where(Provincia.nombre == n)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe una provincia con ese nombre",
        )
    p = Provincia(nombre=n)
    db.add(p)
    db.flush()
    log.info("Provincia creada id=%s nombre=%s", p.id, n)
    return p


def actualizar_provincia(db: Session, provincia_id: int, data: ProvinciaUpdate) -> Provincia:
    p = db.get(Provincia, provincia_id)
    if not p:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provincia no encontrada")
    if data.nombre is None:
        return p
    n = normalizar_nombre_catalogo(data.nombre)
    existente = db.scalar(select(Provincia).where(Provincia.nombre == n, Provincia.id != provincia_id))
    if existente:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe otra provincia con ese nombre",
        )
    p.nombre = n
    db.flush()
    log.info("Provincia actualizada id=%s", provincia_id)
    return p


def eliminar_provincia(db: Session, provincia_id: int) -> None:
    p = db.get(Provincia, provincia_id)
    if not p:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provincia no encontrada")
    try:
        db.delete(p)
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        log.warning("No se pudo eliminar provincia id=%s: %s", provincia_id, exc)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se puede eliminar: hay municipios o contactos que referencian esta provincia",
        ) from exc
    log.info("Provincia eliminada id=%s", provincia_id)


# --- Municipio CRUD ---


def obtener_municipio(db: Session, municipio_id: int) -> Municipio | None:
    return db.get(Municipio, municipio_id)


def crear_municipio(db: Session, data: MunicipioCreate) -> Municipio:
    if not db.get(Provincia, data.provincia_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="provincia_id no existe",
        )
    n = normalizar_nombre_catalogo(data.nombre)
    duplicado = db.scalar(
        select(Municipio).where(Municipio.nombre == n, Municipio.provincia_id == data.provincia_id)
    )
    if duplicado:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un municipio con ese nombre en la misma provincia",
        )
    m = Municipio(nombre=n, provincia_id=data.provincia_id)
    db.add(m)
    db.flush()
    log.info("Municipio creado id=%s nombre=%s provincia_id=%s", m.id, n, data.provincia_id)
    return m


def actualizar_municipio(db: Session, municipio_id: int, data: MunicipioUpdate) -> Municipio:
    m = db.get(Municipio, municipio_id)
    if not m:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Municipio no encontrado")

    nueva_provincia_id = data.provincia_id if data.provincia_id is not None else m.provincia_id
    if data.provincia_id is not None and not db.get(Provincia, nueva_provincia_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="provincia_id no existe",
        )

    nuevo_nombre = normalizar_nombre_catalogo(data.nombre) if data.nombre is not None else m.nombre

    if data.nombre is not None or data.provincia_id is not None:
        duplicado = db.scalar(
            select(Municipio).where(
                Municipio.nombre == nuevo_nombre,
                Municipio.provincia_id == nueva_provincia_id,
                Municipio.id != municipio_id,
            )
        )
        if duplicado:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya existe otro municipio con ese nombre en la provincia indicada",
            )

    if data.nombre is not None:
        m.nombre = nuevo_nombre
    if data.provincia_id is not None:
        m.provincia_id = nueva_provincia_id
    db.flush()
    log.info("Municipio actualizado id=%s", municipio_id)
    return m


def eliminar_municipio(db: Session, municipio_id: int) -> None:
    m = db.get(Municipio, municipio_id)
    if not m:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Municipio no encontrado")
    try:
        db.delete(m)
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        log.warning("No se pudo eliminar municipio id=%s: %s", municipio_id, exc)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se puede eliminar: hay contactos que referencian este municipio",
        ) from exc
    log.info("Municipio eliminado id=%s", municipio_id)


# --- Cargo CRUD ---


def obtener_cargo(db: Session, cargo_id: int) -> Cargo | None:
    return db.get(Cargo, cargo_id)


def crear_cargo(db: Session, data: CargoCreate) -> Cargo:
    n = normalizar_nombre_catalogo(data.nombre)
    if db.scalar(select(Cargo).where(Cargo.nombre == n)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un cargo con ese nombre",
        )
    c = Cargo(nombre=n)
    db.add(c)
    db.flush()
    log.info("Cargo creado id=%s nombre=%s", c.id, n)
    return c


def actualizar_cargo(db: Session, cargo_id: int, data: CargoUpdate) -> Cargo:
    c = db.get(Cargo, cargo_id)
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cargo no encontrado")
    if data.nombre is None:
        return c
    n = normalizar_nombre_catalogo(data.nombre)
    existente = db.scalar(select(Cargo).where(Cargo.nombre == n, Cargo.id != cargo_id))
    if existente:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe otro cargo con ese nombre",
        )
    c.nombre = n
    db.flush()
    log.info("Cargo actualizado id=%s", cargo_id)
    return c


def eliminar_cargo(db: Session, cargo_id: int) -> None:
    c = db.get(Cargo, cargo_id)
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cargo no encontrado")
    try:
        db.delete(c)
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se puede eliminar: hay contactos que referencian este cargo",
        ) from exc
    log.info("Cargo eliminado id=%s", cargo_id)


# --- Partido CRUD ---


def obtener_partido(db: Session, partido_id: int) -> Partido | None:
    return db.get(Partido, partido_id)


def crear_partido(db: Session, data: PartidoCreate) -> Partido:
    n = normalizar_nombre_catalogo(data.nombre)
    if db.scalar(select(Partido).where(Partido.nombre == n)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un partido con ese nombre",
        )
    p = Partido(nombre=n)
    db.add(p)
    db.flush()
    log.info("Partido creado id=%s nombre=%s", p.id, n)
    return p


def actualizar_partido(db: Session, partido_id: int, data: PartidoUpdate) -> Partido:
    p = db.get(Partido, partido_id)
    if not p:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Partido no encontrado")
    if data.nombre is None:
        return p
    n = normalizar_nombre_catalogo(data.nombre)
    existente = db.scalar(select(Partido).where(Partido.nombre == n, Partido.id != partido_id))
    if existente:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe otro partido con ese nombre",
        )
    p.nombre = n
    db.flush()
    log.info("Partido actualizado id=%s", partido_id)
    return p


def eliminar_partido(db: Session, partido_id: int) -> None:
    p = db.get(Partido, partido_id)
    if not p:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Partido no encontrado")
    try:
        db.delete(p)
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se puede eliminar: hay contactos que referencian este partido",
        ) from exc
    log.info("Partido eliminado id=%s", partido_id)


# --- Tipo CRUD ---


def obtener_tipo(db: Session, tipo_id: int) -> Tipo | None:
    return db.get(Tipo, tipo_id)


def crear_tipo(db: Session, data: TipoCreate) -> Tipo:
    n = normalizar_nombre_catalogo(data.nombre)
    if db.scalar(select(Tipo).where(Tipo.nombre == n)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un tipo con ese nombre",
        )
    t = Tipo(nombre=n)
    db.add(t)
    db.flush()
    log.info("Tipo creado id=%s nombre=%s", t.id, n)
    return t


def actualizar_tipo(db: Session, tipo_id: int, data: TipoUpdate) -> Tipo:
    t = db.get(Tipo, tipo_id)
    if not t:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tipo no encontrado")
    if data.nombre is None:
        return t
    n = normalizar_nombre_catalogo(data.nombre)
    existente = db.scalar(select(Tipo).where(Tipo.nombre == n, Tipo.id != tipo_id))
    if existente:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe otro tipo con ese nombre",
        )
    t.nombre = n
    db.flush()
    log.info("Tipo actualizado id=%s", tipo_id)
    return t


def eliminar_tipo(db: Session, tipo_id: int) -> None:
    t = db.get(Tipo, tipo_id)
    if not t:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tipo no encontrado")
    try:
        db.delete(t)
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se puede eliminar: hay contactos que referencian este tipo",
        ) from exc
    log.info("Tipo eliminado id=%s", tipo_id)


# --- Helpers usados por importación Excel (sin cambiar firma pública) ---


def obtener_o_crear_provincia(db: Session, nombre: str) -> Provincia:
    nombre_norm = normalizar_nombre_catalogo(nombre)
    existente = db.scalar(select(Provincia).where(Provincia.nombre == nombre_norm))
    if existente:
        return existente
    p = Provincia(nombre=nombre_norm)
    db.add(p)
    db.flush()
    log.info("Provincia creada: %s", nombre_norm)
    return p


def obtener_o_crear_municipio(db: Session, nombre: str, provincia: Provincia) -> Municipio:
    nombre_norm = normalizar_nombre_catalogo(nombre)
    stmt = select(Municipio).where(
        Municipio.nombre == nombre_norm,
        Municipio.provincia_id == provincia.id,
    )
    m = db.scalar(stmt)
    if m:
        return m
    m = Municipio(nombre=nombre_norm, provincia_id=provincia.id)
    db.add(m)
    db.flush()
    log.info("Municipio creado: %s (%s)", nombre_norm, provincia.nombre)
    return m


def obtener_o_crear_partido(db: Session, nombre: str) -> Partido:
    nombre_norm = normalizar_nombre_catalogo(nombre)
    p = db.scalar(select(Partido).where(Partido.nombre == nombre_norm))
    if p:
        return p
    p = Partido(nombre=nombre_norm)
    db.add(p)
    db.flush()
    log.info("Partido creado: %s", nombre_norm)
    return p


def obtener_o_crear_cargo(db: Session, nombre: str) -> Cargo:
    nombre_norm = normalizar_nombre_catalogo(nombre)
    c = db.scalar(select(Cargo).where(Cargo.nombre == nombre_norm))
    if c:
        return c
    c = Cargo(nombre=nombre_norm)
    db.add(c)
    db.flush()
    log.info("Cargo creado: %s", nombre_norm)
    return c


def obtener_o_crear_tipo(db: Session, nombre: str) -> Tipo:
    nombre_norm = normalizar_nombre_catalogo(nombre)
    t = db.scalar(select(Tipo).where(Tipo.nombre == nombre_norm))
    if t:
        return t
    t = Tipo(nombre=nombre_norm)
    db.add(t)
    db.flush()
    log.info("Tipo creado: %s", nombre_norm)
    return t
