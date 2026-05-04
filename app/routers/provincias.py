"""CRUD de provincias."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.municipio import MunicipioResponse
from app.schemas.provincia import ProvinciaCreate, ProvinciaResponse, ProvinciaUpdate
from app.services import catalogo_service

log = logging.getLogger(__name__)

router = APIRouter(prefix="/provincias", tags=["provincias"])


@router.get(
    "",
    response_model=list[ProvinciaResponse],
    summary="Listar todas las provincias",
    description=(
        "Catálogo completo ordenado por nombre. Sin parámetros devuelve todas; "
        "con `nombre` filtra por coincidencia parcial (ILIKE)."
    ),
    operation_id="listar_todas_las_provincias",
)
def listar_provincias(
    db: Session = Depends(get_db),
    nombre: str | None = Query(None, description="Opcional: búsqueda parcial por nombre (ILIKE)"),
) -> list[ProvinciaResponse]:
    rows = catalogo_service.listar_provincias(db, nombre=nombre)
    return [ProvinciaResponse.model_validate(r) for r in rows]


@router.get("/{provincia_id}/municipios", response_model=list[MunicipioResponse])
def listar_municipios_por_provincia(
    provincia_id: int,
    db: Session = Depends(get_db),
) -> list[MunicipioResponse]:
    """
    Municipios de una provincia (REST anidado).

    ``GET /provincias/{id}/municipios`` — 404 si la provincia no existe.
    """
    if catalogo_service.obtener_provincia(db, provincia_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provincia no encontrada")
    rows = catalogo_service.listar_municipios(db, provincia_id=provincia_id)
    return [MunicipioResponse.model_validate(r) for r in rows]


@router.get("/{provincia_id}", response_model=ProvinciaResponse)
def obtener_provincia(provincia_id: int, db: Session = Depends(get_db)) -> ProvinciaResponse:
    r = catalogo_service.obtener_provincia(db, provincia_id)
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provincia no encontrada")
    return ProvinciaResponse.model_validate(r)


@router.post("", response_model=ProvinciaResponse, status_code=status.HTTP_201_CREATED)
def crear_provincia(payload: ProvinciaCreate, db: Session = Depends(get_db)) -> ProvinciaResponse:
    log.info("POST provincia nombre=%s", payload.nombre)
    r = catalogo_service.crear_provincia(db, payload)
    return ProvinciaResponse.model_validate(r)


@router.put("/{provincia_id}", response_model=ProvinciaResponse)
def actualizar_provincia(
    provincia_id: int,
    payload: ProvinciaUpdate,
    db: Session = Depends(get_db),
) -> ProvinciaResponse:
    r = catalogo_service.actualizar_provincia(db, provincia_id, payload)
    return ProvinciaResponse.model_validate(r)


@router.delete("/{provincia_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_provincia(provincia_id: int, db: Session = Depends(get_db)) -> None:
    catalogo_service.eliminar_provincia(db, provincia_id)
