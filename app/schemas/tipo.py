"""Esquemas Pydantic para tipos de figura (alcalde, concejal, etc.)."""

from pydantic import BaseModel, ConfigDict, Field


class TipoCreate(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=120)


class TipoUpdate(BaseModel):
    nombre: str | None = Field(None, min_length=1, max_length=120)


class TipoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
