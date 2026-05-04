"""Rutas HTTP para CRUD y listado filtrado de contactos."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Tipo
from app.schemas.contacto import ContactoCreate, ContactoResponse, ContactoUpdate
from app.schemas.pagination import PaginatedResponse
from app.services import contacto_service

log = logging.getLogger(__name__)

router = APIRouter()


@router.post("", response_model=ContactoResponse, status_code=status.HTTP_201_CREATED)
def crear_contacto(payload: ContactoCreate, db: Session = Depends(get_db)) -> ContactoResponse:
    log.info("POST contacto nombre=%s", payload.nombre)
    return contacto_service.crear_contacto(db, payload)


@router.get(
    "/por-tipo/{tipo_id}",
    response_model=PaginatedResponse[ContactoResponse],
    summary="Listar contactos de un tipo",
    description="Paginado; equivale a GET /contactos?tipo_id=… con validación de que el tipo exista.",
)
def listar_contactos_por_tipo(
    tipo_id: int,
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    nombre: str | None = Query(None, description="Busca en nombre o apellidos (ILIKE)"),
    afinidad: str | None = None,
    influencia: str | None = None,
    periodo: str | None = None,
) -> PaginatedResponse[ContactoResponse]:
    if not db.get(Tipo, tipo_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tipo no encontrado")
    return contacto_service.listar_contactos(
        db,
        tipo_id=tipo_id,
        nombre=nombre,
        afinidad=afinidad,
        influencia=influencia,
        periodo=periodo,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/filtrar",
    response_model=PaginatedResponse[ContactoResponse],
    summary="Listar contactos con filtros múltiples opcionales",
    description=(
        "Filtros opcionales por listas de IDs (AND entre dimensiones). "
        "Repetir query param: ?provincia_ids=1&provincia_ids=2. "
        "También: nombre (ILIKE), afinidad, influencia, periodo, paginación."
    ),
)
def filtrar_contactos(
    db: Session = Depends(get_db),
    provincia_ids: list[int] | None = Query(
        None,
        description="Uno o más IDs de provincia (OR dentro del grupo)",
    ),
    municipio_ids: list[int] | None = Query(None, description="Uno o más IDs de municipio"),
    cargo_ids: list[int] | None = Query(None, description="Uno o más IDs de cargo"),
    partido_ids: list[int] | None = Query(None, description="Uno o más IDs de partido"),
    tipo_ids: list[int] | None = Query(None, description="Uno o más IDs de tipo"),
    relacion_ids: list[int] | None = Query(None, description="Uno o más IDs de relación"),
    nombre: str | None = Query(None, description="Busca en nombre o apellidos (ILIKE)"),
    afinidad: str | None = None,
    influencia: str | None = None,
    periodo: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[ContactoResponse]:
    return contacto_service.listar_contactos(
        db,
        provincia_ids=provincia_ids,
        municipio_ids=municipio_ids,
        cargo_ids=cargo_ids,
        partido_ids=partido_ids,
        tipo_ids=tipo_ids,
        relacion_ids=relacion_ids,
        nombre=nombre,
        afinidad=afinidad,
        influencia=influencia,
        periodo=periodo,
        page=page,
        page_size=page_size,
    )


@router.get("", response_model=PaginatedResponse[ContactoResponse])
def listar_contactos(
    db: Session = Depends(get_db),
    municipio_id: int | None = Query(None, ge=1),
    provincia_id: int | None = Query(None, ge=1),
    cargo_id: int | None = Query(None, ge=1),
    partido_id: int | None = Query(None, ge=1),
    tipo_id: int | None = Query(None, ge=1),
    relacion_id: int | None = Query(None, ge=1),
    afinidad: str | None = None,
    influencia: str | None = None,
    periodo: str | None = None,
    nombre: str | None = Query(None, description="Busca en nombre o apellidos (ILIKE)"),
    page: int = 1,
    page_size: int = 20,
) -> PaginatedResponse[ContactoResponse]:
    """
    Lista paginada con joins (nombres de municipio, provincia, cargo, partido, tipo).

    Orden: prioridad, proximo_contacto, ultimo_contacto, id.
    """
    return contacto_service.listar_contactos(
        db,
        municipio_id=municipio_id,
        provincia_id=provincia_id,
        cargo_id=cargo_id,
        partido_id=partido_id,
        tipo_id=tipo_id,
        relacion_id=relacion_id,
        afinidad=afinidad,
        influencia=influencia,
        periodo=periodo,
        nombre=nombre,
        page=page,
        page_size=page_size,
    )


@router.get("/{contacto_id}", response_model=ContactoResponse)
def obtener_contacto(contacto_id: int, db: Session = Depends(get_db)) -> ContactoResponse:
    c = contacto_service.obtener_contacto(db, contacto_id)
    if not c:
        raise HTTPException(status_code=404, detail="Contacto no encontrado")
    return contacto_service.serialize_contacto(c)


@router.put("/{contacto_id}", response_model=ContactoResponse)
def actualizar_contacto(
    contacto_id: int,
    payload: ContactoUpdate,
    db: Session = Depends(get_db),
) -> ContactoResponse:
    return contacto_service.actualizar_contacto(db, contacto_id, payload)


@router.delete("/{contacto_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_contacto(contacto_id: int, db: Session = Depends(get_db)) -> None:
    contacto_service.eliminar_contacto(db, contacto_id)
