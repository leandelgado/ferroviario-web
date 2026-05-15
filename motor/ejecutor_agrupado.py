"""
Executes an intent grouped by year (Etapa 5).

`ejecutar_agrupado` returns a `Comparacion` whose items are one row per year
(monoline) or one row per (línea, año) pair (multi-line). It reuses the
existing comparison response shape so the frontend renderer needs no changes.
"""

from __future__ import annotations

import itertools
import math

import pandas as pd

from motor._ratios import FORMULAS_RATIOS
from motor.almacen import Almacen
from motor.respuesta import Comparacion, ItemComparacion


def _ranking(items: list[ItemComparacion], direccion_mejor: str) -> list[str]:
    """Order item labels best→worst per direccion_mejor."""
    if direccion_mejor == "mayor":
        ordered = sorted(items, key=lambda x: x.valor, reverse=True)
    elif direccion_mejor == "menor":
        ordered = sorted(items, key=lambda x: x.valor, reverse=False)
    else:  # neutral — preserve display order
        ordered = list(items)
    return [i.etiqueta for i in ordered]


def ejecutar_agrupado(intent, almacen) -> tuple[Comparacion, list[str]]:
    """Execute an intent with grupo_por="año".

    Parameters
    ----------
    intent:
        ``semantica.Intent`` with ``grupo_por == "año"``.
    almacen:
        The ``Almacen`` class (namespace).

    Returns
    -------
    tuple[Comparacion, list[str]]
        Comparacion with one item per year (or per línea-año) and
        any advisory warnings.

    Raises
    ------
    ValueError
        If no data matches the filters or the metric column is missing.
    """
    advertencias: list[str] = []
    metrica = intent.metrica

    # Metric metadata
    dim = almacen.obtener("dim_indicadores")
    dim_row = dim[dim["campo"] == metrica]
    unidad = dim_row["unidad"].iloc[0] if not dim_row.empty else ""
    direccion_mejor = (
        dim_row["direccion_mejor"].iloc[0] if not dim_row.empty else "neutral"
    )
    agregable = bool(dim_row["agregable"].iloc[0]) if not dim_row.empty else True

    # 1. Load table
    df = almacen.obtener(intent.tabla)

    # 2. Temporal filter
    if intent.rango_temporal:
        df = df[
            (df["periodo"] >= intent.rango_temporal.desde)
            & (df["periodo"] <= intent.rango_temporal.hasta)
        ]

    # 3. Line filter
    if intent.filtros_linea:
        if "linea" in df.columns:
            df = df[df["linea"].isin(intent.filtros_linea)]
        else:
            advertencias.append(
                f"Tabla '{intent.tabla}' no tiene columna 'linea'; "
                "filtro de línea ignorado."
            )

    if df.empty:
        raise ValueError("Sin datos para los filtros aplicados")

    if metrica not in df.columns and metrica not in FORMULAS_RATIOS:
        raise ValueError(
            f"Métrica '{metrica}' no encontrada en tabla '{intent.tabla}'"
        )

    # 4. Extract year from periodo (YYYY-MM → YYYY)
    df = df.copy()
    df["anio"] = df["periodo"].astype(str).str[:4]

    # 5. Decide grouping keys: include "linea" only when filtering on >1 lines
    multi_linea = (
        len(intent.filtros_linea) > 1 and "linea" in df.columns
    )
    group_keys = ["linea", "anio"] if multi_linea else ["anio"]

    # 6. Aggregate
    if metrica in FORMULAS_RATIOS:
        num_col, den_col = FORMULAS_RATIOS[metrica]
        if num_col not in df.columns or den_col not in df.columns:
            raise ValueError(
                f"Componentes del ratio '{metrica}' ausentes en la tabla."
            )
        agg = df.groupby(group_keys, as_index=False).agg(
            _num=(num_col, lambda s: pd.to_numeric(s, errors="coerce").sum()),
            _den=(den_col, lambda s: pd.to_numeric(s, errors="coerce").sum()),
        )
        valid = agg["_den"] != 0
        if not valid.any():
            raise ValueError(f"Denominador cero en todos los grupos para {metrica}")
        agg = agg[valid].copy()
        agg["_valor"] = agg["_num"] / agg["_den"]
    else:
        if not agregable:
            advertencias.append(
                f"'{metrica}' no es agregable; se usó promedio por grupo."
            )
            agg = (
                df.assign(_num=pd.to_numeric(df[metrica], errors="coerce"))
                .groupby(group_keys, as_index=False)["_num"]
                .mean()
                .rename(columns={"_num": "_valor"})
            )
        else:
            agg = (
                df.assign(_num=pd.to_numeric(df[metrica], errors="coerce"))
                .groupby(group_keys, as_index=False)["_num"]
                .sum()
                .rename(columns={"_num": "_valor"})
            )

    # Drop groups whose value is NaN (all-null metric column for the group)
    agg = agg[agg["_valor"].notna()]
    if agg.empty:
        raise ValueError("No se pudieron calcular valores para ningún año")

    # 7. Sort for display: línea asc, año asc (or just año asc)
    if multi_linea:
        agg = agg.sort_values(["linea", "anio"]).reset_index(drop=True)
    else:
        agg = agg.sort_values("anio").reset_index(drop=True)

    # 8. Build items
    items: list[ItemComparacion] = []
    for _, row in agg.iterrows():
        anio = str(row["anio"])
        if multi_linea:
            etiqueta = f"{row['linea']} {anio}"
        else:
            etiqueta = anio
        items.append(
            ItemComparacion(etiqueta=etiqueta, valor=float(row["_valor"]), unidad=unidad)
        )

    # 9. Heterogeneous coverage warning (multi-line only)
    if multi_linea:
        anios_por_linea = agg.groupby("linea")["anio"].nunique()
        if anios_por_linea.nunique() > 1:
            advertencias.append(
                "Cobertura desigual entre líneas: alguna(s) tienen más años de datos que otra(s)."
            )

    ranking = _ranking(items, direccion_mejor)

    return Comparacion(
        eje="periodo",
        items=items,
        diferencias=[],
        ranking=ranking,
    ), advertencias
