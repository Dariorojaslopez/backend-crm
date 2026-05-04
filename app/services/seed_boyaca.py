"""
Siembra de provincias (subregiones) y municipios de Boyacá.

Las claves del JSON se persisten como ``Provincia.nombre``; cada lista como
``Municipio`` vinculado por ``provincia_id``. Idempotente: no duplica por nombre.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import init_db
from app.models import Municipio, Provincia
from app.services.catalogo_service import normalizar_nombre_catalogo

log = logging.getLogger(__name__)

# Fuente: agrupación regional dentro del departamento (claves = "provincias" lógicas del seed).
BOYACA_DATA: dict[str, list[str]] = {
    "Centro": [
        "Tunja",
        "Cómbita",
        "Oicatá",
        "Chivatá",
        "Motavita",
        "Sora",
        "Soracá",
        "Toca",
        "Samacá",
        "Ventaquemada",
        "Siachoque",
        "Chíquiza",
    ],
    "Tundama": [
        "Duitama",
        "Paipa",
        "Santa Rosa de Viterbo",
        "Cerinza",
        "Belén",
        "Tutazá",
        "Floresta",
        "Busbanzá",
    ],
    "Sugamuxi": [
        "Sogamoso",
        "Aquitania",
        "Firavitoba",
        "Iza",
        "Pesca",
        "Tota",
        "Cuitiva",
        "Monguí",
        "Mongua",
        "Gameza",
        "Nobsa",
        "Tibasosa",
    ],
    "Occidente": [
        "Chiquinquirá",
        "Saboyá",
        "Briceño",
        "Buenavista",
        "Caldas",
        "Coper",
        "La Victoria",
        "Maripí",
        "Muzo",
        "Otanche",
        "Pauna",
        "Quípama",
        "San Miguel de Sema",
        "San Pablo de Borbur",
    ],
    "Oriente": [
        "Miraflores",
        "Berbeo",
        "Campohermoso",
        "Páez",
        "San Eduardo",
        "Zetaquirá",
    ],
    "Lengupá": [
        "Miraflores",
        "Berbeo",
        "Campohermoso",
        "Páez",
        "San Eduardo",
        "Zetaquirá",
    ],
    "Neira": [
        "Garagoa",
        "Chinavita",
        "Macanal",
        "San Luis de Gaceno",
        "Santa María",
        "Sutatenza",
        "Tenza",
        "Guateque",
        "La Capilla",
        "Pachavita",
        "Somondoco",
    ],
    "Ricaurte": [
        "Moniquirá",
        "Arcabuco",
        "Chitaraque",
        "Gachantivá",
        "Ráquira",
        "Sáchica",
        "San José de Pare",
        "Santa Sofía",
        "Sutamarchán",
        "Tinjacá",
        "Villa de Leyva",
    ],
    "Valderrama": [
        "Socha",
        "Paz de Río",
        "Sativanorte",
        "Sativasur",
        "Jericó",
        "Chita",
        "Socotá",
        "Tasco",
        "Betéitiva",
    ],
    "Norte": [
        "Soatá",
        "Boavita",
        "Covarachía",
        "La Uvita",
        "San Mateo",
        "Susacón",
        "Tipacoque",
        "El Espino",
        "Guacamayas",
        "Panqueba",
        "Chiscas",
        "El Cocuy",
        "Güicán",
    ],
    "Gutiérrez": [
        "El Cocuy",
        "Güicán",
        "Chiscas",
        "Panqueba",
        "Guacamayas",
    ],
    "Márquez": [
        "Ramiriquí",
        "Boyacá",
        "Ciénega",
        "Jenesano",
        "Nuevo Colón",
        "Rondón",
        "Tibaná",
        "Turmequé",
        "Viracachá",
        "Umbita",
    ],
    "La Libertad": [
        "Pisba",
        "Paya",
        "Labranzagrande",
    ],
}


def seed_boyaca(db: Session) -> dict[str, Any]:
    """
    Inserta provincias (claves de ``BOYACA_DATA``) y municipios asociados si no existen.

    Crea antes el esquema con ``init_db()`` si la base aún no tiene tablas (p. ej. PostgreSQL nuevo
    en Render sin haber ejecutado migraciones manualmente).

    Cuenta solo filas nuevas creadas en esta ejecución. La sesión debe gestionar commit/rollback
    (p. ej. dependencia ``get_db``).
    """
    init_db()
    db.expire_all()

    provincias_creadas = 0
    municipios_creados = 0

    try:
        for zona_raw, municipios in BOYACA_DATA.items():
            nombre_provincia = normalizar_nombre_catalogo(zona_raw)
            provincia = db.scalar(select(Provincia).where(Provincia.nombre == nombre_provincia))
            if provincia is None:
                provincia = Provincia(nombre=nombre_provincia)
                db.add(provincia)
                db.flush()
                provincias_creadas += 1
                log.info("Provincia creada (seed): %s", nombre_provincia)

            for mun_raw in municipios:
                nombre_mun = normalizar_nombre_catalogo(mun_raw)
                existe = db.scalar(
                    select(Municipio).where(
                        Municipio.nombre == nombre_mun,
                        Municipio.provincia_id == provincia.id,
                    )
                )
                if existe is None:
                    db.add(Municipio(nombre=nombre_mun, provincia_id=provincia.id))
                    municipios_creados += 1

        db.flush()
    except SQLAlchemyError:
        log.exception("Fallo en seed_boyaca; se revierte la transacción")
        raise

    log.info(
        "seed_boyaca completado: provincias_creadas=%s municipios_creados=%s",
        provincias_creadas,
        municipios_creados,
    )
    return {
        "provincias_creadas": provincias_creadas,
        "municipios_creados": municipios_creados,
    }
