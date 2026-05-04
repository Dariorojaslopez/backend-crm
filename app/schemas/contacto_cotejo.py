"""Cotejo de datos de contacto contra catálogos (sin persistir)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ContactoCotejoFilaEntrada(BaseModel):
    """Textos como en plantilla Excel y/o IDs explícitos para validar."""

    nombre: str | None = Field(None, max_length=120)
    apellidos: str | None = Field(None, max_length=180)
    provincia: str | None = None
    municipio: str | None = None
    cargo: str | None = None
    partido: str | None = None
    tipo: str | None = None
    relacion: str | None = None

    provincia_id: int | None = Field(None, ge=1)
    municipio_id: int | None = Field(None, ge=1)
    cargo_id: int | None = Field(None, ge=1)
    partido_id: int | None = Field(None, ge=1)
    tipo_id: int | None = Field(None, ge=1)
    relacion_id: int | None = Field(None, ge=1)


class ContactoCotejoFilaSalida(BaseModel):
    """Resultado del cotejo de una fila contra provincias, municipios, cargos, partidos, tipos y relaciones."""

    indice: int = Field(..., ge=0, description="Índice 0-based en el arreglo enviado")
    provincia_id: int | None = None
    municipio_id: int | None = None
    cargo_id: int | None = None
    partido_id: int | None = None
    tipo_id: int | None = None
    relacion_id: int | None = None

    provincia_nombre: str | None = None
    municipio_nombre: str | None = None
    cargo_nombre: str | None = None
    partido_nombre: str | None = None
    tipo_nombre: str | None = None
    relacion_nombre: str | None = None

    alertas: list[str] = Field(default_factory=list)
    cotejo_sin_alertas: bool = Field(
        ...,
        description="True si no hay incoherencias ni valores de catálogo no resueltos",
    )


class ContactoCotejarRequest(BaseModel):
    filas: list[ContactoCotejoFilaEntrada] = Field(
        ...,
        max_length=500,
        description="Hasta 500 filas por petición",
    )


class ContactoCotejarResponse(BaseModel):
    total_filas: int
    filas_sin_alertas: int
    filas_con_alertas: int
    resultados: list[ContactoCotejoFilaSalida]
