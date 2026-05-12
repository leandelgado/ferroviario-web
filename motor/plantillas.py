"""
Deterministic f-string templates for all 5 response types.

Used as fallback when Gemini is unavailable. All output is plain Spanish text
(rioplatense informal). No markdown, no bullets, no emojis.
"""

from __future__ import annotations

import math


# ---------------------------------------------------------------------------
# Private render functions
# ---------------------------------------------------------------------------

def _render_dato(
    metrica: str,
    etiqueta_humana: str,
    valor: float,
    unidad: str,
    agregacion: str,
    periodo_desde: str,
    periodo_hasta: str,
    filtros: str = "red",
    **kwargs,
) -> str:
    """Render a single-value result sentence."""
    # Format the value: use M suffix for millions, K for thousands
    valor_fmt = _formatear_valor(valor, unidad)

    # Build subject
    if filtros and filtros != "red":
        sujeto = f"La línea {filtros}"
    else:
        sujeto = "La red"

    # Build period phrase
    if periodo_desde and periodo_hasta:
        if periodo_desde == periodo_hasta:
            periodo_str = f"en {periodo_desde}"
        else:
            periodo_str = f"en el período {periodo_desde} a {periodo_hasta}"
    else:
        periodo_str = ""

    # Build aggregation label
    agg_label = _formatear_agregacion(agregacion)

    partes = [f"{sujeto} registró {valor_fmt} {etiqueta_humana}"]
    if agg_label:
        partes[0] += f" ({agg_label})"
    if periodo_str:
        partes[0] += f" {periodo_str}"

    return partes[0] + "."


def _render_comparacion(
    eje: str,
    items: list,
    diferencias: list,
    ranking: list,
    **kwargs,
) -> str:
    """Render a comparison result sentence."""
    # Build eje label
    eje_label = "línea" if eje == "linea" else "período"

    # Build items string
    items_str = " | ".join(
        f"{item['etiqueta']}: {_formatear_valor(item['valor'], item.get('unidad', ''))}"
        for item in items
    )

    texto = f"Comparación por {eje_label}: {items_str}."

    # Add ranking comment if available
    if ranking:
        mejor = ranking[0]
        articulo = "La" if eje == "linea" else "El"
        texto += f" {articulo} {eje_label} {mejor} tuvo mejor desempeño."

    return texto


def _render_ood(sugerencias: list[str], **kwargs) -> str:
    """Render an out-of-domain response."""
    sugerencias_str = " | ".join(sugerencias)
    return (
        "Lo que preguntás está fuera de mi área. "
        f"Puedo ayudarte con preguntas como: {sugerencias_str}"
    )


def _render_sin_datos(mensaje: str, sugerencias: list[str], **kwargs) -> str:
    """Render a no-data response."""
    base = f"No encontré datos para tu consulta."
    if mensaje:
        base += f" {mensaje}" if mensaje.endswith(".") else f" {mensaje}."
    if sugerencias:
        sugerencias_str = " | ".join(sugerencias)
        base += f" Podés intentar con: {sugerencias_str}"
    return base


def _render_error(mensaje: str = "", **kwargs) -> str:
    """Render a generic error response."""
    base = "Ocurrió un error al procesar tu consulta. Intentá reformularla."
    if mensaje:
        base += f" Detalle: {mensaje}"
    return base


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _formatear_valor(valor: float, unidad: str = "") -> str:
    """Format a numeric value with optional unit suffix."""
    if math.isnan(valor):
        return f"sin dato ({unidad})" if unidad else "sin dato"
    if abs(valor) >= 1_000_000:
        return f"{valor / 1_000_000:.1f}M"
    if abs(valor) >= 1_000:
        return f"{valor / 1_000:.1f}K"
    # For ratios / percentages keep 2 decimal places
    if unidad and "%" in unidad:
        return f"{valor:.1f}%"
    return f"{valor:.2f}"


def _formatear_agregacion(agregacion: str) -> str:
    """Return a human-friendly label for the aggregation type."""
    mapping = {
        "sum": "suma",
        "mean": "promedio",
        "max": "máximo",
        "min": "mínimo",
        "ratio_recalculado": "ratio",
        "none": "",
    }
    return mapping.get(agregacion, agregacion)


# ---------------------------------------------------------------------------
# Public dispatcher
# ---------------------------------------------------------------------------

_DISPATCH = {
    "dato": _render_dato,
    "comparacion": _render_comparacion,
    "ood": _render_ood,
    "sin_datos": _render_sin_datos,
    "error": _render_error,
}


def render(tipo: str, **kwargs) -> str:
    """Return a plain-text response for the given tipo using only kwargs.

    Parameters
    ----------
    tipo:
        One of "dato", "comparacion", "ood", "sin_datos", "error".
    **kwargs:
        Arguments forwarded to the matching private render function.

    Returns
    -------
    str
        Plain Spanish text (rioplatense informal). No markdown, no bullets,
        no emojis.

    Raises
    ------
    ValueError
        If *tipo* is not recognised.
    """
    if tipo not in _DISPATCH:
        raise ValueError(
            f"Tipo desconocido: {tipo!r}. "
            f"Tipos válidos: {list(_DISPATCH)}"
        )
    return _DISPATCH[tipo](**kwargs)
