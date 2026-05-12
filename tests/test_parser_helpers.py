"""
Unit tests for internal helper functions in semantica.parser_reglas:
  - _detectar_tipo
  - _es_dominio

These functions previously had zero test coverage.
"""

import pytest

from semantica.normalizacion import normalizar
from semantica.parser_reglas import _detectar_tipo, _es_dominio


# ---------------------------------------------------------------------------
# _detectar_tipo
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("pregunta,lineas,expected_tipo", [
    # Simple query — no comparison keyword, single year
    (
        "cuantos pasajeros tuvo mitre en 2023",
        ["Mitre"],
        "simple",
    ),
    # Comparacion de lineas — "vs" keyword + two lines detected
    (
        "comparar mitre vs sarmiento en 2023",
        ["Mitre", "Sarmiento"],
        "comparacion_lineas",
    ),
    # Comparacion de periodos — "diferencia entre" keyword + two distinct years, no lines
    (
        "diferencia entre 2022 y 2023 en la red",
        [],
        "comparacion_periodos",
    ),
    # Comparison keyword present but only one line and one year → fallback to comparacion_lineas
    (
        "comparar pasajeros de la red",
        [],
        "comparacion_lineas",
    ),
    # "vs" with two years, no lines → comparacion_periodos
    (
        "puntualidad 2021 vs 2022 en el sarmiento",
        ["Sarmiento"],
        "comparacion_periodos",
    ),
    # No comparison keyword at all → simple even with two lines
    (
        "pasajeros de mitre y sarmiento en 2023",
        ["Mitre", "Sarmiento"],
        "simple",
    ),
    # " contra " (space-padded) triggers comparison
    (
        "mitre contra sarmiento en 2023",
        ["Mitre", "Sarmiento"],
        "comparacion_lineas",
    ),
    # "contradictorios" should NOT trigger comparison
    (
        "datos contradictorios en la red",
        [],
        "simple",
    ),
])
def test_detectar_tipo(pregunta, lineas, expected_tipo):
    """_detectar_tipo returns correct query type for parametrized cases."""
    # texto_norm is already normalized in these test cases; pass directly
    result = _detectar_tipo(pregunta, lineas, rango_temporal=None)
    assert result == expected_tipo, (
        f"pregunta={pregunta!r}, lineas={lineas!r}: "
        f"got {result!r}, expected {expected_tipo!r}"
    )


def test_detectar_tipo_with_raw_text_normalization():
    """_detectar_tipo correctly detects comparacion_periodos from normalized raw input."""
    raw = "Diferencia entre 2022 y 2023 en la red ferroviaria"
    texto_norm = normalizar(raw)
    result = _detectar_tipo(texto_norm, lineas=[], rango_temporal=None)
    assert result == "comparacion_periodos"


# ---------------------------------------------------------------------------
# _es_dominio
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("pregunta_norm,metrica,lineas,expected", [
    # Has metric → always True
    ("cuantos pasajeros tuvo mitre", "pax_pagos", [], True),
    # Has line → True even without metric
    ("cuantos pasajeros tuvo mitre", None, ["Mitre"], True),
    # Ferroviario keyword "tren" in text → True
    ("tren de la costa en 2022", None, [], True),
    # Ferroviario keyword "ferrocarril" → True
    ("historia del ferrocarril argentino", None, [], True),
    # Ferroviario keyword "cnrt" → True
    ("datos de cnrt 2023", None, [], True),
    # No metric, no lines, no ferroviario keyword → False
    ("cual es la capital de francia", None, [], False),
    # "precio del dolar hoy" — no railway content → False
    ("precio del dolar hoy", None, [], False),
    # "receta de asado" — clearly out of domain → False
    ("receta de asado", None, [], False),
    # Word "servicio" in railway context (has keyword) → True
    ("regularidad del servicio ferroviario", None, [], True),
    # Word "linea" as standalone word (word boundary) → True
    ("pasajeros por linea en 2022", None, [], True),
    # Tricky: "alineacion" should NOT match "linea" at word boundary
    ("alineacion de equipos deportivos", None, [], False),
    # Plurals must match ferroviario keywords
    ("pasajeros en 2023", None, [], True),   # "pasajeros" → ferroviario
    ("servicios corridos", None, [], True),  # "servicios" → ferroviario
    ("trenes puntuales", None, [], True),    # "trenes" → ferroviario
])
def test_es_dominio(pregunta_norm, metrica, lineas, expected):
    """_es_dominio correctly classifies in-domain vs out-of-domain queries."""
    result = _es_dominio(pregunta_norm, metrica, lineas)
    assert result == expected, (
        f"pregunta_norm={pregunta_norm!r}, metrica={metrica!r}, lineas={lineas!r}: "
        f"got {result!r}, expected {expected!r}"
    )
