"""Respuestas paginadas reutilizables."""

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Contenedor genérico de paginación para listados grandes."""

    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int
