"""Carga de partidos políticos desde Excel (solo nombres no presentes en BD)."""

from __future__ import annotations

import io
import logging
from typing import Any

import pandas as pd
from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import Partido
from app.services.catalogo_service import normalizar_nombre_catalogo
from app.services.seed_partidos_service import CHUNK_SIZE
from app.utils import normalizer

log = logging.getLogger(__name__)


def _clave_partido(nombre: str) -> str:
    """Clave estable para comparar con la BD (misma idea que el catálogo)."""
    return normalizar_nombre_catalogo(nombre)


def _serie_nombres_desde_dataframe(df: pd.DataFrame) -> pd.Series:
    """Obtiene la columna de nombres: una sola columna sin cabecera o columna nombre/partido."""
    if df.shape[1] == 0:
        return pd.Series(dtype=object)
    if df.shape[1] == 1:
        return df.iloc[:, 0]
    df2 = df.copy()
    df2.columns = [normalizer.normalizar_nombre_columna_excel(c) for c in df2.columns]
    for cand in ("partido", "nombre", "nombre_partido", "partido_politico"):
        if cand in df2.columns:
            return df2[cand]
    return df2.iloc[:, 0]


def seed_partidos_desde_excel(db: Session, archivo: UploadFile) -> dict[str, Any]:
    """
    Lee un ``.xlsx`` con una columna de nombres de partido (con o sin fila de cabecera).

    Inserta solo los nombres que **no** existan ya en ``partidos`` (comparación por nombre
    normalizado: trim + mayúsculas). Dentro del Excel se deduplican por esa misma clave.
    """
    if not archivo.filename or not archivo.filename.lower().endswith(".xlsx"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se admiten archivos .xlsx",
        )

    raw = archivo.file.read()
    try:
        df0 = pd.read_excel(io.BytesIO(raw), header=None)
    except Exception as exc:  # noqa: BLE001
        log.exception("Fallo leyendo Excel de partidos")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se pudo leer el Excel: {exc}",
        ) from exc

    if df0.empty:
        return {
            "status": "ok",
            "filas_leidas": 0,
            "nombres_unicos_en_excel": 0,
            "insertados": 0,
            "omitidos_ya_en_bd": 0,
            "omitidos_vacio_en_excel": 0,
        }

    if df0.shape[1] == 1:
        c0 = str(df0.iloc[0, 0]).strip().lower()
        if c0 in {"nombre", "partido", "partido_politico"}:
            df0 = df0.iloc[1:].reset_index(drop=True)

    series = _serie_nombres_desde_dataframe(df0)
    filas_leidas = int(series.shape[0])

    vistos: set[str] = set()
    nombres_a_insertar: list[str] = []
    omitidos_vacio = 0

    for val in series.tolist():
        if val is None or (isinstance(val, float) and pd.isna(val)):
            omitidos_vacio += 1
            continue
        s = str(val).strip()
        if not s:
            omitidos_vacio += 1
            continue
        clave = _clave_partido(s)
        if not clave:
            omitidos_vacio += 1
            continue
        if clave in vistos:
            continue
        vistos.add(clave)
        nombres_a_insertar.append(clave)

    existentes = {
        _clave_partido(p.nombre)
        for p in db.scalars(select(Partido)).all()
    }

    nuevos: list[str] = []
    omitidos_bd = 0
    for clave in nombres_a_insertar:
        if clave in existentes:
            omitidos_bd += 1
            continue
        nuevos.append(clave)
        existentes.add(clave)

    insertados = 0
    if nuevos:
        rows = [{"nombre": n} for n in nuevos]
        for i in range(0, len(rows), CHUNK_SIZE):
            chunk = rows[i : i + CHUNK_SIZE]
            stmt = insert(Partido).values(chunk)
            stmt = stmt.on_conflict_do_nothing(index_elements=["nombre"])
            result = db.execute(stmt)
            insertados += int(result.rowcount or 0)

    log.info(
        "Seed partidos Excel: filas=%s unicos_excel=%s insertados=%s omit_bd=%s omit_vacio=%s",
        filas_leidas,
        len(nombres_a_insertar),
        insertados,
        omitidos_bd,
        omitidos_vacio,
    )

    return {
        "status": "ok",
        "filas_leidas": filas_leidas,
        "nombres_unicos_en_excel": len(nombres_a_insertar),
        "insertados": insertados,
        "omitidos_ya_en_bd": omitidos_bd,
        "omitidos_vacio_en_excel": omitidos_vacio,
    }
