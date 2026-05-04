"""Respuesta del endpoint de siembra geográfica Boyacá."""

from pydantic import BaseModel, Field


class SeedBoyacaResponse(BaseModel):
    provincias_creadas: int = Field(..., ge=0, description="Provincias insertadas en esta ejecución")
    municipios_creados: int = Field(..., ge=0, description="Municipios insertados en esta ejecución")


class SyncGeografiaExcelResponse(BaseModel):
    """Resultado de importar provincias/municipios desde Excel (plantilla Nombre + Provincia)."""

    status: str = Field(..., description="ok o mensaje de estado")
    filas_leidas: int = Field(..., ge=0, description="Filas del Excel con nombre y provincia no vacíos")
    provincias_creadas: int = Field(..., ge=0)
    municipios_creados: int = Field(..., ge=0)
    municipios_provincia_actualizada: int = Field(
        ...,
        ge=0,
        description="Municipios existentes cuya provincia se corrigió según el Excel",
    )
    municipios_homonimos_fusionados: int = Field(
        ...,
        ge=0,
        description="Registros municipio duplicados eliminados tras fusionar homónimos",
    )
    advertencias: list[str] = Field(default_factory=list)
