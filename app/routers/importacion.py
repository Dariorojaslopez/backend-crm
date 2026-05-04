"""Importación masiva desde Excel."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import contacto_service

log = logging.getLogger(__name__)

router = APIRouter(tags=["importacion"])


@router.post("/import-excel")
def importar_excel(
    db: Session = Depends(get_db),
    archivo: UploadFile = File(..., description="Archivo .xlsx con columnas de contacto"),
) -> dict:
    log.info("Inicio importación Excel filename=%s", archivo.filename)
    return contacto_service.importar_desde_excel(db, archivo)
