"""Normalización de celdas Excel antes de validar contra la base de datos."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
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


def afinidad_normalizada(val: Any) -> str:
    s = lower_campo(val)
    return s if s else "neutro"


def influencia_normalizada(val: Any) -> str:
    s = lower_campo(val)
    return s if s else "medio"


def prioridad_normalizada(val: Any) -> str:
    s = lower_campo(val)
    return s if s else "media"


@dataclass
class FilaImportNormalizada:
    """
    Una fila del Excel ya limpia (solo transformaciones de texto/fechas/moviliza).
    ``errores_normalizacion`` reúne fallos de formato antes de tocar la base de datos.
    """

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
    afinidad: str = "neutro"
    influencia: str = "medio"
    moviliza: bool | None = None
    ultimo_contacto: date | None = None
    proximo_contacto: date | None = None
    responsable: str = ""
    prioridad: str = "media"
    notas: str = ""
    periodo: str = ""
    errores_normalizacion: list[str] = field(default_factory=list)


def normalizar_dataframe_import_contactos(df: pd.DataFrame) -> list[FilaImportNormalizada]:
    """
    Recorre el DataFrame completo y devuelve una lista de filas ya normalizadas.

    No accede a la base de datos. Debe llamarse con columnas ya renombradas
    (snake_case) e incluir todas las columnas requeridas del import.
    """
    salida: list[FilaImportNormalizada] = []
    for idx, row in df.iterrows():
        fila_excel = int(idx) + 2
        errs: list[str] = []

        nombre = trim(row.get("nombre"))
        apellidos = trim(row.get("apellidos"))
        telefono = null_a_vacio(row.get("telefono"))
        provincia = upper_catalogo(row.get("provincia"))
        municipio = upper_catalogo(row.get("municipio"))
        cargo = upper_catalogo(row.get("cargo"))
        partido = upper_catalogo(row.get("partido"))
        tipo = upper_catalogo(row.get("tipo"))
        relacion = trim(row.get("relacion"))
        afinidad = afinidad_normalizada(row.get("afinidad"))
        influencia = influencia_normalizada(row.get("influencia"))
        prioridad = prioridad_normalizada(row.get("prioridad"))
        responsable = null_a_vacio(row.get("responsable"))
        notas = null_a_vacio(row.get("notas"))
        periodo = periodo_a_str(row.get("periodo"))

        mov, err_mov = parse_moviliza_si_no(row.get("moviliza"))
        if err_mov:
            errs.append(err_mov)

        ultimo, u_err = parse_fecha_iso(row.get("ultimo_contacto"))
        if u_err:
            errs.append(f"ultimo_contacto: {u_err}")
        proximo, p_err = parse_fecha_iso(row.get("proximo_contacto"))
        if p_err:
            errs.append(f"proximo_contacto: {p_err}")

        if not nombre:
            errs.append("nombre obligatorio vacío")
        if not apellidos:
            errs.append("apellidos obligatorio vacío")
        if not provincia:
            errs.append("provincia vacía")
        if not municipio:
            errs.append("municipio vacío")
        if not cargo:
            errs.append("cargo vacío")
        if not partido:
            errs.append("partido vacío")
        if not tipo:
            errs.append("tipo vacío")
        if not relacion:
            errs.append("relacion vacía")
        if not periodo:
            errs.append("periodo vacío")

        if len(nombre) > 120:
            errs.append(f"nombre excede 120 caracteres ({len(nombre)})")
        if len(apellidos) > 180:
            errs.append(f"apellidos exceden 180 caracteres ({len(apellidos)})")
        if len(telefono) > 40:
            errs.append(f"telefono excede 40 caracteres ({len(telefono)})")

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
                errores_normalizacion=errs,
            )
        )
    return salida
