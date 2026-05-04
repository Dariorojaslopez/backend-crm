"""Modelo Provincia (Boyacá y otras)."""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Provincia(Base):
    __tablename__ = "provincias"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)

    municipios: Mapped[list[Municipio]] = relationship(
        "Municipio",
        back_populates="provincia",
    )
    contactos: Mapped[list[Contacto]] = relationship("Contacto", back_populates="provincia")
