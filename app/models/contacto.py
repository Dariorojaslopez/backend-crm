"""Modelo Contacto político CRM."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, Text, false, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.cargo import Cargo
from app.models.municipio import Municipio
from app.models.partido import Partido
from app.models.provincia import Provincia
from app.models.relacion import Relacion
from app.models.tipo import Tipo


class Contacto(Base):
    __tablename__ = "contactos"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nombre: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    apellidos: Mapped[str | None] = mapped_column(String(180), nullable=True, index=True)
    telefono: Mapped[str | None] = mapped_column(String(40), nullable=True)

    municipio_id: Mapped[int | None] = mapped_column(
        ForeignKey("municipios.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    provincia_id: Mapped[int | None] = mapped_column(
        ForeignKey("provincias.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    cargo_id: Mapped[int | None] = mapped_column(
        ForeignKey("cargos.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    partido_id: Mapped[int | None] = mapped_column(
        ForeignKey("partidos.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    tipo_id: Mapped[int | None] = mapped_column(
        ForeignKey("tipos.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    relacion_id: Mapped[int | None] = mapped_column(
        ForeignKey("relaciones.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    afinidad: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    influencia: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)

    moviliza: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )

    ultimo_contacto: Mapped[date | None] = mapped_column(Date, nullable=True)
    proximo_contacto: Mapped[date | None] = mapped_column(Date, nullable=True)

    responsable: Mapped[str | None] = mapped_column(String(200), nullable=True)
    prioridad: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    notas: Mapped[str | None] = mapped_column(Text, nullable=True)

    periodo: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    municipio: Mapped[Municipio | None] = relationship("Municipio", back_populates="contactos")
    provincia: Mapped[Provincia | None] = relationship("Provincia", back_populates="contactos")
    cargo: Mapped[Cargo | None] = relationship("Cargo", back_populates="contactos")
    partido: Mapped[Partido | None] = relationship("Partido", back_populates="contactos")
    tipo: Mapped[Tipo | None] = relationship("Tipo", back_populates="contactos")
    relacion: Mapped[Relacion | None] = relationship("Relacion", back_populates="contactos")
