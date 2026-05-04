"""CRUD de partidos."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.partido import PartidoCreate, PartidoResponse, PartidoUpdate
from app.services import catalogo_service

log = logging.getLogger(__name__)

router = APIRouter(prefix="/partidos", tags=["partidos"])


@router.get(
    "",
    response_model=list[PartidoResponse],
    summary="Listar todos los partidos",
    description=(
        "Catálogo completo de partidos (id, nombre), ordenado por nombre ascendente. "
        "Opcional: `nombre` filtra por coincidencia parcial (LIKE, sensible a mayúsculas/minúsculas)."
    ),
    operation_id="listar_todos_los_partidos",
)
def listar_partidos(
    db: Session = Depends(get_db),
    nombre: str | None = Query(None, description="Opcional: búsqueda parcial por nombre (LIKE %valor%)"),
) -> list[PartidoResponse]:
    rows = catalogo_service.listar_partidos(db, nombre=nombre)
    return [PartidoResponse.model_validate(r) for r in rows]


@router.get("/{partido_id}", response_model=PartidoResponse)
def obtener_partido(partido_id: int, db: Session = Depends(get_db)) -> PartidoResponse:
    r = catalogo_service.obtener_partido(db, partido_id)
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Partido no encontrado")
    return PartidoResponse.model_validate(r)


@router.post("", response_model=PartidoResponse, status_code=status.HTTP_201_CREATED)
def crear_partido(payload: PartidoCreate, db: Session = Depends(get_db)) -> PartidoResponse:
    log.info("POST partido nombre=%s", payload.nombre)
    r = catalogo_service.crear_partido(db, payload)
    return PartidoResponse.model_validate(r)


@router.put("/{partido_id}", response_model=PartidoResponse)
def actualizar_partido(
    partido_id: int,
    payload: PartidoUpdate,
    db: Session = Depends(get_db),
) -> PartidoResponse:
    r = catalogo_service.actualizar_partido(db, partido_id, payload)
    return PartidoResponse.model_validate(r)


@router.delete("/{partido_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_partido(partido_id: int, db: Session = Depends(get_db)) -> None:
    catalogo_service.eliminar_partido(db, partido_id)
