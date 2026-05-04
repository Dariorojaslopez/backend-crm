"""Catálogo de tipo de relación con el contacto (débil, medio, fuerte, etc.)."""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Relacion(Base):
    __tablename__ = "relaciones"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)

    contactos: Mapped[list[Contacto]] = relationship("Contacto", back_populates="relacion")
