"""
Unit tests for semantica.normalizacion — normalizar() and tokenizar().

All tests are deterministic (no LLM calls).
"""

import pytest

from semantica.normalizacion import normalizar, tokenizar


# ---------------------------------------------------------------------------
# normalizar() parametrize cases
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("texto,expected", [
    # Tildes removed: accented vowels
    ("á é í ó ú", "a e i o u"),
    # n-tilde converted: "año" → "ano"
    ("año", "ano"),
    # Uppercase to lowercase
    ("MITRE", "mitre"),
    # Punctuation removed: "¿Cuántos?" → "cuantos"
    ("¿Cuántos?", "cuantos"),
    # Multiple spaces collapsed
    ("  hola   mundo  ", "hola mundo"),
    # Strip leading/trailing whitespace
    ("  hola  ", "hola"),
    # Combined: full typical railway question
    (
        "¿Cuántos pasajeros tuvo la línea Mitre?",
        "cuantos pasajeros tuvo la linea mitre",
    ),
    # Empty string
    ("", ""),
])
def test_normalizar(texto, expected):
    assert normalizar(texto) == expected


# ---------------------------------------------------------------------------
# tokenizar() tests
# ---------------------------------------------------------------------------

def test_tokenizar_basic():
    """¿Cuántos pasajeros? → ['cuantos', 'pasajeros']"""
    result = tokenizar("¿Cuántos pasajeros?")
    assert result == ["cuantos", "pasajeros"]


def test_tokenizar_empty():
    assert tokenizar("") == []


@pytest.mark.parametrize("texto,expected", [
    # Accented punctuation query
    ("¿Cuántos pasajeros?", ["cuantos", "pasajeros"]),
    # Already clean text
    ("hola mundo", ["hola", "mundo"]),
    # Single word
    ("mitre", ["mitre"]),
    # Multiple spaces
    ("  hola   mundo  ", ["hola", "mundo"]),
    # Empty
    ("", []),
])
def test_tokenizar_parametrize(texto, expected):
    assert tokenizar(texto) == expected
