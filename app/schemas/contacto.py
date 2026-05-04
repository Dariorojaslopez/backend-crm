"""Esquemas Pydantic para contactos políticos."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class ContactoCreate(BaseModel):
    """Payload para crear un contacto (validación de entrada)."""

    nombre: str = Field(..., max_length=120)
    apellidos: str = Field(..., max_length=180)
    telefono: str | None = Field(None, max_length=40)

    municipio_id: int = Field(..., ge=1)
    provincia_id: int = Field(..., ge=1)
    cargo_id: int = Field(..., ge=1)
    partido_id: int = Field(..., ge=1)
    tipo_id: int = Field(..., ge=1)

    afinidad: str = Field(..., description="aliado | neutro | opositor")
    influencia: str = Field(..., description="alto | medio | bajo")
    relacion: str = Field(..., description="fuerte | media | debil | sin_contacto")

    moviliza: bool = False

    ultimo_contacto: date | None = None
    proximo_contacto: date | None = None

    responsable: str | None = Field(None, max_length=200)
    prioridad: str = Field(..., description="alta | media | baja")
    notas: str | None = None
    periodo: str = Field(..., max_length=64)


class ContactoUpdate(BaseModel):
    """Actualización parcial (PUT con campos opcionales)."""

    nombre: str | None = Field(None, max_length=120)
    apellidos: str | None = Field(None, max_length=180)
    telefono: str | None = Field(None, max_length=40)

    municipio_id: int | None = Field(None, ge=1)
    provincia_id: int | None = Field(None, ge=1)
    cargo_id: int | None = Field(None, ge=1)
    partido_id: int | None = Field(None, ge=1)
    tipo_id: int | None = Field(None, ge=1)

    afinidad: str | None = None
    influencia: str | None = None
    relacion: str | None = None

    moviliza: bool | None = None

    ultimo_contacto: date | None = None
    proximo_contacto: date | None = None

    responsable: str | None = Field(None, max_length=200)
    prioridad: str | None = None
    notas: str | None = None
    periodo: str | None = Field(None, max_length=64)


class ContactoResponse(BaseModel):
    """Contacto serializado para el frontend (catálogos resueltos por join)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    apellidos: str
    telefono: str | None

    municipio_id: int
    provincia_id: int
    cargo_id: int
    partido_id: int
    tipo_id: int

    municipio_nombre: str | None = None
    provincia_nombre: str | None = None
    cargo_nombre: str | None = None
    partido_nombre: str | None = None
    tipo_nombre: str | None = None

    afinidad: str
    influencia: str
    relacion: str

    moviliza: bool

    ultimo_contacto: date | None
    proximo_contacto: date | None

    responsable: str | None
    prioridad: str
    notas: str | None

    periodo: str
    created_at: datetime
