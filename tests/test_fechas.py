"""
Unit tests for semantica.fechas — extraer_fecha().

Input is already-normalized text (no accents, lowercase).
All tests are deterministic (no LLM calls).
"""

from datetime import datetime

import pytest

from semantica.fechas import extraer_fecha


# ---------------------------------------------------------------------------
# Fixed date expressions (absolute)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("texto,expected_desde,expected_hasta", [
    # Month + year
    ("marzo 2024", "2024-03", "2024-03"),
    ("en enero de 2023", "2023-01", "2023-01"),
    ("diciembre 2019", "2019-12", "2019-12"),
    # Year ranges
    ("entre 2010 y 2020", "2010-01", "2020-12"),
    ("de 2015 a 2020", "2015-01", "2020-12"),
    ("2015-2020", "2015-01", "2020-12"),
    ("desde 2015 hasta 2020", "2015-01", "2020-12"),
    # Single year
    ("en 2023", "2023-01", "2023-12"),
    ("durante 2023", "2023-01", "2023-12"),
])
def test_fechas_absolutas(texto, expected_desde, expected_hasta):
    result = extraer_fecha(texto)
    assert result is not None, f"Se esperaba un RangoTemporal para {texto!r}"
    assert result.desde == expected_desde
    assert result.hasta == expected_hasta


# ---------------------------------------------------------------------------
# Relative date expressions
# ---------------------------------------------------------------------------

def test_este_ano():
    result = extraer_fecha("este ano")
    assert result is not None
    current_year = datetime.now().year
    desde_year = int(result.desde.split("-")[0])
    assert desde_year == current_year


def test_ano_pasado():
    result = extraer_fecha("ano pasado")
    assert result is not None
    current_year = datetime.now().year
    desde_year = int(result.desde.split("-")[0])
    assert desde_year == current_year - 1


def test_ultimos_3_anos():
    result = extraer_fecha("ultimos 3 anos")
    assert result is not None
    desde_year = int(result.desde.split("-")[0])
    hasta_year = int(result.hasta.split("-")[0])
    # Should span exactly 3 years
    assert hasta_year - desde_year == 3


def test_ultimos_6_meses():
    result = extraer_fecha("ultimos 6 meses")
    assert result is not None
    # Should have a desde and hasta in YYYY-MM format
    assert len(result.desde) == 7
    assert len(result.hasta) == 7
    assert result.desde <= result.hasta


# ---------------------------------------------------------------------------
# No-date expressions — must return None
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("texto", [
    "cuantos pasajeros en la linea mitre",
    "belgrano norte",
    "pasajeros mitre",
])
def test_no_fecha(texto):
    result = extraer_fecha(texto)
    assert result is None, f"Se esperaba None para {texto!r}, se obtuvo {result!r}"
