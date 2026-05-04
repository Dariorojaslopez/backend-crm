"""Esquemas Pydantic exportados."""

from app.schemas.cargo import CargoCreate, CargoResponse, CargoUpdate
from app.schemas.contacto import ContactoCreate, ContactoResponse, ContactoUpdate
from app.schemas.municipio import MunicipioCreate, MunicipioResponse, MunicipioUpdate
from app.schemas.pagination import PaginatedResponse
from app.schemas.seed_boyaca import SeedBoyacaResponse
from app.schemas.partido import PartidoCreate, PartidoResponse, PartidoUpdate
from app.schemas.provincia import ProvinciaCreate, ProvinciaResponse, ProvinciaUpdate
from app.schemas.tipo import TipoCreate, TipoResponse, TipoUpdate

__all__ = [
    "CargoCreate",
    "CargoResponse",
    "CargoUpdate",
    "ContactoCreate",
    "ContactoResponse",
    "ContactoUpdate",
    "MunicipioCreate",
    "MunicipioResponse",
    "MunicipioUpdate",
    "PaginatedResponse",
    "SeedBoyacaResponse",
    "PartidoCreate",
    "PartidoResponse",
    "PartidoUpdate",
    "ProvinciaCreate",
    "ProvinciaResponse",
    "ProvinciaUpdate",
    "TipoCreate",
    "TipoResponse",
    "TipoUpdate",
]
