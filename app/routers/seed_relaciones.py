"""Seed del catálogo de relaciones."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.relacion_service import seed_relaciones as ejecutar_seed_relaciones

log = logging.getLogger(__name__)

router = APIRouter(prefix="/seed", tags=["seed"])


class SeedRelacionesResponse(BaseModel):
    relaciones_creadas: int = Field(..., ge=0)


@router.post(
    "/relaciones",
    response_model=SeedRelacionesResponse,
    status_code=status.HTTP_200_OK,
    summary="Insertar relaciones estándar (DEBIL, MEDIO, FUERTE, SIN CONTACTO) si faltan",
)
def post_seed_relaciones(db: Session = Depends(get_db)) -> SeedRelacionesResponse:
    try:
        out = ejecutar_seed_relaciones(db)
        return SeedRelacionesResponse.model_validate(out)
    except SQLAlchemyError as exc:
        log.exception("Error en POST /seed/relaciones")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No se pudo completar el seed: {exc}",
        ) from exc
