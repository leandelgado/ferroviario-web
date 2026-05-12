"""
Executes a simple (non-comparison) intent against the parquet tables.

The public function `ejecutar_simple` applies temporal and dimensional filters,
selects the requested metric column, aggregates it correctly (including
ratio recalculation for non-aggregable ratio metrics), and returns a populated
`Dato` instance together with any advisory warnings.
"""

from __future__ import annotations

import pandas as pd

from motor.almacen import Almacen
from motor.respuesta import Dato

# ---------------------------------------------------------------------------
# Ratio metric formulas
# ---------------------------------------------------------------------------
# For these metrics, we must NOT use mean() — instead recalculate from the
# underlying numerator and denominator columns.

_FORMULAS_RATIOS: dict[str, tuple[str, str]] = {
    "regularidad_absoluta": ("trenes_puntuales", "trenes_programados"),
    "regularidad_relativa": ("trenes_puntuales", "trenes_corridos"),
    "cumplimiento_programa": ("trenes_corridos", "trenes_programados"),
    "tasa_cancelacion": ("trenes_cancelados", "trenes_programados"),
    "tarifa_media_pesos": ("recaudacion_pesos", "pax_pagos"),
}


# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------

def ejecutar_simple(intent, almacen: Almacen) -> tuple[Dato, list[str]]:
    """Execute intent against parquets. Returns (Dato, advertencias).

    Parameters
    ----------
    intent:
        A ``semantica.Intent`` instance with fields: tabla, metrica,
        rango_temporal, filtros_linea, agregacion, confianza, es_dominio.
    almacen:
        The ``Almacen`` class (used as a namespace; all methods are class
        methods).

    Returns
    -------
    tuple[Dato, list[str]]
        A ``Dato`` instance with the aggregated result and a (possibly empty)
        list of warning strings.

    Raises
    ------
    ValueError
        If no data is found after filtering, or if the requested metric column
        is absent from the table.
    """
    advertencias: list[str] = []

    # ------------------------------------------------------------------
    # Step 1: Load table
    # ------------------------------------------------------------------
    df = almacen.obtener(intent.tabla)

    # ------------------------------------------------------------------
    # Step 2: Apply temporal filter
    # ------------------------------------------------------------------
    if intent.rango_temporal:
        df = df[
            (df["periodo"] >= intent.rango_temporal.desde)
            & (df["periodo"] <= intent.rango_temporal.hasta)
        ]

    # ------------------------------------------------------------------
    # Step 3: Apply line filter (only if "linea" column exists)
    # ------------------------------------------------------------------
    if intent.filtros_linea:
        if "linea" in df.columns:
            df = df[df["linea"].isin(intent.filtros_linea)]
        else:
            advertencias.append(
                f"Tabla '{intent.tabla}' no tiene columna 'linea'; filtro de línea ignorado."
            )

    # ------------------------------------------------------------------
    # Step 4: Check data exists
    # ------------------------------------------------------------------
    if df.empty:
        raise ValueError("Sin datos para los filtros aplicados")

    # ------------------------------------------------------------------
    # Step 5: Get metric column
    # ------------------------------------------------------------------
    metrica = intent.metrica
    if metrica not in df.columns:
        raise ValueError(
            f"Métrica '{metrica}' no encontrada en tabla '{intent.tabla}'"
        )

    # ------------------------------------------------------------------
    # Step 5b: Load dim_indicadores once (used in steps 6 and 7)
    # ------------------------------------------------------------------
    dim = almacen.obtener("dim_indicadores")
    dim_row = dim[dim["campo"] == metrica]

    # ------------------------------------------------------------------
    # Step 6: Aggregate / recalculate
    # ------------------------------------------------------------------
    if metrica in _FORMULAS_RATIOS:
        # Recalculate ratio from components — do NOT average
        num_col, den_col = _FORMULAS_RATIOS[metrica]
        numerador = pd.to_numeric(df[num_col], errors="coerce").sum()
        denominador = pd.to_numeric(df[den_col], errors="coerce").sum()
        if denominador == 0:
            raise ValueError(f"Denominador cero para {metrica}")
        valor = numerador / denominador
        agregacion_usada = "ratio_recalculado"
    else:
        # Look up aggregability from dim_indicadores
        agregable = dim_row["agregable"].iloc[0] if not dim_row.empty else True

        # Requested aggregation from intent
        agg = getattr(intent, "agregacion", "sum")

        # If not aggregable and sum was requested, fall back to mean
        if not agregable and agg == "sum":
            agg = "mean"
            advertencias.append(
                f"'{metrica}' no es agregable; se usó promedio en lugar de suma."
            )

        col_numeric = pd.to_numeric(df[metrica], errors="coerce")
        if agg == "sum":
            valor = col_numeric.sum()
            agregacion_usada = agg
        elif agg == "mean":
            valor = col_numeric.mean()
            agregacion_usada = agg
        elif agg == "max":
            valor = col_numeric.max()
            agregacion_usada = agg
        elif agg == "min":
            valor = col_numeric.min()
            agregacion_usada = agg
        else:
            valor = col_numeric.mean()
            advertencias.append(f"Agregación '{agg}' no reconocida; se usó promedio.")
            agregacion_usada = "mean"

    # ------------------------------------------------------------------
    # Step 7: Get metadata from dim_indicadores (dim/dim_row already loaded)
    # ------------------------------------------------------------------
    etiqueta_humana = (
        dim_row["etiqueta_humana"].iloc[0] if not dim_row.empty else metrica
    )
    unidad = dim_row["unidad"].iloc[0] if not dim_row.empty else ""

    # ------------------------------------------------------------------
    # Step 8: Build filas_detalle (up to 50 rows)
    # ------------------------------------------------------------------
    cols = ["periodo"]
    if "linea" in df.columns:
        cols.append("linea")
    cols.append(metrica)
    filas_detalle = df[cols].head(50).to_dict("records")

    # ------------------------------------------------------------------
    # Step 9: Return
    # ------------------------------------------------------------------
    return Dato(
        metrica=metrica,
        etiqueta_humana=etiqueta_humana,
        unidad=unidad,
        valor=valor,
        agregacion=agregacion_usada,
        filas_detalle=filas_detalle,
    ), advertencias
