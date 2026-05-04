"""Seed masivo del catálogo de tipos (segmentación de registros)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.seed_tipos_service import seed_tipos_bulk_insert

log = logging.getLogger(__name__)

router = APIRouter(prefix="/seed", tags=["seed"])


class SeedTiposResponse(BaseModel):
    intentados: int = Field(..., ge=0)
    insertados: int = Field(..., ge=0)
    omitidos_por_duplicado_o_conflicto: int = Field(..., ge=0)


@router.post(
    "/tipos",
    response_model=SeedTiposResponse,
    status_code=status.HTTP_200_OK,
    summary="Bulk insert de tipos predefinidos (ON CONFLICT DO NOTHING)",
)
def post_seed_tipos(db: Session = Depends(get_db)) -> SeedTiposResponse:
    try:
        out = seed_tipos_bulk_insert(db)
        return SeedTiposResponse.model_validate(out)
    except SQLAlchemyError as exc:
        log.exception("Error en POST /seed/tipos")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No se pudo completar el seed de tipos: {exc}",
        ) from exc
