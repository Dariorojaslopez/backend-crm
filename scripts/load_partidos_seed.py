"""
Carga masiva de partidos desde un .txt (una línea = un nombre).

Uso:
  set DATABASE_URL=postgresql://...
  python scripts/load_partidos_seed.py
  python scripts/load_partidos_seed.py ruta\\al\\archivo.txt

Requiere tabla ``partidos`` con UNIQUE en ``nombre`` (p. ej. tras ``init_db``).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import get_engine, get_session_factory, init_db  # noqa: E402
from app.services.seed_partidos_service import (  # noqa: E402
    DEFAULT_PARTIDOS_SEED_PATH,
    read_partidos_lines_from_file,
    seed_partidos_bulk_insert,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Bulk insert partidos desde .txt")
    parser.add_argument(
        "archivo",
        nargs="?",
        type=Path,
        default=DEFAULT_PARTIDOS_SEED_PATH,
        help=f"Ruta al .txt (por defecto: {DEFAULT_PARTIDOS_SEED_PATH})",
    )
    parser.add_argument(
        "--no-init-db",
        action="store_true",
        help="No ejecutar init_db() antes (usa si el esquema ya existe)",
    )
    args = parser.parse_args()
    path: Path = args.archivo

    if not path.is_file():
        print(f"Error: no existe el archivo {path}", file=sys.stderr)
        return 1

    try:
        get_engine()
    except RuntimeError as e:
        print(e, file=sys.stderr)
        return 1

    if not args.no_init_db:
        init_db()

    lineas = read_partidos_lines_from_file(path)
    factory = get_session_factory()
    db = factory()
    try:
        out = seed_partidos_bulk_insert(db, lineas)
        db.commit()
        print(out)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
