"""Esquemas Pydantic para municipios."""

from pydantic import BaseModel, ConfigDict, Field


class MunicipioCreate(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=120)
    provincia_id: int = Field(..., ge=1)


class MunicipioUpdate(BaseModel):
    nombre: str | None = Field(None, min_length=1, max_length=120)
    provincia_id: int | None = Field(None, ge=1)


class MunicipioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    provincia_id: int
