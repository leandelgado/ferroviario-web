"""
Executes comparison intents (comparacion_lineas, comparacion_periodos) against
the parquet data warehouse.

The public function `ejecutar_comparacion` handles both comparison types,
grouping data by line or period and computing the requested metric for each
group. Results are returned as a `Comparacion` with ranking and pairwise diffs.
"""

from __future__ import annotations

import itertools

import pandas as pd

from motor.almacen import Almacen
from motor.respuesta import Comparacion, ItemComparacion
from motor.ejecutor import _FORMULAS_RATIOS


# ---------------------------------------------------------------------------
# Private helper
# ---------------------------------------------------------------------------

def _calcular_metrica_grupo(
    df_grupo: pd.DataFrame,
    metrica: str,
    almacen,
) -> tuple[float, str, list[str]]:
    """Compute metric for a data group.

    Parameters
    ----------
    df_grupo:
        Sub-DataFrame for a single line or period.
    metrica:
        The metric column name (campo from dim_indicadores).
    almacen:
        The Almacen class used to load dim_indicadores.

    Returns
    -------
    tuple[float, str, list[str]]
        (valor, agregacion_usada, advertencias)

    Raises
    ------
    ValueError
        If the denominator is zero for a ratio metric, or the metric column
        is missing.
    """
    advertencias: list[str] = []

    if metrica not in df_grupo.columns:
        raise ValueError(
            f"Métrica '{metrica}' no encontrada en el grupo de datos."
        )

    if metrica in _FORMULAS_RATIOS:
        # Recalculate ratio from components — do NOT average
        num_col, den_col = _FORMULAS_RATIOS[metrica]
        numerador = pd.to_numeric(df_grupo[num_col], errors="coerce").sum()
        denominador = pd.to_numeric(df_grupo[den_col], errors="coerce").sum()
        if denominador == 0:
            raise ValueError(f"Denominador cero para '{metrica}'.")
        valor = numerador / denominador
        agregacion_usada = "ratio_recalculado"
    else:
        # Look up aggregability from dim_indicadores
        dim = almacen.obtener("dim_indicadores")
        dim_row = dim[dim["campo"] == metrica]
        agregable = dim_row["agregable"].iloc[0] if not dim_row.empty else True

        if agregable:
            # Aggregable metrics: always sum for comparisons
            col_numeric = pd.to_numeric(df_grupo[metrica], errors="coerce")
            valor = col_numeric.sum()
            agregacion_usada = "sum"
        else:
            # Non-aggregable, non-ratio metrics: always mean for comparisons
            col_numeric = pd.to_numeric(df_grupo[metrica], errors="coerce")
            valor = col_numeric.mean()
            agregacion_usada = "mean"

    return valor, agregacion_usada, advertencias


# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------

def ejecutar_comparacion(intent, almacen) -> tuple[Comparacion, list[str]]:
    """Execute a comparison intent. Returns (Comparacion, advertencias).

    Handles both comparacion_lineas and comparacion_periodos.

    Parameters
    ----------
    intent:
        A ``semantica.Intent`` instance with tipo in
        {"comparacion_lineas", "comparacion_periodos"}.
    almacen:
        The ``Almacen`` class (used as a namespace; all methods are class
        methods).

    Returns
    -------
    tuple[Comparacion, list[str]]
        A ``Comparacion`` instance and a (possibly empty) list of warning
        strings.

    Raises
    ------
    ValueError
        If no data is found after filtering, or the metric / linea column is
        missing from the table.
    """
    advertencias: list[str] = []
    metrica = intent.metrica

    # ------------------------------------------------------------------
    # Load dim_indicadores once (needed for unidad and direccion_mejor)
    # ------------------------------------------------------------------
    dim = almacen.obtener("dim_indicadores")
    dim_row = dim[dim["campo"] == metrica]
    unidad = dim_row["unidad"].iloc[0] if not dim_row.empty else ""
    direccion_mejor = dim_row["direccion_mejor"].iloc[0] if not dim_row.empty else "neutral"

    # ------------------------------------------------------------------
    # Branch A: comparacion_lineas
    # ------------------------------------------------------------------
    if intent.tipo == "comparacion_lineas":
        # 1. Load table
        df = almacen.obtener(intent.tabla)

        # 2. Apply temporal filter
        if intent.rango_temporal:
            df = df[
                (df["periodo"] >= intent.rango_temporal.desde)
                & (df["periodo"] <= intent.rango_temporal.hasta)
            ]

        # 3. Apply line filter (if provided)
        if intent.filtros_linea:
            if "linea" in df.columns:
                df = df[df["linea"].isin(intent.filtros_linea)]
            else:
                advertencias.append(
                    f"Tabla '{intent.tabla}' no tiene columna 'linea'; "
                    "filtro de línea ignorado."
                )

        # 4. Validate
        if df.empty or "linea" not in df.columns:
            raise ValueError(
                "Sin datos para los filtros aplicados o tabla sin columna 'linea'."
            )

        # 5–6. Compute metric per line and build items
        items: list[ItemComparacion] = []
        for linea, df_grupo in df.groupby("linea"):
            try:
                valor, _, adv_grupo = _calcular_metrica_grupo(df_grupo, metrica, almacen)
            except ValueError:
                # Skip lines where computation fails (e.g. zero denominator)
                continue
            advertencias.extend(adv_grupo)
            items.append(ItemComparacion(etiqueta=str(linea), valor=valor, unidad=unidad))

        if not items:
            raise ValueError("No se pudieron calcular valores para ninguna línea.")

        # 7–8. Sort items by value according to direccion_mejor
        if direccion_mejor == "mayor":
            items_sorted = sorted(items, key=lambda i: i.valor, reverse=True)
        elif direccion_mejor == "menor":
            items_sorted = sorted(items, key=lambda i: i.valor, reverse=False)
        else:
            # neutral: alphabetical by etiqueta
            items_sorted = sorted(items, key=lambda i: i.etiqueta)

        # 9. Build ranking
        ranking = [item.etiqueta for item in items_sorted]

        # 10. Build pairwise diferencias
        diferencias: list[dict] = []
        for a, b in itertools.combinations(items_sorted, 2):
            diferencias.append({
                "entre": [a.etiqueta, b.etiqueta],
                "delta": abs(a.valor - b.valor),
            })

        return Comparacion(
            eje="linea",
            items=items_sorted,
            diferencias=diferencias,
            ranking=ranking,
        ), advertencias

    # ------------------------------------------------------------------
    # Branch B: comparacion_periodos
    # ------------------------------------------------------------------
    elif intent.tipo == "comparacion_periodos":
        # 1. Load table
        df = almacen.obtener(intent.tabla)

        # 2. Apply line filter (if provided and column exists)
        if intent.filtros_linea and "linea" in df.columns:
            df = df[df["linea"].isin(intent.filtros_linea)]

        # 3. For each period range, compute the metric
        items_p: list[ItemComparacion] = []
        for rango in intent.rangos_temporales:
            df_periodo = df[
                (df["periodo"] >= rango.desde)
                & (df["periodo"] <= rango.hasta)
            ]
            if df_periodo.empty:
                advertencias.append(
                    f"Sin datos para el periodo {rango.desde}/{rango.hasta}."
                )
                continue

            try:
                valor, _, adv_grupo = _calcular_metrica_grupo(df_periodo, metrica, almacen)
            except ValueError as exc:
                advertencias.append(str(exc))
                continue

            advertencias.extend(adv_grupo)
            etiqueta = rango.etiqueta or f"{rango.desde}/{rango.hasta}"
            items_p.append(ItemComparacion(etiqueta=etiqueta, valor=valor, unidad=unidad))

        if not items_p:
            raise ValueError("No se pudieron calcular valores para ningún periodo.")

        # 4. Sort by direccion_mejor
        if direccion_mejor == "mayor":
            items_p_sorted = sorted(items_p, key=lambda i: i.valor, reverse=True)
        elif direccion_mejor == "menor":
            items_p_sorted = sorted(items_p, key=lambda i: i.valor, reverse=False)
        else:
            items_p_sorted = sorted(items_p, key=lambda i: i.etiqueta)

        ranking_p = [item.etiqueta for item in items_p_sorted]

        diferencias_p: list[dict] = []
        for a, b in itertools.combinations(items_p_sorted, 2):
            diferencias_p.append({
                "entre": [a.etiqueta, b.etiqueta],
                "delta": abs(a.valor - b.valor),
            })

        return Comparacion(
            eje="periodo",
            items=items_p_sorted,
            diferencias=diferencias_p,
            ranking=ranking_p,
        ), advertencias

    else:
        raise ValueError(
            f"Tipo de comparación no soportado: '{intent.tipo}'. "
            "Use 'comparacion_lineas' o 'comparacion_periodos'."
        )
