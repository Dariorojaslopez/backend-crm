"""Reglas de negocio y consultas para contactos políticos."""

from __future__ import annotations

import io
import logging
import math
import re
from datetime import date, datetime
from typing import Any

import pandas as pd
from fastapi import HTTPException, UploadFile
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models import Cargo, Contacto, Municipio, Partido, Relacion, Tipo
from app.schemas.contacto import ContactoCreate, ContactoResponse, ContactoUpdate
from app.schemas.pagination import PaginatedResponse
from app.services import catalogo_service, relacion_service

log = logging.getLogger(__name__)

_PRIORIDAD_ORDEN = case(
    (Contacto.prioridad == "alta", 1),
    (Contacto.prioridad == "media", 2),
    (Contacto.prioridad == "baja", 3),
    else_=4,
)


def _normalizar_texto_corto(val: str | None) -> str | None:
    if val is None:
        return None
    s = str(val).strip()
    return s.lower() if s else None


def _validar_coherencia_geografica(db: Session, municipio_id: int, provincia_id: int) -> None:
    m = db.get(Municipio, municipio_id)
    if not m:
        raise HTTPException(status_code=404, detail="Municipio no encontrado")
    if m.provincia_id != provincia_id:
        raise HTTPException(
            status_code=400,
            detail="El municipio no pertenece a la provincia indicada",
        )


def _validar_relacion_id(db: Session, relacion_id: int) -> None:
    if not db.get(Relacion, relacion_id):
        raise HTTPException(status_code=400, detail="relacion_id no existe")


def _validar_fks_catalogo(db: Session, *, cargo_id: int, partido_id: int, tipo_id: int) -> None:
    if not db.get(Cargo, cargo_id):
        raise HTTPException(status_code=404, detail="Cargo no encontrado")
    if not db.get(Partido, partido_id):
        raise HTTPException(status_code=404, detail="Partido no encontrado")
    if not db.get(Tipo, tipo_id):
        raise HTTPException(status_code=404, detail="Tipo no encontrado")


def serialize_contacto(c: Contacto) -> ContactoResponse:
    return ContactoResponse(
        id=c.id,
        nombre=c.nombre,
        apellidos=c.apellidos,
        telefono=c.telefono,
        municipio_id=c.municipio_id,
        provincia_id=c.provincia_id,
        cargo_id=c.cargo_id,
        partido_id=c.partido_id,
        tipo_id=c.tipo_id,
        relacion_id=c.relacion_id,
        municipio_nombre=c.municipio.nombre if c.municipio else None,
        provincia_nombre=c.provincia.nombre if c.provincia else None,
        cargo_nombre=c.cargo.nombre if c.cargo else None,
        partido_nombre=c.partido.nombre if c.partido else None,
        tipo_nombre=c.tipo.nombre if c.tipo else None,
        relacion_nombre=c.relacion.nombre if c.relacion else None,
        afinidad=c.afinidad,
        influencia=c.influencia,
        moviliza=c.moviliza,
        ultimo_contacto=c.ultimo_contacto,
        proximo_contacto=c.proximo_contacto,
        responsable=c.responsable,
        prioridad=c.prioridad,
        notas=c.notas,
        periodo=c.periodo,
        created_at=c.created_at,
    )


def crear_contacto(db: Session, data: ContactoCreate) -> ContactoResponse:
    _validar_coherencia_geografica(db, data.municipio_id, data.provincia_id)
    _validar_fks_catalogo(
        db,
        cargo_id=data.cargo_id,
        partido_id=data.partido_id,
        tipo_id=data.tipo_id,
    )
    _validar_relacion_id(db, data.relacion_id)
    c = Contacto(
        nombre=data.nombre.strip(),
        apellidos=data.apellidos.strip(),
        telefono=data.telefono.strip() if data.telefono else None,
        municipio_id=data.municipio_id,
        provincia_id=data.provincia_id,
        cargo_id=data.cargo_id,
        partido_id=data.partido_id,
        tipo_id=data.tipo_id,
        relacion_id=data.relacion_id,
        afinidad=_normalizar_texto_corto(data.afinidad) or "",
        influencia=_normalizar_texto_corto(data.influencia) or "",
        moviliza=data.moviliza,
        ultimo_contacto=data.ultimo_contacto,
        proximo_contacto=data.proximo_contacto,
        responsable=data.responsable.strip() if data.responsable else None,
        prioridad=_normalizar_texto_corto(data.prioridad) or data.prioridad.strip().lower(),
        notas=data.notas.strip() if data.notas else None,
        periodo=data.periodo.strip(),
    )
    db.add(c)
    db.flush()
    cargado = obtener_contacto(db, c.id)
    if not cargado:
        raise HTTPException(status_code=500, detail="No se pudo recargar el contacto creado")
    log.info("Contacto creado id=%s nombre=%s", c.id, c.nombre)
    return serialize_contacto(cargado)


def obtener_contacto(db: Session, contacto_id: int) -> Contacto | None:
    stmt = (
        select(Contacto)
        .options(
            joinedload(Contacto.municipio),
            joinedload(Contacto.provincia),
            joinedload(Contacto.cargo),
            joinedload(Contacto.partido),
            joinedload(Contacto.tipo),
            joinedload(Contacto.relacion),
        )
        .where(Contacto.id == contacto_id)
    )
    return db.scalars(stmt).unique().one_or_none()


def listar_contactos(
    db: Session,
    *,
    municipio_id: int | None = None,
    provincia_id: int | None = None,
    cargo_id: int | None = None,
    partido_id: int | None = None,
    tipo_id: int | None = None,
    relacion_id: int | None = None,
    afinidad: str | None = None,
    influencia: str | None = None,
    periodo: str | None = None,
    nombre: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> PaginatedResponse[ContactoResponse]:
    if page < 1:
        raise HTTPException(status_code=400, detail="page debe ser >= 1")
    if page_size < 1 or page_size > 100:
        raise HTTPException(status_code=400, detail="page_size entre 1 y 100")

    filtros: list[Any] = []
    if municipio_id is not None:
        filtros.append(Contacto.municipio_id == municipio_id)
    if provincia_id is not None:
        filtros.append(Contacto.provincia_id == provincia_id)
    if cargo_id is not None:
        filtros.append(Contacto.cargo_id == cargo_id)
    if partido_id is not None:
        filtros.append(Contacto.partido_id == partido_id)
    if tipo_id is not None:
        filtros.append(Contacto.tipo_id == tipo_id)
    if relacion_id is not None:
        filtros.append(Contacto.relacion_id == relacion_id)
    if afinidad:
        filtros.append(Contacto.afinidad == afinidad.strip().lower())
    if influencia:
        filtros.append(Contacto.influencia == influencia.strip().lower())
    if periodo:
        filtros.append(Contacto.periodo == periodo.strip())
    if nombre and nombre.strip():
        term = f"%{nombre.strip()}%"
        filtros.append(
            or_(
                Contacto.nombre.ilike(term),
                Contacto.apellidos.ilike(term),
            )
        )

    count_stmt = select(func.count()).select_from(Contacto)
    if filtros:
        count_stmt = count_stmt.where(*filtros)
    total = db.scalar(count_stmt) or 0

    base_opts = (
        joinedload(Contacto.municipio),
        joinedload(Contacto.provincia),
        joinedload(Contacto.cargo),
        joinedload(Contacto.partido),
        joinedload(Contacto.tipo),
        joinedload(Contacto.relacion),
    )
    stmt = select(Contacto).options(*base_opts)
    if filtros:
        stmt = stmt.where(*filtros)

    stmt = stmt.order_by(
        _PRIORIDAD_ORDEN.asc(),
        Contacto.proximo_contacto.asc().nulls_last(),
        Contacto.ultimo_contacto.desc().nulls_last(),
        Contacto.id.asc(),
    )
    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)

    rows = db.scalars(stmt).unique().all()
    items = [serialize_contacto(c) for c in rows]
    pages = math.ceil(total / page_size) if page_size else 0
    log.debug("Listado contactos total=%s page=%s", total, page)
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


def actualizar_contacto(db: Session, contacto_id: int, data: ContactoUpdate) -> ContactoResponse:
    c = obtener_contacto(db, contacto_id)
    if not c:
        raise HTTPException(status_code=404, detail="Contacto no encontrado")

    payload = data.model_dump(exclude_unset=True)
    municipio_id = int(payload.get("municipio_id", c.municipio_id))
    provincia_id = int(payload.get("provincia_id", c.provincia_id))
    if "municipio_id" in payload or "provincia_id" in payload:
        _validar_coherencia_geografica(db, municipio_id, provincia_id)

    cargo_id = int(payload.get("cargo_id", c.cargo_id))
    partido_id = int(payload.get("partido_id", c.partido_id))
    tipo_id = int(payload.get("tipo_id", c.tipo_id))
    if "cargo_id" in payload or "partido_id" in payload or "tipo_id" in payload:
        _validar_fks_catalogo(db, cargo_id=cargo_id, partido_id=partido_id, tipo_id=tipo_id)

    if "relacion_id" in payload and payload["relacion_id"] is not None:
        _validar_relacion_id(db, int(payload["relacion_id"]))

    for campo, valor in payload.items():
        if campo in {"afinidad", "influencia", "prioridad"} and isinstance(valor, str):
            valor = valor.strip().lower()
        if campo in {"nombre", "apellidos", "periodo"} and isinstance(valor, str):
            valor = valor.strip()
        if campo == "telefono" and isinstance(valor, str):
            valor = valor.strip() or None
        if campo == "notas" and isinstance(valor, str):
            valor = valor.strip() or None
        if campo == "responsable" and isinstance(valor, str):
            valor = valor.strip() or None
        setattr(c, campo, valor)

    db.flush()
    cargado = obtener_contacto(db, contacto_id)
    if not cargado:
        raise HTTPException(status_code=404, detail="Contacto no encontrado tras actualizar")
    log.info("Contacto actualizado id=%s", contacto_id)
    return serialize_contacto(cargado)


def eliminar_contacto(db: Session, contacto_id: int) -> None:
    c = db.get(Contacto, contacto_id)
    if not c:
        raise HTTPException(status_code=404, detail="Contacto no encontrado")
    db.delete(c)
    log.info("Contacto eliminado id=%s", contacto_id)


def _parse_bool_moviliza(val: Any) -> bool:
    if pd.isna(val) or val is None or val == "":
        return False
    s = str(val).strip().upper()
    if s in {"SI", "S", "TRUE", "1", "YES", "Y"}:
        return True
    if s in {"NO", "N", "FALSE", "0"}:
        return False
    return bool(val)


def _parse_fecha(val: Any) -> date | None:
    if pd.isna(val) or val is None or val == "":
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    ts = pd.to_datetime(val, errors="coerce")
    if pd.isna(ts):
        return None
    return ts.date()


def _limpiar_str(val: Any) -> str | None:
    if pd.isna(val) or val is None:
        return None
    s = str(val).strip()
    return s.upper() if s else None


def _limpiar_nombre_persona(val: Any) -> str | None:
    if pd.isna(val) or val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    return " ".join(part.capitalize() for part in s.split())


def _celda_periodo(val: Any) -> str:
    if pd.isna(val) or val is None:
        return ""
    if isinstance(val, float):
        if val == int(val):
            return str(int(val))
    return str(val).strip()


def _limpiar_str_lower(val: Any) -> str | None:
    if pd.isna(val) or val is None:
        return None
    s = str(val).strip()
    return s.lower() if s else None


def _normalizar_nombre_columna(name: str) -> str:
    n = str(name).strip().lower()
    n = re.sub(r"\s+", "_", n)
    return n


def importar_desde_excel(db: Session, archivo: UploadFile) -> dict[str, Any]:
    """
    Importa filas desde Excel: busca o crea catálogos e inserta contactos.

    Columnas esperadas: nombre, apellidos, telefono, provincia, municipio,
    partido, cargo, tipo, afinidad, influencia, relacion (texto → catálogo relaciones),
    moviliza, ultimo_contacto, proximo_contacto, responsable, prioridad, notas, periodo.
    """
    if not archivo.filename or not archivo.filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="Solo se admiten archivos .xlsx (openpyxl)")

    raw = archivo.file.read()
    try:
        df = pd.read_excel(io.BytesIO(raw))
    except Exception as exc:  # noqa: BLE001
        log.exception("Fallo leyendo Excel")
        raise HTTPException(status_code=400, detail=f"No se pudo leer el Excel: {exc}") from exc

    if df.empty:
        return {"insertados": 0, "errores": ["Archivo sin filas de datos"]}

    df.columns = [_normalizar_nombre_columna(c) for c in df.columns]

    alias = {
        "nombres": "nombre",
        "apellido": "apellidos",
        "tel": "telefono",
        "telefono_movil": "telefono",
        "rol": "tipo",
        "tipo_contacto": "tipo",
        "tipo_figura": "tipo",
    }
    df.rename(columns={k: v for k, v in alias.items() if k in df.columns}, inplace=True)

    requeridas = {
        "nombre",
        "apellidos",
        "provincia",
        "municipio",
        "partido",
        "cargo",
        "tipo",
        "periodo",
    }
    faltan = requeridas - set(df.columns)
    if faltan:
        raise HTTPException(
            status_code=400,
            detail=f"Faltan columnas obligatorias en el Excel: {sorted(faltan)}",
        )

    insertados = 0
    errores: list[str] = []

    for idx, row in df.iterrows():
        fila = int(idx) + 2
        try:
            nombre = _limpiar_nombre_persona(row.get("nombre"))
            apellidos = _limpiar_nombre_persona(row.get("apellidos"))
            if not nombre or not apellidos:
                errores.append(f"Fila {fila}: nombre o apellidos vacíos")
                continue

            provincia_nombre = _limpiar_str(row.get("provincia"))
            municipio_nombre = _limpiar_str(row.get("municipio"))
            if not provincia_nombre or not municipio_nombre:
                errores.append(f"Fila {fila}: provincia o municipio vacíos")
                continue

            partido_nombre = _limpiar_str(row.get("partido"))
            cargo_nombre = _limpiar_str(row.get("cargo"))
            tipo_nombre = _limpiar_str(row.get("tipo"))
            if not partido_nombre or not cargo_nombre or not tipo_nombre:
                errores.append(f"Fila {fila}: partido, cargo o tipo vacíos")
                continue

            provincia = catalogo_service.obtener_o_crear_provincia(db, provincia_nombre)
            municipio = catalogo_service.obtener_o_crear_municipio(db, municipio_nombre, provincia)
            partido = catalogo_service.obtener_o_crear_partido(db, partido_nombre)
            cargo = catalogo_service.obtener_o_crear_cargo(db, cargo_nombre)
            tipo = catalogo_service.obtener_o_crear_tipo(db, tipo_nombre)

            telefono = _limpiar_str(row.get("telefono"))
            afinidad = _limpiar_str_lower(row.get("afinidad")) or "neutro"
            influencia = _limpiar_str_lower(row.get("influencia")) or "medio"
            relacion_raw = row.get("relacion")
            if pd.isna(relacion_raw) or str(relacion_raw).strip() == "":
                relacion_txt = "sin_contacto"
            else:
                relacion_txt = str(relacion_raw).strip()
            rel = relacion_service.obtener_o_crear_relacion(db, relacion_txt)

            moviliza = _parse_bool_moviliza(row.get("moviliza"))
            ultimo = _parse_fecha(row.get("ultimo_contacto"))
            proximo = _parse_fecha(row.get("proximo_contacto"))
            responsable_raw = row.get("responsable")
            responsable = None if pd.isna(responsable_raw) else str(responsable_raw).strip() or None
            prioridad = _limpiar_str_lower(row.get("prioridad")) or "media"
            notas_raw = row.get("notas")
            notas = None if pd.isna(notas_raw) else str(notas_raw).strip() or None
            periodo = _celda_periodo(row.get("periodo"))
            if not periodo:
                errores.append(f"Fila {fila}: periodo vacío")
                continue

            c = Contacto(
                nombre=nombre,
                apellidos=apellidos,
                telefono=telefono,
                municipio_id=municipio.id,
                provincia_id=provincia.id,
                cargo_id=cargo.id,
                partido_id=partido.id,
                tipo_id=tipo.id,
                relacion_id=rel.id,
                afinidad=afinidad,
                influencia=influencia,
                moviliza=moviliza,
                ultimo_contacto=ultimo,
                proximo_contacto=proximo,
                responsable=responsable,
                prioridad=prioridad,
                notas=notas,
                periodo=periodo,
            )
            db.add(c)
            insertados += 1
        except Exception as exc:  # noqa: BLE001
            log.warning("Error importando fila %s: %s", fila, exc)
            errores.append(f"Fila {fila}: {exc}")

    log.info("Importación Excel insertados=%s errores=%s", insertados, len(errores))
    return {"insertados": insertados, "errores": errores}
