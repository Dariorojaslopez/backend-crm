"""Modelos ORM: importar este módulo antes de ``init_db()`` para registrar tablas."""

from app.models.base import Base
from app.models.cargo import Cargo
from app.models.contacto import Contacto
from app.models.municipio import Municipio
from app.models.partido import Partido
from app.models.provincia import Provincia
from app.models.relacion import Relacion
from app.models.tipo import Tipo

__all__ = ["Base", "Cargo", "Contacto", "Municipio", "Partido", "Provincia", "Relacion", "Tipo"]
