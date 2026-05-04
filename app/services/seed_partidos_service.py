"""Carga masiva de partidos desde lista o archivo (sin normalizar texto)."""

from pathlib import Path

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import Partido

DEFAULT_PARTIDOS_SEED_PATH = Path(__file__).resolve().parent.parent / "data" / "partidos_seed.txt"
CHUNK_SIZE = 500


def read_partidos_lines_from_file(path: Path) -> list[str]:
    """Lee líneas del archivo; solo quita el salto de línea final de cada línea (no strip del contenido)."""
    raw = path.read_text(encoding="utf-8")
    return [line.removesuffix("\r\n").removesuffix("\n") for line in raw.splitlines()]


def seed_partidos_bulk_insert(session: Session, nombres: list[str]) -> dict[str, int]:
    """
    INSERT masivo con ON CONFLICT (nombre) DO NOTHING.
    No modifica mayúsculas ni contenido de los strings.
    """
    rows = [{"nombre": n} for n in nombres if n != ""]
    if not rows:
        return {
            "intentados": 0,
            "insertados": 0,
            "omitidos_por_duplicado_o_conflicto": 0,
        }

    intentados = len(rows)
    insertados = 0

    for i in range(0, len(rows), CHUNK_SIZE):
        chunk = rows[i : i + CHUNK_SIZE]
        stmt = insert(Partido).values(chunk)
        stmt = stmt.on_conflict_do_nothing(index_elements=["nombre"])
        result = session.execute(stmt)
        insertados += result.rowcount or 0

    return {
        "intentados": intentados,
        "insertados": insertados,
        "omitidos_por_duplicado_o_conflicto": intentados - insertados,
    }
