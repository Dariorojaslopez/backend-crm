"""Endpoint de siembra geográfica Boyacá."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db_seed_boyaca
from app.schemas.seed_boyaca import SeedBoyacaResponse
from app.services.seed_boyaca import seed_boyaca as ejecutar_seed_boyaca

log = logging.getLogger(__name__)

router = APIRouter(tags=["seed"])


@router.post(
    "/seed-boyaca",
    response_model=SeedBoyacaResponse,
    status_code=status.HTTP_200_OK,
    summary="Poblar provincias y municipios Boyacá (idempotente)",
)
def post_seed_boyaca(db: Session = Depends(get_db_seed_boyaca)) -> SeedBoyacaResponse:
    try:
        resultado = ejecutar_seed_boyaca(db)
        return SeedBoyacaResponse.model_validate(resultado)
    except SQLAlchemyError as exc:
        log.exception("Error de base de datos en POST /seed-boyaca")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No se pudo completar el seed: {exc}",
        ) from exc
