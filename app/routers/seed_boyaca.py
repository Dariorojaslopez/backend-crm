"""Endpoint de siembra geográfica Boyacá."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db_seed_boyaca
from app.schemas.seed_boyaca import SeedBoyacaResponse, SyncGeografiaExcelResponse
from app.services.geografia_excel_service import sincronizar_municipios_provincias_desde_excel
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


@router.post(
    "/seed-boyaca/municipios-desde-excel",
    response_model=SyncGeografiaExcelResponse,
    status_code=status.HTTP_200_OK,
    summary="Actualizar provincias y municipios desde Excel",
    description=(
        "Archivo .xlsx con columnas **Nombre** (municipio) y **Provincia** (subregión). "
        "Crea lo que falte, corrige ``provincia_id`` de municipios existentes y alinea contactos."
    ),
)
def post_municipios_desde_excel(
    db: Session = Depends(get_db_seed_boyaca),
    archivo: UploadFile = File(
        ...,
        description="Excel con columnas Nombre y Provincia (multipart, campo `archivo`).",
    ),
) -> SyncGeografiaExcelResponse:
    try:
        resultado = sincronizar_municipios_provincias_desde_excel(db, archivo)
        return SyncGeografiaExcelResponse.model_validate(resultado)
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        log.exception("Error de base de datos en POST /seed-boyaca/municipios-desde-excel")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No se pudo sincronizar la geografía: {exc}",
        ) from exc
