"""Esquemas Pydantic para provincias."""

from pydantic import BaseModel, ConfigDict, Field


class ProvinciaCreate(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=120)


class ProvinciaUpdate(BaseModel):
    nombre: str | None = Field(None, min_length=1, max_length=120)


class ProvinciaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
