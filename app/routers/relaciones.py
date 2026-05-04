"""CRUD del catálogo ``relaciones`` (tipo de vínculo con el contacto)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.relacion import RelacionCreate, RelacionResponse, RelacionUpdate
from app.services import relacion_service

log = logging.getLogger(__name__)

router = APIRouter(prefix="/relaciones", tags=["relaciones"])


@router.get(
    "",
    response_model=list[RelacionResponse],
    summary="Listar todas las relaciones",
    description=(
        "Devuelve todas las relaciones (id, nombre), ordenadas por nombre ascendente. "
        "Sin query params lista el catálogo completo; con `nombre` filtra por ILIKE."
    ),
    operation_id="listar_todas_las_relaciones",
)
def listar_relaciones(
    db: Session = Depends(get_db),
    nombre: str | None = Query(None, description="Opcional: búsqueda parcial por nombre (ILIKE)"),
) -> list[RelacionResponse]:
    rows = relacion_service.listar_relaciones(db, nombre=nombre)
    return [RelacionResponse.model_validate(r) for r in rows]


@router.get("/{relacion_id}", response_model=RelacionResponse)
def obtener_relacion(relacion_id: int, db: Session = Depends(get_db)) -> RelacionResponse:
    r = relacion_service.obtener_relacion(db, relacion_id)
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Relación no encontrada")
    return RelacionResponse.model_validate(r)


@router.post("", response_model=RelacionResponse, status_code=status.HTTP_201_CREATED)
def crear_relacion(payload: RelacionCreate, db: Session = Depends(get_db)) -> RelacionResponse:
    log.info("POST relación nombre=%s", payload.nombre)
    r = relacion_service.crear_relacion(db, payload)
    return RelacionResponse.model_validate(r)


@router.put("/{relacion_id}", response_model=RelacionResponse)
def actualizar_relacion(
    relacion_id: int,
    payload: RelacionUpdate,
    db: Session = Depends(get_db),
) -> RelacionResponse:
    r = relacion_service.actualizar_relacion(db, relacion_id, payload)
    return RelacionResponse.model_validate(r)


@router.delete("/{relacion_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_relacion(relacion_id: int, db: Session = Depends(get_db)) -> None:
    relacion_service.eliminar_relacion(db, relacion_id)
