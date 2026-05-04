"""Esquemas Pydantic para partidos."""

from pydantic import BaseModel, ConfigDict, Field


class PartidoCreate(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=120)


class PartidoUpdate(BaseModel):
    nombre: str | None = Field(None, min_length=1, max_length=120)


class PartidoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
