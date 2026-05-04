"""Seed masivo del catálogo de cargos desde archivo empaquetado."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.seed_cargos_service import (
    DEFAULT_CARGOS_SEED_PATH,
    read_cargos_lines_from_file,
    seed_cargos_bulk_insert,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/seed", tags=["seed"])


class SeedCargosResponse(BaseModel):
    intentados: int = Field(..., ge=0)
    insertados: int = Field(..., ge=0)
    omitidos_por_duplicado_o_conflicto: int = Field(..., ge=0)


@router.post(
    "/cargos",
    response_model=SeedCargosResponse,
    status_code=status.HTTP_200_OK,
    summary="Bulk insert de cargos desde cargos_seed.txt (ON CONFLICT DO NOTHING)",
)
def post_seed_cargos(db: Session = Depends(get_db)) -> SeedCargosResponse:
    if not DEFAULT_CARGOS_SEED_PATH.is_file():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No se encontró el archivo de seed: {DEFAULT_CARGOS_SEED_PATH}",
        )
    try:
        lineas = read_cargos_lines_from_file(DEFAULT_CARGOS_SEED_PATH)
        out = seed_cargos_bulk_insert(db, lineas)
        return SeedCargosResponse.model_validate(out)
    except SQLAlchemyError as exc:
        log.exception("Error en POST /seed/cargos")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No se pudo completar el seed de cargos: {exc}",
        ) from exc
