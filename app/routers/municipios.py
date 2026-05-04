"""CRUD de municipios (provincia_id validado en servicio)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.municipio import MunicipioCreate, MunicipioResponse, MunicipioUpdate
from app.services import catalogo_service

log = logging.getLogger(__name__)

router = APIRouter(prefix="/municipios", tags=["municipios"])


@router.get(
    "",
    response_model=list[MunicipioResponse],
    summary="Listar todos los municipios",
    description=(
        "Catálogo completo ordenado por nombre. Sin filtros devuelve todos los municipios. "
        "Opcional: `provincia_id` acota a una provincia (404 si no existe); `nombre` filtra por ILIKE."
    ),
    operation_id="listar_todos_los_municipios",
)
def listar_municipios(
    db: Session = Depends(get_db),
    provincia_id: int | None = Query(
        None,
        description="Opcional: solo municipios de esta provincia",
        ge=1,
    ),
    nombre: str | None = Query(None, description="Opcional: búsqueda parcial por nombre (ILIKE)"),
) -> list[MunicipioResponse]:
    """
    Lista municipios ordenados por nombre.

    - Sin ``provincia_id``: todos los municipios (opcionalmente filtrados por ``nombre``).
    - Con ``provincia_id``: solo los de esa provincia (404 si la provincia no existe).
    """
    if provincia_id is not None and catalogo_service.obtener_provincia(db, provincia_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provincia no encontrada")
    rows = catalogo_service.listar_municipios(db, provincia_id=provincia_id, nombre=nombre)
    return [MunicipioResponse.model_validate(r) for r in rows]


@router.get("/{municipio_id}", response_model=MunicipioResponse)
def obtener_municipio(municipio_id: int, db: Session = Depends(get_db)) -> MunicipioResponse:
    r = catalogo_service.obtener_municipio(db, municipio_id)
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Municipio no encontrado")
    return MunicipioResponse.model_validate(r)


@router.post("", response_model=MunicipioResponse, status_code=status.HTTP_201_CREATED)
def crear_municipio(payload: MunicipioCreate, db: Session = Depends(get_db)) -> MunicipioResponse:
    log.info("POST municipio nombre=%s provincia_id=%s", payload.nombre, payload.provincia_id)
    r = catalogo_service.crear_municipio(db, payload)
    return MunicipioResponse.model_validate(r)


@router.put("/{municipio_id}", response_model=MunicipioResponse)
def actualizar_municipio(
    municipio_id: int,
    payload: MunicipioUpdate,
    db: Session = Depends(get_db),
) -> MunicipioResponse:
    r = catalogo_service.actualizar_municipio(db, municipio_id, payload)
    return MunicipioResponse.model_validate(r)


@router.delete("/{municipio_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_municipio(municipio_id: int, db: Session = Depends(get_db)) -> None:
    catalogo_service.eliminar_municipio(db, municipio_id)
