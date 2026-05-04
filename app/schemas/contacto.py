"""Esquemas Pydantic para contactos políticos."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class ContactoCreate(BaseModel):
    """Payload para crear un contacto; todos los campos son opcionales."""

    nombre: str | None = Field(None, max_length=120)
    apellidos: str | None = Field(None, max_length=180)
    telefono: str | None = Field(None, max_length=40)

    municipio_id: int | None = None
    provincia_id: int | None = None
    cargo_id: int | None = None
    partido_id: int | None = None
    tipo_id: int | None = None
    relacion_id: int | None = None

    afinidad: str | None = Field(None, description="aliado | neutro | opositor")
    influencia: str | None = Field(None, description="alto | medio | bajo")

    moviliza: bool = False

    ultimo_contacto: date | None = None
    proximo_contacto: date | None = None

    responsable: str | None = Field(None, max_length=200)
    prioridad: str | None = Field(None, description="alta | media | baja")
    notas: str | None = None
    periodo: str | None = Field(None, max_length=64)


class ContactoUpdate(BaseModel):
    """Actualización parcial (PUT con campos opcionales)."""

    nombre: str | None = Field(None, max_length=120)
    apellidos: str | None = Field(None, max_length=180)
    telefono: str | None = Field(None, max_length=40)

    municipio_id: int | None = None
    provincia_id: int | None = None
    cargo_id: int | None = None
    partido_id: int | None = None
    tipo_id: int | None = None
    relacion_id: int | None = None

    afinidad: str | None = None
    influencia: str | None = None

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
    nombre: str | None
    apellidos: str | None
    telefono: str | None

    municipio_id: int | None
    provincia_id: int | None
    cargo_id: int | None
    partido_id: int | None
    tipo_id: int | None
    relacion_id: int | None

    municipio_nombre: str | None = None
    provincia_nombre: str | None = None
    cargo_nombre: str | None = None
    partido_nombre: str | None = None
    tipo_nombre: str | None = None
    relacion_nombre: str | None = None

    afinidad: str | None
    influencia: str | None

    moviliza: bool

    ultimo_contacto: date | None
    proximo_contacto: date | None

    responsable: str | None
    prioridad: str | None
    notas: str | None

    periodo: str | None
    created_at: datetime
