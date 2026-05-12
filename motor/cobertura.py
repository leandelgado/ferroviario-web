"""
Pure validation functions for query coverage checks.

These functions have no side effects: they receive an intent and an almacen
instance and return a ResultadoCobertura dataclass describing whether the
query is satisfiable with available data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class ResultadoCobertura:
    """Outcome of a coverage validation check."""

    valido: bool
    mensaje: str = ""  # Human-readable explanation when not valid


# ---------------------------------------------------------------------------
# Tren de la Costa helpers
# ---------------------------------------------------------------------------

_COSTA_VARIANTES = {
    "tren de la costa",
    "la costa",
    "costa",
    "tren costa",
}


def _es_tren_de_la_costa(lineas: list[str]) -> bool:
    """Return True if any of *lineas* refers to Tren de la Costa."""
    for linea in lineas:
        if linea.lower() in _COSTA_VARIANTES or "costa" in linea.lower():
            return True
    return False


# ---------------------------------------------------------------------------
# Validation functions
# ---------------------------------------------------------------------------

def validar_temporal(intent, almacen) -> ResultadoCobertura:
    """Check that intent's temporal range is covered by the available data.

    Parameters
    ----------
    intent:
        A ``semantica.Intent`` instance (typed as Any to avoid circular import).
    almacen:
        An ``Almacen`` class or compatible object with a ``cobertura`` method.

    Returns
    -------
    ResultadoCobertura
        ``valido=True`` when data is available; ``valido=False`` with a
        human-readable ``mensaje`` otherwise.
    """
    tabla = intent.tabla
    desde, hasta = almacen.cobertura(tabla)

    # Dimension tables have no temporal coverage → always valid
    if desde == "" and hasta == "":
        return ResultadoCobertura(valido=True)

    # No temporal range requested → always valid
    if intent.rango_temporal is None:
        return ResultadoCobertura(valido=True)

    rango = intent.rango_temporal

    # Check whether the requested range falls outside available data
    fuera_de_rango = (
        rango.desde < desde
        or rango.hasta > hasta
    )

    if fuera_de_rango:
        return ResultadoCobertura(
            valido=False,
            mensaje=(
                f"No tengo datos para el período solicitado. "
                f"Cobertura disponible: {desde} a {hasta} para {tabla}."
            ),
        )

    # Special case: Tren de la Costa has data only from 2015-05
    lineas = getattr(intent, "filtros_linea", []) or []
    if _es_tren_de_la_costa(lineas) and rango.desde < "2015-05":
        return ResultadoCobertura(
            valido=False,
            mensaje="La Tren de la Costa tiene datos disponibles desde mayo 2015.",
        )

    return ResultadoCobertura(valido=True)


def validar_lineas(intent, almacen) -> ResultadoCobertura:
    """Validate that requested lines exist in the dataset.

    For now always returns valid — the parser already canonicalises line names.
    """
    return ResultadoCobertura(valido=True)


def validar_metrica_granularidad(intent, almacen) -> ResultadoCobertura:
    """Warn when a service-level metric is requested at network level.

    Returns ``valido=True`` in all cases; sets ``mensaje`` to a warning
    string when the combination may produce misleadingly aggregated data.
    """
    dim = almacen.obtener("dim_indicadores")

    metrica = intent.metrica
    tabla = intent.tabla

    # Look up the metric in dim_indicadores (column is 'campo')
    if "campo" in dim.columns:
        fila = dim[dim["campo"] == metrica]
    else:
        fila = dim[dim.index == metrica] if metrica in dim.index else dim.iloc[0:0]

    if not fila.empty:
        granularidad_minima = fila.iloc[0].get("granularidad_minima", "")
        if granularidad_minima == "servicio" and tabla == "red_mensual":
            return ResultadoCobertura(
                valido=True,
                mensaje=(
                    f"Advertencia: '{metrica}' tiene granularidad mínima por servicio; "
                    f"los datos a nivel red pueden ser agregados."
                ),
            )

    return ResultadoCobertura(valido=True)
