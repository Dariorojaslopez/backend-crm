"""Seed masivo del catálogo de partidos desde archivo empaquetado."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.partidos_excel_service import seed_partidos_desde_excel
from app.services.seed_partidos_service import (
    DEFAULT_PARTIDOS_SEED_PATH,
    read_partidos_lines_from_file,
    seed_partidos_bulk_insert,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/seed", tags=["seed"])


class SeedPartidosResponse(BaseModel):
    intentados: int = Field(..., ge=0)
    insertados: int = Field(..., ge=0)
    omitidos_por_duplicado_o_conflicto: int = Field(..., ge=0)


class SeedPartidosExcelResponse(BaseModel):
    status: str = Field(default="ok")
    filas_leidas: int = Field(..., ge=0)
    nombres_unicos_en_excel: int = Field(..., ge=0)
    insertados: int = Field(..., ge=0)
    omitidos_ya_en_bd: int = Field(..., ge=0)
    omitidos_vacio_en_excel: int = Field(..., ge=0)


@router.post(
    "/partidos",
    response_model=SeedPartidosResponse,
    status_code=status.HTTP_200_OK,
    summary="Bulk insert de partidos desde partidos_seed.txt (ON CONFLICT DO NOTHING)",
)
def post_seed_partidos(db: Session = Depends(get_db)) -> SeedPartidosResponse:
    if not DEFAULT_PARTIDOS_SEED_PATH.is_file():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No se encontró el archivo de seed: {DEFAULT_PARTIDOS_SEED_PATH}",
        )
    try:
        lineas = read_partidos_lines_from_file(DEFAULT_PARTIDOS_SEED_PATH)
        out = seed_partidos_bulk_insert(db, lineas)
        return SeedPartidosResponse.model_validate(out)
    except SQLAlchemyError as exc:
        log.exception("Error en POST /seed/partidos")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No se pudo completar el seed de partidos: {exc}",
        ) from exc


@router.post(
    "/partidos-desde-excel",
    response_model=SeedPartidosExcelResponse,
    status_code=status.HTTP_200_OK,
    summary="Insertar partidos desde Excel (solo los que no existen)",
    description=(
        "Archivo .xlsx con una columna de nombres de partido, o columnas «nombre» / «partido». "
        "Se deduplica por nombre normalizado (trim + mayúsculas) y se insertan solo filas nuevas."
    ),
)
def post_seed_partidos_desde_excel(
    db: Session = Depends(get_db),
    archivo: UploadFile = File(
        ...,
        description="Excel con listado de partidos (multipart, campo `archivo`).",
    ),
) -> SeedPartidosExcelResponse:
    try:
        resultado = seed_partidos_desde_excel(db, archivo)
        return SeedPartidosExcelResponse.model_validate(resultado)
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        log.exception("Error en POST /seed/partidos-desde-excel")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No se pudo importar partidos desde Excel: {exc}",
        ) from exc
