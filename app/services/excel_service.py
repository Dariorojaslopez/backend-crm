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


def _validar_longitudes(nombre: str, apellidos: str, telefono: str) -> list[str]:
    err: list[str] = []
    if len(nombre) > 120:
        err.append(f"nombre excede 120 caracteres ({len(nombre)})")
    if len(apellidos) > 180:
        err.append(f"apellidos exceden 180 caracteres ({len(apellidos)})")
    if len(telefono) > 40:
        err.append(f"telefono excede 40 caracteres ({len(telefono)})")
    return err


def importar_excel_contactos(
    db: Session,
    archivo: UploadFile,
    *,
    omitir_duplicados: bool = False,
) -> dict[str, Any]:
    """
    Lee ``.xlsx``, normaliza, valida catálogos existentes (sin crear) e inserta filas válidas
    en bloque con ``INSERT`` masivo.
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

    detalle_errores: list[dict[str, Any]] = []
    mappings: list[dict[str, Any]] = []
    vistos_archivo: set[tuple[str, str, int]] = set()

    for idx, row in df.iterrows():
        fila = int(idx) + 2
        errs: list[str] = []

        nombre = normalizer.trim(row.get("nombre"))
        apellidos = normalizer.trim(row.get("apellidos"))
        if not nombre:
            errs.append("nombre obligatorio vacío")
        if not apellidos:
            errs.append("apellidos obligatorio vacío")

        provincia_nom = normalizer.upper_catalogo(row.get("provincia"))
        municipio_nom = normalizer.upper_catalogo(row.get("municipio"))
        cargo_nom = normalizer.upper_catalogo(row.get("cargo"))
        partido_nom = normalizer.upper_catalogo(row.get("partido"))
        tipo_nom = normalizer.upper_catalogo(row.get("tipo"))
        relacion_txt = normalizer.trim(row.get("relacion"))

        if not provincia_nom:
            errs.append("provincia vacía")
        if not municipio_nom:
            errs.append("municipio vacío")
        if not cargo_nom:
            errs.append("cargo vacío")
        if not partido_nom:
            errs.append("partido vacío")
        if not tipo_nom:
            errs.append("tipo vacío")
        if not relacion_txt:
            errs.append("relacion vacía")

        mov, err_mov = normalizer.parse_moviliza_si_no(row.get("moviliza"))
        if err_mov:
            errs.append(err_mov)

        u_err: str | None = None
        p_err: str | None = None
        ultimo, u_err = normalizer.parse_fecha_iso(row.get("ultimo_contacto"))
        proximo, p_err = normalizer.parse_fecha_iso(row.get("proximo_contacto"))
        if u_err:
            errs.append(f"ultimo_contacto: {u_err}")
        if p_err:
            errs.append(f"proximo_contacto: {p_err}")

        telefono = normalizer.null_a_vacio(row.get("telefono"))
        afinidad = normalizer.lower_campo(row.get("afinidad")) or "neutro"
        influencia = normalizer.lower_campo(row.get("influencia")) or "medio"
        responsable_s = normalizer.null_a_vacio(row.get("responsable"))
        responsable = responsable_s if responsable_s else None
        prioridad = normalizer.lower_campo(row.get("prioridad")) or "media"
        notas_s = normalizer.null_a_vacio(row.get("notas"))
        notas = notas_s if notas_s else None
        periodo = normalizer.periodo_a_str(row.get("periodo"))
        if not periodo:
            errs.append("periodo vacío")

        provincia = get_provincia(db, provincia_nom) if provincia_nom else None
        if provincia_nom and not provincia:
            errs.append(f"provincia no existe: {provincia_nom}")

        municipio = None
        if provincia and municipio_nom:
            municipio = get_municipio(db, municipio_nom, provincia.id)
            if not municipio:
                errs.append(f"municipio no existe: {municipio_nom}")

        cargo = get_cargo(db, cargo_nom) if cargo_nom else None
        if cargo_nom and not cargo:
            errs.append(f"cargo no existe: {cargo_nom}")

        partido = get_partido(db, partido_nom) if partido_nom else None
        if partido_nom and not partido:
            errs.append(f"partido no existe: {partido_nom}")

        tipo = get_tipo(db, tipo_nom) if tipo_nom else None
        if tipo_nom and not tipo:
            errs.append(f"tipo no existe: {tipo_nom}")

        relacion = get_relacion(db, relacion_txt) if relacion_txt else None
        if relacion_txt and not relacion:
            errs.append(f"relacion no existe: {relacion_txt}")

        errs.extend(_validar_longitudes(nombre, apellidos, telefono))

        if errs:
            log.warning("Import Excel fila %s errores=%s", fila, errs)
            detalle_errores.append({"fila": fila, "errores": errs})
            continue

        if not (provincia and municipio and cargo and partido and tipo and relacion and mov is not None):
            log.error("Import Excel fila %s estado inconsistente tras validar", fila)
            detalle_errores.append({"fila": fila, "errores": ["error interno de validación"]})
            continue

        clave_dup = (nombre, apellidos, municipio.id)
        if clave_dup in vistos_archivo:
            detalle_errores.append(
                {"fila": fila, "errores": ["duplicado en el mismo archivo (nombre+apellidos+municipio_id)"]}
            )
            continue
        vistos_archivo.add(clave_dup)

        tel_db = telefono if telefono else None

        mappings.append(
            {
                "nombre": nombre,
                "apellidos": apellidos,
                "telefono": tel_db,
                "municipio_id": municipio.id,
                "provincia_id": provincia.id,
                "cargo_id": cargo.id,
                "partido_id": partido.id,
                "tipo_id": tipo.id,
                "relacion_id": relacion.id,
                "afinidad": afinidad,
                "influencia": influencia,
                "moviliza": mov,
                "ultimo_contacto": ultimo,
                "proximo_contacto": proximo,
                "responsable": responsable,
                "prioridad": prioridad,
                "notas": notas,
                "periodo": periodo,
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
