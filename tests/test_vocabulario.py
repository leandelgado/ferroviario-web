"""
Unit tests for semantica.vocabulario — cargar_vocabulario() and resetear_vocabulario().

These tests hit the real parquet files (no mocking — they are fast reads).
All tests are deterministic (no LLM calls).
"""

import pytest

from semantica.vocabulario import cargar_vocabulario, resetear_vocabulario


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the vocabulary singleton before and after each test."""
    resetear_vocabulario()
    yield
    resetear_vocabulario()


# ---------------------------------------------------------------------------
# Basic structure
# ---------------------------------------------------------------------------

def test_vocabulario_has_8_lineas():
    voc = cargar_vocabulario()
    assert len(voc.lineas_canonicas) == 8


def test_all_canonical_lineas_present():
    voc = cargar_vocabulario()
    expected = {
        "Belgrano Norte",
        "Belgrano Sur",
        "Mitre",
        "Roca",
        "San Martín",
        "Sarmiento",
        "Tren de la Costa",
        "Urquiza",
    }
    assert set(voc.lineas_canonicas) == expected


def test_metricas_count():
    """There are 20 indicator campos indexed (each with multiple synonyms)."""
    voc = cargar_vocabulario()
    # The vocabulary has many synonym keys, but all should map to known campos
    campos = {row["campo"] for row in voc.metricas_por_sinonimo.values()}
    assert len(campos) == 20


# ---------------------------------------------------------------------------
# Key campos present in metricas_por_sinonimo synonym index
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("sinonimo,expected_campo", [
    ("pasajeros", "pax_pagos"),
    ("trenes cancelados", "trenes_cancelados"),
    ("cancelaciones", "trenes_cancelados"),
    ("regularidad", "regularidad_absoluta"),
    ("puntualidad", "regularidad_absoluta"),
    ("recaudacion pesos", "recaudacion_pesos"),
    ("trenes corridos", "trenes_corridos"),
    ("trenes programados", "trenes_programados"),
    ("trenes puntuales", "trenes_puntuales"),
    ("cumplimiento", "cumplimiento_programa"),
])
def test_metricas_sinonimos(sinonimo, expected_campo):
    voc = cargar_vocabulario()
    assert sinonimo in voc.metricas_por_sinonimo, f"Sinónimo {sinonimo!r} no encontrado"
    assert voc.metricas_por_sinonimo[sinonimo]["campo"] == expected_campo


def test_sinonimo_pasajeros_maps_to_pax_pagos():
    voc = cargar_vocabulario()
    assert voc.metricas_por_sinonimo["pasajeros"]["campo"] == "pax_pagos"


def test_sinonimo_puntualidad_maps_to_regularidad_absoluta():
    voc = cargar_vocabulario()
    assert voc.metricas_por_sinonimo["puntualidad"]["campo"] == "regularidad_absoluta"


# ---------------------------------------------------------------------------
# Alias lookups
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("alias,expected_canonical", [
    ("mitre", "Mitre"),
    ("sarmiento", "Sarmiento"),
    ("bn", "Belgrano Norte"),
    ("belgrano norte", "Belgrano Norte"),
    ("roca", "Roca"),
    ("urquiza", "Urquiza"),
])
def test_aliases_linea(alias, expected_canonical):
    voc = cargar_vocabulario()
    assert alias in voc.aliases_linea, f"Alias {alias!r} no encontrado"
    assert voc.aliases_linea[alias] == expected_canonical


# ---------------------------------------------------------------------------
# Servicios and tracciones
# ---------------------------------------------------------------------------

def test_servicios_count():
    """There are 41 unique services in the dataset."""
    voc = cargar_vocabulario()
    assert len(voc.servicios) > 10


def test_servicios_exact_count():
    voc = cargar_vocabulario()
    assert len(voc.servicios) == 41


def test_tracciones_at_least_2():
    voc = cargar_vocabulario()
    assert len(voc.tracciones) >= 2


# ---------------------------------------------------------------------------
# Singleton behaviour
# ---------------------------------------------------------------------------

def test_singleton_same_object():
    """cargar_vocabulario() always returns the same object."""
    voc1 = cargar_vocabulario()
    voc2 = cargar_vocabulario()
    assert voc1 is voc2


def test_reset_forces_rebuild():
    """After resetear_vocabulario(), next call builds a new object."""
    voc1 = cargar_vocabulario()
    resetear_vocabulario()
    voc2 = cargar_vocabulario()
    assert voc1 is not voc2
