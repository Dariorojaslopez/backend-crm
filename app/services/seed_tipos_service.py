"""Carga masiva del catálogo ``tipos`` (sin alterar los literales de cada nombre)."""

from __future__ import annotations

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import Tipo

CHUNK_SIZE = 500

# Guión tipográfico U+2013 (tal como en el catálogo solicitado).
_EN = "\u2013"

TIPOS_SEED: tuple[str, ...] = (
    f"ALCALDES 2024{_EN}2027",
    f"ALCALDES 2020{_EN}2023",
    f"DIPUTADOS 2024{_EN}2027",
    f"CONCEJALES 2024{_EN}2027",
    f"CONCEJALES 2020{_EN}2023",
    f"CMJ 2020{_EN}2023",
    "JOVENES SUTA",
    "JAC 2024",
    "JOVENES RURALES",
    "MUJERES PRESIDENTAS",
    "INSCRITO JOVENES",
)


def seed_tipos_bulk_insert(session: Session) -> dict[str, int]:
    """
    INSERT masivo con ON CONFLICT (nombre) DO NOTHING.
    No modifica mayúsculas ni el contenido de los strings.
    """
    rows = [{"nombre": n} for n in TIPOS_SEED]
    intentados = len(rows)
    insertados = 0

    for i in range(0, len(rows), CHUNK_SIZE):
        chunk = rows[i : i + CHUNK_SIZE]
        stmt = insert(Tipo).values(chunk)
        stmt = stmt.on_conflict_do_nothing(index_elements=["nombre"])
        result = session.execute(stmt)
        insertados += result.rowcount or 0

    return {
        "intentados": intentados,
        "insertados": insertados,
        "omitidos_por_duplicado_o_conflicto": intentados - insertados,
    }
