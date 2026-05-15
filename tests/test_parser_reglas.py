"""
Unit tests for semantica.parser_reglas — parse().

Tests intent fields extracted by the deterministic rule-based pipeline.
All tests are deterministic (no LLM calls).
"""

import pytest

from semantica.parser_reglas import parse


# ---------------------------------------------------------------------------
# Core parametrize cases: (pregunta, metrica, lineas, tabla, agregacion)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("pregunta,exp_metrica,exp_lineas,exp_tabla,exp_agregacion", [
    (
        "¿Cuántos pasajeros transportó la línea Mitre en 2023?",
        "pax_pagos", ["Mitre"], "linea_mensual", "sum",
    ),
    (
        "Cancelaciones en Belgrano Norte y Urquiza entre 2018 y 2020",
        "trenes_cancelados", ["Belgrano Norte", "Urquiza"], "linea_mensual", "sum",
    ),
    (
        "Recaudación total de la red en 2022",
        "recaudacion_pesos", [], "red_mensual", "sum",
    ),
    (
        "Regularidad promedio del Sarmiento en los últimos 3 años",
        "regularidad_absoluta", ["Sarmiento"], "linea_mensual", "mean",
    ),
    (
        "Cuántas cancelaciones tuvo la red en 2022",
        "trenes_cancelados", [], "red_mensual", "sum",
    ),
    (
        "Cuántos trenes corridos tuvo el Roca",
        "trenes_corridos", ["Roca"], "linea_mensual", "sum",
    ),
    # Pasajeros Sarmiento
    (
        "Cuántos pasajeros tuvo el Sarmiento en 2021",
        "pax_pagos", ["Sarmiento"], "linea_mensual", "sum",
    ),
    # Belgrano Norte recaudacion
    (
        "Recaudación de Belgrano Norte en 2020",
        "recaudacion_pesos", ["Belgrano Norte"], "linea_mensual", "sum",
    ),
    # Red trenes corridos
    (
        "Cuántos trenes corridos tuvo la red en 2019",
        "trenes_corridos", [], "red_mensual", "sum",
    ),
    # Trenes programados Roca
    (
        "Trenes programados del Roca en marzo 2022",
        "trenes_programados", ["Roca"], "linea_mensual", "sum",
    ),
])
def test_parse_intent_fields(pregunta, exp_metrica, exp_lineas, exp_tabla, exp_agregacion):
    result = parse(pregunta)
    intent = result.intent
    assert intent.metrica == exp_metrica, f"metrica: got {intent.metrica!r}, expected {exp_metrica!r}"
    assert intent.filtros_linea == exp_lineas, f"lineas: got {intent.filtros_linea!r}, expected {exp_lineas!r}"
    assert intent.tabla == exp_tabla, f"tabla: got {intent.tabla!r}, expected {exp_tabla!r}"
    assert intent.agregacion == exp_agregacion, f"agregacion: got {intent.agregacion!r}, expected {exp_agregacion!r}"


# ---------------------------------------------------------------------------
# requiere_llm flag
# ---------------------------------------------------------------------------

def test_low_confidence_query_requires_llm():
    """A vague query with no clear metric should fall to LLM."""
    result = parse("Qué tan puntual fue la red")
    assert result.requiere_llm is True


def test_high_confidence_query_does_not_require_llm():
    """A precise query should be resolved by rules alone."""
    result = parse("¿Cuántos pasajeros transportó la línea Mitre en 2023?")
    assert result.requiere_llm is False


def test_no_metric_requires_llm():
    """When metric is None, requiere_llm must be True."""
    result = parse("Qué ocurrió en la red")
    assert result.requiere_llm is True


# ---------------------------------------------------------------------------
# Additional structural checks
# ---------------------------------------------------------------------------

def test_result_has_intent_and_flag():
    """ParseResult must have .intent and .requiere_llm attributes."""
    result = parse("Cuántos pasajeros tuvo Mitre en 2022")
    assert hasattr(result, "intent")
    assert hasattr(result, "requiere_llm")


def test_origen_is_reglas():
    """Rule-based parse always returns origen='reglas'."""
    result = parse("¿Cuántos pasajeros transportó la línea Mitre en 2023?")
    assert result.intent.origen == "reglas"


# ---------------------------------------------------------------------------
# Etapa 5: grupo_por (agrupamiento por año)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("pregunta,exp_grupo", [
    ("Pasajeros por año en el Urquiza entre 2000 y 2005", "año"),
    ("Cuántos trenes corrieron anualmente en el Mitre desde 2018", "año"),
    ("Cancelaciones anuales del Sarmiento desde 2020", "año"),
    ("Pasajeros por cada año del Roca entre 2018 y 2022", "año"),
    # Variantes con "año a año" — caso reportado como bug
    ("Como fue la cantidad de trenes cancelados en urquiza entre 2015 y 2025 año a año", "año"),
    ("Trenes cancelados en urquiza año a año entre 2015 y 2025", "año"),
    ("Pasajeros año por año en el Mitre desde 2018", "año"),
    ("Cancelaciones año tras año del Sarmiento desde 2020", "año"),
    # Control negativo — sin keyword de agrupamiento
    ("Pasajeros del Mitre en 2023", None),
    ("Recaudación total de la red en 2022", None),
])
def test_parse_detecta_grupo_por(pregunta, exp_grupo):
    result = parse(pregunta)
    assert result.intent.grupo_por == exp_grupo


def test_grupo_por_sin_rango_genera_advertencia():
    """grupo_por='año' sin rango_temporal debe agregar una advertencia."""
    result = parse("Pasajeros por año en el Urquiza")
    assert result.intent.grupo_por == "año"
    assert result.intent.rango_temporal is None
    assert any("rango temporal" in a.lower() for a in result.intent.advertencias)
