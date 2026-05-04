"""Normalización de celdas Excel antes de validar contra la base de datos."""

from __future__ import annotations

import re
from dataclasses import dataclass
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


def parse_moviliza_opcional(val: Any) -> bool:
    """SI → True, NO → False; vacío u otro valor → False (sin error)."""
    s = trim(val).upper()
    if s == "SI":
        return True
    return False


def parse_fecha_opcional(val: Any) -> date | None:
    """Intenta obtener fecha; si no es válida o está vacío → ``None`` (sin error)."""
    if pd.isna(val) or val is None:
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    s = trim(val)
    if s == "":
        return None
    if len(s) == 10 and s[4] == "-" and s[7] == "-":
        try:
            y, mo, d = int(s[0:4]), int(s[5:7]), int(s[8:10])
            out = date(y, mo, d)
            if out.strftime("%Y-%m-%d") != s:
                return None
            return out
        except ValueError:
            return None
    ts = pd.to_datetime(val, errors="coerce")
    if not pd.isna(ts):
        return ts.date()
    return None


def periodo_a_str(val: Any) -> str:
    if pd.isna(val) or val is None:
        return ""
    if isinstance(val, float):
        if val == int(val):
            return str(int(val))
    return str(val).strip()


def afinidad_normalizada(val: Any) -> str:
    s = lower_campo(val)
    return s if s else ""


def influencia_normalizada(val: Any) -> str:
    s = lower_campo(val)
    return s if s else ""


def prioridad_normalizada(val: Any) -> str:
    s = lower_campo(val)
    return s if s else ""


@dataclass
class FilaImportNormalizada:
    """Fila del Excel normalizada; ningún campo es obligatorio a nivel de plantilla."""

    fila_excel: int
    nombre: str = ""
    apellidos: str = ""
    telefono: str = ""
    provincia: str = ""
    municipio: str = ""
    cargo: str = ""
    partido: str = ""
    tipo: str = ""
    relacion: str = ""
    afinidad: str = ""
    influencia: str = ""
    moviliza: bool = False
    ultimo_contacto: date | None = None
    proximo_contacto: date | None = None
    responsable: str = ""
    prioridad: str = ""
    notas: str = ""
    periodo: str = ""


def _trunc(s: str, max_len: int) -> str:
    if len(s) <= max_len:
        return s
    return s[:max_len]


def normalizar_dataframe_import_contactos(df: pd.DataFrame) -> list[FilaImportNormalizada]:
    """
    Recorre el DataFrame completo y devuelve una lista de filas ya normalizadas.

    No accede a la base de datos. Ningún valor obligatorio: textos largos se truncan silenciosamente.
    """
    salida: list[FilaImportNormalizada] = []
    for idx, row in df.iterrows():
        fila_excel = int(idx) + 2

        nombre = _trunc(trim(row.get("nombre")), 120)
        apellidos = _trunc(trim(row.get("apellidos")), 180)
        telefono = _trunc(null_a_vacio(row.get("telefono")), 40)
        provincia = upper_catalogo(row.get("provincia"))
        municipio = upper_catalogo(row.get("municipio"))
        cargo = upper_catalogo(row.get("cargo"))
        partido = upper_catalogo(row.get("partido"))
        tipo = upper_catalogo(row.get("tipo"))
        relacion = trim(row.get("relacion"))
        afinidad = _trunc(afinidad_normalizada(row.get("afinidad")), 32)
        influencia = _trunc(influencia_normalizada(row.get("influencia")), 32)
        prioridad = _trunc(prioridad_normalizada(row.get("prioridad")), 16)
        responsable = _trunc(null_a_vacio(row.get("responsable")), 200)
        notas = null_a_vacio(row.get("notas"))
        periodo = _trunc(periodo_a_str(row.get("periodo")), 64)

        mov = parse_moviliza_opcional(row.get("moviliza"))
        ultimo = parse_fecha_opcional(row.get("ultimo_contacto"))
        proximo = parse_fecha_opcional(row.get("proximo_contacto"))

        salida.append(
            FilaImportNormalizada(
                fila_excel=fila_excel,
                nombre=nombre,
                apellidos=apellidos,
                telefono=telefono,
                provincia=provincia,
                municipio=municipio,
                cargo=cargo,
                partido=partido,
                tipo=tipo,
                relacion=relacion,
                afinidad=afinidad,
                influencia=influencia,
                moviliza=mov,
                ultimo_contacto=ultimo,
                proximo_contacto=proximo,
                responsable=responsable,
                prioridad=prioridad,
                notas=notas,
                periodo=periodo,
            )
        )
    return salida
