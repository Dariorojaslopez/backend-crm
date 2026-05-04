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
    Clave estable para comparar con la BD: NFKC, trim, espacios colapsados, mayúsculas.
    Así "Boyacá ", "BOYACA" y variantes razonables coinciden con el nombre almacenado.
    """
    if not s:
        return ""
    t = unicodedata.normalize("NFKC", str(s).strip())
    t = re.sub(r"\s+", " ", t).upper()
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


COLUMNAS_REQUERIDAS: frozenset[str] = frozenset(
    {
        "nombre",
        "apellidos",
        "telefono",
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
    }
)


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
    if "provincia" not in df.columns:
        df["provincia"] = ""

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

    detalle_errores: list[dict[str, Any]] = []
    mappings: list[dict[str, Any]] = []
    vistos_archivo: set[tuple[str, str, int]] = set()

    for fn in filas_normalizadas:
        fila = fn.fila_excel
        errs: list[str] = list(fn.errores_normalizacion)

        provincia: Provincia | None = None
        municipio: Municipio | None = None

        if fn.provincia:
            provincia = _resolver_por_mapa(prov_map, fn.provincia)
            if not provincia:
                errs.append(f"provincia no encontrada en BD (valor Excel): {fn.provincia}")

        if fn.municipio:
            if provincia is not None:
                municipio = _resolver_municipio(mun_map, provincia.id, fn.municipio)
                if not municipio:
                    errs.append(
                        f"municipio no encontrado en BD para la provincia indicada (valor Excel): {fn.municipio}"
                    )
                elif municipio.provincia_id != provincia.id:
                    errs.append(
                        "municipio no pertenece a la provincia del Excel; "
                        "corrija la provincia o déjela vacía para tomarla automáticamente del municipio"
                    )
            else:
                candidatos = _candidatos_municipio_por_nombre(mun_por_nombre_idx, fn.municipio)
                if len(candidatos) == 1:
                    municipio = candidatos[0]
                    provincia = prov_por_id.get(municipio.provincia_id)
                    if provincia is None:
                        errs.append("provincia asociada al municipio no encontrada en catálogo")
                elif len(candidatos) == 0:
                    errs.append(f"municipio no encontrado en BD (valor Excel): {fn.municipio}")
                else:
                    nombres_prov = sorted(
                        {prov_por_id[m.provincia_id].nombre for m in candidatos if m.provincia_id in prov_por_id}
                    )
                    errs.append(
                        "municipio ambiguo: existe en varias provincias; indique la columna provincia. "
                        f"Candidatas: {', '.join(nombres_prov)}"
                    )

        cargo = _resolver_por_mapa(cargo_map, fn.cargo) if fn.cargo else None
        if fn.cargo and not cargo:
            errs.append(f"cargo no encontrado en BD (valor Excel): {fn.cargo}")

        partido = _resolver_por_mapa(partido_map, fn.partido) if fn.partido else None
        if fn.partido and not partido:
            errs.append(f"partido no encontrado en BD (valor Excel): {fn.partido}")

        tipo = _resolver_por_mapa(tipo_map, fn.tipo) if fn.tipo else None
        if fn.tipo and not tipo:
            errs.append(f"tipo no encontrado en BD (valor Excel): {fn.tipo}")

        relacion = _resolver_relacion(rel_map, fn.relacion) if fn.relacion else None
        if fn.relacion and not relacion:
            errs.append(f"relacion no encontrada en BD (valor Excel): {fn.relacion}")

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
