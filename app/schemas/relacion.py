"""Esquemas Pydantic para relaciones (contacto)."""

from pydantic import BaseModel, ConfigDict, Field


class RelacionCreate(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=120)


class RelacionUpdate(BaseModel):
    nombre: str | None = Field(None, min_length=1, max_length=120)


class RelacionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
