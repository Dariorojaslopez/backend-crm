"""Respuestas del endpoint ``POST /import-excel``."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class FilaErrorDetalle(BaseModel):
    fila: int = Field(..., ge=2, description="Número de fila en el Excel (1 = cabecera)")
    errores: list[str]


class ImportExcelResponse(BaseModel):
    status: Literal["ok", "error"] = "ok"
    insertados: int = Field(..., ge=0)
    errores: int = Field(..., ge=0, description="Cantidad de filas con al menos un error (no insertadas)")
    omitidos_duplicados: int = Field(
        0,
        ge=0,
        description="Filas válidas omitidas por duplicado (solo si omitir_duplicados=true)",
    )
    detalle_errores: list[FilaErrorDetalle] = Field(default_factory=list)
