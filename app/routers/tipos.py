"""CRUD de tipos de figura (alcalde, concejal, diputado, etc.)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.tipo import TipoCreate, TipoResponse, TipoUpdate
from app.services import catalogo_service

log = logging.getLogger(__name__)

router = APIRouter(prefix="/tipos", tags=["tipos"])


@router.get(
    "",
    response_model=list[TipoResponse],
    summary="Listar todos los tipos",
    description=(
        "Catálogo completo de tipos de figura (id, nombre), ordenado por nombre ascendente. "
        "Opcional: `nombre` filtra por coincidencia parcial (ILIKE)."
    ),
    operation_id="listar_todos_los_tipos",
)
def listar_tipos(
    db: Session = Depends(get_db),
    nombre: str | None = Query(None, description="Opcional: búsqueda parcial por nombre (ILIKE)"),
) -> list[TipoResponse]:
    rows = catalogo_service.listar_tipos(db, nombre=nombre)
    return [TipoResponse.model_validate(r) for r in rows]


@router.get("/{tipo_id}", response_model=TipoResponse)
def obtener_tipo(tipo_id: int, db: Session = Depends(get_db)) -> TipoResponse:
    r = catalogo_service.obtener_tipo(db, tipo_id)
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tipo no encontrado")
    return TipoResponse.model_validate(r)


@router.post("", response_model=TipoResponse, status_code=status.HTTP_201_CREATED)
def crear_tipo(payload: TipoCreate, db: Session = Depends(get_db)) -> TipoResponse:
    log.info("POST tipo nombre=%s", payload.nombre)
    r = catalogo_service.crear_tipo(db, payload)
    return TipoResponse.model_validate(r)


@router.put("/{tipo_id}", response_model=TipoResponse)
def actualizar_tipo(
    tipo_id: int,
    payload: TipoUpdate,
    db: Session = Depends(get_db),
) -> TipoResponse:
    r = catalogo_service.actualizar_tipo(db, tipo_id, payload)
    return TipoResponse.model_validate(r)


@router.delete("/{tipo_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_tipo(tipo_id: int, db: Session = Depends(get_db)) -> None:
    catalogo_service.eliminar_tipo(db, tipo_id)
