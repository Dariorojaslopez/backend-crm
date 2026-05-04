"""Importación de contactos desde Excel: normalización, resolución de catálogos e inserción masiva."""

from __future__ import annotations

import io
import logging
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any, TypeVar

import pandas as pd
from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select, tuple_
from sqlalchemy.orm import Session

from app.models import Cargo, Contacto, Municipio, Partido, Provincia, Relacion, Tipo
from app.services import relacion_service
from app.utils import normalizer

log = logging.getLogger(__name__)

T = TypeVar("T", Provincia, Municipio, Cargo, Partido, Tipo, Relacion)

_GUION_EN = "\u2013"  # Unicode en-dash (p. ej. tipos "2024–2027")
_GUION_MI = "\u2012"  # figure dash


def _clave_catalogo(s: str) -> str:
    """
    Clave estable para comparar con la BD:
    - normaliza Unicode,
    - elimina tildes/diacríticos,
    - homogeniza guiones/separadores,
    - colapsa espacios y pasa a mayúsculas.
    Así "Boyacá ", "BOYACA" y variantes razonables coinciden con el nombre almacenado.
    """
    if not s:
        return ""
    t = str(s).strip()
    # Casos observados en importaciones desde Excel con codificación irregular.
    t = t.replace("\u00a0", " ")
    t = t.replace("\u2010", "-").replace("\u2011", "-").replace("\u2012", "-").replace("\u2013", "-").replace("\u2014", "-")
    t = t.replace("\ufffd", " ")

    # Quita tildes/diacríticos para comparar de forma robusta.
    t = unicodedata.normalize("NFKD", t)
    t = "".join(ch for ch in t if not unicodedata.combining(ch))

    # Deja solo alfanumérico, guion y espacios.
    t = re.sub(r"[^A-Za-z0-9\- ]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip().upper()
    return t


def _variantes_guion(clave: str) -> list[str]:
    """Alterna guión ASCII, en-dash y figure-dash (típico en rangos de años en Excel)."""
    out: list[str] = []
    if not clave:
        return out
    if "-" in clave:
        out.append(clave.replace("-", _GUION_EN))
        out.append(clave.replace("-", _GUION_MI))
    if _GUION_EN in clave:
        out.append(clave.replace(_GUION_EN, "-"))
        out.append(clave.replace(_GUION_EN, _GUION_MI))
    if _GUION_MI in clave:
        out.append(clave.replace(_GUION_MI, "-"))
        out.append(clave.replace(_GUION_MI, _GUION_EN))
    return out


def _registrar_claves_mapa(dest: dict[str, T], entidad: T, texto_bd: str) -> None:
    """Asocia la entidad a la clave normalizada y a variantes de guión."""
    base = _clave_catalogo(texto_bd)
    if not base:
        return
    claves = {base, *_variantes_guion(base)}
    for k in claves:
        if k:
            dest[k] = entidad


def _resolver_por_mapa(mapa: dict[str, T], texto_excel: str) -> T | None:
    """Busca en mapa usando la misma normalización + variantes de guión."""
    k = _clave_catalogo(texto_excel)
    if k in mapa:
        return mapa[k]
    for alt in _variantes_guion(k):
        if alt in mapa:
            return mapa[alt]
    return None


def _cargar_mapas_catalogo(db: Session) -> tuple[
    dict[str, Provincia],
    dict[tuple[int, str], Municipio],
    dict[str, Cargo],
    dict[str, Partido],
    dict[str, Tipo],
    dict[str, Relacion],
]:
    prov_map: dict[str, Provincia] = {}
    for p in db.scalars(select(Provincia)).all():
        _registrar_claves_mapa(prov_map, p, p.nombre)

    mun_map: dict[tuple[int, str], Municipio] = {}
    for m in db.scalars(select(Municipio)).all():
        base = _clave_catalogo(m.nombre)
        for k in {base, *_variantes_guion(base)}:
            if k:
                mun_map[(m.provincia_id, k)] = m

    cargo_map: dict[str, Cargo] = {}
    for c in db.scalars(select(Cargo)).all():
        _registrar_claves_mapa(cargo_map, c, c.nombre)

    partido_map: dict[str, Partido] = {}
    for p in db.scalars(select(Partido)).all():
        _registrar_claves_mapa(partido_map, p, p.nombre)

    tipo_map: dict[str, Tipo] = {}
    for t in db.scalars(select(Tipo)).all():
        _registrar_claves_mapa(tipo_map, t, t.nombre)

    rel_map: dict[str, Relacion] = {}
    for r in db.scalars(select(Relacion)).all():
        rel_map[r.nombre] = r
        _registrar_claves_mapa(rel_map, r, r.nombre)

    return prov_map, mun_map, cargo_map, partido_map, tipo_map, rel_map


def _resolver_relacion(rel_map: dict[str, Relacion], texto_excel: str) -> Relacion | None:
    """Primero la regla del catálogo (sin_contacto → SIN CONTACTO); luego clave normalizada."""
    if not texto_excel or not str(texto_excel).strip():
        return None
    clave = relacion_service.normalizar_nombre_relacion(texto_excel.strip())
    if clave in rel_map:
        return rel_map[clave]
    return _resolver_por_mapa(rel_map, texto_excel)


def _resolver_municipio(
    mun_map: dict[tuple[int, str], Municipio],
    provincia_id: int,
    texto_excel: str,
) -> Municipio | None:
    k = _clave_catalogo(texto_excel)
    for cand in [k, *_variantes_guion(k)]:
        if not cand:
            continue
        m = mun_map.get((provincia_id, cand))
        if m:
            return m
    return None


def _indice_municipios_por_nombre(mun_map: dict[tuple[int, str], Municipio]) -> dict[str, list[Municipio]]:
    """Clave normalizada de nombre → municipios (puede haber homónimos en distintas provincias)."""
    idx: dict[str, list[Municipio]] = {}
    for m in {mm.id: mm for mm in mun_map.values()}.values():
        base = _clave_catalogo(m.nombre)
        for k in {base, *_variantes_guion(base)}:
            if k:
                idx.setdefault(k, []).append(m)
    return idx


def _candidatos_municipio_por_nombre(
    idx: dict[str, list[Municipio]],
    texto_excel: str,
) -> list[Municipio]:
    """Lista deduplicada por id de municipios cuyo nombre coincide con el Excel."""
    seen: dict[int, Municipio] = {}
    k = _clave_catalogo(texto_excel)
    for cand in [k, *_variantes_guion(k)]:
        for m in idx.get(cand, []):
            seen[m.id] = m
    return list(seen.values())


# Columnas reconocidas por el import (si faltan en el Excel se añaden vacías). Ninguna es obligatoria.
COLUMNAS_IMPORT_CONTACTO: tuple[str, ...] = (
    "nombre",
    "apellidos",
    "telefono",
    "provincia",
    "municipio",
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
)


def importar_excel_contactos(
    db: Session,
    archivo: UploadFile,
    *,
    omitir_duplicados: bool = False,
) -> dict[str, Any]:
    """
    Lee ``.xlsx``, normaliza filas, resuelve catálogos cuando hay coincidencia
    (si no hay, deja FKs en ``NULL``) e inserta todas las filas en bloque.
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
    for col in COLUMNAS_IMPORT_CONTACTO:
        if col not in df.columns:
            df[col] = ""

    filas_normalizadas = normalizer.normalizar_dataframe_import_contactos(df)
    log.info("Import Excel: normalizadas %s filas (sin BD)", len(filas_normalizadas))

    prov_map, mun_map, cargo_map, partido_map, tipo_map, rel_map = _cargar_mapas_catalogo(db)
    prov_por_id: dict[int, Provincia] = {p.id: p for p in {pp.id: pp for pp in prov_map.values()}.values()}
    mun_por_nombre_idx = _indice_municipios_por_nombre(mun_map)
    log.info(
        "Import Excel: catálogos indexados (prov=%s, mun=%s, cargo=%s, partido=%s, tipo=%s, rel=%s)",
        len(prov_por_id),
        len({id(v) for v in mun_map.values()}),
        len({id(v) for v in cargo_map.values()}),
        len({id(v) for v in partido_map.values()}),
        len({id(v) for v in tipo_map.values()}),
        len({id(v) for v in rel_map.values()}),
    )

    mappings: list[dict[str, Any]] = []

    for fn in filas_normalizadas:
        provincia: Provincia | None = None
        municipio: Municipio | None = None

        if fn.provincia:
            provincia = _resolver_por_mapa(prov_map, fn.provincia)

        if fn.municipio:
            if provincia is not None:
                municipio = _resolver_municipio(mun_map, provincia.id, fn.municipio)
            if municipio is None:
                candidatos = _candidatos_municipio_por_nombre(mun_por_nombre_idx, fn.municipio)
                if len(candidatos) == 1:
                    municipio = candidatos[0]
                    provincia = prov_por_id.get(municipio.provincia_id)
                elif len(candidatos) > 1 and provincia is not None:
                    for c in candidatos:
                        if c.provincia_id == provincia.id:
                            municipio = c
                            break

        cargo = _resolver_por_mapa(cargo_map, fn.cargo) if fn.cargo else None
        partido = _resolver_por_mapa(partido_map, fn.partido) if fn.partido else None
        tipo = _resolver_por_mapa(tipo_map, fn.tipo) if fn.tipo else None
        relacion = _resolver_relacion(rel_map, fn.relacion) if fn.relacion else None

        tel_db = fn.telefono or None
        responsable = fn.responsable or None
        notas = fn.notas or None

        mappings.append(
            {
                "nombre": fn.nombre or None,
                "apellidos": fn.apellidos or None,
                "telefono": tel_db,
                "municipio_id": municipio.id if municipio else None,
                "provincia_id": provincia.id if provincia else None,
                "cargo_id": cargo.id if cargo else None,
                "partido_id": partido.id if partido else None,
                "tipo_id": tipo.id if tipo else None,
                "relacion_id": relacion.id if relacion else None,
                "afinidad": fn.afinidad or None,
                "influencia": fn.influencia or None,
                "moviliza": fn.moviliza,
                "ultimo_contacto": fn.ultimo_contacto,
                "proximo_contacto": fn.proximo_contacto,
                "responsable": responsable,
                "prioridad": fn.prioridad or None,
                "notas": notas,
                "periodo": fn.periodo or None,
            }
        )

    omitidos_dup = 0
    if omitir_duplicados and mappings:
        con_mun = [m for m in mappings if m.get("municipio_id") is not None]
        sin_mun = [m for m in mappings if m.get("municipio_id") is None]
        claves = [(m["nombre"], m["apellidos"], m["municipio_id"]) for m in con_mun]
        existentes: set[tuple[Any, Any, int]] = set()
        chunk = 400
        for i in range(0, len(claves), chunk):
            sub = claves[i : i + chunk]
            if not sub:
                break
            stmt = select(Contacto.nombre, Contacto.apellidos, Contacto.municipio_id).where(
                tuple_(Contacto.nombre, Contacto.apellidos, Contacto.municipio_id).in_(sub)
            )
            for r in db.execute(stmt):
                existentes.add((r[0], r[1], r[2]))

        filtrados: list[dict[str, Any]] = []
        for m in con_mun:
            ck = (m["nombre"], m["apellidos"], m["municipio_id"])
            if ck in existentes:
                omitidos_dup += 1
                log.info("Omitido duplicado en BD: %s", ck)
                continue
            filtrados.append(m)
        mappings = sin_mun + filtrados

    mappings.sort(
        key=lambda x: (
            x.get("provincia_id") or 0,
            x.get("municipio_id") or 0,
            x.get("apellidos") or "",
            x.get("nombre") or "",
        ),
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
            # Diagnóstico: intenta ubicar la primera fila que rompe el insert.
            fila_pos: int | None = None
            fila_data: dict[str, Any] | None = None
            fila_error: str | None = None
            for idx, row in enumerate(mappings, start=1):
                try:
                    with db.begin_nested():
                        db.bulk_insert_mappings(Contacto, [row])
                        db.flush()
                except Exception as row_exc:  # noqa: BLE001
                    fila_pos = idx
                    fila_data = row
                    fila_error = str(row_exc)
                    break

            if fila_pos is not None and fila_data is not None:
                resumen = {
                    "nombre": fila_data.get("nombre"),
                    "apellidos": fila_data.get("apellidos"),
                    "telefono": fila_data.get("telefono"),
                    "municipio_id": fila_data.get("municipio_id"),
                    "provincia_id": fila_data.get("provincia_id"),
                    "cargo_id": fila_data.get("cargo_id"),
                    "partido_id": fila_data.get("partido_id"),
                    "tipo_id": fila_data.get("tipo_id"),
                    "relacion_id": fila_data.get("relacion_id"),
                    "afinidad": fila_data.get("afinidad"),
                    "influencia": fila_data.get("influencia"),
                    "prioridad": fila_data.get("prioridad"),
                    "periodo": fila_data.get("periodo"),
                }
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=(
                        "Error al insertar contactos en bloque. "
                        f"Primera fila con error (posición en lote ordenado: {fila_pos}). "
                        f"Motivo SQL: {fila_error or str(exc)}. "
                        f"Resumen fila: {resumen}"
                    ),
                ) from exc

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error al insertar contactos en bloque; motivo SQL: {exc}",
            ) from exc

    return {
        "status": "ok",
        "insertados": insertados,
        "errores": 0,
        "omitidos_duplicados": omitidos_dup,
        "detalle_errores": [],
    }
