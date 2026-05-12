"""
Integration tests for the full motor pipeline using a gold set.

Uses forzar_reglas=True and sin_llm_nl=True for deterministic, offline testing.
Some gold set entries are marked xfail where the rules-only parser cannot
correctly detect the expected tipo (e.g. OOD detection requires LLM, or
period comparison requires LLM-extracted rangos_temporales).
"""

import json
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from motor import responder
from motor.almacen import Almacen

_GOLD_PATH = Path(__file__).parent / "gold_set_motor.json"
GOLD = json.loads(_GOLD_PATH.read_text(encoding="utf-8"))

# Cases that are known to fail with rules-only parser:
# - "Datos de la red en 1985": parser returns OOD (no recognized metric) instead of sin_datos
# - "Comparar puntualidad ...": rules parser may not detect puntualidad as regularidad_absoluta
# - "Qué pasó con los pasajeros en 2022 vs 2021": comparacion_periodos with empty rangos_temporales
_XFAIL_PREGUNTAS = {
    "Datos de la red en 1985",  # rules-only: ood, not sin_datos
    "Qué pasó con los pasajeros en 2022 vs 2021",  # rules-only: no rangos extracted → error
}


def _make_test_id(caso):
    return caso["pregunta"][:40]


@pytest.fixture(autouse=True)
def reset_almacen():
    Almacen.reset()
    yield
    Almacen.reset()


@pytest.mark.parametrize("caso", GOLD, ids=[_make_test_id(c) for c in GOLD])
def test_gold_set_motor(caso):
    pregunta = caso["pregunta"]
    tipo_esperado = caso["tipo_esperado"]
    metrica_esperada = caso.get("metrica_esperada")

    # Mark known failures as xfail
    if pregunta in _XFAIL_PREGUNTAS:
        pytest.xfail(
            reason=(
                f"Rules-only parser cannot resolve this case as expected. "
                f"Requires LLM for '{pregunta[:50]}'."
            )
        )

    resp = responder(pregunta, sin_llm_nl=True, forzar_reglas=True)

    assert resp.tipo == tipo_esperado, (
        f"Pregunta: {pregunta!r}\n"
        f"Esperado: {tipo_esperado!r}, Obtenido: {resp.tipo!r}\n"
        f"texto_nl: {resp.texto_nl!r}\n"
        f"advertencias: {resp.advertencias}"
    )

    if metrica_esperada is not None:
        assert resp.dato is not None, (
            f"Se esperaba dato con metrica={metrica_esperada!r}, pero dato=None"
        )
        assert resp.dato.metrica == metrica_esperada, (
            f"Metrica esperada: {metrica_esperada!r}, obtenida: {resp.dato.metrica!r}"
        )
