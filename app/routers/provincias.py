"""CRUD de provincias."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.provincia import ProvinciaCreate, ProvinciaResponse, ProvinciaUpdate
from app.services import catalogo_service

log = logging.getLogger(__name__)

router = APIRouter(prefix="/provincias", tags=["provincias"])


@router.get("", response_model=list[ProvinciaResponse])
def listar_provincias(
    db: Session = Depends(get_db),
    nombre: str | None = Query(None, description="Búsqueda parcial (ILIKE), insensible a mayúsculas"),
) -> list[ProvinciaResponse]:
    rows = catalogo_service.listar_provincias(db, nombre=nombre)
    return [ProvinciaResponse.model_validate(r) for r in rows]


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
