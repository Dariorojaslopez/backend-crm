"""Modelo Municipio ligado a una provincia."""

from __future__ import annotations

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.provincia import Provincia


class Municipio(Base):
    __tablename__ = "municipios"
    __table_args__ = (
        UniqueConstraint("nombre", "provincia_id", name="uq_municipio_nombre_provincia"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    provincia_id: Mapped[int] = mapped_column(
        ForeignKey("provincias.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    provincia: Mapped[Provincia] = relationship("Provincia", back_populates="municipios")
    contactos: Mapped[list[Contacto]] = relationship("Contacto", back_populates="municipio")
