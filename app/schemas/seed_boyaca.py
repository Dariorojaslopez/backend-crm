"""Respuesta del endpoint de siembra geográfica Boyacá."""

from pydantic import BaseModel, Field


class SeedBoyacaResponse(BaseModel):
    provincias_creadas: int = Field(..., ge=0, description="Provincias insertadas en esta ejecución")
    municipios_creados: int = Field(..., ge=0, description="Municipios insertados en esta ejecución")
