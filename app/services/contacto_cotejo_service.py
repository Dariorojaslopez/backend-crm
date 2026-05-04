"""Cotejo de filas de contacto contra catálogos parametrizados (misma lógica que import Excel)."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.models import Cargo, Municipio, Partido, Provincia, Relacion, Tipo
from app.schemas.contacto_cotejo import (
    ContactoCotejoFilaEntrada,
    ContactoCotejoFilaSalida,
    ContactoCotejarResponse,
)
from app.services.excel_service import (
    _cargar_mapas_catalogo,
    _indice_municipios_por_nombre,
    resolver_parametros_catalogo_para_fila,
)
from app.utils.normalizer import FilaImportNormalizada, trim, upper_catalogo

log = logging.getLogger(__name__)


def _entrada_a_fila_import(idx: int, e: ContactoCotejoFilaEntrada) -> FilaImportNormalizada:
    """Replica la normalización de importación para campos de catálogo."""
    return FilaImportNormalizada(
        fila_excel=idx + 1,
        nombre=trim(e.nombre)[:120] if e.nombre else "",
        apellidos=trim(e.apellidos)[:180] if e.apellidos else "",
        telefono="",
        provincia=upper_catalogo(e.provincia) if e.provincia else "",
        municipio=upper_catalogo(e.municipio) if e.municipio else "",
        cargo=upper_catalogo(e.cargo) if e.cargo else "",
        partido=upper_catalogo(e.partido) if e.partido else "",
        tipo=upper_catalogo(e.tipo) if e.tipo else "",
        relacion=trim(e.relacion) if e.relacion else "",
        afinidad="",
        influencia="",
        moviliza=False,
        ultimo_contacto=None,
        proximo_contacto=None,
        responsable="",
        prioridad="",
        notas="",
        periodo="",
    )


def cotejar_carga_contactos(db: Session, filas: list[ContactoCotejoFilaEntrada]) -> ContactoCotejarResponse:
    prov_map, mun_map, cargo_map, partido_map, tipo_map, rel_map = _cargar_mapas_catalogo(db)
    prov_por_id: dict[int, Provincia] = {p.id: p for p in {pp.id: pp for pp in prov_map.values()}.values()}
    mun_por_nombre_idx = _indice_municipios_por_nombre(mun_map)

    resultados: list[ContactoCotejoFilaSalida] = []
    sin_alertas = 0

    for idx, entrada in enumerate(filas):
        fn = _entrada_a_fila_import(idx, entrada)
        provincia, municipio, cargo, partido, tipo, relacion, alertas = resolver_parametros_catalogo_para_fila(
            fn,
            prov_map=prov_map,
            mun_map=mun_map,
            cargo_map=cargo_map,
            partido_map=partido_map,
            tipo_map=tipo_map,
            rel_map=rel_map,
            prov_por_id=prov_por_id,
            mun_por_nombre_idx=mun_por_nombre_idx,
        )

        pid = provincia.id if provincia else None
        mid = municipio.id if municipio else None
        cid = cargo.id if cargo else None
        prid = partido.id if partido else None
        tid = tipo.id if tipo else None
        rid = relacion.id if relacion else None

        pn = provincia.nombre if provincia else None
        mn = municipio.nombre if municipio else None
        cn = cargo.nombre if cargo else None
        prn = partido.nombre if partido else None
        tn = tipo.nombre if tipo else None
        rn = relacion.nombre if relacion else None

        if entrada.municipio_id is not None:
            m_db = db.get(Municipio, entrada.municipio_id)
            if m_db is None:
                alertas.append(f"municipio_id={entrada.municipio_id} no existe en la base de datos.")
            else:
                if municipio is not None and municipio.id != entrada.municipio_id:
                    alertas.append(
                        "municipio_id no coincide con el municipio resuelto por el texto «municipio» enviado.",
                    )
                mid = entrada.municipio_id
                mn = m_db.nombre
                if m_db.provincia_id:
                    p_db = prov_por_id.get(m_db.provincia_id)
                    if p_db is not None:
                        if pid is None:
                            pid = p_db.id
                            pn = p_db.nombre
                        elif pid != m_db.provincia_id:
                            alertas.append(
                                "provincia_id implícito del municipio_id no coincide con la provincia resuelta por texto.",
                            )

        if entrada.provincia_id is not None:
            p_db = db.get(Provincia, entrada.provincia_id)
            if p_db is None:
                alertas.append(f"provincia_id={entrada.provincia_id} no existe en la base de datos.")
            else:
                if provincia is not None and provincia.id != entrada.provincia_id:
                    alertas.append(
                        "provincia_id no coincide con la provincia resuelta por el texto «provincia» enviado.",
                    )
                pid = entrada.provincia_id
                pn = p_db.nombre

        if entrada.cargo_id is not None:
            c_db = db.get(Cargo, entrada.cargo_id)
            if c_db is None:
                alertas.append(f"cargo_id={entrada.cargo_id} no existe en la base de datos.")
            else:
                if cargo is not None and cargo.id != entrada.cargo_id:
                    alertas.append("cargo_id no coincide con el cargo resuelto por texto.")
                cid = entrada.cargo_id
                cn = c_db.nombre

        if entrada.partido_id is not None:
            p_db = db.get(Partido, entrada.partido_id)
            if p_db is None:
                alertas.append(f"partido_id={entrada.partido_id} no existe en la base de datos.")
            else:
                if partido is not None and partido.id != entrada.partido_id:
                    alertas.append("partido_id no coincide con el partido resuelto por texto.")
                prid = entrada.partido_id
                prn = p_db.nombre

        if entrada.tipo_id is not None:
            t_db = db.get(Tipo, entrada.tipo_id)
            if t_db is None:
                alertas.append(f"tipo_id={entrada.tipo_id} no existe en la base de datos.")
            else:
                if tipo is not None and tipo.id != entrada.tipo_id:
                    alertas.append("tipo_id no coincide con el tipo resuelto por texto.")
                tid = entrada.tipo_id
                tn = t_db.nombre

        if entrada.relacion_id is not None:
            r_db = db.get(Relacion, entrada.relacion_id)
            if r_db is None:
                alertas.append(f"relacion_id={entrada.relacion_id} no existe en la base de datos.")
            else:
                if relacion is not None and relacion.id != entrada.relacion_id:
                    alertas.append("relacion_id no coincide con la relación resuelta por texto.")
                rid = entrada.relacion_id
                rn = r_db.nombre

        ok = len(alertas) == 0
        if ok:
            sin_alertas += 1

        resultados.append(
            ContactoCotejoFilaSalida(
                indice=idx,
                provincia_id=pid,
                municipio_id=mid,
                cargo_id=cid,
                partido_id=prid,
                tipo_id=tid,
                relacion_id=rid,
                provincia_nombre=pn,
                municipio_nombre=mn,
                cargo_nombre=cn,
                partido_nombre=prn,
                tipo_nombre=tn,
                relacion_nombre=rn,
                alertas=alertas,
                cotejo_sin_alertas=ok,
            )
        )

    total = len(filas)
    return ContactoCotejarResponse(
        total_filas=total,
        filas_sin_alertas=sin_alertas,
        filas_con_alertas=total - sin_alertas,
        resultados=resultados,
    )
