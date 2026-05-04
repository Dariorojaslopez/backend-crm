"""CRUD de cargos."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.cargo import CargoCreate, CargoResponse, CargoUpdate
from app.services import catalogo_service

log = logging.getLogger(__name__)

router = APIRouter(prefix="/cargos", tags=["cargos"])


@router.get("", response_model=list[CargoResponse])
def listar_cargos(
    db: Session = Depends(get_db),
    nombre: str | None = Query(None, description="Búsqueda parcial (ILIKE)"),
) -> list[CargoResponse]:
    rows = catalogo_service.listar_cargos(db, nombre=nombre)
    return [CargoResponse.model_validate(r) for r in rows]


@router.get("/{cargo_id}", response_model=CargoResponse)
def obtener_cargo(cargo_id: int, db: Session = Depends(get_db)) -> CargoResponse:
    r = catalogo_service.obtener_cargo(db, cargo_id)
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cargo no encontrado")
    return CargoResponse.model_validate(r)


@router.post("", response_model=CargoResponse, status_code=status.HTTP_201_CREATED)
def crear_cargo(payload: CargoCreate, db: Session = Depends(get_db)) -> CargoResponse:
    log.info("POST cargo nombre=%s", payload.nombre)
    r = catalogo_service.crear_cargo(db, payload)
    return CargoResponse.model_validate(r)


@router.put("/{cargo_id}", response_model=CargoResponse)
def actualizar_cargo(
    cargo_id: int,
    payload: CargoUpdate,
    db: Session = Depends(get_db),
) -> CargoResponse:
    r = catalogo_service.actualizar_cargo(db, cargo_id, payload)
    return CargoResponse.model_validate(r)


@router.delete("/{cargo_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_cargo(cargo_id: int, db: Session = Depends(get_db)) -> None:
    catalogo_service.eliminar_cargo(db, cargo_id)
