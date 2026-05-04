"""Importación masiva de contactos desde Excel (``POST /import-excel``)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.import_excel import ImportExcelResponse
from app.services.excel_service import importar_excel_contactos

log = logging.getLogger(__name__)

router = APIRouter(tags=["importacion"])


@router.post("/import-excel", response_model=ImportExcelResponse)
def post_import_excel(
    db: Session = Depends(get_db),
    archivo: UploadFile = File(
        ...,
        description=(
            "Archivo .xlsx con columnas: nombre, apellidos, telefono, municipio, provincia, cargo, "
            "partido, tipo, relacion, afinidad, influencia, moviliza, ultimo_contacto, proximo_contacto, "
            "responsable, prioridad, notas, periodo. Catálogos deben existir en BD (no se crean)."
        ),
    ),
    omitir_duplicados: bool = Query(
        False,
        description="Si es true, no inserta filas cuyo par (nombre, apellidos, municipio_id) ya exista",
    ),
) -> ImportExcelResponse:
    log.info("POST /import-excel filename=%s omitir_duplicados=%s", archivo.filename, omitir_duplicados)
    data = importar_excel_contactos(db, archivo, omitir_duplicados=omitir_duplicados)
    return ImportExcelResponse.model_validate(data)
