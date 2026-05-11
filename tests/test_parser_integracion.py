"""
End-to-end integration tests for semantica.parse() — the hybrid orchestrator.

LLM paths use StubBackend so tests do not require GEMINI_API_KEY.
All tests are deterministic (no real LLM calls).
"""

import pytest

from semantica import parse, Intent
from semantica.parser_llm import StubBackend


# ---------------------------------------------------------------------------
# 1. Basic import
# ---------------------------------------------------------------------------

def test_import_works():
    """from semantica import parse — basic import check."""
    from semantica import parse as _parse  # noqa: F401
    assert callable(_parse)


# ---------------------------------------------------------------------------
# 2. High-confidence query returns origen="reglas"
# ---------------------------------------------------------------------------

def test_high_confidence_returns_reglas():
    intent = parse("¿Cuántos pasajeros transportó la línea Mitre en 2023?")
    assert intent.origen == "reglas"


# ---------------------------------------------------------------------------
# 3. Low-confidence query with StubBackend returns origen="hibrido"
# ---------------------------------------------------------------------------

def test_low_confidence_returns_hibrido():
    intent = parse("Qué tan puntual fue la red", llm_backend=StubBackend())
    assert intent.origen == "hibrido"


# ---------------------------------------------------------------------------
# 4. forzar_llm=True with StubBackend returns origen="llm"
# ---------------------------------------------------------------------------

def test_forzar_llm_returns_llm():
    intent = parse("Mitre pasajeros 2023", forzar_llm=True, llm_backend=StubBackend())
    assert intent.origen == "llm"


# ---------------------------------------------------------------------------
# 5. Returned intent is a valid Intent instance
# ---------------------------------------------------------------------------

def test_returns_valid_intent():
    intent = parse("¿Cuántos pasajeros transportó la línea Mitre en 2023?")
    assert isinstance(intent, Intent)
    # Check all required fields exist
    assert hasattr(intent, "metrica")
    assert hasattr(intent, "agregacion")
    assert hasattr(intent, "filtros_linea")
    assert hasattr(intent, "filtros_servicio")
    assert hasattr(intent, "filtros_traccion")
    assert hasattr(intent, "rango_temporal")
    assert hasattr(intent, "granularidad")
    assert hasattr(intent, "tabla")
    assert hasattr(intent, "confianza")
    assert hasattr(intent, "origen")
    assert hasattr(intent, "advertencias")


# ---------------------------------------------------------------------------
# 6. intent.model_dump() works (JSON-serializable)
# ---------------------------------------------------------------------------

def test_intent_model_dump_works():
    intent = parse("¿Cuántos pasajeros transportó la línea Mitre en 2023?")
    dumped = intent.model_dump()
    assert isinstance(dumped, dict)
    assert "metrica" in dumped
    assert "origen" in dumped
    assert "confianza" in dumped


def test_intent_model_dump_with_stub():
    intent = parse("Qué tan puntual fue la red", llm_backend=StubBackend())
    dumped = intent.model_dump()
    assert isinstance(dumped, dict)
    assert "metrica" in dumped


# ---------------------------------------------------------------------------
# 7. Additional integration checks
# ---------------------------------------------------------------------------

def test_high_confidence_intent_has_correct_metrica():
    intent = parse("¿Cuántos pasajeros transportó la línea Mitre en 2023?")
    assert intent.metrica == "pax_pagos"


def test_high_confidence_intent_has_correct_linea():
    intent = parse("¿Cuántos pasajeros transportó la línea Mitre en 2023?")
    assert "Mitre" in intent.filtros_linea


def test_forzar_llm_stub_returns_intent_instance():
    intent = parse("cualquier cosa", forzar_llm=True, llm_backend=StubBackend())
    assert isinstance(intent, Intent)
    assert intent.origen == "llm"
