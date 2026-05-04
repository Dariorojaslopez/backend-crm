"""Normalización de celdas Excel antes de validar contra la base de datos."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

import pandas as pd


def normalizar_nombre_columna_excel(name: str) -> str:
    """Cabeceras a snake_case minúsculas (espacios → ``_``)."""
    n = str(name).strip().lower()
    n = re.sub(r"\s+", "_", n)
    return n


def trim(val: Any) -> str:
    if pd.isna(val) or val is None:
        return ""
    return str(val).strip()


def null_a_vacio(val: Any) -> str:
    """Representación estable para null/NaN como cadena vacía."""
    if pd.isna(val) or val is None:
        return ""
    return str(val).strip()


def upper_catalogo(val: Any) -> str:
    """Trim + mayúsculas para provincia, municipio, cargo, partido, tipo, relación."""
    s = trim(val)
    return s.upper() if s else ""


def lower_campo(val: Any) -> str:
    """Trim + minúsculas para afinidad, influencia, prioridad."""
    s = trim(val)
    return s.lower() if s else ""


def parse_moviliza_si_no(val: Any) -> tuple[bool | None, str | None]:
    """
    Solo acepta SI / NO (tras trim y mayúsculas).
    Retorna (bool, None) si OK, o (None, mensaje_error).
    """
    s = trim(val).upper()
    if s == "":
        return None, "moviliza vacío (use SI o NO)"
    if s == "SI":
        return True, None
    if s == "NO":
        return False, None
    return None, f"moviliza inválido: {s!r} (solo SI o NO)"


def parse_fecha_iso(val: Any) -> tuple[date | None, str | None]:
    """
    Fecha obligatoria en formato ``YYYY-MM-DD`` si hay valor.
    Celda vacía / null → (None, None) sin error.
    """
    if pd.isna(val) or val is None:
        return None, None
    if isinstance(val, datetime):
        return val.date(), None
    if isinstance(val, date):
        return val, None
    s = trim(val)
    if s == "":
        return None, None
    if len(s) == 10 and s[4] == "-" and s[7] == "-":
        try:
            y, mo, d = int(s[0:4]), int(s[5:7]), int(s[8:10])
            out = date(y, mo, d)
            if out.strftime("%Y-%m-%d") != s:
                return None, f"fecha inválida: {s!r}"
            return out, None
        except ValueError:
            return None, f"fecha inválida (use YYYY-MM-DD): {s!r}"
    ts = pd.to_datetime(val, errors="coerce")
    if not pd.isna(ts):
        return ts.date(), None
    return None, f"fecha inválida (use YYYY-MM-DD): {s!r}"


def periodo_a_str(val: Any) -> str:
    if pd.isna(val) or val is None:
        return ""
    if isinstance(val, float):
        if val == int(val):
            return str(int(val))
    return str(val).strip()
