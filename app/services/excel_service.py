"""Importación de contactos desde Excel: normalización, resolución de catálogos e inserción masiva."""

from __future__ import annotations

import io
import logging
from datetime import datetime, timezone
from typing import Any

import pandas as pd
from fastapi import HTTPException, UploadFile, status
from sqlalchemy import func, select, tuple_
from sqlalchemy.orm import Session

from app.models import Cargo, Contacto, Municipio, Partido, Provincia, Relacion, Tipo
from app.services import relacion_service
from app.utils import normalizer

log = logging.getLogger(__name__)

COLUMNAS_REQUERIDAS: frozenset[str] = frozenset(
    {
        "nombre",
        "apellidos",
        "telefono",
        "municipio",
        "provincia",
        "cargo",
        "partido",
        "tipo",
        "relacion",
        "afinidad",
        "influencia",
        "moviliza",
        "ultimo_contacto",
        "proximo_contacto",
        "responsable",
        "prioridad",
        "notas",
        "periodo",
    }
)


def get_provincia(db: Session, nombre: str) -> Provincia | None:
    if not nombre:
        return None
    return db.scalar(select(Provincia).where(Provincia.nombre == nombre))


def get_municipio(db: Session, nombre: str, provincia_id: int) -> Municipio | None:
    if not nombre:
        return None
    return db.scalar(
        select(Municipio).where(
            Municipio.nombre == nombre,
            Municipio.provincia_id == provincia_id,
        )
    )


def get_cargo(db: Session, nombre: str) -> Cargo | None:
    if not nombre:
        return None
    return db.scalar(select(Cargo).where(Cargo.nombre == nombre))


def get_partido(db: Session, nombre: str) -> Partido | None:
    if not nombre:
        return None
    return db.scalar(select(Partido).where(Partido.nombre == nombre))


def get_tipo(db: Session, nombre: str) -> Tipo | None:
    if not nombre:
        return None
    return db.scalar(select(Tipo).where(func.upper(Tipo.nombre) == nombre))


def get_relacion(db: Session, nombre_raw: str) -> Relacion | None:
    if not nombre_raw or not str(nombre_raw).strip():
        return None
    clave = relacion_service.normalizar_nombre_relacion(str(nombre_raw).strip())
    if not clave:
        return None
    return db.scalar(select(Relacion).where(Relacion.nombre == clave))


def importar_excel_contactos(
    db: Session,
    archivo: UploadFile,
    *,
    omitir_duplicados: bool = False,
) -> dict[str, Any]:
    """
    Lee ``.xlsx``, **normaliza todas las filas** (sin BD), luego valida contra catálogos,
    deduplica opcionalmente e inserta en bloque con ``bulk_insert_mappings``.
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
        log.exception("Fallo leyendo Excel")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se pudo leer el Excel: {exc}",
        ) from exc

    if df.empty:
        return {
            "status": "ok",
            "insertados": 0,
            "errores": 0,
            "omitidos_duplicados": 0,
            "detalle_errores": [],
        }

    df.columns = [normalizer.normalizar_nombre_columna_excel(c) for c in df.columns]
    columnas = set(df.columns)
    faltan = COLUMNAS_REQUERIDAS - columnas
    if faltan:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Faltan columnas obligatorias en el Excel: {sorted(faltan)}",
        )

    filas_normalizadas = normalizer.normalizar_dataframe_import_contactos(df)
    log.info("Import Excel: normalizadas %s filas (sin BD)", len(filas_normalizadas))

    detalle_errores: list[dict[str, Any]] = []
    mappings: list[dict[str, Any]] = []
    vistos_archivo: set[tuple[str, str, int]] = set()

    for fn in filas_normalizadas:
        fila = fn.fila_excel
        errs: list[str] = list(fn.errores_normalizacion)

        provincia = get_provincia(db, fn.provincia) if fn.provincia else None
        if fn.provincia and not provincia:
            errs.append(f"provincia no existe: {fn.provincia}")

        municipio = None
        if provincia and fn.municipio:
            municipio = get_municipio(db, fn.municipio, provincia.id)
            if not municipio:
                errs.append(f"municipio no existe: {fn.municipio}")

        cargo = get_cargo(db, fn.cargo) if fn.cargo else None
        if fn.cargo and not cargo:
            errs.append(f"cargo no existe: {fn.cargo}")

        partido = get_partido(db, fn.partido) if fn.partido else None
        if fn.partido and not partido:
            errs.append(f"partido no existe: {fn.partido}")

        tipo = get_tipo(db, fn.tipo) if fn.tipo else None
        if fn.tipo and not tipo:
            errs.append(f"tipo no existe: {fn.tipo}")

        relacion = get_relacion(db, fn.relacion) if fn.relacion else None
        if fn.relacion and not relacion:
            errs.append(f"relacion no existe: {fn.relacion}")

        if errs:
            log.warning("Import Excel fila %s errores=%s", fila, errs)
            detalle_errores.append({"fila": fila, "errores": errs})
            continue

        if not (
            provincia
            and municipio
            and cargo
            and partido
            and tipo
            and relacion
            and fn.moviliza is not None
        ):
            log.error("Import Excel fila %s estado inconsistente tras validar catálogo", fila)
            detalle_errores.append({"fila": fila, "errores": ["error interno de validación"]})
            continue

        clave_dup = (fn.nombre, fn.apellidos, municipio.id)
        if clave_dup in vistos_archivo:
            detalle_errores.append(
                {"fila": fila, "errores": ["duplicado en el mismo archivo (nombre+apellidos+municipio_id)"]}
            )
            continue
        vistos_archivo.add(clave_dup)

        tel_db = fn.telefono if fn.telefono else None
        responsable = fn.responsable if fn.responsable else None
        notas = fn.notas if fn.notas else None

        mappings.append(
            {
                "nombre": fn.nombre,
                "apellidos": fn.apellidos,
                "telefono": tel_db,
                "municipio_id": municipio.id,
                "provincia_id": provincia.id,
                "cargo_id": cargo.id,
                "partido_id": partido.id,
                "tipo_id": tipo.id,
                "relacion_id": relacion.id,
                "afinidad": fn.afinidad,
                "influencia": fn.influencia,
                "moviliza": fn.moviliza,
                "ultimo_contacto": fn.ultimo_contacto,
                "proximo_contacto": fn.proximo_contacto,
                "responsable": responsable,
                "prioridad": fn.prioridad,
                "notas": notas,
                "periodo": fn.periodo,
            }
        )

    omitidos_dup = 0
    if omitir_duplicados and mappings:
        claves = [(m["nombre"], m["apellidos"], m["municipio_id"]) for m in mappings]
        existentes: set[tuple[str, str, int]] = set()
        chunk = 400
        for i in range(0, len(claves), chunk):
            sub = claves[i : i + chunk]
            stmt = select(Contacto.nombre, Contacto.apellidos, Contacto.municipio_id).where(
                tuple_(Contacto.nombre, Contacto.apellidos, Contacto.municipio_id).in_(sub)
            )
            for r in db.execute(stmt):
                existentes.add((r[0], r[1], r[2]))

        filtrados: list[dict[str, Any]] = []
        for m in mappings:
            ck = (m["nombre"], m["apellidos"], m["municipio_id"])
            if ck in existentes:
                omitidos_dup += 1
                log.info("Omitido duplicado en BD: %s %s mun=%s", ck[0], ck[1], ck[2])
                continue
            filtrados.append(m)
        mappings = filtrados

    mappings.sort(
        key=lambda x: (x["provincia_id"], x["municipio_id"], x["apellidos"], x["nombre"]),
    )

    insertados = 0
    if mappings:
        ahora = datetime.now(timezone.utc)
        for m in mappings:
            m["created_at"] = ahora
        try:
            db.bulk_insert_mappings(Contacto, mappings)
            db.flush()
            insertados = len(mappings)
            log.info("Import Excel bulk_insert_mappings insertados=%s", insertados)
        except Exception as exc:
            log.exception("Fallo bulk insert contactos desde Excel")
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error al insertar contactos en bloque; se revirtió la transacción de esta petición",
            ) from exc

    return {
        "status": "ok",
        "insertados": insertados,
        "errores": len(detalle_errores),
        "omitidos_duplicados": omitidos_dup,
        "detalle_errores": detalle_errores,
    }
