"""Esquemas Pydantic para cargos."""

from pydantic import BaseModel, ConfigDict, Field


class CargoCreate(BaseModel):
    nombre: str = Field(..., min_length=1)


class CargoUpdate(BaseModel):
    nombre: str | None = Field(None, min_length=1)


class CargoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
