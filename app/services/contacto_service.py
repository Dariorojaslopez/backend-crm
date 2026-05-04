"""Reglas de negocio y consultas para contactos políticos."""

from __future__ import annotations

import logging
import math
from datetime import date, datetime
from collections.abc import Sequence
from typing import Any

from fastapi import HTTPException
from sqlalchemy import case, delete, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models import Cargo, Contacto, Municipio, Partido, Provincia, Relacion, Tipo
from app.schemas.contacto import ContactoCreate, ContactoResponse, ContactoUpdate
from app.schemas.pagination import PaginatedResponse

log = logging.getLogger(__name__)

_PRIORIDAD_ORDEN = case(
    (Contacto.prioridad == "alta", 1),
    (Contacto.prioridad == "media", 2),
    (Contacto.prioridad == "baja", 3),
    else_=4,
)


def _normalizar_texto_corto(val: str | None) -> str | None:
    if val is None:
        return None
    s = str(val).strip()
    return s.lower() if s else None


def _fk_valido(db: Session, model: type, id_: int | None) -> int | None:
    if id_ is None:
        return None
    return id_ if db.get(model, id_) else None


def serialize_contacto(c: Contacto) -> ContactoResponse:
    return ContactoResponse(
        id=c.id,
        nombre=c.nombre,
        apellidos=c.apellidos,
        telefono=c.telefono,
        municipio_id=c.municipio_id,
        provincia_id=c.provincia_id,
        cargo_id=c.cargo_id,
        partido_id=c.partido_id,
        tipo_id=c.tipo_id,
        relacion_id=c.relacion_id,
        municipio_nombre=c.municipio.nombre if c.municipio else None,
        provincia_nombre=c.provincia.nombre if c.provincia else None,
        cargo_nombre=c.cargo.nombre if c.cargo else None,
        partido_nombre=c.partido.nombre if c.partido else None,
        tipo_nombre=c.tipo.nombre if c.tipo else None,
        relacion_nombre=c.relacion.nombre if c.relacion else None,
        afinidad=c.afinidad,
        influencia=c.influencia,
        moviliza=c.moviliza,
        ultimo_contacto=c.ultimo_contacto,
        proximo_contacto=c.proximo_contacto,
        responsable=c.responsable,
        prioridad=c.prioridad,
        notas=c.notas,
        periodo=c.periodo,
        created_at=c.created_at,
    )


def crear_contacto(db: Session, data: ContactoCreate) -> ContactoResponse:
    mun_id = _fk_valido(db, Municipio, data.municipio_id)
    prov_id = _fk_valido(db, Provincia, data.provincia_id)
    if mun_id is not None:
        m = db.get(Municipio, mun_id)
        if m:
            prov_id = m.provincia_id
        else:
            mun_id = None

    cargo_id = _fk_valido(db, Cargo, data.cargo_id)
    partido_id = _fk_valido(db, Partido, data.partido_id)
    tipo_id = _fk_valido(db, Tipo, data.tipo_id)
    relacion_id = _fk_valido(db, Relacion, data.relacion_id)

    nombre = data.nombre.strip() if data.nombre else None
    apellidos = data.apellidos.strip() if data.apellidos else None
    afinidad = _normalizar_texto_corto(data.afinidad) if data.afinidad else None
    influencia = _normalizar_texto_corto(data.influencia) if data.influencia else None
    if data.prioridad:
        prioridad = _normalizar_texto_corto(data.prioridad) or data.prioridad.strip().lower()
    else:
        prioridad = None
    periodo = data.periodo.strip() if data.periodo else None

    c = Contacto(
        nombre=nombre,
        apellidos=apellidos,
        telefono=data.telefono.strip() if data.telefono else None,
        municipio_id=mun_id,
        provincia_id=prov_id,
        cargo_id=cargo_id,
        partido_id=partido_id,
        tipo_id=tipo_id,
        relacion_id=relacion_id,
        afinidad=afinidad,
        influencia=influencia,
        moviliza=data.moviliza,
        ultimo_contacto=data.ultimo_contacto,
        proximo_contacto=data.proximo_contacto,
        responsable=data.responsable.strip() if data.responsable else None,
        prioridad=prioridad,
        notas=data.notas.strip() if data.notas else None,
        periodo=periodo,
    )
    db.add(c)
    db.flush()
    cargado = obtener_contacto(db, c.id)
    if not cargado:
        raise HTTPException(status_code=500, detail="No se pudo recargar el contacto creado")
    log.info("Contacto creado id=%s nombre=%s", c.id, c.nombre)
    return serialize_contacto(cargado)


def obtener_contacto(db: Session, contacto_id: int) -> Contacto | None:
    stmt = (
        select(Contacto)
        .options(
            joinedload(Contacto.municipio),
            joinedload(Contacto.provincia),
            joinedload(Contacto.cargo),
            joinedload(Contacto.partido),
            joinedload(Contacto.tipo),
            joinedload(Contacto.relacion),
        )
        .where(Contacto.id == contacto_id)
    )
    return db.scalars(stmt).unique().one_or_none()


def _ids_catalogo_validos(ids: Sequence[int] | None) -> list[int] | None:
    """Lista deduplicada de enteros >= 1, o None si no hay filtro por catálogo."""
    if ids is None or len(ids) == 0:
        return None
    out = sorted({int(x) for x in ids if x is not None and int(x) >= 1})
    return out or None


def _filtros_listado_contactos(
    *,
    municipio_id: int | None = None,
    municipio_ids: Sequence[int] | None = None,
    provincia_id: int | None = None,
    provincia_ids: Sequence[int] | None = None,
    cargo_id: int | None = None,
    cargo_ids: Sequence[int] | None = None,
    partido_id: int | None = None,
    partido_ids: Sequence[int] | None = None,
    tipo_id: int | None = None,
    tipo_ids: Sequence[int] | None = None,
    relacion_id: int | None = None,
    relacion_ids: Sequence[int] | None = None,
    afinidad: str | None = None,
    influencia: str | None = None,
    periodo: str | None = None,
    nombre: str | None = None,
) -> list[Any]:
    filtros: list[Any] = []

    def add(column: Any, single: int | None, multi: Sequence[int] | None) -> None:
        m = _ids_catalogo_validos(multi)
        if m is not None:
            filtros.append(column.in_(m))
        elif single is not None:
            filtros.append(column == single)

    add(Contacto.municipio_id, municipio_id, municipio_ids)
    add(Contacto.provincia_id, provincia_id, provincia_ids)
    add(Contacto.cargo_id, cargo_id, cargo_ids)
    add(Contacto.partido_id, partido_id, partido_ids)
    add(Contacto.tipo_id, tipo_id, tipo_ids)
    add(Contacto.relacion_id, relacion_id, relacion_ids)

    if afinidad:
        filtros.append(Contacto.afinidad == afinidad.strip().lower())
    if influencia:
        filtros.append(Contacto.influencia == influencia.strip().lower())
    if periodo:
        filtros.append(Contacto.periodo == periodo.strip())
    if nombre and nombre.strip():
        term = f"%{nombre.strip()}%"
        filtros.append(
            or_(
                Contacto.nombre.ilike(term),
                Contacto.apellidos.ilike(term),
            )
        )
    return filtros


def listar_contactos(
    db: Session,
    *,
    municipio_id: int | None = None,
    municipio_ids: Sequence[int] | None = None,
    provincia_id: int | None = None,
    provincia_ids: Sequence[int] | None = None,
    cargo_id: int | None = None,
    cargo_ids: Sequence[int] | None = None,
    partido_id: int | None = None,
    partido_ids: Sequence[int] | None = None,
    tipo_id: int | None = None,
    tipo_ids: Sequence[int] | None = None,
    relacion_id: int | None = None,
    relacion_ids: Sequence[int] | None = None,
    afinidad: str | None = None,
    influencia: str | None = None,
    periodo: str | None = None,
    nombre: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> PaginatedResponse[ContactoResponse]:
    if page < 1:
        raise HTTPException(status_code=400, detail="page debe ser >= 1")
    if page_size < 1 or page_size > 100:
        raise HTTPException(status_code=400, detail="page_size entre 1 y 100")

    filtros = _filtros_listado_contactos(
        municipio_id=municipio_id,
        municipio_ids=municipio_ids,
        provincia_id=provincia_id,
        provincia_ids=provincia_ids,
        cargo_id=cargo_id,
        cargo_ids=cargo_ids,
        partido_id=partido_id,
        partido_ids=partido_ids,
        tipo_id=tipo_id,
        tipo_ids=tipo_ids,
        relacion_id=relacion_id,
        relacion_ids=relacion_ids,
        afinidad=afinidad,
        influencia=influencia,
        periodo=periodo,
        nombre=nombre,
    )

    count_stmt = select(func.count()).select_from(Contacto)
    if filtros:
        count_stmt = count_stmt.where(*filtros)
    total = db.scalar(count_stmt) or 0

    base_opts = (
        joinedload(Contacto.municipio),
        joinedload(Contacto.provincia),
        joinedload(Contacto.cargo),
        joinedload(Contacto.partido),
        joinedload(Contacto.tipo),
        joinedload(Contacto.relacion),
    )
    stmt = select(Contacto).options(*base_opts)
    if filtros:
        stmt = stmt.where(*filtros)

    stmt = stmt.order_by(
        _PRIORIDAD_ORDEN.asc(),
        Contacto.proximo_contacto.asc().nulls_last(),
        Contacto.ultimo_contacto.desc().nulls_last(),
        Contacto.id.asc(),
    )
    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)

    rows = db.scalars(stmt).unique().all()
    items = [serialize_contacto(c) for c in rows]
    pages = math.ceil(total / page_size) if page_size else 0
    log.debug("Listado contactos total=%s page=%s", total, page)
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


def actualizar_contacto(db: Session, contacto_id: int, data: ContactoUpdate) -> ContactoResponse:
    c = obtener_contacto(db, contacto_id)
    if not c:
        raise HTTPException(status_code=404, detail="Contacto no encontrado")

    payload = data.model_dump(exclude_unset=True)

    for campo, valor in payload.items():
        if campo in {"afinidad", "influencia", "prioridad"} and isinstance(valor, str):
            valor = valor.strip().lower() or None
        if campo in {"nombre", "apellidos", "periodo"} and isinstance(valor, str):
            valor = valor.strip() or None
        if campo == "telefono" and isinstance(valor, str):
            valor = valor.strip() or None
        if campo == "notas" and isinstance(valor, str):
            valor = valor.strip() or None
        if campo == "responsable" and isinstance(valor, str):
            valor = valor.strip() or None
        if campo in {"municipio_id", "provincia_id", "cargo_id", "partido_id", "tipo_id", "relacion_id"}:
            modelo = {
                "municipio_id": Municipio,
                "provincia_id": Provincia,
                "cargo_id": Cargo,
                "partido_id": Partido,
                "tipo_id": Tipo,
                "relacion_id": Relacion,
            }[campo]
            if valor is not None and not db.get(modelo, int(valor)):
                valor = None
        setattr(c, campo, valor)

    if c.municipio_id is not None:
        m = db.get(Municipio, c.municipio_id)
        if m:
            c.provincia_id = m.provincia_id
        else:
            c.municipio_id = None

    if c.provincia_id is not None and not db.get(Provincia, c.provincia_id):
        c.provincia_id = None

    for fk_attr, modelo in (
        ("cargo_id", Cargo),
        ("partido_id", Partido),
        ("tipo_id", Tipo),
        ("relacion_id", Relacion),
    ):
        vid = getattr(c, fk_attr)
        if vid is not None and not db.get(modelo, vid):
            setattr(c, fk_attr, None)

    db.flush()
    cargado = obtener_contacto(db, contacto_id)
    if not cargado:
        raise HTTPException(status_code=404, detail="Contacto no encontrado tras actualizar")
    log.info("Contacto actualizado id=%s", contacto_id)
    return serialize_contacto(cargado)


def eliminar_contacto(db: Session, contacto_id: int) -> None:
    c = db.get(Contacto, contacto_id)
    if not c:
        raise HTTPException(status_code=404, detail="Contacto no encontrado")
    db.delete(c)
    log.info("Contacto eliminado id=%s", contacto_id)


def eliminar_todos_contactos(db: Session) -> int:
    """Elimina todos los contactos y devuelve la cantidad de filas borradas."""
    result = db.execute(delete(Contacto))
    eliminados = int(result.rowcount or 0)
    log.warning("Eliminación masiva de contactos completada, total=%s", eliminados)
    return eliminados
