"""Sincronización de provincias y municipios desde plantilla Excel (Nombre + Provincia)."""

from __future__ import annotations

import io
import logging
from typing import Any

import pandas as pd
from fastapi import HTTPException, UploadFile, status
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.models import Contacto, Municipio, Provincia
from app.services.catalogo_service import normalizar_nombre_catalogo
from app.utils import normalizer

log = logging.getLogger(__name__)


def _nombre_celda(val: Any) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    return normalizar_nombre_catalogo(str(val))


def sincronizar_municipios_provincias_desde_excel(db: Session, archivo: UploadFile) -> dict[str, Any]:
    """
    Lee un ``.xlsx`` con columnas **Nombre** (municipio) y **Provincia** (subregión).

    - Crea provincias que no existan (nombre normalizado como en el resto del catálogo).
    - Crea municipios faltantes en la provincia indicada.
    - Si un municipio ya existe con el mismo nombre pero en otra provincia, actualiza
      ``provincia_id`` y alinea ``contactos.provincia_id`` para los contactos que apuntan a ese municipio.
    - Si hubiera varias filas ``municipios`` con el mismo nombre, consolida en una sola y reasigna contactos.
    """
    if not archivo.filename or not archivo.filename.lower().endswith(".xlsx"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se admiten archivos .xlsx",
        )

    raw = archivo.file.read()
    try:
        df = pd.read_excel(io.BytesIO(raw))
    except Exception as exc:  # noqa: BLE001
        log.exception("Fallo leyendo Excel de geografía")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se pudo leer el Excel: {exc}",
        ) from exc

    if df.empty:
        return {
            "status": "ok",
            "filas_leidas": 0,
            "provincias_creadas": 0,
            "municipios_creados": 0,
            "municipios_provincia_actualizada": 0,
            "municipios_homonimos_fusionados": 0,
            "advertencias": [],
        }

    df.columns = [normalizer.normalizar_nombre_columna_excel(c) for c in df.columns]
    if "nombre" not in df.columns or "provincia" not in df.columns:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El Excel debe incluir columnas «Nombre» y «Provincia» (cabeceras en español).",
        )

    provincias_creadas = 0
    municipios_creados = 0
    municipios_movidos = 0
    homonimos_fusionados = 0
    advertencias: list[str] = []
    homonimo_advertido: set[str] = set()

    def obtener_o_crear_provincia(nombre_norm: str) -> Provincia:
        nonlocal provincias_creadas
        p = db.scalar(select(Provincia).where(Provincia.nombre == nombre_norm))
        if p is None:
            p = Provincia(nombre=nombre_norm)
            db.add(p)
            db.flush()
            provincias_creadas += 1
            log.info("Provincia creada (sync Excel): %s", nombre_norm)
        return p

    def alinear_contactos(municipio_id: int, provincia_id: int) -> None:
        db.execute(
            update(Contacto)
            .where(Contacto.municipio_id == municipio_id)
            .values(provincia_id=provincia_id)
        )

    def fusionar_misma_clave_nombre(mun_n: str) -> Municipio | None:
        """Si hay varios municipios con el mismo nombre, deja uno y devuelve ese registro."""
        nonlocal homonimos_fusionados
        todos = list(db.scalars(select(Municipio).where(Municipio.nombre == mun_n)).all())
        if len(todos) <= 1:
            return todos[0] if todos else None
        if mun_n not in homonimo_advertido:
            homonimo_advertido.add(mun_n)
            advertencias.append(
                f"Varios registros con nombre de municipio «{mun_n}» en BD; se consolidan en uno solo.",
            )
        canonical = min(todos, key=lambda m: m.id)
        for m in todos:
            if m.id == canonical.id:
                continue
            db.execute(
                update(Contacto).where(Contacto.municipio_id == m.id).values(municipio_id=canonical.id)
            )
            db.flush()
            db.execute(delete(Municipio).where(Municipio.id == m.id))
            homonimos_fusionados += 1
        db.refresh(canonical)
        return canonical

    filas_utiles = 0
    for _, row in df.iterrows():
        mun_n = _nombre_celda(row.get("nombre"))
        prov_n = _nombre_celda(row.get("provincia"))
        if not mun_n or not prov_n:
            continue
        filas_utiles += 1

        provincia = obtener_o_crear_provincia(prov_n)

        exacto = db.scalar(
            select(Municipio).where(
                Municipio.nombre == mun_n,
                Municipio.provincia_id == provincia.id,
            )
        )
        if exacto is not None:
            continue

        m = fusionar_misma_clave_nombre(mun_n)

        if m is None:
            db.add(Municipio(nombre=mun_n, provincia_id=provincia.id))
            municipios_creados += 1
            db.flush()
            continue

        if m.provincia_id == provincia.id:
            continue

        ocupante = db.scalar(
            select(Municipio).where(
                Municipio.nombre == mun_n,
                Municipio.provincia_id == provincia.id,
            )
        )
        if ocupante is not None and ocupante.id != m.id:
            db.execute(
                update(Contacto)
                .where(Contacto.municipio_id == m.id)
                .values(municipio_id=ocupante.id, provincia_id=provincia.id)
            )
            db.flush()
            db.execute(delete(Municipio).where(Municipio.id == m.id))
            homonimos_fusionados += 1
            alinear_contactos(ocupante.id, provincia.id)
            continue

        m.provincia_id = provincia.id
        db.flush()
        municipios_movidos += 1
        alinear_contactos(m.id, provincia.id)
        log.info("Municipio reasignado a provincia: nombre=%s provincia_id=%s", mun_n, provincia.id)

    db.flush()
    log.info(
        "Sync geografía Excel: filas=%s prov_creadas=%s mun_creados=%s mun_movidos=%s fusion=%s",
        filas_utiles,
        provincias_creadas,
        municipios_creados,
        municipios_movidos,
        homonimos_fusionados,
    )

    return {
        "status": "ok",
        "filas_leidas": filas_utiles,
        "provincias_creadas": provincias_creadas,
        "municipios_creados": municipios_creados,
        "municipios_provincia_actualizada": municipios_movidos,
        "municipios_homonimos_fusionados": homonimos_fusionados,
        "advertencias": advertencias,
    }
